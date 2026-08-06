"""Explicit local REST orchestration after plan approval and consumption.

This module is the small, auditable bridge between the pure runtime contracts
and a local ComfyUI HTTP server.  It does not approve plans or infer graphs:
callers must provide the approved plan, canonical consumption evidence and
the profile/capability evidence needed to reconstruct the exact submission.
"""

from __future__ import annotations

import math
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .capabilities import build_capability_report
from .comfy_api import ComfyApi
from .comfy_submit import ComfyPromptSubmitter
from .workflow_discovery import reread_workflow_evidence
from .adapters.camera import normalize_camera_api_graph
from .adapters.camera import is_pinned_camera_profile
from .stage_execution import (
    StageExecutionError,
    _LTX_DURATION_PROFILE_HASHES,
    _LTX_DURATION_PROFILE_IDS,
    _LTX_PROFILE_HASH,
    _LTX_PROFILE_ID,
    _stage_plan,
    build_stage_submission,
    submit_stage,
)
from .execution import (
    ExecutionError,
    build_character_base_submission,
    submit_character_base,
    validate_stage_handoff,
)
from .contracts import content_hash
from .lora_discovery import LoraDiscoveryError, hash_inventory, verify_lora_presence
from .result_manifest import build_effective_camera_result
from .mcp_bridge import McpBridge, McpBridgeError
from .workflow_assets import WorkflowAssetError, load_fixed_api_workflow, load_fixed_workflow


_REST_ADAPTER = {
    "name": "prompt-forge-rest",
    "version": "1.0",
    "tools": [],
    "runtime_classification": "local",
}
_PROFILE_ROOT = Path(__file__).with_name("profiles")
_TRUSTED_CAMERA_PROFILE_FILES = {
    "camera-anima-v1": "camera-anima.json",
    "camera-anima-base-v1": "camera-anima-base.json",
}
_LTX_WORKFLOW_NAME = "LTX全新导演台工作流.json"


def _validate_timeout(timeout: object) -> float:
    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise StageExecutionError("local orchestrator timeout must be a positive finite number")
    return float(timeout)


def _require_idle(report: dict) -> None:
    try:
        queue = report["queue"]
        running = queue["running"]
        pending = queue["pending"]
    except (KeyError, TypeError) as exc:
        raise StageExecutionError("live CapabilityReport queue evidence is incomplete") from exc
    if running or pending:
        raise StageExecutionError("local ComfyUI queue is not idle; no stage was submitted")


def _reject_untrusted_source_graph(source_api_graph: object) -> None:
    """Reject graph-shaped receipts and grouped virtual buses before API use."""
    if not isinstance(source_api_graph, dict):
        raise StageExecutionError("source API graph must be an object")
    forbidden = {
        "conversion_receipt",
        "converted_api_graph",
        "__conversion_receipt__",
        "promotion_receipt",
    }
    if forbidden.intersection(source_api_graph):
        raise StageExecutionError("caller-supplied conversion receipts are not accepted")
    if isinstance(source_api_graph.get("groups"), list):
        raise StageExecutionError("grouped Flux API graphs are not production-resolvable")
    for node in source_api_graph.values():
        if not isinstance(node, dict):
            continue
        if "virtualbus" in str(node.get("class_type", "")).casefold():
            raise StageExecutionError("grouped Flux virtual buses are not production-resolvable")


def _fixed_camera_asset(profile: dict | None) -> str | None:
    if not isinstance(profile, dict):
        return None
    asset = profile.get("fixed_workflow_asset")
    if asset is None and profile.get("source_profile_id") == "camera-anima-v1":
        asset = "camera-anima.json"
    return asset if isinstance(asset, str) and asset else None


