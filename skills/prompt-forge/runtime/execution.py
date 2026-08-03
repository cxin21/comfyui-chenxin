"""Fail-closed execution plans and immutable runtime provenance records."""

from __future__ import annotations

import copy
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from .capabilities import report_is_fresh
from .contracts import ContractError, canonical_json, content_hash, validate_task_context
from .prompt_quality import validate_anima_prompt_build
from .workflow_profile import ProfileError, resolve_slots, structure_fingerprint


class ExecutionError(ValueError):
    """Raised when execution evidence does not satisfy the runtime boundary."""


_CHARACTER_BASE_PROFILE_ID = "camera-anima-v1"
_CHARACTER_BASE_OUTPUTS = ["image/png"]
_CHARACTER_BASE_SLOTS = {"positive_prompt": 24, "negative_prompt": 25}
_CHARACTER_BASE_SELECTORS = {
    "positive_prompt": {
        "id": 24,
        "type": "ImpactWildcardProcessor",
        "title": "POSITIVE",
    },
    "negative_prompt": {
        "id": 25,
        "type": "ImpactWildcardProcessor",
        "title": "NEGATIVE",
    },
}
_MULTIVIEW_STAGE = "character-multiview"
_MULTIVIEW_PROFILE_ID = "flux2-klein-multiview-v1"
_MULTIVIEW_FINGERPRINT = "fff6236efa6727ac6584d61f640a63f9602b2d07a545d216b96a870a681e6faf"
_MULTIVIEW_OUTPUTS = ["image/png"]
_MULTIVIEW_SLOTS = {"base_image_primary": 111, "base_image_secondary": 667}
_MULTIVIEW_SELECTORS = {
    "base_image_primary": {"id": 111, "type": "LoadImage"},
    "base_image_secondary": {"id": 667, "type": "LoadImage"},
}
_PATCH_KEYS = frozenset(("slot", "input", "value"))
_TERMINAL_STATUSES = frozenset(("succeeded", "failed"))
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STAGE1_DRAFT_KEYS = frozenset(
    (
        "schema_version",
        "stage",
        "plan_state",
        "prompt_build_id",
        "capability_report_hash",
        "workflow_profile_id",
        "profile_hash",
        "workflow_fingerprint",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "patches",
        "immutable_inputs",
        "local_only",
        "preflight",
        "expected_outputs",
        "execution_approved",
        "draft_hash",
    )
)
_MULTIVIEW_DRAFT_KEYS = frozenset(
    (
        "schema_version",
        "stage",
        "plan_state",
        "upstream_record_hash",
        "source_artifact_hash",
        "lineage_id",
        "uploaded_filename",
        "capability_report_hash",
        "workflow_profile_id",
        "profile_hash",
        "workflow_fingerprint",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "patches",
        "immutable_inputs",
        "local_only",
        "preflight",
        "expected_outputs",
        "execution_approved",
        "draft_hash",
    )
)
_APPROVAL_PLAN_FIELDS = frozenset(
    (
        "approval_event",
        "approval_id",
        "plan_hash",
    )
)
_APPROVAL_EVENT_KEYS = frozenset(
    (
        "decision",
        "draft_hash",
        "displayed_at",
        "approved_at",
        "expires_at",
        "scope",
        "consumption_root",
        "actor",
        "source",
    )
)


def _utc_now() -> datetime:
    """Return the trusted production clock used for capability freshness."""
    return datetime.now(timezone.utc)


def _character_base_patches(prompt_build: dict) -> list[dict]:
    return [
        {
            "slot": "positive_prompt",
            "input": "wildcard_text",
            "value": prompt_build["prompt"],
        },
        {
            "slot": "positive_prompt",
            "input": "populated_text",
            "value": prompt_build["prompt"],
        },
        {
            "slot": "negative_prompt",
            "input": "wildcard_text",
            "value": prompt_build["negative_prompt"],
        },
        {
            "slot": "negative_prompt",
            "input": "populated_text",
            "value": prompt_build["negative_prompt"],
        },
    ]


def _validate_character_base_profile(profile: object, profile_id: object) -> None:
    if not isinstance(profile, dict) or profile.get("schema_version") != "1.0":
        raise ExecutionError("a versioned workflow profile is required")
    if profile_id != _CHARACTER_BASE_PROFILE_ID or profile.get("profile_id") != profile_id:
        raise ExecutionError("character-base requires profile camera-anima-v1")
    if profile.get("runtime_classification") != "local":
        raise ExecutionError("character-base profile must be local")
    if profile.get("expected_outputs") != _CHARACTER_BASE_OUTPUTS:
        raise ExecutionError("character-base profile must expect only image/png")
    slots = profile.get("slots")
    if not isinstance(slots, dict):
        raise ExecutionError("character-base profile requires slots")
    for slot_name, node_id in _CHARACTER_BASE_SLOTS.items():
        selector = slots.get(slot_name)
        if selector != _CHARACTER_BASE_SELECTORS[slot_name]:
            raise ExecutionError(
                f"character-base profile slot '{slot_name}' must be the fixed node {node_id} selector"
            )


def _require_idle_local_capability(report: object, now: datetime) -> None:
    if not isinstance(report, dict) or report.get("schema_version") != "1.0":
        raise ExecutionError("a current CapabilityReport is required")
    if not report_is_fresh(report, now):
        raise ExecutionError("CapabilityReport must be fresh")
    try:
        classification = report["adapter"]["runtime_classification"]
        reachable = report["comfyui"]["reachable"]
        running = report["queue"]["running"]
        pending = report["queue"]["pending"]
    except (KeyError, TypeError) as exc:
        raise ExecutionError("CapabilityReport is incomplete") from exc
    if classification != "local" or reachable is not True:
        raise ExecutionError("execution requires a reachable local runtime")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (running, pending)
    ):
        raise ExecutionError("CapabilityReport queue counts must be non-negative integers")
    if running or pending:
        raise ExecutionError("one ComfyUI job at a time is allowed")


