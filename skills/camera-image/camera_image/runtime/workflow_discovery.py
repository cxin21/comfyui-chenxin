"""Read-only discovery and hard-gated validation of production workflows.

The compiler owns neither UI-to-API conversion nor workflow selection.  This
module records observations made by a negotiated local adapter and binds them
to the repository's immutable workflow profiles.  A missing or partial tool
negotiation is represented as an unavailable candidate, never as an empty
success result.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from .contracts import content_hash
from .workflow_assets import WorkflowAssetError, load_fixed_api_workflow
from .workflow_profile import ProfileError, resolve_slots, structure_fingerprint


REQUIRED_WORKFLOW_TOOLS = frozenset(
    {"get_workflow", "strip_workflow", "validate_workflow", "check_workflow_runtime"}
)
_PROFILE_ROOT = Path(__file__).with_name("profiles")

# The Flux workflow with virtual buses is kept as a diagnostic candidate.
# The flat-v2 workflow is the production path, not a silent fallback,
# because the bus-based graph currently has unresolved virtual buses in the
# local ComfyUI instance.
DEFAULT_WORKFLOW_SPECS = (
    {
        "role": "character-base",
        "profile_file": "camera-anima.json",
        "production": True,
    },
    {
        "role": "character-multiview-requested",
        "profile_file": "flux2-klein-multiview.json",
        "production": False,
        "replacement_workflow_name": "Flux2-Klein-multiview-flat-v2.json",
    },
    {
        "role": "character-multiview",
        "profile_file": "flux2-klein-multiview-flat-v2.json",
        "production": True,
        "replaces_workflow_name": "Flux2-Klein浜虹墿涓€閿瑙嗗浘宸ヤ綔娴?json",
    },
    {
        "role": "video",
        "profile_file": "ltx-yusu-director.json",
        "production": True,
    },
)


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("workflow discovery clock must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _profile_from_spec(spec: dict) -> dict:
    profile = spec.get("profile")
    if isinstance(profile, dict):
        return copy.deepcopy(profile)
    profile_file = spec.get("profile_file")
    if not isinstance(profile_file, str) or not profile_file:
        raise ValueError("workflow discovery spec requires profile or profile_file")
    path = (_PROFILE_ROOT / profile_file).resolve()
    if not path.is_file() or not path.is_relative_to(_PROFILE_ROOT.resolve()):
        raise ValueError("workflow discovery profile path is invalid")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("workflow discovery profile is unreadable") from exc
    if not isinstance(loaded, dict):
        raise ValueError("workflow discovery profile must be an object")
    return loaded


def _bounded_issues(value: object) -> list:
    if not isinstance(value, list):
        return []
    # Validation output is evidence, not an unbounded log sink.
    return copy.deepcopy(value[:32])


def _tool_call(tools: dict, name: str, arguments: dict):
    try:
        return tools[name](copy.deepcopy(arguments))
    except Exception as exc:  # adapter failures become candidate evidence
        raise RuntimeError(f"{name}: {exc.__class__.__name__}") from exc


def _base_candidate(spec: dict, profile: dict, observed_at: str) -> dict:
    workflow_name = spec.get("workflow_name", profile.get("workflow_name"))
    if not isinstance(workflow_name, str) or not workflow_name:
        raise ValueError("workflow discovery workflow_name is required")
    candidate = {
        "schema_version": "1.0",
        "role": spec.get("role", "unknown"),
        "workflow_name": workflow_name,
        "profile_id": profile.get("profile_id"),
        "production": spec.get("production") is True,
        "profile_fingerprint": profile.get("workflow_fingerprint"),
        "observed_at": observed_at,
        "status": "unavailable",
        "ready": False,
        "reason_codes": [],
        "reasons": [],
    }
    for field in ("replacement_workflow_name", "replaces_workflow_name"):
        if field in spec:
            candidate[field] = spec[field]
    return candidate


def _mark(candidate: dict, code: str, reason: str) -> None:
    candidate["reason_codes"].append(code)
    candidate["reasons"].append(reason)


def _looks_grouped_workflow(profile: dict, workflow_name: str, graph: dict) -> bool:
    """Detect the Flux graph whose virtual buses are not production-safe.

    Grouped graphs are intentionally rejected by evidence, not by filename
    alone.  A profile may explicitly mark itself as grouped, while an API
    graph can expose the same condition through virtual-bus class names or
    unresolved group references.
    """
    profile_id = profile.get("profile_id")
    if profile_id in {"flux2-klein-multiview-v1", "flux2-klein-multiview-grouped-v1"}:
        return True
    lowered_name = workflow_name.casefold()
    if "flux2-klein" in lowered_name and "flat-v2" not in lowered_name:
        return True
    if not isinstance(graph, dict):
        return False
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", "")).casefold()
        if "virtualbus" in class_type or "virtual_bus" in class_type:
            return True
        inputs = node.get("inputs")
        if isinstance(inputs, dict) and any(
            "bus" in str(key).casefold() or "group" in str(key).casefold()
            for key in inputs
        ) and "flux" in lowered_name:
            return True
    return False


def _has_invalid_orientation_evidence(profile: dict) -> bool:
    outputs = profile.get("output_nodes") if isinstance(profile, dict) else None
    if not isinstance(outputs, dict):
        return False
    for descriptor in outputs.values():
        if not isinstance(descriptor, dict):
            continue
        label = str(descriptor.get("view_label", "")).casefold()
        if label == "side_unknown":
            evidence = descriptor.get("orientation_evidence")
            # An unresolved output label is allowed in the profile; reject it
            # only when a caller explicitly supplies contradictory evidence.
            if isinstance(evidence, dict) and evidence.get("verified") is not True:
                return True
    return False


def reread_workflow_evidence(
    workflow_tools: dict,
    workflow_name: str,
    *,
    profile: dict | None = None,
    normalize=None,
) -> dict:
    """Read a workflow UI/API pair again immediately before production.

    This helper accepts only negotiated callables.  It never trusts a caller's
    conversion receipt and returns hashes of the observed graphs.  An optional
    ``normalize`` callable can repair a pinned camera conversion bridge before
    the source graph is hashed.
    """
    if not isinstance(workflow_tools, dict) or not all(
        callable(workflow_tools.get(name)) for name in REQUIRED_WORKFLOW_TOOLS
    ):
        raise ValueError("required local workflow discovery callables are unavailable")
    if not isinstance(workflow_name, str) or not workflow_name:
        raise ValueError("workflow name is required")
    ui_graph = _tool_call(workflow_tools, "get_workflow", {"filename": workflow_name, "format": "ui"})
    converted = _tool_call(workflow_tools, "get_workflow", {"filename": workflow_name, "format": "api"})
    stripped = _tool_call(workflow_tools, "strip_workflow", {"filename": workflow_name, "format": "api"})
    if not all(isinstance(graph, dict) for graph in (ui_graph, converted, stripped)):
        raise ValueError("workflow adapter returned a non-object graph")
    if converted != stripped:
        raise ValueError("caller-supplied conversion receipt or stale API conversion is untrusted")
    normalized = stripped
    if normalize is not None:
        normalized = normalize(stripped, ui_graph, profile or {})
        if not isinstance(normalized, dict):
            raise ValueError("workflow normalization did not return an API graph")
    return {
        "workflow_name": workflow_name,
        "ui_workflow": copy.deepcopy(ui_graph),
        "api_graph": copy.deepcopy(normalized),
        "ui_fingerprint": structure_fingerprint(ui_graph),
        "api_graph_hash": content_hash(normalized),
        "raw_api_graph_hash": content_hash(stripped),
    }


def discover_workflow_candidates(
    *,
    saved_workflows: list[str],
    workflow_tools: dict | None,
    now: datetime,
    workflow_specs: list[dict] | tuple[dict, ...] | None = None,
    available_node_types: object = None,
) -> list[dict]:
    """Observe and validate each configured workflow without mutating ComfyUI.

    The adapter callables are deliberately injected.  This keeps the module
    independent of a particular MCP SDK while making the external boundary
    explicit and testable.  Each candidate is returned even when unavailable
    or rejected, so an operator can distinguish "not discovered" from "known
    bad" and from a production-ready profile.
    """
    if not isinstance(saved_workflows, list) or not all(
        isinstance(name, str) for name in saved_workflows
    ):
        raise ValueError("saved_workflows must be a string list")
    observed_at = _utc_timestamp(now)
    specs = DEFAULT_WORKFLOW_SPECS if workflow_specs is None else workflow_specs
    if not isinstance(specs, (list, tuple)):
        raise ValueError("workflow_specs must be a list")
    tools_ready = isinstance(workflow_tools, dict) and all(
        callable(workflow_tools.get(name)) for name in REQUIRED_WORKFLOW_TOOLS
    )
    candidates: list[dict] = []
    for raw_spec in specs:
        if not isinstance(raw_spec, dict):
            raise ValueError("workflow discovery spec must be an object")
        profile = _profile_from_spec(raw_spec)
        candidate = _base_candidate(raw_spec, profile, observed_at)
        workflow_name = candidate["workflow_name"]

        fixed_asset = profile.get("fixed_workflow_asset")
        if isinstance(fixed_asset, str) and fixed_asset:
            try:
                fixed_graph = load_fixed_api_workflow(fixed_asset)
            except WorkflowAssetError as exc:
                _mark(candidate, "fixed_asset_invalid", str(exc))
                candidates.append(candidate)
                continue
            candidate["fixed_workflow_asset"] = fixed_asset
            candidate["workflow_fingerprint"] = profile.get("workflow_fingerprint")
            candidate["api_graph_hash"] = content_hash(fixed_graph)
            if isinstance(available_node_types, dict):
                missing = sorted(
                    {
                        node.get("class_type")
                        for node in fixed_graph.values()
                        if isinstance(node, dict)
                        and isinstance(node.get("class_type"), str)
                        and node.get("class_type") not in available_node_types
                    }
                )
                if missing:
                    _mark(candidate, "missing_fixed_asset_nodes", ", ".join(missing))
            fixed_tools = workflow_tools if isinstance(workflow_tools, dict) else {}
            validate_tool = fixed_tools.get("validate_workflow")
            runtime_tool = fixed_tools.get("check_workflow_runtime")
            if not callable(validate_tool) or not callable(runtime_tool):
                _mark(candidate, "fixed_capability_unchecked", "fixed workflow lacks live validate/runtime evidence")
            if callable(validate_tool):
                validation = _tool_call(fixed_tools, "validate_workflow", {"workflow": fixed_graph})
                if isinstance(validation, dict):
                    candidate["validation"] = {
                        "valid": validation.get("valid") is True,
                        "errors": _bounded_issues(validation.get("errors")),
                        "warnings": _bounded_issues(validation.get("warnings")),
                        "digest": content_hash(validation),
                    }
                    if candidate["validation"]["valid"] is not True:
                        _mark(candidate, "workflow_invalid", "bundled fixed workflow validation returned errors")
            if callable(runtime_tool):
                runtime = _tool_call(fixed_tools, "check_workflow_runtime", {"graph": fixed_graph})
                if isinstance(runtime, dict):
                    candidate["runtime"] = {
                        "runtime": runtime.get("runtime"),
                        "uses_api_nodes": _bounded_issues(runtime.get("usesApiNodes", runtime.get("apiNodes"))),
                        "unknown_nodes": _bounded_issues(runtime.get("unknownNodes")),
                        "digest": content_hash(runtime),
                    }
                    if candidate["runtime"].get("runtime") != "local":
                        _mark(candidate, "runtime_not_local", "bundled fixed workflow is not confirmed local/free")
            if not candidate["reason_codes"]:
                candidate["status"] = "ready"
                candidate["ready"] = candidate["production"] is True
            elif candidate["reason_codes"] == ["fixed_capability_unchecked"]:
                candidate["status"] = "unavailable"
            else:
                candidate["status"] = "rejected"
            candidates.append(candidate)
            continue

        if workflow_name not in saved_workflows:
            _mark(candidate, "workflow_not_saved", "workflow is not present in ComfyUI's saved library")
            candidates.append(candidate)
            continue
        if not tools_ready:
            _mark(
                candidate,
                "mcp_tools_unavailable",
                "required local workflow discovery callables were not negotiated",
            )
            candidates.append(candidate)
            continue

        try:
            ui_graph = _tool_call(
                workflow_tools, "get_workflow", {"filename": workflow_name, "format": "ui"}
            )
            converted_graph = _tool_call(
                workflow_tools, "get_workflow", {"filename": workflow_name, "format": "api"}
            )
            stripped_graph = _tool_call(
                workflow_tools, "strip_workflow", {"filename": workflow_name, "format": "api"}
            )
            if not isinstance(ui_graph, dict) or not isinstance(converted_graph, dict) or not isinstance(stripped_graph, dict):
                raise ValueError("workflow adapter returned a non-object graph")
            candidate["workflow_fingerprint"] = structure_fingerprint(ui_graph)
            candidate["api_graph_hash"] = content_hash(stripped_graph)
            candidate["converted_api_graph_hash"] = content_hash(converted_graph)
            if _looks_grouped_workflow(profile, workflow_name, stripped_graph):
                _mark(
                    candidate,
                    "unresolved_grouped_flux_buses",
                    "grouped Flux virtual buses are not production-resolvable; use flat-v2",
                )
            if _has_invalid_orientation_evidence(profile):
                _mark(
                    candidate,
                    "invalid_orientation_evidence",
                    "side or rear outputs require explicit directional orientation evidence",
                )
            if converted_graph != stripped_graph:
                _mark(candidate, "conversion_mismatch", "get_workflow(api) differs from strip_workflow(api)")
                _mark(
                    candidate,
                    "conversion_receipt_untrusted",
                    "the caller cannot supply or override a conversion receipt",
                )

            validation = _tool_call(
                workflow_tools, "validate_workflow", {"workflow": stripped_graph}
            )
            runtime = _tool_call(
                workflow_tools, "check_workflow_runtime", {"graph": stripped_graph}
            )
            if not isinstance(validation, dict) or not isinstance(runtime, dict):
                raise ValueError("workflow adapter validation/runtime result is not an object")
            candidate["validation"] = {
                "valid": validation.get("valid") is True,
                "errors": _bounded_issues(validation.get("errors")),
                "warnings": _bounded_issues(validation.get("warnings")),
                "digest": content_hash(validation),
            }
            candidate["runtime"] = {
                "runtime": runtime.get("runtime"),
                "uses_api_nodes": _bounded_issues(runtime.get("usesApiNodes", runtime.get("apiNodes"))),
                "unknown_nodes": _bounded_issues(runtime.get("unknownNodes")),
                "digest": content_hash(runtime),
            }
            try:
                if profile.get("slots"):
                    candidate["resolved_slots"] = resolve_slots(ui_graph, profile)
            except (ProfileError, TypeError, ValueError) as exc:
                _mark(candidate, "profile_slots_mismatch", str(exc))
            if candidate["workflow_fingerprint"] != profile.get("workflow_fingerprint"):
                _mark(candidate, "fingerprint_drift", "live UI workflow fingerprint differs from pinned profile")
            if candidate["validation"]["valid"] is not True:
                if profile.get("api_normalization"):
                    _mark(
                        candidate,
                        "raw_graph_requires_normalization",
                        "raw conversion is invalid; the pinned normalization bridge must run before execution",
                    )
                else:
                    _mark(candidate, "workflow_invalid", "workflow validation returned errors")
            if candidate["runtime"].get("runtime") != "local":
                _mark(candidate, "runtime_not_local", "workflow is not confirmed local/free")
        except (RuntimeError, TypeError, ValueError, ProfileError) as exc:
            _mark(candidate, "discovery_failed", str(exc))

        if not candidate["reason_codes"]:
            candidate["status"] = "ready"
            candidate["ready"] = candidate["production"] is True
        elif "raw_graph_requires_normalization" in candidate["reason_codes"] and len(candidate["reason_codes"]) == 1:
            candidate["status"] = "needs-normalization"
        else:
            candidate["status"] = "rejected"
        candidates.append(candidate)
    return candidates