def _fixed_camera_source_graph(source_api_graph: dict, profile: dict) -> dict:
    """Resolve fixed camera graphs in one canonical normalized domain."""
    asset = _fixed_camera_asset(profile)
    if asset is None:
        return source_api_graph
    try:
        fixed_graph = load_fixed_api_workflow(asset)
        ui_workflow = load_fixed_workflow(asset) if profile.get("api_normalization") else None
        if ui_workflow is not None:
            fixed_graph = normalize_camera_api_graph(fixed_graph, ui_workflow, profile)
    except (WorkflowAssetError, ValueError) as exc:
        raise StageExecutionError(f"fixed camera workflow normalization failed: {exc}") from exc
    if not source_api_graph:
        return fixed_graph
    candidate = source_api_graph
    if ui_workflow is not None:
        try:
            candidate = normalize_camera_api_graph(candidate, ui_workflow, profile)
        except ValueError as exc:
            raise StageExecutionError(f"source camera workflow normalization failed: {exc}") from exc
    if candidate != fixed_graph:
        raise StageExecutionError("source API graph does not match the bundled fixed camera workflow")
    return candidate

def _trusted_camera_workflow_name(profile: dict) -> str:
    """Resolve camera-base aliases through the canonical pinned profile."""
    profile_file = _TRUSTED_CAMERA_PROFILE_FILES.get(profile.get("profile_id"))
    if profile_file is None:
        raise StageExecutionError("fresh workflow re-read requires a trusted workflow_name")
    try:
        canonical = json.loads((_PROFILE_ROOT / profile_file).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StageExecutionError("trusted camera profile contract is unreadable") from exc
    workflow_name = canonical.get("workflow_name") if isinstance(canonical, dict) else None
    if not isinstance(workflow_name, str) or not workflow_name:
        source_profile_id = canonical.get("source_profile_id") if isinstance(canonical, dict) else None
        source_file = _TRUSTED_CAMERA_PROFILE_FILES.get(source_profile_id)
        if source_file and source_file != profile_file:
            try:
                source = json.loads((_PROFILE_ROOT / source_file).read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise StageExecutionError("trusted camera profile contract is unreadable") from exc
            workflow_name = source.get("workflow_name") if isinstance(source, dict) else None
    if not isinstance(workflow_name, str) or not workflow_name:
        raise StageExecutionError("trusted camera profile has no workflow_name")
    return workflow_name


def _refresh_workflow_before_submission(
    source_api_graph: dict,
    profile: dict,
    workflow_tools: dict | None,
    approved_plan: dict,
) -> dict:
    """Return the freshly observed/normalized graph or fail closed."""
    if _fixed_camera_asset(profile) is not None:
        return _fixed_camera_source_graph(source_api_graph, profile)
    if workflow_tools is None:
        return source_api_graph
    workflow_name = profile.get("workflow_name")
    if not isinstance(workflow_name, str) or not workflow_name:
        if profile.get("profile_id") in {"camera-anima-v1", "camera-anima-base-v1"}:
            workflow_name = _trusted_camera_workflow_name(profile)
        else:
            raise StageExecutionError("fresh workflow re-read requires a trusted workflow_name")
    normalizer = normalize_camera_api_graph if profile.get("api_normalization") else None
    try:
        evidence = reread_workflow_evidence(
            workflow_tools,
            workflow_name,
            profile=profile,
            normalize=normalizer,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        raise StageExecutionError(f"fresh workflow re-read failed: {exc}") from exc
    if evidence["api_graph"] != source_api_graph:
        raise StageExecutionError("source API graph is stale or differs from the fresh local workflow")
    trusted_fingerprint = profile.get("workflow_fingerprint")
    if isinstance(trusted_fingerprint, str) and evidence["ui_fingerprint"] != trusted_fingerprint:
        raise StageExecutionError("fresh UI workflow fingerprint does not match the trusted profile")
    plan = approved_plan.get("stage_plan") if isinstance(approved_plan.get("stage_plan"), dict) else approved_plan
    planned_fingerprint = plan.get("workflow_fingerprint") if isinstance(plan, dict) else None
    if isinstance(planned_fingerprint, str) and evidence["ui_fingerprint"] != planned_fingerprint:
        raise StageExecutionError("fresh UI workflow fingerprint does not match the approved plan")
    return evidence["api_graph"]


def validate_trusted_stage_profile(stage_or_draft: dict, profile: dict) -> dict:
    """Bind an approval/submission boundary to the immutable profile contract."""
    if not isinstance(stage_or_draft, dict):
        raise StageExecutionError("stage plan or draft must be an object")
    plan = stage_or_draft.get("stage_plan", stage_or_draft)
    try:
        safe_plan = _stage_plan(plan, plan.get("stage"))
    except (AttributeError, StageExecutionError) as exc:
        raise StageExecutionError(f"trusted stage profile validation failed: {exc}") from exc
    if not isinstance(profile, dict) or content_hash(profile) != safe_plan.get("profile_hash"):
        raise StageExecutionError("workflow profile hash does not match the approved stage plan")
    if safe_plan["stage"] == "shot-image":
        validate_trusted_camera_profile(profile)
    else:
        profile_id = profile.get("profile_id")
        duration_id = safe_plan.get("duration_profile_id")
        if profile_id not in {_LTX_PROFILE_ID, *_LTX_DURATION_PROFILE_IDS}:
            raise StageExecutionError("Stage 4 requires the trusted LTX profile contract")
        expected_hash = (
            _LTX_PROFILE_HASH
            if profile_id == _LTX_PROFILE_ID
            else _LTX_DURATION_PROFILE_HASHES.get(profile_id)
        )
        if expected_hash is None or content_hash(profile) != expected_hash:
            raise StageExecutionError("Stage 4 profile is not an immutable trusted duration profile")
        if duration_id in _LTX_DURATION_PROFILE_IDS and profile_id != duration_id:
            raise StageExecutionError("Stage 4 duration profile does not match the approved profile")
    return safe_plan


def validate_trusted_camera_profile(profile: dict) -> None:
    if not is_pinned_camera_profile(profile):
        raise StageExecutionError("Stage 3 requires the trusted camera profile contract")
    profile_id = profile.get("profile_id")
    profile_file = _TRUSTED_CAMERA_PROFILE_FILES.get(profile_id)
    try:
        trusted_profile = (
            json.loads((_PROFILE_ROOT / profile_file).read_text(encoding="utf-8"))
            if profile_file
            else None
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StageExecutionError("trusted camera profile contract is unreadable") from exc
    if not isinstance(trusted_profile, dict) or profile != trusted_profile:
        raise StageExecutionError("Stage 3 profile is not the immutable trusted camera profile")


def validate_trusted_video_evidence(profile: dict, workflow_graph: dict, duration_profile_id: str) -> None:
    """Validate CLI-supplied Stage 4 evidence against immutable local pins."""
    if not isinstance(profile, dict) or not isinstance(workflow_graph, dict):
        raise StageExecutionError("trusted video workflow evidence must be objects")
    if profile.get("profile_id") not in {_LTX_PROFILE_ID, *_LTX_DURATION_PROFILE_IDS}:
        raise StageExecutionError("video workflow profile_id is not trusted")
    expected_hash = (
        _LTX_PROFILE_HASH
        if profile["profile_id"] == _LTX_PROFILE_ID
        else _LTX_DURATION_PROFILE_HASHES.get(profile["profile_id"])
    )
    if expected_hash is None or content_hash(profile) != expected_hash:
        raise StageExecutionError("video workflow profile is not an immutable trusted profile")
    if profile.get("workflow_name") != _LTX_WORKFLOW_NAME or profile.get("runtime_classification") != "local":
        raise StageExecutionError("video workflow profile runtime contract is invalid")
    if profile.get("api_graph_hash") != content_hash(workflow_graph):
        raise StageExecutionError("workflow graph does not match the trusted LTX profile")
    if duration_profile_id in _LTX_DURATION_PROFILE_IDS and profile.get("profile_id") != duration_profile_id:
        raise StageExecutionError("video duration profile does not match the trusted workflow profile")


def _bind_workflow_tools(
    workflow_tools: dict | None,
    mcp_bridge: McpBridge | None,
    *,
    fixed_asset: bool = False,
) -> tuple[dict | None, McpBridge | None]:
    """Resolve a host-neutral bridge into the callable map used by the runtime."""
    if workflow_tools is not None and mcp_bridge is not None:
        raise StageExecutionError("provide workflow_tools or mcp_bridge, not both")
    if mcp_bridge is None:
        return workflow_tools, None
    try:
        tools = (
            mcp_bridge.fixed_workflow_tools()
            if fixed_asset
            else mcp_bridge.workflow_tools()
        )
        return tools, mcp_bridge
    except McpBridgeError as exc:
        raise StageExecutionError(f"MCP bridge negotiation failed: {exc}") from exc


def _verify_pre_submission_loras(approved_plan, lora_inventory, lora_plan):
    """Fail closed when approved LoRA selections are absent from a fresh inventory."""
    if lora_inventory is None and lora_plan is None:
        return
    if lora_inventory is None or lora_plan is None:
        raise StageExecutionError(
            "pre-submission LoRA check requires both inventory and lora_plan"
        )
    selections = lora_plan.get("selections") if isinstance(lora_plan, dict) else None
    try:
        fresh_hash = hash_inventory(lora_inventory)
        declared = (
            approved_plan.get("lora_inventory_hash")
            if isinstance(approved_plan, dict)
            else None
        )
        if isinstance(declared, str) and declared != fresh_hash:
            raise LoraDiscoveryError(
                "fresh LoRA inventory hash does not match the approved plan"
            )
        plan_hash = lora_plan.get("inventory_hash") if isinstance(lora_plan, dict) else None
        if isinstance(plan_hash, str) and plan_hash != fresh_hash:
            raise LoraDiscoveryError(
                "fresh LoRA inventory hash does not match the approved lora_plan"
            )
        verify_lora_presence(lora_inventory, selections)
    except LoraDiscoveryError as exc:
        raise StageExecutionError(
            f"pre-submission LoRA presence check failed: {exc}"
        ) from exc

def submit_stage_via_local_rest(
    approved_plan: dict,
    source_api_graph: dict,
    consumption: dict,
    consumption_path: str | Path,
    *,
    profile: dict,
    capability_report: dict,
    base_url: str = "http://127.0.0.1:8188",
    timeout: float = 30.0,
    ui_workflow: dict | None = None,
    reference_image_name: str | None = None,
    reference_artifact: dict | None = None,
    image_ref: dict | None = None,
    workflow_tools: dict | None = None,
    mcp_bridge: McpBridge | None = None,
    lora_inventory: object | None = None,
    lora_plan: object | None = None,
) -> dict:
    """Build, guard and enqueue one consumed Stage 3/4 submission.

    A fresh read-only report guards the queue immediately before POST.  The
    approved/frozen report is still passed to ``build_stage_submission`` and
    remains part of the plan hash; the fresh report cannot rewrite that plan.
    ``submit_stage`` then owns the exclusive intent/receipt sentinel.
    """
    workflow_tools, mcp_bridge = _bind_workflow_tools(workflow_tools, mcp_bridge)
    production = isinstance(approved_plan, dict) and approved_plan.get("production_eligible") is True
    if isinstance(approved_plan, dict) and isinstance(approved_plan.get("stage_plan"), dict):
        production = approved_plan["stage_plan"].get("production_eligible") is True
    if isinstance(approved_plan, dict) and approved_plan.get("plan_mode") == "legacy-dry-run":
        raise StageExecutionError("legacy dry-run plans cannot be submitted")
    if isinstance(approved_plan, dict) and approved_plan.get("production_eligible") is False:
        raise StageExecutionError("non-production stage plans cannot be submitted")
    _verify_pre_submission_loras(approved_plan, lora_inventory, lora_plan)
    # Validate graph shape before profile checks so malformed handoffs expose
    # their precise evidence failure while still remaining pre-API.
    _reject_untrusted_source_graph(source_api_graph)
    handoff_plan = (
        approved_plan.get("stage_plan")
        if isinstance(approved_plan, dict) and isinstance(approved_plan.get("stage_plan"), dict)
        else approved_plan
    )
    handoff_artifact = (
        reference_artifact if handoff_plan.get("stage") == "shot-image" else image_ref
    ) if isinstance(handoff_plan, dict) else None
    expected_hash = (
        handoff_plan.get("reference_hash")
        if isinstance(handoff_plan, dict) and handoff_plan.get("stage") == "shot-image"
        else handoff_plan.get("source_shot_hash") if isinstance(handoff_plan, dict) else None
    )
    if handoff_artifact is not None or expected_hash is not None:
        try:
            validate_stage_handoff(handoff_plan, handoff_artifact)
        except ExecutionError as exc:
            raise StageExecutionError(f"stage handoff validation failed: {exc}") from exc
    # Validate the full Stage 3/4 intent and immutable profile before any REST
    # client or capability read is constructed.
    validate_trusted_stage_profile(approved_plan, profile)
    if production and workflow_tools is None:
        raise StageExecutionError(
            "production submission requires negotiated local workflow tools and a fresh workflow re-read"
        )
    source_api_graph = _refresh_workflow_before_submission(
        source_api_graph, profile, workflow_tools, approved_plan
    )
    stage_plan = approved_plan.get("stage_plan", approved_plan)
    if isinstance(stage_plan, dict) and stage_plan.get("stage") == "video":
        validate_trusted_video_evidence(
            profile,
            source_api_graph,
            stage_plan.get("duration_profile_id", "ltx-yusu-short-v1"),
        )

    timeout_value = _validate_timeout(timeout)
    api = ComfyApi(base_url=base_url, timeout=timeout_value)
    frozen_url = capability_report.get("comfyui", {}).get("url") if isinstance(capability_report, dict) else None
    if isinstance(frozen_url, str) and frozen_url.rstrip("/") != api.base_url:
        raise StageExecutionError("live ComfyUI URL does not match the approved CapabilityReport")
    live_report = build_capability_report(api, _REST_ADAPTER, datetime.now(timezone.utc))
    _require_idle(live_report)

    optional = {
        key: value
        for key, value in {
            "ui_workflow": ui_workflow,
            "reference_image_name": reference_image_name,
            "reference_artifact": reference_artifact,
            "image_ref": image_ref,
        }.items()
        if value is not None
    }
    submission = build_stage_submission(
        approved_plan,
        source_api_graph,
        consumption,
        consumption_path,
        profile=profile,
        capability_report=capability_report,
        **optional,
    )
    root = Path(submission["consumption_root"]).resolve()
    receipt_path = root / f'{submission["consumption_id"]}.stage-enqueue-receipt.json'
    submitter = ComfyPromptSubmitter(base_url=api.base_url, timeout=timeout_value)
    receipt = submit_stage(submission, submitter.submit, receipt_path=receipt_path)
    history = api.history(receipt["prompt_id"])
    history_entry = history.get(prompt_id) if isinstance(history, dict) else None
    history_graph = history_entry.get("prompt") if isinstance(history_entry, dict) else None
    effective_graph = history_graph if isinstance(history_graph, dict) else result["submission"]["api_graph"]
    result_manifest = build_effective_camera_result(effective_graph, ui_workflow=ui_workflow)
    result = {
        "submission": submission,
        "receipt": receipt,
        "receipt_path": str(receipt_path.resolve()),
        "history": history,
        "result_manifest": result_manifest,
        "effective_config": result_manifest["config"],
        "lora": result_manifest["lora"],
        "config_hash": result_manifest["config_hash"],
        "live_capability_report": live_report,
    }
    if mcp_bridge is not None:
        result["mcp_bridge_receipt"] = mcp_bridge.receipt()
    return result


def submit_character_base_via_local_rest(
    approved_plan: dict,
    prompt_build: dict,
    source_api_graph: dict,
    consumption: dict,
    consumption_path: str | Path,
    *,
    base_url: str = "http://127.0.0.1:8188",
    timeout: float = 30.0,
    ui_workflow: dict | None = None,
    profile: dict | None = None,
    workflow_tools: dict | None = None,
    mcp_bridge: McpBridge | None = None,
    lora_inventory: object | None = None,
    lora_plan: object | None = None,
) -> dict:
    """Build and enqueue the consumed Stage 1 camera text-to-image graph.

    The REST client remains transport-only. Approval, exact graph rebuilding,
    and the exclusive receipt are owned by ``submit_character_base``.
    """
    workflow_tools, mcp_bridge = _bind_workflow_tools(
        workflow_tools, mcp_bridge, fixed_asset=_fixed_camera_asset(profile) is not None
    )
    _verify_pre_submission_loras(approved_plan, lora_inventory, lora_plan)
    production = isinstance(approved_plan, dict) and (
        approved_plan.get("execution_approved") is True
        or approved_plan.get("production_eligible") is True
        or approved_plan.get("plan_mode") == "production"
    )
    if not isinstance(profile, dict):
        raise StageExecutionError("character-base submission requires the trusted camera profile")
    validate_trusted_camera_profile(profile)
    expected_profile_hash = approved_plan.get("profile_hash") if isinstance(approved_plan, dict) else None
    if expected_profile_hash is not None and expected_profile_hash != content_hash(profile):
        raise StageExecutionError("character-base profile hash does not match the approved plan")
    fixed_camera = _fixed_camera_asset(profile) is not None
    if production and workflow_tools is None and not fixed_camera:
        raise StageExecutionError(
            "production submission requires negotiated local workflow tools and a fresh workflow re-read"
        )
    source_api_graph = _fixed_camera_source_graph(source_api_graph, profile)
    _reject_untrusted_source_graph(source_api_graph)
    source_api_graph = _refresh_workflow_before_submission(
        source_api_graph, profile, workflow_tools, approved_plan
    )
    timeout_value = _validate_timeout(timeout)
    api = ComfyApi(base_url=base_url, timeout=timeout_value)
    live_report = build_capability_report(api, _REST_ADAPTER, datetime.now(timezone.utc))
    _require_idle(live_report)
    submission = build_character_base_submission(
        approved_plan=approved_plan,
        prompt_build=prompt_build,
        source_api_graph=source_api_graph,
        approval_consumption=consumption,
        consumption_path=consumption_path,
        ui_workflow=ui_workflow,
    )
    submitter = ComfyPromptSubmitter(base_url=api.base_url, timeout=timeout_value)
    result = submit_character_base(
        approved_plan=approved_plan,
        prompt_build=prompt_build,
        source_api_graph=source_api_graph,
        approval_consumption=consumption,
        consumption_path=consumption_path,
        enqueue_workflow=submitter.submit,
        receipt_root=consumption["consumption_root"],
        ui_workflow=ui_workflow,
    )
    prompt_id = result["enqueue_receipt"]["prompt_id"]
    history = api.history(prompt_id)
    history_entry = history.get(prompt_id) if isinstance(history, dict) else None
    history_graph = history_entry.get("prompt") if isinstance(history_entry, dict) else None
    effective_graph = history_graph if isinstance(history_graph, dict) else result["submission"]["api_graph"]
    result_manifest = build_effective_camera_result(effective_graph, ui_workflow=ui_workflow)
    result = {
        "submission": submission,
        **result,
        "history": history,
        "result_manifest": result_manifest,
        "effective_config": result_manifest["config"],
        "lora": result_manifest["lora"],
        "config_hash": result_manifest["config_hash"],
        "live_capability_report": live_report,
    }
    if mcp_bridge is not None:
        result["mcp_bridge_receipt"] = mcp_bridge.receipt()
    return result


def wait_for_stage_history(
    api: ComfyApi,
    prompt_id: str,
    *,
    timeout: float = 3600.0,
    poll_interval: float = 2.0,
) -> dict:
    """Poll one local history entry until ComfyUI reports a terminal result."""
    timeout_value = _validate_timeout(timeout)
    interval = _validate_timeout(poll_interval)
    if interval > 60:
        raise StageExecutionError("history poll interval must not exceed 60 seconds")
    deadline = time.monotonic() + timeout_value
    while True:
        history = api.history(prompt_id)
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        status = entry.get("status") if isinstance(entry, dict) else None
        if isinstance(status, dict) and status.get("completed") is True:
            return history
        if isinstance(status, dict) and status.get("status_str") in {"error", "failed"}:
            raise StageExecutionError(f"ComfyUI stage {prompt_id} failed")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise StageExecutionError(f"timed out waiting for ComfyUI stage {prompt_id}")
        time.sleep(min(interval, remaining))