def _derived_preflight(
    workflow_fingerprint: str,
    source_api_graph_hash: str,
    executable_api_graph_hash: str,
    capability_report_hash: str,
    profile_hash: str,
    slots: dict[str, int],
) -> dict:
    return {
        "workflow": {
            "verified": True,
            "fingerprint": workflow_fingerprint,
            "slots": copy.deepcopy(slots),
        },
        "api_graph": {
            "verified": True,
            "source_hash": source_api_graph_hash,
            "executable_hash": executable_api_graph_hash,
        },
        "capability": {"verified": True, "report_hash": capability_report_hash},
        "profile": {"verified": True, "hash": profile_hash},
    }


def build_execution_draft(
    stage: str,
    prompt_build: dict,
    workflow_profile_id: str,
    workflow_fingerprint: str,
    patches: list,
    *,
    capability_report: dict | None = None,
    profile: dict | None = None,
    actual_ui_workflow: dict | None = None,
    api_graph: dict | None = None,
) -> dict:
    """Build an unapproved character-base draft from recomputed local evidence."""
    if stage != "character-base":
        raise ExecutionError("this execution boundary supports only character-base")
    if not isinstance(prompt_build, dict) or prompt_build.get("ready_to_execute") is not True:
        raise ExecutionError("PromptBuild must be ready to execute")
    execution = prompt_build.get("execution")
    if not isinstance(execution, dict) or execution.get("requested") is not True:
        raise ExecutionError("PromptBuild execution must be requested")
    if execution.get("performed") is not False:
        raise ExecutionError("PromptBuild execution.performed must remain false")
    quality_errors = validate_anima_prompt_build(
        prompt_build, {"locked_facts": prompt_build.get("locked_facts")}
    )
    if quality_errors:
        raise ExecutionError("PromptBuild quality gate failed: " + "; ".join(quality_errors))

    _validate_character_base_profile(profile, workflow_profile_id)
    _require_idle_local_capability(capability_report, _utc_now())
    if not isinstance(api_graph, dict):
        raise ExecutionError("actual API graph must be an object")

    try:
        resolved_slots = resolve_slots(actual_ui_workflow, profile)
        actual_fingerprint = structure_fingerprint(actual_ui_workflow)
        source_graph_hash = content_hash(api_graph)
        report_hash = content_hash(capability_report)
        profile_hash = content_hash(profile)
    except (ProfileError, TypeError, ValueError) as exc:
        raise ExecutionError(f"execution evidence is invalid: {exc}") from exc
    if workflow_fingerprint != actual_fingerprint:
        raise ExecutionError("workflow fingerprint does not match the actual UI workflow")
    prompt_slots = {
        "positive_prompt": resolved_slots.get("positive_prompt"),
        "negative_prompt": resolved_slots.get("negative_prompt"),
    }
    if prompt_slots != _CHARACTER_BASE_SLOTS:
        raise ExecutionError("character-base workflow slot resolution does not match nodes 24/25")

    if not isinstance(patches, list) or any(
        not isinstance(item, dict) or set(item) != _PATCH_KEYS for item in patches
    ):
        raise ExecutionError("character-base requires the exact four prompt patches")
    expected_patches = _character_base_patches(prompt_build)
    if patches != expected_patches:
        raise ExecutionError("character-base requires the exact four prompt-derived patches")

    # This call is validation, not execution: it deep-copies the graph and proves
    # nodes 24/25, their class types and all four prompt inputs exist.
    from .adapters.camera import patch_character_base

    patched_graph = patch_character_base(api_graph, prompt_build, prompt_slots)
    executable_graph_hash = content_hash(patched_graph)
    derived_preflight = _derived_preflight(
        actual_fingerprint,
        source_graph_hash,
        executable_graph_hash,
        report_hash,
        profile_hash,
        prompt_slots,
    )

    draft = {
        "schema_version": "1.0",
        "stage": "character-base",
        "plan_state": "draft",
        "prompt_build_id": content_hash(prompt_build),
        "capability_report_hash": report_hash,
        "workflow_profile_id": _CHARACTER_BASE_PROFILE_ID,
        "profile_hash": profile_hash,
        "workflow_fingerprint": actual_fingerprint,
        "source_api_graph_hash": source_graph_hash,
        "executable_api_graph_hash": executable_graph_hash,
        "patches": copy.deepcopy(expected_patches),
        "immutable_inputs": [],
        "local_only": True,
        "preflight": derived_preflight,
        "expected_outputs": list(_CHARACTER_BASE_OUTPUTS),
        "execution_approved": False,
    }
    draft["draft_hash"] = content_hash(draft)
    return draft


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_stage1_source(stage1_record: object, base_artifact: object) -> tuple[dict, dict]:
    if not isinstance(stage1_record, dict) or stage1_record.get("schema_version") != "1.0":
        raise ExecutionError("an accepted Stage 1 RunRecord is required")
    record_hash = stage1_record.get("record_hash")
    unsigned_record = dict(stage1_record)
    unsigned_record.pop("record_hash", None)
    if not isinstance(record_hash, str) or not _SHA256_RE.fullmatch(record_hash):
        raise ExecutionError("Stage 1 RunRecord record_hash must be a lowercase SHA-256 digest")
    if record_hash != content_hash(unsigned_record):
        raise ExecutionError("Stage 1 RunRecord record_hash is not self-consistent")
    if stage1_record.get("terminal_status") != "succeeded" or stage1_record.get("history_verified") is not True:
        raise ExecutionError("Stage 1 RunRecord must be a verified successful run")
    source_plan = stage1_record.get("execution_plan")
    if not isinstance(source_plan, dict) or source_plan.get("stage") != "character-base":
        raise ExecutionError("Stage 1 RunRecord must describe character-base")
    if source_plan.get("workflow_profile_id") != _CHARACTER_BASE_PROFILE_ID:
        raise ExecutionError("Stage 1 RunRecord profile lineage is invalid")

    if not isinstance(base_artifact, dict) or base_artifact.get("schema_version") != "1.0":
        raise ExecutionError("a versioned CharacterBaseImage artifact is required")
    if base_artifact.get("artifact_type") != "CharacterBaseImage":
        raise ExecutionError("Stage 2 requires artifact_type=CharacterBaseImage")
    if base_artifact.get("accepted") is not True:
        raise ExecutionError("CharacterBaseImage must be accepted before Stage 2")
    artifact_hash = base_artifact.get("content_hash")
    if not isinstance(artifact_hash, str) or not _SHA256_RE.fullmatch(artifact_hash):
        raise ExecutionError("CharacterBaseImage content_hash must be a lowercase SHA-256 digest")
    lineage_id = base_artifact.get("lineage_id")
    if not isinstance(lineage_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", lineage_id):
        raise ExecutionError("CharacterBaseImage lineage_id must be a safe non-empty identifier")
    if base_artifact.get("source_record_hash") != record_hash:
        raise ExecutionError("CharacterBaseImage source record lineage does not match RunRecord")
    visual = base_artifact.get("visual_acceptance")
    if not isinstance(visual, dict) or visual.get("front_facing") is not True:
        raise ExecutionError("CharacterBaseImage requires front-facing visual acceptance")
    if visual.get("identity_visible") is not True:
        raise ExecutionError("CharacterBaseImage visual acceptance requires visible identity")

    root_text = base_artifact.get("artifact_root")
    path_text = base_artifact.get("artifact_path")
    if not isinstance(root_text, str) or not isinstance(path_text, str):
        raise ExecutionError("CharacterBaseImage artifact path/root are required")
    root = Path(root_text)
    path = Path(path_text)
    try:
        resolved_root = root.resolve(strict=True)
        resolved_path = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExecutionError("CharacterBaseImage artifact path/root must exist") from exc
    if str(root) != str(resolved_root) or str(path) != str(resolved_path):
        raise ExecutionError("CharacterBaseImage artifact path/root must be canonical")
    if not resolved_root.is_dir() or not resolved_path.is_file() or not resolved_path.is_relative_to(resolved_root):
        raise ExecutionError("CharacterBaseImage artifact path must remain inside artifact root")
    if _file_sha256(resolved_path) != artifact_hash:
        raise ExecutionError("CharacterBaseImage content_hash does not match artifact bytes")
    output_hashes = stage1_record.get("output_hashes")
    if not isinstance(output_hashes, dict) or output_hashes.get(resolved_path.name) != artifact_hash:
        raise ExecutionError("CharacterBaseImage hash does not match Stage 1 RunRecord outputs")
    return copy.deepcopy(stage1_record), copy.deepcopy(base_artifact)


def _validate_multiview_profile(profile: object, profile_id: object) -> None:
    if not isinstance(profile, dict) or profile.get("schema_version") != "1.0":
        raise ExecutionError("a versioned Flux workflow profile is required")
    if profile_id != _MULTIVIEW_PROFILE_ID or profile.get("profile_id") != profile_id:
        raise ExecutionError("character-multiview requires profile flux2-klein-multiview-v1")
    if profile.get("workflow_fingerprint") != _MULTIVIEW_FINGERPRINT:
        raise ExecutionError("Flux profile fingerprint is not the verified fingerprint")
    if profile.get("runtime_classification") != "local":
        raise ExecutionError("Flux profile must be local")
    if profile.get("expected_outputs") != _MULTIVIEW_OUTPUTS:
        raise ExecutionError("Flux profile must expect only image/png")
    if profile.get("slots") != _MULTIVIEW_SELECTORS:
        raise ExecutionError("Flux profile requires the verified nodes 111/667 selectors")
    pose_ids = profile.get("immutable_roles", {}).get("pose_references")
    if not isinstance(pose_ids, list) or not pose_ids:
        raise ExecutionError("Flux profile requires immutable pose references")


def _multiview_upload_name(lineage_id: str, artifact_hash: str) -> str:
    return f"prompt-forge/{lineage_id}/character-base-{artifact_hash}.png"


def _multiview_patches(filename: str, artifact_hash: str) -> list[dict]:
    return [
        {"slot": slot, "input": "image", "value": filename, "source_hash": artifact_hash}
        for slot in ("base_image_primary", "base_image_secondary")
    ]


def _multiview_immutable_inputs(api_graph: dict, profile: dict) -> list[dict]:
    result = []
    for node_id in profile["immutable_roles"]["pose_references"]:
        node = api_graph.get(str(node_id))
        image = node.get("inputs", {}).get("image") if isinstance(node, dict) else None
        if not isinstance(node, dict) or node.get("class_type") != "LoadImage" or not isinstance(image, str) or not image:
            raise ExecutionError(f"immutable pose node {node_id} must be a configured LoadImage")
        result.append({"node_id": node_id, "input": "image", "value": image})
    return result


def build_multiview_draft(
    *,
    stage1_record: dict,
    base_artifact: dict,
    workflow_profile_id: str,
    workflow_fingerprint: str,
    capability_report: dict,
    profile: dict,
    actual_ui_workflow: dict,
    api_graph: dict,
) -> dict:
    """Build an unapproved Stage 2 draft bound to one accepted Stage 1 artifact."""
    safe_record, safe_artifact = _validated_stage1_source(stage1_record, base_artifact)
    _validate_multiview_profile(profile, workflow_profile_id)
    _require_idle_local_capability(capability_report, _utc_now())
    if not isinstance(api_graph, dict):
        raise ExecutionError("actual Flux API graph must be an object")
    try:
        slots = resolve_slots(actual_ui_workflow, profile)
        actual_fingerprint = structure_fingerprint(actual_ui_workflow)
    except (ProfileError, TypeError, ValueError) as exc:
        raise ExecutionError(f"Flux execution evidence is invalid: {exc}") from exc
    if slots != _MULTIVIEW_SLOTS:
        raise ExecutionError("Flux workflow slot resolution does not match nodes 111/667")
    if workflow_fingerprint != _MULTIVIEW_FINGERPRINT or actual_fingerprint != workflow_fingerprint:
        raise ExecutionError("Flux workflow fingerprint does not match verified actual UI")

    filename = _multiview_upload_name(safe_artifact["lineage_id"], safe_artifact["content_hash"])
    from .adapters.flux_multiview import FluxAdapterError, patch_base_images
    try:
        executable = patch_base_images(api_graph, filename, slots)
    except FluxAdapterError as exc:
        raise ExecutionError(f"Flux API graph is invalid: {exc}") from exc
    source_hash = content_hash(api_graph)
    executable_hash = content_hash(executable)
    report_hash = content_hash(capability_report)
    profile_hash = content_hash(profile)
    preflight = _derived_preflight(
        actual_fingerprint, source_hash, executable_hash, report_hash, profile_hash, slots
    )
    preflight["upstream"] = {
        "verified": True,
        "record_hash": safe_record["record_hash"],
        "artifact_hash": safe_artifact["content_hash"],
        "lineage_id": safe_artifact["lineage_id"],
    }
    draft = {
        "schema_version": "1.0",
        "stage": _MULTIVIEW_STAGE,
        "plan_state": "draft",
        "upstream_record_hash": safe_record["record_hash"],
        "source_artifact_hash": safe_artifact["content_hash"],
        "lineage_id": safe_artifact["lineage_id"],
        "uploaded_filename": filename,
        "capability_report_hash": report_hash,
        "workflow_profile_id": _MULTIVIEW_PROFILE_ID,
        "profile_hash": profile_hash,
        "workflow_fingerprint": actual_fingerprint,
        "source_api_graph_hash": source_hash,
        "executable_api_graph_hash": executable_hash,
        "patches": _multiview_patches(filename, safe_artifact["content_hash"]),
        "immutable_inputs": _multiview_immutable_inputs(api_graph, profile),
        "local_only": True,
        "preflight": preflight,
        "expected_outputs": list(_MULTIVIEW_OUTPUTS),
        "execution_approved": False,
    }
    draft["draft_hash"] = content_hash(draft)
    return draft


def _validate_multiview_draft_contract(draft: dict) -> None:
    for field in (
        "upstream_record_hash",
        "source_artifact_hash",
        "capability_report_hash",
        "profile_hash",
        "workflow_fingerprint",
        "source_api_graph_hash",
        "executable_api_graph_hash",
    ):
        if not isinstance(draft.get(field), str) or not _SHA256_RE.fullmatch(draft[field]):
            raise ExecutionError("Stage 2 draft lineage hashes must be lowercase SHA-256 digests")
    lineage_id = draft.get("lineage_id")
    if not isinstance(lineage_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", lineage_id):
        raise ExecutionError("Stage 2 draft lineage_id is invalid")
    expected_filename = _multiview_upload_name(lineage_id, draft["source_artifact_hash"])
    if draft.get("uploaded_filename") != expected_filename:
        raise ExecutionError("Stage 2 draft uploaded filename is not content-derived")
    if draft.get("workflow_profile_id") != _MULTIVIEW_PROFILE_ID:
        raise ExecutionError("Stage 2 draft profile is invalid")
    if draft.get("workflow_fingerprint") != _MULTIVIEW_FINGERPRINT:
        raise ExecutionError("Stage 2 draft fingerprint is invalid")
    if draft.get("expected_outputs") != _MULTIVIEW_OUTPUTS or draft.get("local_only") is not True:
        raise ExecutionError("Stage 2 draft output/runtime policy is invalid")
    if draft.get("patches") != _multiview_patches(expected_filename, draft["source_artifact_hash"]):
        raise ExecutionError("Stage 2 draft exact dual image patches are invalid")
    immutable = draft.get("immutable_inputs")
    pose_ids = {368, 151, 152, 154, 360, 364, 148, 149, 147, 373, 150, 367}
    if not isinstance(immutable, list) or {item.get("node_id") for item in immutable if isinstance(item, dict)} != pose_ids:
        raise ExecutionError("Stage 2 draft immutable pose inputs are invalid")
    if any(
        not isinstance(item, dict)
        or set(item) != {"node_id", "input", "value"}
        or item.get("input") != "image"
        or not isinstance(item.get("value"), str)
        or not item["value"]
        for item in immutable
    ):
        raise ExecutionError("Stage 2 draft immutable pose inputs are invalid")
    upstream = draft.get("preflight", {}).get("upstream")
    if upstream != {
        "verified": True,
        "record_hash": draft["upstream_record_hash"],
        "artifact_hash": draft["source_artifact_hash"],
        "lineage_id": lineage_id,
    }:
        raise ExecutionError("Stage 2 draft upstream preflight is invalid")


def _validate_draft_hash(draft: object) -> dict:
    if not isinstance(draft, dict):
        raise ExecutionError("ExecutionDraft schema is incomplete or contains unexpected fields")
    expected_keys = (
        _STAGE1_DRAFT_KEYS if draft.get("stage") == "character-base" else _MULTIVIEW_DRAFT_KEYS
    )
    if set(draft) != expected_keys:
        raise ExecutionError("ExecutionDraft schema is incomplete or contains unexpected fields")
    if draft.get("schema_version") != "1.0" or draft.get("stage") not in {"character-base", _MULTIVIEW_STAGE}:
        raise ExecutionError("ExecutionDraft stage is unsupported")
    if draft.get("plan_state") != "draft" or draft.get("execution_approved") is not False:
        raise ExecutionError("ExecutionDraft must remain unapproved")
    if draft.get("stage") == _MULTIVIEW_STAGE:
        _validate_multiview_draft_contract(draft)
    unsigned = dict(draft)
    claimed_hash = unsigned.pop("draft_hash")
    if not isinstance(claimed_hash, str) or claimed_hash != content_hash(unsigned):
        raise ExecutionError("ExecutionDraft draft_hash is not self-consistent")
    return copy.deepcopy(draft)


def _parse_utc_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ExecutionError(f"approval event {label} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionError(f"approval event {label} must be a UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ExecutionError(f"approval event {label} must be UTC")
    return parsed


def _canonical_consumption_root(value: object, label: str) -> str:
    if not isinstance(value, (str, Path)):
        raise ExecutionError(f"{label} consumption root must be an absolute canonical path")
    raw_text = str(value)
    raw_path = Path(raw_text)
    if not raw_path.is_absolute():
        raise ExecutionError(f"{label} consumption root must be an absolute canonical path")
    try:
        resolved = raw_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExecutionError(f"{label} consumption root must be an existing directory") from exc
    if not resolved.is_dir():
        raise ExecutionError(f"{label} consumption root must be an existing directory")
    canonical = str(resolved)
    if raw_text != canonical:
        raise ExecutionError(f"{label} consumption root must not use a path alias")
    return canonical


def _validate_approval_event(
    event: object,
    draft_hash: str,
    *,
    trusted_now: datetime | None,
    expected_consumption_root: object | None,
) -> dict:
    if not isinstance(event, dict) or set(event) != _APPROVAL_EVENT_KEYS:
        raise ExecutionError("approval event schema is incomplete or contains unexpected fields")
    if event.get("decision") != "approved":
        raise ExecutionError("approval event decision must be approved")
    if event.get("draft_hash") != draft_hash:
        raise ExecutionError("approval event draft_hash does not match the displayed draft")
    if event.get("scope") != "enqueue-once":
        raise ExecutionError("approval event scope must be enqueue-once")
    event_root = _canonical_consumption_root(
        event.get("consumption_root"), "approval event"
    )
    if expected_consumption_root is not None:
        expected_root = _canonical_consumption_root(
            expected_consumption_root, "expected"
        )
        if event_root != expected_root:
            raise ExecutionError(
                "approval event consumption root does not match the expected consumption root"
            )
    for field in ("actor", "source"):
        value = event.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ExecutionError(f"approval event {field} must be a non-empty string")

    displayed_at = _parse_utc_timestamp(event.get("displayed_at"), "displayed_at")
    approved_at = _parse_utc_timestamp(event.get("approved_at"), "approved_at")
    expires_at = _parse_utc_timestamp(event.get("expires_at"), "expires_at")
    if not displayed_at <= approved_at:
        raise ExecutionError("approval event timestamp order is invalid")
    if (expires_at - displayed_at).total_seconds() > 600:
        raise ExecutionError("approval event window must not exceed 600 seconds")
    if approved_at >= expires_at:
        raise ExecutionError("approval event timestamp order is invalid")
    if trusted_now is not None:
        if trusted_now.tzinfo is None or trusted_now.utcoffset() != timezone.utc.utcoffset(trusted_now):
            raise ExecutionError("trusted approval clock must be UTC")
        if approved_at > trusted_now:
            raise ExecutionError("approval event timestamp order is invalid")
        if trusted_now >= expires_at:
            raise ExecutionError("approval event is expired")
    return copy.deepcopy(event)


def approve_execution_draft(
    draft: dict,
    approval_event: dict,
    *,
    consumption_root: str | Path,
) -> dict:
    """Approve exactly one displayed draft with a fresh external event."""
    safe_draft = _validate_draft_hash(draft)
    safe_event = _validate_approval_event(
        approval_event,
        safe_draft["draft_hash"],
        trusted_now=_utc_now(),
        expected_consumption_root=consumption_root,
    )
    plan = copy.deepcopy(safe_draft)
    plan["plan_state"] = "approved"
    plan["execution_approved"] = True
    plan["approval_event"] = safe_event
    plan["approval_id"] = content_hash(safe_event)
    plan["plan_hash"] = content_hash(plan)
    return plan


def _validate_approved_plan(plan: object, *, trusted_now: datetime | None) -> dict:
    if not isinstance(plan, dict):
        raise ExecutionError("ExecutionPlan lineage is incomplete")
    draft_keys = (
        _STAGE1_DRAFT_KEYS if plan.get("stage") == "character-base" else _MULTIVIEW_DRAFT_KEYS
    )
    if set(plan) != draft_keys.union(_APPROVAL_PLAN_FIELDS):
        raise ExecutionError("ExecutionPlan lineage is incomplete")
    stage = plan.get("stage")
    if plan.get("schema_version") != "1.0" or stage not in {"character-base", _MULTIVIEW_STAGE}:
        raise ExecutionError("ExecutionPlan stage is unsupported")
    expected_profile = _CHARACTER_BASE_PROFILE_ID if stage == "character-base" else _MULTIVIEW_PROFILE_ID
    expected_outputs = _CHARACTER_BASE_OUTPUTS if stage == "character-base" else _MULTIVIEW_OUTPUTS
    expected_slots = _CHARACTER_BASE_SLOTS if stage == "character-base" else _MULTIVIEW_SLOTS
    if plan.get("workflow_profile_id") != expected_profile:
        raise ExecutionError("ExecutionPlan profile does not match its stage")
    if plan.get("plan_state") != "approved":
        raise ExecutionError("ExecutionPlan must be approved")
    if plan.get("local_only") is not True or plan.get("execution_approved") is not True:
        raise ExecutionError("ExecutionPlan must be local-only and approved")
    if plan.get("expected_outputs") != expected_outputs:
        raise ExecutionError("ExecutionPlan must expect exactly image/png")
    if stage == "character-base" and plan.get("immutable_inputs") != []:
        raise ExecutionError("ExecutionPlan immutable_inputs contract is invalid")
    reconstructed_draft = {key: copy.deepcopy(plan[key]) for key in draft_keys}
    reconstructed_draft["plan_state"] = "draft"
    reconstructed_draft["execution_approved"] = False
    _validate_draft_hash(reconstructed_draft)
    safe_event = _validate_approval_event(
        plan.get("approval_event"),
        plan["draft_hash"],
        trusted_now=trusted_now,
        expected_consumption_root=None,
    )
    if plan.get("approval_id") != content_hash(safe_event):
        raise ExecutionError("ExecutionPlan approval_id is not self-consistent")
    for field in (
        "profile_hash",
        "workflow_fingerprint",
        "capability_report_hash",
        "source_api_graph_hash",
        "executable_api_graph_hash",
    ):
        if not isinstance(plan[field], str) or not _SHA256_RE.fullmatch(plan[field]):
            raise ExecutionError("ExecutionPlan lineage hashes must be lowercase SHA-256 digests")
    expected_preflight = _derived_preflight(
        plan["workflow_fingerprint"],
        plan["source_api_graph_hash"],
        plan["executable_api_graph_hash"],
        plan["capability_report_hash"],
        plan["profile_hash"],
        expected_slots,
    )
    if stage == _MULTIVIEW_STAGE:
        for field in ("upstream_record_hash", "source_artifact_hash"):
            if not isinstance(plan[field], str) or not _SHA256_RE.fullmatch(plan[field]):
                raise ExecutionError("ExecutionPlan upstream hashes must be lowercase SHA-256 digests")
        expected_preflight["upstream"] = {
            "verified": True,
            "record_hash": plan["upstream_record_hash"],
            "artifact_hash": plan["source_artifact_hash"],
            "lineage_id": plan["lineage_id"],
        }
    elif not isinstance(plan.get("prompt_build_id"), str) or not _SHA256_RE.fullmatch(plan["prompt_build_id"]):
        raise ExecutionError("ExecutionPlan prompt_build_id must be a lowercase SHA-256 digest")
    if plan.get("preflight") != expected_preflight:
        raise ExecutionError("ExecutionPlan preflight lineage is not self-consistent")
    unsigned = dict(plan)
    claimed_hash = unsigned.pop("plan_hash")
    if not isinstance(claimed_hash, str) or claimed_hash != content_hash(unsigned):
        raise ExecutionError("ExecutionPlan plan_hash is not self-consistent")
    return copy.deepcopy(plan)


def build_approval_consumption(approved_plan: dict, enqueue_request_id: str) -> dict:
    """Consume a fresh approved plan for one stable enqueue request."""
    trusted_now = _utc_now()
    safe_plan = _validate_approved_plan(approved_plan, trusted_now=trusted_now)
    if (
        not isinstance(enqueue_request_id, str)
        or not enqueue_request_id.strip()
        or len(enqueue_request_id) > 256
    ):
        raise ExecutionError("enqueue request id must be a non-empty string up to 256 characters")
    record = {
        "schema_version": "1.0",
        "approval_id": safe_plan["approval_id"],
        "plan_hash": safe_plan["plan_hash"],
        "draft_hash": safe_plan["draft_hash"],
        "consumption_root": safe_plan["approval_event"]["consumption_root"],
        "enqueue_request_id": enqueue_request_id,
        "consumed_at": trusted_now.isoformat().replace("+00:00", "Z"),
    }
    record["consumption_id"] = content_hash(record)
    return record


def _validated_hashes(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ExecutionError(f"{label} hashes must be an object")
    result: dict[str, str] = {}
    for name, digest in value.items():
        if not isinstance(name, str) or not name:
            raise ExecutionError(f"{label} hash names must be non-empty strings")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise ExecutionError(f"{label} hashes must be lowercase SHA-256 digests")
        result[name] = digest
    return result


def _validate_plan_lineage(plan: object, prompt_build: dict, api_graph: dict) -> None:
    plan = _validate_approved_plan(plan, trusted_now=None)
    if plan["prompt_build_id"] != content_hash(prompt_build):
        raise ExecutionError("ExecutionPlan prompt_build_id does not match PromptBuild")
    if plan["source_api_graph_hash"] != content_hash(api_graph):
        raise ExecutionError("ExecutionPlan source_api_graph_hash does not match API graph")
    if plan.get("patches") != _character_base_patches(prompt_build):
        raise ExecutionError("ExecutionPlan exact four patches do not match PromptBuild")
    from .adapters.camera import patch_character_base

    patched_graph = patch_character_base(api_graph, prompt_build, _CHARACTER_BASE_SLOTS)
    if plan["executable_api_graph_hash"] != content_hash(patched_graph):
        raise ExecutionError("ExecutionPlan executable_api_graph_hash does not match patched graph")


def _history_outputs(outputs: object) -> list[dict]:
    if not isinstance(outputs, dict):
        raise ExecutionError("raw ComfyUI history outputs must be an object")
    descriptors: list[dict] = []
    for node_id, node_outputs in outputs.items():
        if not isinstance(node_id, str) or not isinstance(node_outputs, dict):
            raise ExecutionError("raw ComfyUI history output entries are invalid")
        images = node_outputs.get("images", [])
        if not isinstance(images, list):
            raise ExecutionError("raw ComfyUI history images must be a list")
        for image in images:
            if not isinstance(image, dict):
                raise ExecutionError("raw ComfyUI history image descriptors must be objects")
            filename = image.get("filename")
            subfolder = image.get("subfolder")
            output_type = image.get("type")
            if not isinstance(filename, str) or not filename:
                raise ExecutionError("raw ComfyUI history image filename is required")
            if not isinstance(subfolder, str) or not isinstance(output_type, str):
                raise ExecutionError("raw ComfyUI history image location is invalid")
            descriptors.append(
                {
                    "node_id": node_id,
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": output_type,
                }
            )
    filenames = [item["filename"] for item in descriptors]
    if len(filenames) != len(set(filenames)):
        raise ExecutionError("raw ComfyUI history output filenames are ambiguous")
    return descriptors


def _parse_history(
    history: object,
    prompt_id: str,
    terminal_status: str,
    executable_api_graph: dict,
) -> tuple[dict, list[dict]]:
    if not isinstance(history, dict) or not isinstance(history.get(prompt_id), dict):
        raise ExecutionError("raw ComfyUI history is missing the prompt_id entry")
    entry = history[prompt_id]
    prompt = entry.get("prompt")
    if not isinstance(prompt, list) or len(prompt) < 3 or prompt[1] != prompt_id:
        raise ExecutionError("raw ComfyUI history prompt tuple is invalid")
    try:
        graph_matches = canonical_json(prompt[2]) == canonical_json(executable_api_graph)
    except (TypeError, ValueError) as exc:
        raise ExecutionError(f"raw ComfyUI history prompt graph is invalid: {exc}") from exc
    if not graph_matches:
        raise ExecutionError("raw ComfyUI history prompt graph does not match executable API graph")

    status = entry.get("status")
    if not isinstance(status, dict):
        raise ExecutionError("raw ComfyUI history status is missing")
    status_str = status.get("status_str")
    completed = status.get("completed")
    expected_status = {
        "succeeded": ("success", True),
        "failed": ("error", False),
    }[terminal_status]
    if (status_str, completed) != expected_status:
        raise ExecutionError("raw ComfyUI history status does not match terminal status")

    descriptors = _history_outputs(entry.get("outputs"))
    if terminal_status == "succeeded" and not descriptors:
        raise ExecutionError("successful raw ComfyUI history requires image outputs")
    return {"status_str": status_str, "completed": completed}, descriptors


def build_run_record(
    task_context: dict,
    prompt_build: dict,
    api_graph: dict,
    execution_plan: dict,
    prompt_id: str,
    terminal_status: str,
    input_hashes: dict,
    output_hashes: dict,
    *,
    history: dict,
) -> dict:
    """Record only terminal history; artifact bytes are verified by a later layer."""
    try:
        safe_context = validate_task_context(task_context)
    except ContractError as exc:
        raise ExecutionError(f"invalid TaskContext: {exc}") from exc
    if not isinstance(prompt_build, dict) or not isinstance(prompt_build.get("execution"), dict):
        raise ExecutionError("RunRecord requires a PromptBuild execution object")
    if prompt_build["execution"].get("performed") is not False:
        raise ExecutionError("PromptBuild execution.performed must remain false")
    _validate_plan_lineage(execution_plan, prompt_build, api_graph)

    if not isinstance(prompt_id, str) or not prompt_id:
        raise ExecutionError("prompt_id is required for a terminal RunRecord")
    if terminal_status not in _TERMINAL_STATUSES:
        raise ExecutionError(
            "cancelled cannot be proven from ComfyUI history; terminal status must be succeeded or failed"
        )
    safe_inputs = _validated_hashes(input_hashes, "input")
    safe_outputs = _validated_hashes(output_hashes, "output")
    if terminal_status == "succeeded" and not safe_outputs:
        raise ExecutionError("succeeded RunRecord requires output hashes")
    from .adapters.camera import patch_character_base

    executable_graph = patch_character_base(
        api_graph, prompt_build, _CHARACTER_BASE_SLOTS
    )
    history_status, history_outputs = _parse_history(
        history, prompt_id, terminal_status, executable_graph
    )
    history_filenames = {item["filename"] for item in history_outputs}
    if set(safe_outputs) != history_filenames:
        raise ExecutionError("output hash filename keys must match raw ComfyUI history")

    record = {
        "schema_version": "1.0",
        "task_context_hash": content_hash(safe_context),
        "prompt_build_hash": content_hash(prompt_build),
        "prompt_build": copy.deepcopy(prompt_build),
        "source_api_graph_hash": execution_plan["source_api_graph_hash"],
        "executable_api_graph_hash": execution_plan["executable_api_graph_hash"],
        "execution_plan_hash": content_hash(execution_plan),
        "execution_plan": copy.deepcopy(execution_plan),
        "prompt_id": prompt_id,
        "terminal_status": terminal_status,
        "history_status": history_status,
        "history_outputs": history_outputs,
        "history_verified": True,
        "artifact_hashes_verified": False,
        "input_hashes": safe_inputs,
        "output_hashes": safe_outputs,
    }
    record["record_hash"] = content_hash(record)
    return record


def build_multiview_run_record(
    task_context: dict,
    stage1_record: dict,
    base_artifact: dict,
    api_graph: dict,
    execution_plan: dict,
    profile: dict,
    prompt_id: str,
    terminal_status: str,
    output_hashes: dict,
    *,
    history: dict,
) -> dict:
    """Retain Stage 2 executable history and normalized artifact lineage."""
    try:
        safe_context = validate_task_context(task_context)
    except ContractError as exc:
        raise ExecutionError(f"invalid TaskContext: {exc}") from exc
    safe_stage1, safe_artifact = _validated_stage1_source(stage1_record, base_artifact)
    safe_plan = _validate_approved_plan(execution_plan, trusted_now=None)
    if safe_plan["stage"] != _MULTIVIEW_STAGE:
        raise ExecutionError("Stage 2 RunRecord requires a character-multiview plan")
    if safe_plan["upstream_record_hash"] != safe_stage1["record_hash"]:
        raise ExecutionError("Stage 2 plan does not match the Stage 1 RunRecord")
    if safe_plan["source_artifact_hash"] != safe_artifact["content_hash"]:
        raise ExecutionError("Stage 2 plan does not match the CharacterBaseImage")
    if safe_plan["lineage_id"] != safe_artifact["lineage_id"]:
        raise ExecutionError("Stage 2 plan lineage_id does not match the CharacterBaseImage")
    _validate_multiview_profile(profile, safe_plan["workflow_profile_id"])
    if content_hash(profile) != safe_plan["profile_hash"]:
        raise ExecutionError("Stage 2 plan profile_hash does not match profile")
    if content_hash(api_graph) != safe_plan["source_api_graph_hash"]:
        raise ExecutionError("Stage 2 plan source graph does not match API graph")

    from .adapters.flux_multiview import FluxAdapterError, patch_base_images
    try:
        executable = patch_base_images(api_graph, safe_plan["uploaded_filename"], _MULTIVIEW_SLOTS)
    except FluxAdapterError as exc:
        raise ExecutionError(f"Stage 2 API graph is invalid: {exc}") from exc
    if content_hash(executable) != safe_plan["executable_api_graph_hash"]:
        raise ExecutionError("Stage 2 executable graph does not match approved plan")
    if safe_plan["patches"] != _multiview_patches(
        safe_plan["uploaded_filename"], safe_artifact["content_hash"]
    ):
        raise ExecutionError("Stage 2 exact dual patches do not match source artifact")

    if not isinstance(prompt_id, str) or not prompt_id:
        raise ExecutionError("prompt_id is required for a terminal Stage 2 RunRecord")
    if terminal_status not in _TERMINAL_STATUSES:
        raise ExecutionError("Stage 2 terminal status must be succeeded or failed")
    safe_outputs = _validated_hashes(output_hashes, "output")
    history_status, history_outputs = _parse_history(
        history, prompt_id, terminal_status, executable
    )
    history_filenames = {item["filename"] for item in history_outputs}
    if set(safe_outputs) != history_filenames:
        raise ExecutionError("output hash filename keys must match raw ComfyUI history")

    entry_outputs = history[prompt_id]["outputs"]
    from .artifacts import ArtifactNormalizationError, normalize_image_outputs
    try:
        artifacts = normalize_image_outputs(
            entry_outputs,
            profile.get("output_nodes"),
            safe_artifact["lineage_id"],
            safe_artifact["content_hash"],
        )
    except ArtifactNormalizationError as exc:
        raise ExecutionError(f"Stage 2 artifact normalization failed: {exc}") from exc
    if terminal_status == "succeeded" and not artifacts:
        raise ExecutionError("successful Stage 2 history requires normalized image artifacts")
    for artifact in artifacts:
        artifact["content_hash"] = safe_outputs[artifact["filename"]]

    record = {
        "schema_version": "1.0",
        "stage": _MULTIVIEW_STAGE,
        "task_context_hash": content_hash(safe_context),
        "upstream_record_hash": safe_stage1["record_hash"],
        "source_artifact_hash": safe_artifact["content_hash"],
        "lineage_id": safe_artifact["lineage_id"],
        "source_api_graph_hash": safe_plan["source_api_graph_hash"],
        "executable_api_graph_hash": safe_plan["executable_api_graph_hash"],
        "execution_plan_hash": content_hash(safe_plan),
        "execution_plan": copy.deepcopy(safe_plan),
        "prompt_id": prompt_id,
        "terminal_status": terminal_status,
        "history_status": history_status,
        "history_outputs": history_outputs,
        "raw_history": copy.deepcopy(history),
        "raw_history_hash": content_hash(history),
        "history_verified": True,
        "artifact_hashes_verified": False,
        "output_hashes": safe_outputs,
        "artifacts": artifacts,
    }
    record["record_hash"] = content_hash(record)
    return record
