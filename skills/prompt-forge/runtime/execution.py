"""Fail-closed execution plans and immutable runtime provenance records."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .capabilities import report_is_fresh
from .contracts import ContractError, canonical_json, content_hash, validate_task_context
from .multiview_evidence import (
    FINGERPRINT as _MULTIVIEW_FINGERPRINT,
    OUTPUTS as _MULTIVIEW_OUTPUTS,
    POSE_IDS as _MULTIVIEW_POSE_IDS,
    PROMOTION_RECEIPT_HASH as _MULTIVIEW_PROMOTION_RECEIPT_HASH,
    PROFILE_ID as _MULTIVIEW_PROFILE_ID,
    SOURCE_API_GRAPH_HASH as _MULTIVIEW_SOURCE_API_GRAPH_HASH,
    SLOTS as _MULTIVIEW_SLOTS,
    MultiviewEvidenceError,
    immutable_inputs as _evidence_immutable_inputs,
    upload_name as _evidence_upload_name,
    validate_mcp_preflight as _evidence_validate_mcp_preflight,
    validate_png_file as _evidence_validate_png_file,
    validate_profile as _evidence_validate_profile,
    validate_upload_receipt as _evidence_validate_upload_receipt,
)
from .prompt_quality import validate_anima_prompt_build
from .workflow_profile import ProfileError, resolve_slots, structure_fingerprint


class ExecutionError(ValueError):
    """Raised when execution evidence does not satisfy the runtime boundary."""


def _handoff_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ExecutionError(f"{label} must be a lowercase SHA-256 digest")
    return value


def validate_stage_handoff(stage_plan: object, artifact: object) -> dict:
    """Validate the exact accepted upstream artifact before any enqueue work."""
    if not isinstance(stage_plan, dict):
        raise ExecutionError("stage handoff requires a stage plan")
    if not isinstance(artifact, dict):
        raise ExecutionError("stage handoff requires an artifact")
    stage = stage_plan.get("stage")
    if stage not in {"shot-image", "video"}:
        raise ExecutionError("stage handoff target is unsupported")
    if artifact.get("accepted") is not True:
        raise ExecutionError("stage handoff artifact must be accepted")

    if stage == "shot-image":
        expected_hash = _handoff_sha256(
            stage_plan.get("reference_hash"), "stage plan reference_hash"
        )
        artifact_hash = _handoff_sha256(
            artifact.get("content_hash"), "stage handoff artifact content_hash"
        )
        if artifact.get("artifact_type") != "CharacterAngleView":
            raise ExecutionError("stage handoff artifact_type must be CharacterAngleView")
        if (
            artifact.get("reference_eligible") is not True
            or artifact.get("semantic_conflict") is not False
            or artifact.get("hash_verified") is not True
        ):
            raise ExecutionError("stage handoff CharacterAngleView is not reference eligible")
        view_label = artifact.get("view_label")
        proof = artifact.get("orientation_proof")
        if (
            not isinstance(view_label, str)
            or not view_label.strip()
            or not isinstance(proof, dict)
            or proof.get("schema_version") != "1.0"
            or proof.get("verified") is not True
            or not isinstance(proof.get("expected_view"), str)
            or not proof["expected_view"].strip()
            or proof.get("observed_view") != proof.get("expected_view")
            or not isinstance(proof.get("source"), str)
            or not proof["source"].strip()
        ):
            raise ExecutionError("stage handoff CharacterAngleView orientation proof is invalid")
        canonical_label = {
            "front_closeup": "front",
            "front_upper": "front",
        }.get(view_label.strip().casefold(), view_label.strip().casefold())
        if canonical_label != proof["observed_view"].strip().casefold():
            raise ExecutionError("stage handoff orientation proof conflicts with view_label")
    else:
        from .artifacts import is_ltx_input_eligible

        expected_hash = _handoff_sha256(
            stage_plan.get("source_shot_hash"), "stage plan source_shot_hash"
        )
        artifact_hash = _handoff_sha256(
            artifact.get("content_hash"), "stage handoff artifact content_hash"
        )
        if not is_ltx_input_eligible(artifact):
            raise ExecutionError("stage handoff requires an accepted ShotImage")
        expected_type = stage_plan.get("source_shot_artifact_type")
        if expected_type is not None and artifact.get("artifact_type") != expected_type:
            raise ExecutionError("stage handoff artifact_type does not match the video plan")
        expected_parent = stage_plan.get("parent_shot_hash")
        if expected_parent is not None and artifact.get("parent_artifact_hash") != expected_parent:
            raise ExecutionError("stage handoff parent_artifact_hash does not match the video plan")
        expected_source = stage_plan.get("source_artifact_hash")
        if expected_source is not None and artifact.get("source_artifact_hash") != expected_source:
            raise ExecutionError("stage handoff source_artifact_hash does not match the video plan")

    if artifact_hash != expected_hash:
        raise ExecutionError("stage handoff content_hash does not match the stage plan")
    for field in (
        "task_context_hash",
        "source_story_hash",
        "art_bible_hash",
        "lineage_id",
    ):
        expected = stage_plan.get(field)
        if expected is not None and artifact.get(field) != expected:
            raise ExecutionError(f"stage handoff {field} does not match the stage plan")
    return copy.deepcopy(artifact)


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
_VIEW_SELECTION_FINGERPRINT = "9dc2b01e2aea0b051113b187b134d007f452df6c83cfcbbd8d325eaa4c29e4da"
_VIEW_SELECTION_SOURCE_API_GRAPH_HASH = "450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36"
_VIEW_SELECTION_PROFILE_HASH = "d225a4be9a9fb9e41cb4c823ebf824d500e5b30f016c9c6c00d5728162f9ebda"
_VIEW_SELECTION_PROFILE_PATH = Path(__file__).parent / "profiles" / "flux2-klein-view-selection.json"
_PATCH_KEYS = frozenset(("slot", "input", "value"))
_TERMINAL_STATUSES = frozenset(("succeeded", "failed"))
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STAGE1_RUN_RECORD_KEYS = frozenset(
    (
        "schema_version",
        "task_context_hash",
        "prompt_build_hash",
        "prompt_build",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "execution_plan_hash",
        "execution_plan",
        "prompt_id",
        "terminal_status",
        "history_status",
        "history_outputs",
        "artifact_descriptor",
        "history_verified",
        "artifact_hashes_verified",
        "input_hashes",
        "output_hashes",
        "record_hash",
    )
)
_STAGE1_RUN_RECORD_EVIDENCE_KEYS = _STAGE1_RUN_RECORD_KEYS.union(
    {
        "approval_consumption",
        "consumption_path",
        "submission",
        "submission_hash",
        "enqueue_receipt",
        "enqueue_receipt_hash",
        "enqueue_receipt_path",
        "raw_history",
        "raw_history_hash",
    }
)
_STAGE1_RUN_RECORD_ARTIFACT_KEYS = _STAGE1_RUN_RECORD_KEYS.union(
    {"artifact_root", "artifact_path"}
)
_STAGE1_RUN_RECORD_EVIDENCE_ARTIFACT_KEYS = _STAGE1_RUN_RECORD_EVIDENCE_KEYS.union(
    {"artifact_root", "artifact_path"}
)
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
        "stage1_artifact_descriptor",
        "lineage_id",
        "uploaded_filename",
        "capability_report_hash",
        "workflow_profile_id",
        "profile_hash",
        "promotion_receipt_hash",
        "promotion_receipt",
        "conversion_receipt_hash",
        "conversion_receipt",
        "upload_receipt_hash",
        "saved_workflow_id",
        "workflow_fingerprint",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "view_selection_profile_hash",
        "view_plan_hash",
        "view_plan",
        "requested_views",
        "output_map",
        "switch_patch",
        "orientation_evidence",
        "patches",
        "immutable_inputs",
        "local_only",
        "preflight",
        "expected_outputs",
        "execution_approved",
        "draft_hash",
    )
)
_CHARACTER_BASE_SUBMISSION_KEYS = frozenset(
    (
        "schema_version",
        "stage",
        "submission_type",
        "plan_hash",
        "draft_hash",
        "approval_id",
        "consumption_id",
        "consumption_root",
        "enqueue_request_id",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "workflow_fingerprint",
        "api_graph",
        "request",
        "submission_hash",
    )
)
_CHARACTER_BASE_INTENT_KEYS = frozenset(
    (
        "schema_version",
        "intent_type",
        "status",
        "stage",
        "consumption_id",
        "enqueue_request_id",
        "submission_hash",
        "submitted_graph_hash",
        "request",
        "intent_hash",
    )
)
_CHARACTER_BASE_RECEIPT_KEYS = frozenset(
    (
        "schema_version",
        "receipt_type",
        "stage",
        "status",
        "plan_hash",
        "consumption_id",
        "submission_hash",
        "prompt_id",
        "enqueue_request_id",
        "submitted_graph_hash",
        "request",
        "response",
        "response_digest",
        "orchestrator",
        "receipt_hash",
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
_APPROVAL_CONSUMPTION_KEYS = frozenset(
    (
        "schema_version",
        "approval_id",
        "plan_hash",
        "draft_hash",
        "consumption_root",
        "enqueue_request_id",
        "consumed_at",
        "consumption_id",
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
    if profile.get("board_role") is not None:
        raise ExecutionError(
            "asset-board profiles are prompt-only and cannot use character-base execution"
        )
    selected_profile_id = profile.get("profile_id")
    alias_is_valid = (
        selected_profile_id == "camera-anima-base-v1"
        and profile.get("source_profile_id") == _CHARACTER_BASE_PROFILE_ID
        and profile.get("execution_profile_id") == _CHARACTER_BASE_PROFILE_ID
    )
    if (
        profile_id != _CHARACTER_BASE_PROFILE_ID
        or (selected_profile_id != profile_id and not alias_is_valid)
    ):
        raise ExecutionError("character-base requires profile camera-anima-v1")
    if alias_is_valid and (
        profile.get("enabled_groups") != []
        or profile.get("enabled_optional_branches") != []
        or profile.get("expected_artifact_type") != "CharacterBaseImage"
    ):
        raise ExecutionError("character-base alias must remain a clean base profile")
    if profile.get("runtime_classification") != "local":
        raise ExecutionError("character-base profile must be local")
    if profile.get("expected_outputs") != _CHARACTER_BASE_OUTPUTS:
        raise ExecutionError("character-base profile must expect only image/png")
    from .adapters.camera import is_pinned_camera_normalization_profile, is_pinned_camera_profile

    if not is_pinned_camera_normalization_profile(profile):
        raise ExecutionError("character-base profile must carry the pinned camera normalization contract")
    profile_fingerprint = profile.get("workflow_fingerprint")
    if not isinstance(profile_fingerprint, str) or not _SHA256_RE.fullmatch(profile_fingerprint):
        raise ExecutionError("character-base profile must carry a verified workflow fingerprint")
    slots = profile.get("slots")
    if not isinstance(slots, dict):
        raise ExecutionError("character-base profile requires slots")
    for slot_name, node_id in _CHARACTER_BASE_SLOTS.items():
        selector = slots.get(slot_name)
        if selector != _CHARACTER_BASE_SELECTORS[slot_name]:
            raise ExecutionError(
                f"character-base profile slot '{slot_name}' must be the fixed node {node_id} selector"
            )
    if not is_pinned_camera_profile(profile):
        raise ExecutionError("character-base profile is not the complete verified camera contract")


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


def _require_workflow_candidate(report: object, profile_id: str) -> None:
    candidates = report.get("workflow_candidates") if isinstance(report, dict) else None
    if not isinstance(candidates, list):
        raise ExecutionError("CapabilityReport workflow candidates are required")
    matches = [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("profile_id") == profile_id
    ]
    if len(matches) != 1:
        raise ExecutionError(
            f"CapabilityReport workflow candidate is missing or ambiguous for {profile_id}"
        )
    candidate = matches[0]
    if candidate.get("production") is not True:
        raise ExecutionError(f"workflow candidate {profile_id} is not production")
    allowed = {"ready"}
    if profile_id == _CHARACTER_BASE_PROFILE_ID:
        allowed.add("needs-normalization")
    if candidate.get("status") not in allowed:
        raise ExecutionError(
            f"workflow candidate {profile_id} is not executable: {candidate.get('status')!r}"
        )
    if candidate.get("status") == "ready" and candidate.get("production_ready") is not True:
        raise ExecutionError(f"workflow candidate {profile_id} is not production-ready")


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
    _require_workflow_candidate(capability_report, workflow_profile_id)
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
    if profile.get("workflow_fingerprint") != actual_fingerprint:
        raise ExecutionError("workflow fingerprint does not match the verified camera profile")
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
    from .adapters.camera import CameraAdapterError, normalize_camera_api_graph, patch_character_base

    try:
        normalized_source = normalize_camera_api_graph(api_graph, actual_ui_workflow, profile)
    except CameraAdapterError as exc:
        raise ExecutionError(f"camera source normalization failed: {exc}") from exc
    if normalized_source != api_graph:
        raise ExecutionError(
            "camera source API graph must be normalized with normalize-camera before planning"
        )

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


def _validate_png_file(path: Path) -> None:
    try:
        _evidence_validate_png_file(path)
    except MultiviewEvidenceError as exc:
        raise ExecutionError(str(exc)) from exc


def _validate_approval_consumption_evidence(
    approved_plan: dict,
    value: object,
    path_value: object,
) -> dict:
    if not isinstance(value, dict) or set(value) != _APPROVAL_CONSUMPTION_KEYS:
        raise ExecutionError("approval consumption evidence schema is invalid")
    unsigned = dict(value)
    claimed_id = unsigned.pop("consumption_id", None)
    if not isinstance(claimed_id, str) or claimed_id != content_hash(unsigned):
        raise ExecutionError("approval consumption evidence hash is invalid")
    for field in ("approval_id", "plan_hash", "draft_hash"):
        if value.get(field) != approved_plan.get(field):
            raise ExecutionError(f"approval consumption {field} does not match approved plan")
    if value.get("consumption_root") != approved_plan["approval_event"]["consumption_root"]:
        raise ExecutionError("approval consumption root does not match approved plan")
    request_id = value.get("enqueue_request_id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 256:
        raise ExecutionError("approval consumption enqueue request id is invalid")
    consumed_at = _parse_utc_timestamp(value.get("consumed_at"), "consumed_at")
    approved_at = _parse_utc_timestamp(approved_plan["approval_event"]["approved_at"], "approved_at")
    expires_at = _parse_utc_timestamp(approved_plan["approval_event"]["expires_at"], "expires_at")
    if not approved_at <= consumed_at < expires_at:
        raise ExecutionError("approval consumption timestamp is outside the approval window")

    root = Path(_canonical_consumption_root(value["consumption_root"], "approval consumption"))
    if not isinstance(path_value, (str, Path)):
        raise ExecutionError("approval consumption evidence path is required")
    raw_path = Path(path_value)
    try:
        resolved_path = raw_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExecutionError("approval consumption evidence file must exist") from exc
    expected_path = root / f'{approved_plan["approval_id"]}.consumed.json'
    if str(raw_path) != str(resolved_path) or resolved_path != expected_path:
        raise ExecutionError("approval consumption evidence path is not canonical for this approval")
    try:
        retained = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionError("approval consumption evidence file is invalid JSON") from exc
    if canonical_json(retained) != canonical_json(value):
        raise ExecutionError("approval consumption evidence file does not match supplied evidence")
    return copy.deepcopy(value)


def _validated_stage1_source(
    stage1_record: object,
    base_artifact: object,
    *,
    stage1_api_graph: object,
    stage1_history: object,
    stage1_approval_consumption: object,
    stage1_consumption_path: object,
) -> tuple[dict, dict]:
    if not isinstance(stage1_record, dict) or stage1_record.get("schema_version") != "1.0":
        raise ExecutionError("an accepted Stage 1 RunRecord is required")
    record_keys = set(stage1_record)
    valid_record_keys = {
        _STAGE1_RUN_RECORD_KEYS,
        _STAGE1_RUN_RECORD_EVIDENCE_KEYS,
        _STAGE1_RUN_RECORD_ARTIFACT_KEYS,
        _STAGE1_RUN_RECORD_EVIDENCE_ARTIFACT_KEYS,
    }
    if record_keys not in valid_record_keys:
        raise ExecutionError("a complete Stage 1 RunRecord is required")
    record_hash = stage1_record.get("record_hash")
    unsigned_record = dict(stage1_record)
    unsigned_record.pop("record_hash", None)
    if not isinstance(record_hash, str) or not _SHA256_RE.fullmatch(record_hash):
        raise ExecutionError("Stage 1 RunRecord record_hash must be a lowercase SHA-256 digest")
    if record_hash != content_hash(unsigned_record):
        raise ExecutionError("Stage 1 RunRecord record_hash is not self-consistent")
    if record_keys in {
        _STAGE1_RUN_RECORD_EVIDENCE_KEYS,
        _STAGE1_RUN_RECORD_EVIDENCE_ARTIFACT_KEYS,
    }:
        raw_history = stage1_record.get("raw_history")
        if not isinstance(raw_history, dict) or stage1_record.get("raw_history_hash") != content_hash(raw_history):
            raise ExecutionError("Stage 1 RunRecord raw history evidence is invalid")
        if canonical_json(raw_history) != canonical_json(stage1_history):
            raise ExecutionError("Stage 1 RunRecord raw history does not match supplied history")
        submission = stage1_record.get("submission")
        if not isinstance(submission, dict):
            raise ExecutionError("Stage 1 RunRecord submission evidence is invalid")
        unsigned_submission = dict(submission)
        claimed_submission_hash = unsigned_submission.pop("submission_hash", None)
        if (
            stage1_record.get("submission_hash") != claimed_submission_hash
            or not isinstance(claimed_submission_hash, str)
            or claimed_submission_hash != content_hash(unsigned_submission)
        ):
            raise ExecutionError("Stage 1 RunRecord submission evidence is invalid")
        enqueue_receipt = stage1_record.get("enqueue_receipt")
        if not isinstance(enqueue_receipt, dict):
            raise ExecutionError("Stage 1 RunRecord receipt evidence is invalid")
        unsigned_receipt = dict(enqueue_receipt)
        claimed_receipt_hash = unsigned_receipt.pop("receipt_hash", None)
        if (
            stage1_record.get("enqueue_receipt_hash") != claimed_receipt_hash
            or not isinstance(claimed_receipt_hash, str)
            or claimed_receipt_hash != content_hash(unsigned_receipt)
        ):
            raise ExecutionError("Stage 1 RunRecord receipt evidence is invalid")
    if stage1_record.get("terminal_status") != "succeeded" or stage1_record.get("history_verified") is not True:
        raise ExecutionError("Stage 1 RunRecord must be a verified successful run")
    source_plan = stage1_record.get("execution_plan")
    if not isinstance(source_plan, dict) or source_plan.get("stage") != "character-base":
        raise ExecutionError("Stage 1 RunRecord must describe character-base")
    if source_plan.get("workflow_profile_id") != _CHARACTER_BASE_PROFILE_ID:
        raise ExecutionError("Stage 1 RunRecord profile lineage is invalid")

    if not isinstance(base_artifact, dict) or base_artifact.get("schema_version") != "1.0":
        raise ExecutionError("a versioned CharacterBaseImage artifact is required")
    if set(base_artifact) != {
        "schema_version",
        "artifact_type",
        "accepted",
        "content_hash",
        "lineage_id",
        "source_record_hash",
        "artifact_path",
        "artifact_root",
        "visual_acceptance",
    }:
        raise ExecutionError("CharacterBaseImage artifact descriptor schema is invalid")
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
    if set(visual) != {"front_facing", "identity_visible"}:
        raise ExecutionError("CharacterBaseImage visual acceptance schema is invalid")

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
    _validate_png_file(resolved_path)
    output_hashes = stage1_record.get("output_hashes")
    if not isinstance(output_hashes, dict) or output_hashes.get(resolved_path.name) != artifact_hash:
        raise ExecutionError("CharacterBaseImage hash does not match Stage 1 RunRecord outputs")

    source_plan = _validate_approved_plan(stage1_record.get("execution_plan"), trusted_now=None)
    if source_plan["stage"] != "character-base" or source_plan["workflow_profile_id"] != _CHARACTER_BASE_PROFILE_ID:
        raise ExecutionError("Stage 1 RunRecord must contain an approved character-base plan")
    if stage1_record.get("execution_plan_hash") != content_hash(source_plan):
        raise ExecutionError("Stage 1 execution_plan_hash is invalid")
    prompt_build = stage1_record.get("prompt_build")
    if not isinstance(prompt_build, dict) or stage1_record.get("prompt_build_hash") != content_hash(prompt_build):
        raise ExecutionError("Stage 1 PromptBuild lineage is invalid")
    if not isinstance(stage1_api_graph, dict):
        raise ExecutionError("Stage 1 source API graph evidence is required")
    _validate_plan_lineage(source_plan, prompt_build, stage1_api_graph)
    if stage1_record.get("source_api_graph_hash") != content_hash(stage1_api_graph):
        raise ExecutionError("Stage 1 source API graph hash is invalid")
    if stage1_record.get("executable_api_graph_hash") != source_plan["executable_api_graph_hash"]:
        raise ExecutionError("Stage 1 executable API graph hash is invalid")
    if not isinstance(stage1_record.get("task_context_hash"), str) or not _SHA256_RE.fullmatch(stage1_record["task_context_hash"]):
        raise ExecutionError("Stage 1 task_context_hash is invalid")
    artifact_evidence = record_keys in {
        _STAGE1_RUN_RECORD_ARTIFACT_KEYS,
        _STAGE1_RUN_RECORD_EVIDENCE_ARTIFACT_KEYS,
    }
    if artifact_evidence:
        root_text = stage1_record.get("artifact_root")
        path_text = stage1_record.get("artifact_path")
        if not isinstance(root_text, str) or not isinstance(path_text, str):
            raise ExecutionError("Stage 1 artifact path/root evidence is incomplete")
        try:
            record_root = Path(root_text).resolve(strict=True)
            record_path = Path(path_text).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ExecutionError("Stage 1 artifact path/root evidence is missing") from exc
        if (
            str(Path(root_text)) != str(record_root)
            or str(Path(path_text)) != str(record_path)
            or not record_root.is_dir()
            or not record_path.is_file()
            or not record_path.is_relative_to(record_root)
        ):
            raise ExecutionError("Stage 1 artifact path/root evidence is not canonical")
        if stage1_record.get("artifact_hashes_verified") is not True:
            raise ExecutionError("Stage 1 artifact verification flag is invalid")
    elif stage1_record.get("artifact_hashes_verified") is not False:
        raise ExecutionError("Stage 1 artifact verification flag must remain false until bytes are checked")
    _validated_hashes(stage1_record.get("input_hashes"), "Stage 1 input")
    safe_record_outputs = _validated_hashes(stage1_record.get("output_hashes"), "Stage 1 output")
    if not isinstance(stage1_record.get("prompt_id"), str) or not stage1_record["prompt_id"]:
        raise ExecutionError("Stage 1 prompt_id is invalid")
    if stage1_record.get("terminal_status") != "succeeded":
        raise ExecutionError("Stage 1 RunRecord must be a successful terminal run")
    from .adapters.camera import patch_character_base

    history_status, history_outputs = _parse_history(
        stage1_history,
        stage1_record.get("prompt_id"),
        stage1_record.get("terminal_status"),
        patch_character_base(stage1_api_graph, prompt_build, _CHARACTER_BASE_SLOTS),
    )
    if stage1_record.get("history_status") != history_status or not _history_outputs_equal(
        stage1_record.get("history_outputs"), history_outputs
    ):
        raise ExecutionError("Stage 1 raw history does not match RunRecord")
    if set(safe_record_outputs) != {item["filename"] for item in history_outputs}:
        raise ExecutionError("Stage 1 output hashes do not match raw history")
    selected_descriptor = stage1_record.get("artifact_descriptor")
    if (
        not isinstance(selected_descriptor, dict)
        or set(selected_descriptor) != {"node_id", "filename", "subfolder", "type"}
        or selected_descriptor not in history_outputs
        or selected_descriptor.get("type") != "output"
    ):
        raise ExecutionError("Stage 1 artifact history descriptor is invalid")
    descriptor_path = resolved_root / selected_descriptor["subfolder"] / selected_descriptor["filename"]
    try:
        resolved_descriptor_path = descriptor_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExecutionError("Stage 1 artifact history descriptor path is missing") from exc
    if (
        not resolved_descriptor_path.is_file()
        or not resolved_descriptor_path.is_relative_to(resolved_root)
        or resolved_descriptor_path != resolved_path
    ):
        raise ExecutionError("Stage 1 artifact history descriptor does not match accepted artifact path")
    if artifact_evidence and (
        stage1_record.get("artifact_root") != str(resolved_root)
        or stage1_record.get("artifact_path") != str(resolved_path)
    ):
        raise ExecutionError("Stage 1 artifact path/root evidence does not match accepted artifact")
    _validate_approval_consumption_evidence(
        source_plan,
        stage1_approval_consumption,
        stage1_consumption_path,
    )
    return copy.deepcopy(stage1_record), copy.deepcopy(base_artifact)


def _validate_multiview_profile(profile: object, profile_id: object) -> None:
    try:
        _evidence_validate_profile(profile, profile_id)
    except MultiviewEvidenceError as exc:
        raise ExecutionError(str(exc)) from exc


def _load_view_selection_profile() -> dict:
    try:
        profile = json.loads(_VIEW_SELECTION_PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionError("flat-v2 view-selection profile is unreadable") from exc
    if not isinstance(profile, dict) or content_hash(profile) != _VIEW_SELECTION_PROFILE_HASH:
        raise ExecutionError("flat-v2 view-selection profile hash is outside the production pin")
    return profile


def _default_multiview_view_plan(selection_profile: dict) -> dict:
    outputs = selection_profile.get("output_nodes")
    if not isinstance(outputs, dict):
        raise ExecutionError("flat-v2 view-selection output map is invalid")
    views = [item["view_label"] for _, item in sorted(outputs.items()) if isinstance(item, dict) and isinstance(item.get("view_label"), str)]
    return {"views": views, "orientation_evidence": {view: {"source": "unresolved-output" if view == "side_unknown" else "profile-output-map", "verified": view != "side_unknown"} for view in views}}


def _bind_multiview_view_plan(view_plan: dict, selection_profile: dict) -> dict:
    """Bind the exact requested views to the pinned flat-v2 output contract."""
    from .adapters.flux_multiview import FluxAdapterError, validate_view_plan
    try:
        safe = validate_view_plan(view_plan, selection_profile)
    except FluxAdapterError as exc:
        raise ExecutionError(str(exc)) from exc
    if selection_profile.get("workflow_fingerprint") != _VIEW_SELECTION_FINGERPRINT or selection_profile.get("source_api_graph_hash") != _VIEW_SELECTION_SOURCE_API_GRAPH_HASH:
        raise ExecutionError("flat-v2 view-selection profile does not match the production graph pin")
    return {
        "view_selection_profile_hash": content_hash(selection_profile), "view_plan_hash": content_hash(view_plan),
        "view_plan": copy.deepcopy(view_plan), "requested_views": safe["views"], "output_map": safe["output_map"],
        "switch_patch": safe["switches"], "orientation_evidence": safe["orientation_evidence"],
    }


def _multiview_executable_from_plan(api_graph: dict, plan: dict) -> dict:
    selection_profile = _load_view_selection_profile()
    if content_hash(selection_profile) != plan.get("view_selection_profile_hash"):
        raise ExecutionError("Stage 2 view-selection profile does not match the approved plan")
    expected = _bind_multiview_view_plan(plan.get("view_plan"), selection_profile)
    for field in ("view_selection_profile_hash", "view_plan_hash", "view_plan", "requested_views", "output_map", "switch_patch", "orientation_evidence"):
        if plan.get(field) != expected[field]:
            raise ExecutionError(f"Stage 2 {field} is not bound to the approved view plan")
    executable_plan = copy.deepcopy(expected["view_plan"])
    executable_plan["base_image"] = plan["uploaded_filename"]
    from .adapters.flux_multiview import FluxAdapterError, patch_view_plan
    try:
        return patch_view_plan(api_graph, executable_plan, selection_profile)
    except FluxAdapterError as exc:
        raise ExecutionError(f"Stage 2 API graph is invalid: {exc}") from exc


def validate_multiview_mcp_preflight(
    *,
    conversion_receipt: object,
    capability_report: object,
    profile: object,
    actual_ui_workflow: object,
    api_graph: object,
    promotion_receipt: object = None,
    converted_api_graph: object = None,
) -> dict:
    """Bind a trusted local MCP observation to the exact saved UI/API pair."""
    try:
        return _evidence_validate_mcp_preflight(
            conversion_receipt=conversion_receipt,
            promotion_receipt=promotion_receipt,
            capability_report=capability_report,
            profile=profile,
            actual_ui_workflow=actual_ui_workflow,
            converted_api_graph=converted_api_graph,
            api_graph=api_graph,
            now=_utc_now(),
        )
    except MultiviewEvidenceError as exc:
        raise ExecutionError(str(exc)) from exc
def _multiview_upload_name(lineage_id: str, artifact_hash: str) -> str:
    return _evidence_upload_name(lineage_id, artifact_hash)


def _validate_multiview_upload_receipt(value: object, artifact: dict) -> dict:
    try:
        return _evidence_validate_upload_receipt(value, artifact)
    except MultiviewEvidenceError as exc:
        raise ExecutionError(str(exc)) from exc
def _multiview_patches(filename: str, artifact_hash: str) -> list[dict]:
    return [
        {"slot": slot, "input": "image", "value": filename, "source_hash": artifact_hash}
        for slot in ("base_image_primary", "base_image_secondary")
    ]


def _multiview_immutable_inputs(api_graph: dict, profile: dict) -> list[dict]:
    try:
        return _evidence_immutable_inputs(api_graph, profile)
    except MultiviewEvidenceError as exc:
        raise ExecutionError(str(exc)) from exc
def _build_multiview_draft_from_validated_mcp(
    *,
    stage1_record: dict,
    base_artifact: dict,
    stage1_api_graph: dict,
    stage1_history: dict,
    stage1_approval_consumption: dict,
    stage1_consumption_path: str | Path,
    workflow_profile_id: str,
    workflow_fingerprint: str,
    capability_report: dict,
    profile: dict,
    actual_ui_workflow: dict,
    converted_api_graph: dict,
    api_graph: dict,
    conversion_receipt: dict,
    promotion_receipt: dict,
    upload_receipt: dict,
    view_plan: dict | None = None,
) -> dict:
    """Pure validator/builder reached only after the controlled MCP call boundary."""
    safe_record, safe_artifact = _validated_stage1_source(
        stage1_record,
        base_artifact,
        stage1_api_graph=stage1_api_graph,
        stage1_history=stage1_history,
        stage1_approval_consumption=stage1_approval_consumption,
        stage1_consumption_path=stage1_consumption_path,
    )
    if workflow_profile_id != _MULTIVIEW_PROFILE_ID:
        raise ExecutionError("production character-multiview requires the promoted flat v2 profile")
    safe_receipt = validate_multiview_mcp_preflight(
        conversion_receipt=conversion_receipt,
        promotion_receipt=promotion_receipt,
        capability_report=capability_report,
        profile=profile,
        actual_ui_workflow=actual_ui_workflow,
        converted_api_graph=converted_api_graph,
        api_graph=api_graph,
    )
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
    safe_upload_receipt = _validate_multiview_upload_receipt(upload_receipt, safe_artifact)
    selection_profile = _load_view_selection_profile()
    selected_view_plan = _default_multiview_view_plan(selection_profile) if view_plan is None else copy.deepcopy(view_plan)
    if isinstance(selected_view_plan, dict) and selected_view_plan.get("base_image") is not None:
        raise ExecutionError("production Stage 2 owns the synchronized base-image slots")
    view_binding = _bind_multiview_view_plan(selected_view_plan, selection_profile)
    executable_view_plan = copy.deepcopy(selected_view_plan)
    executable_view_plan["base_image"] = filename
    from .adapters.flux_multiview import FluxAdapterError, patch_view_plan
    try:
        executable = patch_view_plan(api_graph, executable_view_plan, selection_profile)
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
        "artifact_descriptor": safe_record["artifact_descriptor"],
    }
    receipt_hash = content_hash(safe_receipt)
    promotion_receipt_hash = content_hash(promotion_receipt)
    upload_receipt_hash = content_hash(safe_upload_receipt)
    saved_workflow_id = safe_receipt["saved_workflow"]["workflow_id"]
    preflight["mcp_conversion"] = {
        "verified": True,
        "receipt_hash": receipt_hash,
        "saved_workflow_id": saved_workflow_id,
        "adapter": {"name": "comfyui-mcp", "version": "0.49.0"},
        "ui_fingerprint": actual_fingerprint,
        "api_graph_hash": source_hash,
    }
    preflight["promotion"] = {
        "verified": True,
        "receipt_hash": promotion_receipt_hash,
        "prompt_id": promotion_receipt["source_run"]["prompt_id"],
        "output_png_sha256": promotion_receipt["source_run"]["output_png_sha256"],
        "embedded_api_graph_hash": promotion_receipt["source_run"]["embedded_api_graph_hash"],
        "source_api_graph_hash": source_hash,
    }
    preflight["upload"] = {
        "verified": True,
        "receipt_hash": upload_receipt_hash,
        "filename": filename,
        "source_artifact_hash": safe_artifact["content_hash"],
        "server_content_hash": safe_upload_receipt["server_content_hash"],
    }
    draft = {
        "schema_version": "1.0",
        "stage": _MULTIVIEW_STAGE,
        "plan_state": "draft",
        "upstream_record_hash": safe_record["record_hash"],
        "source_artifact_hash": safe_artifact["content_hash"],
        "stage1_artifact_descriptor": copy.deepcopy(safe_record["artifact_descriptor"]),
        "lineage_id": safe_artifact["lineage_id"],
        "uploaded_filename": filename,
        "capability_report_hash": report_hash,
        "workflow_profile_id": _MULTIVIEW_PROFILE_ID,
        "profile_hash": profile_hash,
        "promotion_receipt_hash": promotion_receipt_hash,
        "promotion_receipt": copy.deepcopy(promotion_receipt),
        "conversion_receipt_hash": receipt_hash,
        "conversion_receipt": copy.deepcopy(safe_receipt),
        "upload_receipt_hash": upload_receipt_hash,
        "saved_workflow_id": saved_workflow_id,
        "workflow_fingerprint": actual_fingerprint,
        "source_api_graph_hash": source_hash,
        "executable_api_graph_hash": executable_hash,
        **view_binding,
        "patches": _multiview_patches(filename, safe_artifact["content_hash"]),
        "immutable_inputs": _multiview_immutable_inputs(api_graph, profile),
        "local_only": True,
        "preflight": preflight,
        "expected_outputs": list(_MULTIVIEW_OUTPUTS),
        "execution_approved": False,
    }
    draft["draft_hash"] = content_hash(draft)
    return draft


def _call_multiview_mcp_tool(name: str, tool, arguments: dict) -> object:
    try:
        return tool(copy.deepcopy(arguments))
    except Exception as exc:
        raise ExecutionError(f"trusted local MCP {name} call failed") from exc


def build_multiview_draft_with_mcp(
    *,
    stage1_record: dict,
    base_artifact: dict,
    stage1_api_graph: dict,
    stage1_history: dict,
    stage1_approval_consumption: dict,
    stage1_consumption_path: str | Path,
    workflow_profile_id: str,
    workflow_fingerprint: str,
    workflow_id: str,
    capability_report: dict,
    profile: dict,
    promotion_receipt: dict,
    upload_receipt: dict,
    mcp_tools: dict,
    view_plan: dict | None = None,
) -> dict:
    """Build a production Stage 2 draft from calls made inside this process.

    ``mcp_tools`` is injected only by the authorized local orchestrator. Raw
    JSON receipts are deliberately not accepted at this production boundary.
    """
    expected_tools = {
        "get_workflow",
        "strip_workflow",
        "validate_workflow",
        "check_workflow_runtime",
    }
    if (
        not isinstance(mcp_tools, dict)
        or set(mcp_tools) != expected_tools
        or any(not callable(mcp_tools[name]) for name in expected_tools)
    ):
        raise ExecutionError("production multiview draft requires trusted local MCP conversion callables")
    if (
        not isinstance(workflow_id, str)
        or not workflow_id.strip()
        or len(workflow_id) > 256
    ):
        raise ExecutionError("production multiview workflow_id is invalid")

    if (
        workflow_profile_id != _MULTIVIEW_PROFILE_ID
        or not isinstance(profile, dict)
        or profile.get("profile_id") != _MULTIVIEW_PROFILE_ID
    ):
        raise ExecutionError("production character-multiview requires the promoted flat v2 profile")
    _validate_multiview_profile(profile, workflow_profile_id)
    if workflow_id != profile.get("workflow_id"):
        raise ExecutionError("production multiview workflow_id does not match the v2 profile")
    _require_idle_local_capability(capability_report, _utc_now())
    _require_workflow_candidate(capability_report, workflow_profile_id)
    load_arguments = {"filename": profile["workflow_name"], "format": "ui"}
    convert_arguments = {"filename": profile["workflow_name"], "format": "api"}
    strip_arguments = {"filename": profile["workflow_name"], "format": "api"}
    actual_ui_workflow = _call_multiview_mcp_tool(
        "get_workflow", mcp_tools["get_workflow"], load_arguments
    )
    converted_api_graph = _call_multiview_mcp_tool(
        "get_workflow", mcp_tools["get_workflow"], convert_arguments
    )
    api_graph = _call_multiview_mcp_tool(
        "strip_workflow", mcp_tools["strip_workflow"], strip_arguments
    )
    if not isinstance(converted_api_graph, dict) or not isinstance(api_graph, dict):
        raise ExecutionError("trusted local MCP conversion must return API graph objects")
    if canonical_json(converted_api_graph) != canonical_json(api_graph):
        raise ExecutionError("trusted local MCP strip result does not match get_workflow format=api")
    validate_arguments = {"workflow": copy.deepcopy(api_graph)}
    validation = _call_multiview_mcp_tool(
        "validate_workflow", mcp_tools["validate_workflow"], validate_arguments
    )
    runtime_arguments = {"graph": copy.deepcopy(api_graph)}
    runtime = _call_multiview_mcp_tool(
        "check_workflow_runtime",
        mcp_tools["check_workflow_runtime"],
        runtime_arguments,
    )
    if not isinstance(actual_ui_workflow, dict):
        raise ExecutionError("trusted local MCP get_workflow format=ui must return an object")
    if not isinstance(validation, dict) or not isinstance(runtime, dict):
        raise ExecutionError("trusted local MCP validation/runtime responses must be objects")

    conversion_receipt = {
        "schema_version": "1.0",
        "receipt_type": "comfyui-mcp-ui-to-api",
        "adapter": {
            "name": "comfyui-mcp",
            "version": "0.49.0",
            "tools": {
                "load": "get_workflow",
                "convert": "get_workflow",
                "strip": "strip_workflow",
                "validate": "validate_workflow",
                "runtime": "check_workflow_runtime",
            },
        },
        "saved_workflow": {
            "workflow_id": workflow_id,
            "workflow_name": profile.get("workflow_name"),
            "ui_fingerprint": workflow_fingerprint,
        },
        "conversion": {
            "source_ui_fingerprint": workflow_fingerprint,
            "api_graph_hash": content_hash(api_graph),
        },
        "validation": copy.deepcopy(validation),
        "runtime": copy.deepcopy(runtime),
        "orchestrator": {
            "name": "prompt-forge",
            "trust_model": "trusted-local-orchestrator",
        },
        "invocations": {
            "load": {
                "name": "get_workflow",
                "arguments": load_arguments,
                "response_digest": content_hash(actual_ui_workflow),
            },
            "convert": {
                "name": "get_workflow",
                "arguments": convert_arguments,
                "response_digest": content_hash(converted_api_graph),
            },
            "strip": {
                "name": "strip_workflow",
                "arguments": strip_arguments,
                "response_digest": content_hash(api_graph),
            },
            "validate": {
                "name": "validate_workflow",
                "arguments": validate_arguments,
                "response_digest": content_hash(validation),
            },
            "runtime": {
                "name": "check_workflow_runtime",
                "arguments": runtime_arguments,
                "response_digest": content_hash(runtime),
            },
        },
    }
    return _build_multiview_draft_from_validated_mcp(
        stage1_record=stage1_record,
        base_artifact=base_artifact,
        stage1_api_graph=stage1_api_graph,
        stage1_history=stage1_history,
        stage1_approval_consumption=stage1_approval_consumption,
        stage1_consumption_path=stage1_consumption_path,
        workflow_profile_id=workflow_profile_id,
        workflow_fingerprint=workflow_fingerprint,
        capability_report=capability_report,
        profile=profile,
        actual_ui_workflow=actual_ui_workflow,
        converted_api_graph=converted_api_graph,
        api_graph=api_graph,
        conversion_receipt=conversion_receipt,
        promotion_receipt=promotion_receipt,
        upload_receipt=upload_receipt,
        view_plan=view_plan,
    )


def build_multiview_draft(**_offline_evidence) -> dict:
    """Reject caller-authored conversion receipts at the production boundary.

    Offline fixtures may call :func:`validate_multiview_mcp_preflight` for
    audit, but they cannot create an approvable draft.
    """
    raise ExecutionError(
        "offline MCP conversion receipts are audit fixtures only; production "
        "plan-multiview requires trusted local MCP conversion callables"
    )


def _validate_multiview_draft_contract(draft: dict) -> None:
    for field in (
        "upstream_record_hash",
        "source_artifact_hash",
        "capability_report_hash",
        "profile_hash",
        "promotion_receipt_hash",
        "conversion_receipt_hash",
        "upload_receipt_hash",
        "workflow_fingerprint",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "view_selection_profile_hash",
        "view_plan_hash",
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
    if draft.get("source_api_graph_hash") != _MULTIVIEW_SOURCE_API_GRAPH_HASH:
        raise ExecutionError("Stage 2 draft source API graph is outside the v2 profile pin")
    if draft.get("promotion_receipt_hash") != _MULTIVIEW_PROMOTION_RECEIPT_HASH:
        raise ExecutionError("Stage 2 draft promotion receipt is outside the v2 profile pin")
    if not isinstance(draft.get("saved_workflow_id"), str) or not draft["saved_workflow_id"]:
        raise ExecutionError("Stage 2 draft saved workflow identity is invalid")
    if draft.get("expected_outputs") != _MULTIVIEW_OUTPUTS or draft.get("local_only") is not True:
        raise ExecutionError("Stage 2 draft output/runtime policy is invalid")
    if draft.get("patches") != _multiview_patches(expected_filename, draft["source_artifact_hash"]):
        raise ExecutionError("Stage 2 draft exact dual image patches are invalid")
    selection_profile = _load_view_selection_profile()
    if draft.get("view_selection_profile_hash") != content_hash(selection_profile):
        raise ExecutionError("Stage 2 draft view-selection profile hash is invalid")
    expected_binding = _bind_multiview_view_plan(draft.get("view_plan"), selection_profile)
    for field in ("view_plan_hash", "requested_views", "output_map", "switch_patch", "orientation_evidence"):
        if draft.get(field) != expected_binding[field]:
            raise ExecutionError(f"Stage 2 draft {field} is invalid")
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
        "artifact_descriptor": draft["stage1_artifact_descriptor"],
    }:
        raise ExecutionError("Stage 2 draft upstream preflight is invalid")
    if (
        not isinstance(draft.get("stage1_artifact_descriptor"), dict)
        or set(draft["stage1_artifact_descriptor"]) != {"node_id", "filename", "subfolder", "type"}
        or draft["stage1_artifact_descriptor"].get("type") != "output"
    ):
        raise ExecutionError("Stage 2 draft Stage 1 artifact descriptor is invalid")
    conversion = draft.get("preflight", {}).get("mcp_conversion")
    if conversion != {
        "verified": True,
        "receipt_hash": draft["conversion_receipt_hash"],
        "saved_workflow_id": draft["saved_workflow_id"],
        "adapter": {"name": "comfyui-mcp", "version": "0.49.0"},
        "ui_fingerprint": draft["workflow_fingerprint"],
        "api_graph_hash": draft["source_api_graph_hash"],
    }:
        raise ExecutionError("Stage 2 draft MCP conversion preflight is invalid")
    retained_receipt = draft.get("conversion_receipt")
    if (
        not isinstance(retained_receipt, dict)
        or content_hash(retained_receipt) != draft["conversion_receipt_hash"]
        or retained_receipt.get("orchestrator")
        != {"name": "prompt-forge", "trust_model": "trusted-local-orchestrator"}
        or retained_receipt.get("saved_workflow", {}).get("workflow_id")
        != draft["saved_workflow_id"]
        or retained_receipt.get("conversion", {}).get("api_graph_hash")
        != draft["source_api_graph_hash"]
    ):
        raise ExecutionError("Stage 2 draft retained MCP conversion receipt is invalid")
    promotion_receipt = draft.get("promotion_receipt")
    source_run = promotion_receipt.get("source_run", {}) if isinstance(promotion_receipt, dict) else {}
    promotion = draft.get("preflight", {}).get("promotion")
    if (
        not isinstance(promotion_receipt, dict)
        or content_hash(promotion_receipt) != draft["promotion_receipt_hash"]
        or promotion_receipt.get("orchestrator")
        != {"name": "prompt-forge", "trust_model": "trusted-local-orchestrator"}
        or promotion_receipt.get("flat_workflow", {}).get("workflow_id")
        != draft["saved_workflow_id"]
        or promotion_receipt.get("flat_workflow", {}).get("ui_fingerprint")
        != draft["workflow_fingerprint"]
        or promotion_receipt.get("flat_workflow", {}).get("source_api_graph_hash")
        != draft["source_api_graph_hash"]
        or promotion
        != {
            "verified": True,
            "receipt_hash": draft["promotion_receipt_hash"],
            "prompt_id": source_run.get("prompt_id"),
            "output_png_sha256": source_run.get("output_png_sha256"),
            "embedded_api_graph_hash": source_run.get("embedded_api_graph_hash"),
            "source_api_graph_hash": draft["source_api_graph_hash"],
        }
    ):
        raise ExecutionError("Stage 2 draft retained promotion receipt is invalid")
    upload = draft.get("preflight", {}).get("upload")
    if upload != {
        "verified": True,
        "receipt_hash": draft["upload_receipt_hash"],
        "filename": draft["uploaded_filename"],
        "source_artifact_hash": draft["source_artifact_hash"],
        "server_content_hash": draft["source_artifact_hash"],
    }:
        raise ExecutionError("Stage 2 draft upload preflight is invalid")


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


def _pending_frozen_inputs(draft: dict) -> dict:
    """Return the execution-critical immutable inputs for a resumable draft."""
    common = {
        "capability_report_hash": draft["capability_report_hash"],
        "profile_hash": draft["profile_hash"],
        "workflow_fingerprint": draft["workflow_fingerprint"],
        "source_api_graph_hash": draft["source_api_graph_hash"],
        "executable_api_graph_hash": draft["executable_api_graph_hash"],
    }
    if draft["stage"] == _MULTIVIEW_STAGE:
        common.update(
            {
                "upstream_record_hash": draft["upstream_record_hash"],
                "source_artifact_hash": draft["source_artifact_hash"],
                "lineage_id": draft["lineage_id"],
                "uploaded_filename": draft["uploaded_filename"],
                "conversion_receipt_hash": draft["conversion_receipt_hash"],
                "promotion_receipt_hash": draft["promotion_receipt_hash"],
                "upload_receipt_hash": draft["upload_receipt_hash"],
                "saved_workflow_id": draft["saved_workflow_id"],
                "view_selection_profile_hash": draft["view_selection_profile_hash"],
                "view_plan_hash": draft["view_plan_hash"],
                "requested_views": copy.deepcopy(draft["requested_views"]),
                "output_map": copy.deepcopy(draft["output_map"]),
                "switch_patch": copy.deepcopy(draft["switch_patch"]),
                "orientation_evidence": copy.deepcopy(draft["orientation_evidence"]),
            }
        )
    else:
        common["prompt_build_id"] = draft["prompt_build_id"]
    return common


def _pending_filename(stage: str, draft_hash: str) -> str:
    return (
        f"pending-c-{draft_hash}.json"
        if stage == _MULTIVIEW_STAGE
        else f"pending-{stage}-{draft_hash}.json"
    )


def write_pending_bundle(
    run_dir: str | Path,
    draft: dict,
    *,
    expires_at: str,
) -> Path:
    """Persist one exact draft for a bounded resume in its own consumption namespace."""
    safe_draft = _validate_draft_hash(draft)
    root_text = _canonical_consumption_root(run_dir, "pending bundle")
    now = _utc_now()
    expiry = _parse_utc_timestamp(expires_at, "expires_at")
    if expiry <= now or (expiry - now).total_seconds() > 600:
        raise ExecutionError("pending bundle expiry must be within the next 600 seconds")
    bundle = {
        "schema_version": "1.0",
        "bundle_type": "prompt-forge-pending-execution",
        "stage": safe_draft["stage"],
        "draft": safe_draft,
        "draft_hash": safe_draft["draft_hash"],
        "frozen_inputs": _pending_frozen_inputs(safe_draft),
        "consumption_root": root_text,
        "consumption_namespace": f'{safe_draft["stage"]}:{safe_draft["draft_hash"]}',
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at,
    }
    bundle["bundle_hash"] = content_hash(bundle)
    path = Path(root_text) / _pending_filename(safe_draft["stage"], safe_draft["draft_hash"])
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(bundle))
            handle.write("\n")
    except FileExistsError as exc:
        raise ExecutionError(f"pending bundle already exists: {path}") from exc
    return path.resolve()


def load_pending_bundle(
    path_value: str | Path,
    *,
    expected_stage: str,
    now: datetime | None = None,
) -> dict:
    """Validate an exact, unexpired pending draft before any resume action."""
    if expected_stage not in {"character-base", _MULTIVIEW_STAGE}:
        raise ExecutionError("pending bundle expected stage is unsupported")
    if not isinstance(path_value, (str, Path)):
        raise ExecutionError("pending bundle path is required")
    raw_path = Path(path_value)
    try:
        path = raw_path.resolve(strict=True)
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionError("pending bundle file is invalid") from exc
    keys = {
        "schema_version", "bundle_type", "stage", "draft", "draft_hash", "frozen_inputs",
        "consumption_root", "consumption_namespace", "created_at", "expires_at", "bundle_hash",
    }
    if not isinstance(bundle, dict) or set(bundle) != keys:
        raise ExecutionError("pending bundle schema is invalid")
    if bundle.get("schema_version") != "1.0" or bundle.get("bundle_type") != "prompt-forge-pending-execution":
        raise ExecutionError("pending bundle type/version is invalid")
    if bundle.get("stage") != expected_stage:
        raise ExecutionError("pending bundle stage does not match resume stage")
    unsigned = dict(bundle)
    claimed_hash = unsigned.pop("bundle_hash")
    if claimed_hash != content_hash(unsigned):
        raise ExecutionError("pending bundle hash is invalid")
    safe_draft = _validate_draft_hash(bundle.get("draft"))
    if bundle.get("draft_hash") != safe_draft["draft_hash"]:
        raise ExecutionError("pending bundle draft hash is invalid")
    if bundle.get("frozen_inputs") != _pending_frozen_inputs(safe_draft):
        raise ExecutionError("pending bundle frozen inputs do not match the exact draft")
    root_text = _canonical_consumption_root(bundle.get("consumption_root"), "pending bundle")
    expected_path = Path(root_text) / _pending_filename(expected_stage, safe_draft["draft_hash"])
    if str(raw_path) != str(path) or path != expected_path:
        raise ExecutionError("pending bundle path is not canonical for this draft")
    if bundle.get("consumption_namespace") != f"{expected_stage}:{safe_draft['draft_hash']}":
        raise ExecutionError("pending bundle consumption namespace is invalid")
    created = _parse_utc_timestamp(bundle.get("created_at"), "created_at")
    expiry = _parse_utc_timestamp(bundle.get("expires_at"), "expires_at")
    if expiry <= created or (expiry - created).total_seconds() > 600:
        raise ExecutionError("pending bundle expiry window is invalid")
    trusted_now = _utc_now() if now is None else now
    if trusted_now.tzinfo is None or trusted_now.utcoffset() != timezone.utc.utcoffset(trusted_now):
        raise ExecutionError("pending bundle trusted clock must be UTC")
    if created > trusted_now:
        raise ExecutionError("pending bundle created_at is in the future")
    if trusted_now >= expiry:
        raise ExecutionError("pending bundle is expired")
    return copy.deepcopy(bundle)


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
            "artifact_descriptor": plan["stage1_artifact_descriptor"],
        }
        expected_preflight["mcp_conversion"] = {
            "verified": True,
            "receipt_hash": plan["conversion_receipt_hash"],
            "saved_workflow_id": plan["saved_workflow_id"],
            "adapter": {"name": "comfyui-mcp", "version": "0.49.0"},
            "ui_fingerprint": plan["workflow_fingerprint"],
            "api_graph_hash": plan["source_api_graph_hash"],
        }
        source_run = plan["promotion_receipt"]["source_run"]
        expected_preflight["promotion"] = {
            "verified": True,
            "receipt_hash": plan["promotion_receipt_hash"],
            "prompt_id": source_run["prompt_id"],
            "output_png_sha256": source_run["output_png_sha256"],
            "embedded_api_graph_hash": source_run["embedded_api_graph_hash"],
            "source_api_graph_hash": plan["source_api_graph_hash"],
        }
        expected_preflight["upload"] = {
            "verified": True,
            "receipt_hash": plan["upload_receipt_hash"],
            "filename": plan["uploaded_filename"],
            "source_artifact_hash": plan["source_artifact_hash"],
            "server_content_hash": plan["source_artifact_hash"],
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


def _validate_character_base_submission_request(submission: dict) -> None:
    request = submission.get("request")
    if not isinstance(request, dict) or set(request) != {"prompt", "client_id", "extra_data"}:
        raise ExecutionError("character-base submission request schema is invalid")
    if canonical_json(request.get("prompt")) != canonical_json(submission.get("api_graph")):
        raise ExecutionError("character-base submission request graph does not match api_graph")
    if request.get("client_id") != submission.get("enqueue_request_id"):
        raise ExecutionError("character-base submission request client_id does not match enqueue_request_id")
    extra_data = request.get("extra_data")
    if not isinstance(extra_data, dict):
        raise ExecutionError("character-base submission request provenance is invalid")
    expected = {
        "prompt_forge_stage": "character-base",
        "prompt_forge_plan_hash": submission.get("plan_hash"),
        "prompt_forge_consumption_id": submission.get("consumption_id"),
        "prompt_forge_enqueue_request_id": submission.get("enqueue_request_id"),
        "prompt_forge_workflow_fingerprint": submission.get("workflow_fingerprint"),
    }
    if any(extra_data.get(key) != value for key, value in expected.items()):
        raise ExecutionError("character-base submission request provenance is invalid")
    unexpected = set(extra_data) - set(expected) - {"extra_pnginfo"}
    if unexpected:
        raise ExecutionError("character-base submission request provenance contains unexpected fields")
    pnginfo = extra_data.get("extra_pnginfo")
    if pnginfo is not None:
        if not isinstance(pnginfo, dict) or not isinstance(pnginfo.get("workflow"), dict):
            raise ExecutionError("character-base submission UI provenance is invalid")
        try:
            if structure_fingerprint(pnginfo["workflow"]) != submission.get("workflow_fingerprint"):
                raise ExecutionError("character-base submission UI fingerprint does not match plan")
        except (TypeError, ValueError, KeyError) as exc:
            raise ExecutionError("character-base submission UI workflow is malformed") from exc


def build_character_base_submission(
    *,
    approved_plan: dict,
    prompt_build: dict,
    source_api_graph: dict,
    approval_consumption: dict,
    consumption_path: str | Path,
    ui_workflow: dict | None = None,
) -> dict:
    """Reconstruct the exact approved Stage 1 graph/request without POSTing.

    Stage 1 uses the same approval/consumption namespace as the historical
    execution boundary, but now has an explicit submission object so a local
    REST transport cannot bypass the plan hash or enqueue-once sentinel.
    """
    safe_plan = _validate_approved_plan(approved_plan, trusted_now=_utc_now())
    if safe_plan["stage"] != "character-base":
        raise ExecutionError("character-base submission requires an approved character-base plan")
    if not isinstance(prompt_build, dict) or content_hash(prompt_build) != safe_plan["prompt_build_id"]:
        raise ExecutionError("character-base submission PromptBuild does not match the approved plan")
    if not isinstance(source_api_graph, dict) or content_hash(source_api_graph) != safe_plan["source_api_graph_hash"]:
        raise ExecutionError("character-base submission source graph does not match the approved plan")
    safe_consumption = _validate_approval_consumption_evidence(
        safe_plan,
        approval_consumption,
        consumption_path,
    )
    from .adapters.camera import CameraAdapterError, patch_character_base

    try:
        executable = patch_character_base(source_api_graph, prompt_build, _CHARACTER_BASE_SLOTS)
    except (CameraAdapterError, TypeError, KeyError) as exc:
        raise ExecutionError(f"character-base submission graph failed validation: {exc}") from exc
    if content_hash(executable) != safe_plan["executable_api_graph_hash"]:
        raise ExecutionError("character-base submission executable graph does not match the approved plan")
    request = {
        "prompt": copy.deepcopy(executable),
        "client_id": safe_consumption["enqueue_request_id"],
        "extra_data": {
            "prompt_forge_stage": "character-base",
            "prompt_forge_plan_hash": safe_plan["plan_hash"],
            "prompt_forge_consumption_id": safe_consumption["consumption_id"],
            "prompt_forge_enqueue_request_id": safe_consumption["enqueue_request_id"],
            "prompt_forge_workflow_fingerprint": safe_plan["workflow_fingerprint"],
        },
    }
    if ui_workflow is not None:
        if not isinstance(ui_workflow, dict):
            raise ExecutionError("character-base submission UI workflow must be an object")
        if structure_fingerprint(ui_workflow) != safe_plan["workflow_fingerprint"]:
            raise ExecutionError("character-base submission UI fingerprint does not match the approved plan")
        request["extra_data"]["extra_pnginfo"] = {"workflow": copy.deepcopy(ui_workflow)}
    submission = {
        "schema_version": "1.0",
        "stage": "character-base",
        "submission_type": "character-base-enqueue",
        "plan_hash": safe_plan["plan_hash"],
        "draft_hash": safe_plan["draft_hash"],
        "approval_id": safe_plan["approval_id"],
        "consumption_id": safe_consumption["consumption_id"],
        "consumption_root": safe_consumption["consumption_root"],
        "enqueue_request_id": safe_consumption["enqueue_request_id"],
        "source_api_graph_hash": safe_plan["source_api_graph_hash"],
        "executable_api_graph_hash": safe_plan["executable_api_graph_hash"],
        "workflow_fingerprint": safe_plan["workflow_fingerprint"],
        "api_graph": copy.deepcopy(executable),
        "request": request,
    }
    _validate_character_base_submission_request(submission)
    submission["submission_hash"] = content_hash(submission)
    return submission


def _validate_character_base_submission(submission: object) -> dict:
    if not isinstance(submission, dict) or set(submission) != _CHARACTER_BASE_SUBMISSION_KEYS:
        raise ExecutionError("character-base submission schema is invalid")
    if (
        submission.get("schema_version") != "1.0"
        or submission.get("stage") != "character-base"
        or submission.get("submission_type") != "character-base-enqueue"
    ):
        raise ExecutionError("character-base submission schema is invalid")
    for field in (
        "plan_hash",
        "draft_hash",
        "approval_id",
        "consumption_id",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "workflow_fingerprint",
    ):
        if not isinstance(submission.get(field), str) or not _SHA256_RE.fullmatch(submission[field]):
            raise ExecutionError(f"character-base submission {field} is invalid")
    if not isinstance(submission.get("consumption_root"), str):
        raise ExecutionError("character-base submission consumption_root is invalid")
    if not isinstance(submission.get("api_graph"), dict):
        raise ExecutionError("character-base submission api_graph is invalid")
    if content_hash(submission["api_graph"]) != submission["executable_api_graph_hash"]:
        raise ExecutionError("character-base submission graph hash is invalid")
    _text_request_id = submission.get("enqueue_request_id")
    if not isinstance(_text_request_id, str) or not _text_request_id.strip() or len(_text_request_id) > 256:
        raise ExecutionError("character-base submission enqueue_request_id is invalid")
    _validate_character_base_submission_request(submission)
    claimed = submission.get("submission_hash")
    unsigned = dict(submission)
    unsigned.pop("submission_hash", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise ExecutionError("character-base submission hash is invalid")
    return copy.deepcopy(submission)


def _validate_character_base_intent(value: object, expected: dict) -> dict:
    if not isinstance(value, dict) or set(value) != _CHARACTER_BASE_INTENT_KEYS:
        raise ExecutionError("existing character-base enqueue intent schema is invalid")
    unsigned = dict(value)
    claimed = unsigned.pop("intent_hash", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise ExecutionError("existing character-base enqueue intent hash is invalid")
    if value != expected:
        raise ExecutionError("existing character-base enqueue intent binds different evidence")
    return copy.deepcopy(value)


def _validate_character_base_receipt(submission: dict, receipt: object) -> dict:
    if not isinstance(receipt, dict) or set(receipt) != _CHARACTER_BASE_RECEIPT_KEYS:
        raise ExecutionError("character-base enqueue receipt schema is invalid")
    unsigned = dict(receipt)
    claimed = unsigned.pop("receipt_hash", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise ExecutionError("character-base enqueue receipt hash is invalid")
    if (
        receipt.get("schema_version") != "1.0"
        or receipt.get("receipt_type") != "character-base-enqueue"
        or receipt.get("stage") != "character-base"
        or receipt.get("status") != "succeeded"
        or receipt.get("plan_hash") != submission["plan_hash"]
        or receipt.get("consumption_id") != submission["consumption_id"]
        or receipt.get("submission_hash") != submission["submission_hash"]
        or receipt.get("enqueue_request_id") != submission["enqueue_request_id"]
        or receipt.get("submitted_graph_hash") != submission["executable_api_graph_hash"]
        or receipt.get("orchestrator")
        != {"name": "prompt-forge", "trust_model": "trusted-local-orchestrator"}
    ):
        raise ExecutionError("character-base enqueue receipt does not match submission")
    response = receipt.get("response")
    prompt_id = receipt.get("prompt_id")
    if (
        not isinstance(response, dict)
        or not isinstance(prompt_id, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", prompt_id)
        or response.get("prompt_id") != prompt_id
        or response.get("node_errors") not in ({}, None)
    ):
        raise ExecutionError("character-base enqueue receipt prompt_id is invalid")
    if receipt.get("response_digest") != content_hash(response):
        raise ExecutionError("character-base enqueue receipt response digest is invalid")
    if receipt.get("request") != submission["request"]:
        raise ExecutionError("character-base enqueue receipt request does not match submission")
    return copy.deepcopy(receipt)


def _validate_character_base_receipt_file(
    submission: dict,
    receipt: dict,
    receipt_path: str | Path,
) -> dict:
    safe = _validate_character_base_receipt(submission, receipt)
    root = Path(_canonical_consumption_root(submission["consumption_root"], "character-base receipt"))
    raw_path = Path(receipt_path)
    try:
        resolved = raw_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExecutionError("character-base enqueue receipt file is missing") from exc
    expected = root / f'{submission["consumption_id"]}.character-base-enqueue-receipt.json'
    if str(raw_path) != str(resolved) or resolved != expected.resolve() or not resolved.is_file():
        raise ExecutionError("character-base enqueue receipt path is not canonical")
    try:
        on_disk = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionError("character-base enqueue receipt file is unreadable") from exc
    if canonical_json(on_disk) != canonical_json(safe):
        raise ExecutionError("character-base enqueue receipt file does not match receipt")
    return safe


def submit_character_base(
    *,
    approved_plan: dict,
    prompt_build: dict,
    source_api_graph: dict,
    approval_consumption: dict,
    consumption_path: str | Path,
    enqueue_workflow,
    receipt_root: str | Path | None = None,
    ui_workflow: dict | None = None,
) -> dict:
    """Submit one consumed Stage 1 graph through a trusted local callable."""
    if not callable(enqueue_workflow):
        raise ExecutionError("character-base submission requires a trusted enqueue callable")
    submission = build_character_base_submission(
        approved_plan=approved_plan,
        prompt_build=prompt_build,
        source_api_graph=source_api_graph,
        approval_consumption=approval_consumption,
        consumption_path=consumption_path,
        ui_workflow=ui_workflow,
    )
    root = Path(_canonical_consumption_root(
        receipt_root if receipt_root is not None else approval_consumption.get("consumption_root"),
        "character-base receipt",
    ))
    expected_root = Path(_canonical_consumption_root(
        submission["consumption_root"], "character-base receipt"
    ))
    if root != expected_root:
        raise ExecutionError("character-base receipt root does not match consumed approval root")
    intent = {
        "schema_version": "1.0",
        "intent_type": "prompt-forge-character-base-enqueue",
        "status": "in-progress",
        "stage": "character-base",
        "consumption_id": submission["consumption_id"],
        "enqueue_request_id": submission["enqueue_request_id"],
        "submission_hash": submission["submission_hash"],
        "submitted_graph_hash": submission["executable_api_graph_hash"],
        "request": copy.deepcopy(submission["request"]),
    }
    intent["intent_hash"] = content_hash(intent)
    intent_path = root / f'{submission["consumption_id"]}.character-base-enqueue-intent.json'
    receipt_path = root / f'{submission["consumption_id"]}.character-base-enqueue-receipt.json'
    try:
        retained_intent = _write_submission_evidence(root, intent_path.name, intent)
    except ExecutionError as exc:
        if not intent_path.is_file():
            raise
        _validate_character_base_intent(
            _read_submission_evidence(intent_path, "existing character-base enqueue intent"), intent
        )
        if receipt_path.is_file():
            retained = _validate_character_base_receipt(
                submission,
                _read_submission_evidence(receipt_path, "existing character-base enqueue receipt"),
            )
            return {
                "submission": submission,
                "enqueue_receipt": retained,
                "enqueue_receipt_path": str(receipt_path.resolve()),
                "submission_intent_path": str(intent_path.resolve()),
            }
        raise ExecutionError(
            f"character-base enqueue already has a retained intent; query server state before retrying: {intent_path}"
        ) from exc
    try:
        response = enqueue_workflow(copy.deepcopy(submission["request"]))
    except Exception as exc:
        failure = {
            "schema_version": "1.0",
            "receipt_type": "character-base-enqueue-failure",
            "status": "failed",
            "intent_hash": intent["intent_hash"],
            "consumption_id": submission["consumption_id"],
            "enqueue_request_id": submission["enqueue_request_id"],
            "submission_hash": submission["submission_hash"],
            "submitted_graph_hash": submission["executable_api_graph_hash"],
            "failure_class": exc.__class__.__name__,
        }
        failure["failure_hash"] = content_hash(failure)
        _write_submission_evidence(root, f'{submission["consumption_id"]}.character-base-enqueue-failed.json', failure)
        raise ExecutionError("character-base enqueue failed; query server state before retrying") from exc
    if (
        not isinstance(response, dict)
        or not isinstance(response.get("prompt_id"), str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", response["prompt_id"])
        or response.get("node_errors") not in ({}, None)
    ):
        raise ExecutionError("character-base enqueue response is invalid")
    receipt = {
        "schema_version": "1.0",
        "receipt_type": "character-base-enqueue",
        "stage": "character-base",
        "status": "succeeded",
        "plan_hash": submission["plan_hash"],
        "consumption_id": submission["consumption_id"],
        "submission_hash": submission["submission_hash"],
        "prompt_id": response["prompt_id"],
        "enqueue_request_id": submission["enqueue_request_id"],
        "submitted_graph_hash": submission["executable_api_graph_hash"],
        "request": copy.deepcopy(submission["request"]),
        "response": copy.deepcopy(response),
        "response_digest": content_hash(response),
        "orchestrator": {"name": "prompt-forge", "trust_model": "trusted-local-orchestrator"},
    }
    receipt["receipt_hash"] = content_hash(receipt)
    receipt_path = _write_submission_evidence(root, receipt_path.name, receipt)
    safe_receipt = _validate_character_base_receipt(submission, receipt)
    return {
        "submission": submission,
        "enqueue_receipt": safe_receipt,
        "enqueue_receipt_path": str(receipt_path),
        "submission_intent_path": str(retained_intent),
    }


def build_multiview_submission(
    *,
    approved_plan: dict,
    source_api_graph: dict,
    upload_receipt: dict,
    approval_consumption: dict,
    consumption_path: str | Path,
) -> dict:
    """Build the only graph object authorized for one consumed Stage 2 enqueue."""
    safe_plan = _validate_approved_plan(approved_plan, trusted_now=_utc_now())
    if safe_plan["stage"] != _MULTIVIEW_STAGE:
        raise ExecutionError("Flux submission requires an approved character-multiview plan")
    if not isinstance(source_api_graph, dict) or content_hash(source_api_graph) != safe_plan["source_api_graph_hash"]:
        raise ExecutionError("Flux submission source graph does not match approved plan")
    artifact_identity = {
        "lineage_id": safe_plan["lineage_id"],
        "content_hash": safe_plan["source_artifact_hash"],
    }
    safe_upload = _validate_multiview_upload_receipt(upload_receipt, artifact_identity)
    if content_hash(safe_upload) != safe_plan["upload_receipt_hash"]:
        raise ExecutionError("Flux submission upload receipt does not match approved plan")
    safe_consumption = _validate_approval_consumption_evidence(
        safe_plan,
        approval_consumption,
        consumption_path,
    )
    immutable_inputs = _multiview_immutable_inputs(
        source_api_graph,
        {"immutable_roles": {"pose_references": _MULTIVIEW_POSE_IDS}},
    )
    if immutable_inputs != safe_plan["immutable_inputs"]:
        raise ExecutionError("Flux submission immutable pose inputs do not match approved plan")
    executable = _multiview_executable_from_plan(source_api_graph, safe_plan)
    if content_hash(executable) != safe_plan["executable_api_graph_hash"]:
        raise ExecutionError("Flux submission executable graph does not match approved plan")
    submission = {
        "schema_version": "1.0",
        "submission_type": "character-multiview-enqueue",
        "plan_hash": safe_plan["plan_hash"],
        "draft_hash": safe_plan["draft_hash"],
        "approval_id": safe_plan["approval_id"],
        "consumption_id": safe_consumption["consumption_id"],
        "enqueue_request_id": safe_consumption["enqueue_request_id"],
        "source_api_graph_hash": safe_plan["source_api_graph_hash"],
        "executable_api_graph_hash": safe_plan["executable_api_graph_hash"],
        "api_graph": executable,
    }
    submission["submission_hash"] = content_hash(submission)
    return submission


def _write_submission_evidence(root: Path, filename: str, value: dict) -> Path:
    path = root / filename
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(value))
            handle.write("\n")
    except FileExistsError as exc:
        raise ExecutionError(f"submission evidence already exists: {path}") from exc
    return path.resolve()


def _read_submission_evidence(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise ExecutionError(f"{label} schema is invalid")
    return value


def _submission_intent(submission: dict, consumption: dict, request: dict) -> dict:
    intent = {
        "schema_version": "1.0",
        "intent_type": "prompt-forge-mcp-enqueue",
        "status": "in-progress",
        "consumption_id": consumption["consumption_id"],
        "enqueue_request_id": consumption["enqueue_request_id"],
        "submission_hash": submission["submission_hash"],
        "submitted_graph_hash": submission["executable_api_graph_hash"],
        "request": copy.deepcopy(request),
    }
    intent["intent_hash"] = content_hash(intent)
    return intent


def _validate_submission_intent(value: object, expected: dict) -> dict:
    expected_keys = {
        "schema_version", "intent_type", "status", "consumption_id",
        "enqueue_request_id", "submission_hash", "submitted_graph_hash",
        "request", "intent_hash",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ExecutionError("existing enqueue intent schema is invalid")
    unsigned = dict(value)
    claimed_hash = unsigned.pop("intent_hash")
    if claimed_hash != content_hash(unsigned):
        raise ExecutionError("existing enqueue intent hash is invalid")
    if value != expected:
        raise ExecutionError("existing enqueue intent binds a different graph, hash, or request")
    return copy.deepcopy(value)


def submit_multiview(
    *,
    approved_plan: dict,
    source_api_graph: dict,
    upload_receipt: dict,
    approval_consumption: dict,
    consumption_path: str | Path,
    enqueue_workflow,
) -> dict:
    """Submit one consumed multiview graph through a trusted local MCP adapter.

    The injected callable is the in-process orchestrator boundary. It must
    return a complete invocation envelope; plain JSON CLI input cannot pretend
    to be this boundary and therefore fails closed.
    """
    if not callable(enqueue_workflow):
        raise ExecutionError("multiview submission requires a trusted MCP enqueue callable")
    submission = build_multiview_submission(
        approved_plan=approved_plan,
        source_api_graph=source_api_graph,
        upload_receipt=upload_receipt,
        approval_consumption=approval_consumption,
        consumption_path=consumption_path,
    )
    request = {
        "prompt": copy.deepcopy(submission["api_graph"]),
        "client_id": submission["enqueue_request_id"],
        "extra_data": {
            "prompt_forge_enqueue_request_id": submission["enqueue_request_id"],
            "prompt_forge_submission_hash": submission["submission_hash"],
        },
    }
    root = Path(_canonical_consumption_root(
        approval_consumption.get("consumption_root"), "enqueue receipt"
    ))
    intent = _submission_intent(submission, approval_consumption, request)
    intent_path = root / f'{approval_consumption["consumption_id"]}.enqueue-intent.json'
    try:
        retained_intent_path = _write_submission_evidence(
            root, intent_path.name, intent
        )
    except ExecutionError as exc:
        if not intent_path.is_file():
            raise
        _validate_submission_intent(_read_submission_evidence(intent_path, "existing enqueue intent"), intent)
        receipt_path = root / f'{approval_consumption["consumption_id"]}.enqueue-receipt.json'
        failed_path = root / f'{approval_consumption["consumption_id"]}.enqueue-failed.json'
        if receipt_path.is_file() and failed_path.is_file():
            raise ExecutionError("existing enqueue state is ambiguous: success and failed receipts both exist")
        if receipt_path.is_file():
            receipt = _read_submission_evidence(receipt_path, "existing enqueue receipt")
            safe_receipt = _validate_enqueue_receipt(
                submission, approval_consumption, receipt, receipt_path
            )
            return {
                "submission": submission,
                "enqueue_receipt": safe_receipt,
                "enqueue_receipt_path": str(receipt_path.resolve()),
                "submission_intent_path": str(intent_path.resolve()),
            }
        if failed_path.is_file():
            failure = _read_submission_evidence(failed_path, "existing enqueue failed receipt")
            _validate_enqueue_failure_receipt(
                submission, approval_consumption, failure, failed_path
            )
            raise ExecutionError(f"trusted MCP enqueue failed receipt retained: {failed_path}") from exc
        raise ExecutionError(f"trusted MCP enqueue already in progress: {intent_path}") from exc
    try:
        observed = enqueue_workflow(copy.deepcopy(request))
    except Exception as exc:
        failure = {
            "schema_version": "1.0",
            "receipt_type": "prompt-forge-mcp-enqueue-failure",
            "status": "failed",
            "submission_intent_hash": intent["intent_hash"],
            "consumption_id": submission["consumption_id"],
            "enqueue_request_id": submission["enqueue_request_id"],
            "submission_hash": submission["submission_hash"],
            "submitted_graph_hash": submission["executable_api_graph_hash"],
            "tool": {"name": "enqueue_workflow", "arguments": request},
            "orchestrator": {
                "name": "prompt-forge",
                "trust_model": "trusted-local-orchestrator",
            },
            "failure_class": exc.__class__.__name__,
        }
        failure["failure_hash"] = content_hash(failure)
        _write_submission_evidence(root, f'{submission["consumption_id"]}.enqueue-failed.json', failure)
        raise ExecutionError("trusted MCP enqueue failed receipt retained; query server before any further action") from exc
    expected_observed_keys = {"tool", "response", "response_digest", "orchestrator"}
    if not isinstance(observed, dict) or set(observed) != expected_observed_keys:
        raise ExecutionError("trusted MCP enqueue receipt schema is invalid")
    if observed.get("tool") != {"name": "enqueue_workflow", "arguments": request}:
        raise ExecutionError("trusted MCP enqueue receipt does not bind exact tool arguments")
    response = observed.get("response")
    if not isinstance(response, dict) or observed.get("response_digest") != content_hash(response):
        raise ExecutionError("trusted MCP enqueue response digest is invalid")
    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", prompt_id):
        raise ExecutionError("trusted MCP enqueue response prompt_id is invalid")
    if response.get("node_errors") not in ({}, None):
        raise ExecutionError("trusted MCP enqueue response contains node errors")
    orchestrator = observed.get("orchestrator")
    if (
        not isinstance(orchestrator, dict)
        or set(orchestrator) != {"name", "trust_model"}
        or not isinstance(orchestrator.get("name"), str)
        or not orchestrator["name"]
        or orchestrator.get("trust_model") != "trusted-local-orchestrator"
    ):
        raise ExecutionError("trusted MCP enqueue orchestrator provenance is invalid")
    receipt = {
        "schema_version": "1.0",
        "receipt_type": "prompt-forge-mcp-enqueue",
        "status": "succeeded",
        "submission_intent_hash": intent["intent_hash"],
        "consumption_id": submission["consumption_id"],
        "prompt_id": prompt_id,
        "enqueue_request_id": submission["enqueue_request_id"],
        "submission_hash": submission["submission_hash"],
        "submitted_graph_hash": submission["executable_api_graph_hash"],
        "tool": copy.deepcopy(observed["tool"]),
        "response": copy.deepcopy(response),
        "response_digest": observed["response_digest"],
        "orchestrator": copy.deepcopy(orchestrator),
    }
    receipt["receipt_hash"] = content_hash(receipt)
    receipt_path = _write_submission_evidence(
        root, f'{submission["consumption_id"]}.enqueue-receipt.json', receipt
    )
    safe_receipt = _validate_enqueue_receipt(
        submission, approval_consumption, receipt, receipt_path
    )
    return {
        "submission": submission,
        "enqueue_receipt": safe_receipt,
        "enqueue_receipt_path": str(receipt_path),
        "submission_intent_path": str(retained_intent_path),
    }


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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ExecutionError("artifact bytes cannot be read") from exc
    return digest.hexdigest()


def _validate_character_base_artifact_bytes(
    history_outputs: list[dict],
    output_hashes: dict[str, str],
    selected_descriptor: dict,
    output_root: str | Path,
) -> tuple[str, str]:
    """Verify every Stage 1 PNG and return the selected output path/root."""
    if not isinstance(output_root, (str, Path)):
        raise ExecutionError("Stage 1 artifact output root must be an absolute canonical directory")
    root = Path(output_root)
    if not root.is_absolute():
        raise ExecutionError("Stage 1 artifact output root must be an absolute canonical directory")
    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExecutionError("Stage 1 artifact output root must be an existing canonical directory") from exc
    if str(root) != str(resolved_root) or not resolved_root.is_dir():
        raise ExecutionError("Stage 1 artifact output root must be an existing canonical directory")

    selected_path: Path | None = None
    for descriptor in history_outputs:
        output_type = descriptor["type"]
        if output_type == "output":
            descriptor_root = resolved_root
        elif output_type == "temp":
            descriptor_root = resolved_root.parent / "temp"
            try:
                descriptor_root = descriptor_root.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise ExecutionError("Stage 1 temporary artifact root is missing") from exc
            if not descriptor_root.is_dir():
                raise ExecutionError("Stage 1 temporary artifact root is invalid")
        else:
            raise ExecutionError("Stage 1 history contains an unsupported image type")
        raw_path = descriptor_root / descriptor["subfolder"] / descriptor["filename"]
        try:
            resolved_path = raw_path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ExecutionError("Stage 1 artifact path does not exist") from exc
        if (
            not resolved_path.is_file()
            or not resolved_path.is_relative_to(descriptor_root)
            or str(raw_path) != str(resolved_path)
        ):
            raise ExecutionError("Stage 1 artifact path must remain inside its output root")
        try:
            _evidence_validate_png_file(resolved_path)
        except (MultiviewEvidenceError, OSError) as exc:
            raise ExecutionError("Stage 1 artifact bytes are not a structurally valid PNG") from exc
        if _file_sha256(resolved_path) != output_hashes[descriptor["filename"]]:
            raise ExecutionError("Stage 1 artifact bytes do not match output_hashes")
        if descriptor == selected_descriptor:
            selected_path = resolved_path
    if selected_path is None:
        raise ExecutionError("Stage 1 selected artifact path is missing")
    return str(resolved_root), str(selected_path)


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


def _normalize_history_graph_numbers(value: object) -> object:
    """Normalize ComfyUI's JSON numeric round-trips without changing semantics.

    The server may deserialize an integer widget value and serialize it back as
    ``1.0``.  Those values are equal in Python but differ in canonical JSON,
    so a byte-level comparison would reject the exact graph that was executed.
    Only integral floats are folded to integers; non-integral values, strings,
    booleans, and graph topology remain untouched.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [_normalize_history_graph_numbers(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _normalize_history_graph_numbers(item) for key, item in value.items()
        }
    return value


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
        graph_matches = canonical_json(
            _normalize_history_graph_numbers(prompt[2])
        ) == canonical_json(_normalize_history_graph_numbers(executable_api_graph))
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


def _history_outputs_equal(left: object, right: object) -> bool:
    """Compare output descriptors as a set; ComfyUI node order is incidental."""
    if not isinstance(left, list) or not isinstance(right, list):
        return False
    try:
        return sorted(canonical_json(item) for item in left) == sorted(
            canonical_json(item) for item in right
        )
    except (TypeError, ValueError):
        return False


def _history_enqueue_request_id(history: object, prompt_id: str) -> str:
    """Read the enqueue identity from the raw ComfyUI prompt tuple only."""
    if not isinstance(history, dict) or not isinstance(history.get(prompt_id), dict):
        raise ExecutionError("raw ComfyUI history is missing the prompt_id entry")
    prompt = history[prompt_id].get("prompt")
    if not isinstance(prompt, list) or len(prompt) < 4 or not isinstance(prompt[3], dict):
        raise ExecutionError("raw ComfyUI history prompt metadata is missing")
    metadata = prompt[3]
    direct = metadata.get("prompt_forge_enqueue_request_id")
    extra_data = metadata.get("extra_data")
    nested = extra_data.get("prompt_forge_enqueue_request_id") if isinstance(extra_data, dict) else None
    if direct is not None and nested is not None and direct != nested:
        raise ExecutionError("raw ComfyUI history enqueue request metadata conflicts")
    value = nested if nested is not None else direct
    if not isinstance(value, str) or not value:
        raise ExecutionError("raw ComfyUI history enqueue request metadata is invalid")
    return value


def _validate_enqueue_receipt(
    submission: dict,
    consumption: dict,
    receipt: object,
    receipt_path: str | Path,
) -> dict:
    expected_keys = {
        "schema_version", "receipt_type", "status", "submission_intent_hash", "consumption_id",
        "prompt_id", "enqueue_request_id",
        "submission_hash", "submitted_graph_hash", "tool", "response",
        "response_digest", "orchestrator", "receipt_hash",
    }
    if not isinstance(receipt, dict) or set(receipt) != expected_keys:
        raise ExecutionError("Stage 2 enqueue receipt schema is invalid")
    if (
        receipt.get("schema_version") != "1.0"
        or receipt.get("receipt_type") != "prompt-forge-mcp-enqueue"
    ):
        raise ExecutionError("Stage 2 enqueue receipt type/version is invalid")
    unsigned = dict(receipt)
    claimed_hash = unsigned.pop("receipt_hash")
    if not isinstance(claimed_hash, str) or claimed_hash != content_hash(unsigned):
        raise ExecutionError("Stage 2 enqueue receipt hash is invalid")
    prompt_id = receipt.get("prompt_id")
    if not isinstance(prompt_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", prompt_id):
        raise ExecutionError("Stage 2 enqueue receipt prompt_id is invalid")
    request = {
        "prompt": submission["api_graph"],
        "client_id": consumption["enqueue_request_id"],
        "extra_data": {
            "prompt_forge_enqueue_request_id": consumption["enqueue_request_id"],
            "prompt_forge_submission_hash": submission["submission_hash"],
        },
    }
    expected_intent = _submission_intent(submission, consumption, request)
    if receipt.get("status") != "succeeded" or receipt.get("submission_intent_hash") != expected_intent["intent_hash"]:
        raise ExecutionError("Stage 2 enqueue receipt intent does not match consumed submission")
    if receipt.get("consumption_id") != consumption["consumption_id"]:
        raise ExecutionError("Stage 2 enqueue receipt consumption does not match consumed approval")
    if receipt.get("tool") != {"name": "enqueue_workflow", "arguments": request}:
        raise ExecutionError("Stage 2 enqueue receipt does not bind exact tool arguments")
    response = receipt.get("response")
    if not isinstance(response, dict) or response.get("prompt_id") != prompt_id:
        raise ExecutionError("Stage 2 enqueue receipt response prompt_id is invalid")
    if response.get("node_errors") not in ({}, None):
        raise ExecutionError("Stage 2 enqueue receipt response contains node errors")
    if receipt.get("response_digest") != content_hash(response):
        raise ExecutionError("Stage 2 enqueue receipt response digest is invalid")
    if receipt.get("enqueue_request_id") != consumption["enqueue_request_id"]:
        raise ExecutionError("Stage 2 enqueue receipt request does not match consumed approval")
    if receipt.get("submission_hash") != submission["submission_hash"]:
        raise ExecutionError("Stage 2 enqueue receipt submission does not match submission")
    if receipt.get("submitted_graph_hash") != submission["executable_api_graph_hash"]:
        raise ExecutionError("Stage 2 enqueue receipt graph does not match submission")
    if receipt.get("orchestrator") is None or not isinstance(receipt["orchestrator"], dict):
        raise ExecutionError("Stage 2 enqueue receipt provenance is invalid")
    orchestrator = receipt["orchestrator"]
    if set(orchestrator) != {"name", "trust_model"} or not isinstance(orchestrator.get("name"), str) or not orchestrator["name"] or orchestrator.get("trust_model") != "trusted-local-orchestrator":
        raise ExecutionError("Stage 2 enqueue receipt provenance is invalid")
    path = Path(receipt_path)
    try:
        resolved_path = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExecutionError("Stage 2 enqueue receipt file is missing") from exc
    expected_path = Path(consumption["consumption_root"]) / f'{consumption["consumption_id"]}.enqueue-receipt.json'
    if str(path) != str(resolved_path) or resolved_path != expected_path.resolve() or not resolved_path.is_file():
        raise ExecutionError("Stage 2 enqueue receipt path is not canonical")
    try:
        on_disk = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExecutionError("Stage 2 enqueue receipt file is unreadable") from exc
    if on_disk != receipt:
        raise ExecutionError("Stage 2 enqueue receipt file does not match receipt")
    return copy.deepcopy(receipt)


def _validate_enqueue_failure_receipt(
    submission: dict,
    consumption: dict,
    receipt: object,
    receipt_path: str | Path,
) -> dict:
    expected_keys = {
        "schema_version", "receipt_type", "status", "submission_intent_hash",
        "consumption_id", "enqueue_request_id", "submission_hash",
        "submitted_graph_hash", "tool", "orchestrator", "failure_class",
        "failure_hash",
    }
    if not isinstance(receipt, dict) or set(receipt) != expected_keys:
        raise ExecutionError("Stage 2 enqueue failed receipt schema is invalid")
    unsigned = dict(receipt)
    claimed_hash = unsigned.pop("failure_hash")
    if not isinstance(claimed_hash, str) or claimed_hash != content_hash(unsigned):
        raise ExecutionError("Stage 2 enqueue failed receipt hash is invalid")
    request = {
        "prompt": submission["api_graph"],
        "client_id": consumption["enqueue_request_id"],
        "extra_data": {
            "prompt_forge_enqueue_request_id": consumption["enqueue_request_id"],
            "prompt_forge_submission_hash": submission["submission_hash"],
        },
    }
    expected_intent = _submission_intent(submission, consumption, request)
    expected_values = {
        "schema_version": "1.0",
        "receipt_type": "prompt-forge-mcp-enqueue-failure",
        "status": "failed",
        "submission_intent_hash": expected_intent["intent_hash"],
        "consumption_id": consumption["consumption_id"],
        "enqueue_request_id": consumption["enqueue_request_id"],
        "submission_hash": submission["submission_hash"],
        "submitted_graph_hash": submission["executable_api_graph_hash"],
        "tool": {"name": "enqueue_workflow", "arguments": request},
        "orchestrator": {
            "name": "prompt-forge",
            "trust_model": "trusted-local-orchestrator",
        },
    }
    for field, expected in expected_values.items():
        if receipt.get(field) != expected:
            raise ExecutionError(f"Stage 2 enqueue failed receipt {field} is invalid")
    if not isinstance(receipt.get("failure_class"), str) or not receipt["failure_class"]:
        raise ExecutionError("Stage 2 enqueue failed receipt failure class is invalid")
    path = Path(receipt_path)
    try:
        resolved_path = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExecutionError("Stage 2 enqueue failed receipt file is missing") from exc
    expected_path = Path(consumption["consumption_root"]) / (
        f'{consumption["consumption_id"]}.enqueue-failed.json'
    )
    if str(path) != str(resolved_path) or resolved_path != expected_path.resolve() or not resolved_path.is_file():
        raise ExecutionError("Stage 2 enqueue failed receipt path is not canonical")
    try:
        on_disk = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionError("Stage 2 enqueue failed receipt file is unreadable") from exc
    if on_disk != receipt:
        raise ExecutionError("Stage 2 enqueue failed receipt file does not match receipt")
    return copy.deepcopy(receipt)


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
    artifact_descriptor: dict | None = None,
    submission: dict | None = None,
    enqueue_receipt: dict | None = None,
    enqueue_receipt_path: str | Path | None = None,
    approval_consumption: dict | None = None,
    consumption_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
) -> dict:
    """Record terminal history with an explicit accepted-output selector.

    ComfyUI histories commonly contain both ``temp`` previews and retained
    ``output`` files.  A Stage 1 record must therefore carry the exact output
    descriptor selected for downstream lineage; inferring it from list length
    is unsafe and made a valid history impossible to consume.
    """
    try:
        safe_context = validate_task_context(task_context)
    except ContractError as exc:
        raise ExecutionError(f"invalid TaskContext: {exc}") from exc
    if not isinstance(prompt_build, dict) or not isinstance(prompt_build.get("execution"), dict):
        raise ExecutionError("RunRecord requires a PromptBuild execution object")
    if prompt_build["execution"].get("performed") is not False:
        raise ExecutionError("PromptBuild execution.performed must remain false")
    _validate_plan_lineage(execution_plan, prompt_build, api_graph)

    bound_submission = None
    bound_receipt = None
    bound_consumption = None
    if any(
        value is not None
        for value in (
            submission,
            enqueue_receipt,
            enqueue_receipt_path,
            approval_consumption,
            consumption_path,
        )
    ):
        if not all(
            value is not None
            for value in (
                submission,
                enqueue_receipt,
                enqueue_receipt_path,
                approval_consumption,
                consumption_path,
            )
        ):
            raise ExecutionError(
                "Stage 1 RunRecord receipt binding requires submission, consumption, and receipt evidence"
            )
        safe_plan = _validate_approved_plan(execution_plan, trusted_now=None)
        bound_submission = _validate_character_base_submission(submission)
        if bound_submission["plan_hash"] != safe_plan["plan_hash"]:
            raise ExecutionError("Stage 1 submission plan does not match the RunRecord plan")
        bound_consumption = _validate_approval_consumption_evidence(
            safe_plan,
            approval_consumption,
            consumption_path,
        )
        if bound_submission["consumption_id"] != bound_consumption["consumption_id"]:
            raise ExecutionError("Stage 1 submission consumption does not match the RunRecord")
        bound_receipt = _validate_character_base_receipt_file(
            bound_submission,
            enqueue_receipt,
            enqueue_receipt_path,
        )

    if artifact_root is not None and bound_submission is None:
        raise ExecutionError(
            "Stage 1 artifact output evidence requires receipt-bound submission evidence"
        )

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

    if terminal_status != "succeeded" and artifact_descriptor is None:
        selected_descriptor = None
    elif artifact_descriptor is None:
        if len(history_outputs) != 1:
            raise ExecutionError(
                "an explicit artifact_descriptor is required when history has multiple outputs"
            )
        selected_descriptor = history_outputs[0]
    else:
        selected_descriptor = copy.deepcopy(artifact_descriptor)
        if (
            not isinstance(selected_descriptor, dict)
            or set(selected_descriptor) != {"node_id", "filename", "subfolder", "type"}
            or selected_descriptor not in history_outputs
            or selected_descriptor.get("type") != "output"
        ):
            raise ExecutionError(
                "artifact_descriptor must select one retained output descriptor from history"
            )

    verified_artifact_root = None
    verified_artifact_path = None
    artifact_hashes_verified = False
    if artifact_root is not None:
        if terminal_status != "succeeded" or selected_descriptor is None:
            raise ExecutionError("Stage 1 artifact root requires a succeeded selected output")
        verified_artifact_root, verified_artifact_path = _validate_character_base_artifact_bytes(
            history_outputs,
            safe_outputs,
            selected_descriptor,
            artifact_root,
        )
        artifact_hashes_verified = True

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
        "artifact_descriptor": selected_descriptor,
        "history_verified": True,
        "artifact_hashes_verified": artifact_hashes_verified,
        "input_hashes": safe_inputs,
        "output_hashes": safe_outputs,
    }
    if verified_artifact_root is not None:
        record.update(
            {
                "artifact_root": verified_artifact_root,
                "artifact_path": verified_artifact_path,
            }
        )
    if bound_submission is not None:
        if artifact_root is None:
            raise ExecutionError(
                "Stage 1 receipt-bound RunRecord requires an explicit artifact output root"
            )
        if bound_receipt["prompt_id"] != prompt_id:
            raise ExecutionError("Stage 1 receipt prompt_id does not match raw history")
        if _history_enqueue_request_id(history, prompt_id) != bound_submission["enqueue_request_id"]:
            raise ExecutionError("Stage 1 history enqueue request does not match submission")
        record.update(
            {
                "approval_consumption": copy.deepcopy(bound_consumption),
                "consumption_path": str(Path(consumption_path).resolve()),
                "submission": copy.deepcopy(bound_submission),
                "submission_hash": bound_submission["submission_hash"],
                "enqueue_receipt": copy.deepcopy(bound_receipt),
                "enqueue_receipt_hash": bound_receipt["receipt_hash"],
                "enqueue_receipt_path": str(Path(enqueue_receipt_path).resolve()),
                "raw_history": copy.deepcopy(history),
                "raw_history_hash": content_hash(history),
            }
        )
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
    *,
    stage1_api_graph: dict,
    stage1_history: dict,
    stage1_approval_consumption: dict,
    stage1_consumption_path: str | Path,
    approval_consumption: dict,
    consumption_path: str | Path,
    submission: dict,
    enqueue_receipt: dict,
    enqueue_receipt_path: str | Path,
    output_root: str | Path,
    history: dict,
) -> dict:
    """Record only the consumed Stage 2 submission and verified output bytes."""
    try:
        safe_context = validate_task_context(task_context)
    except ContractError as exc:
        raise ExecutionError(f"invalid TaskContext: {exc}") from exc
    safe_stage1, safe_artifact = _validated_stage1_source(
        stage1_record,
        base_artifact,
        stage1_api_graph=stage1_api_graph,
        stage1_history=stage1_history,
        stage1_approval_consumption=stage1_approval_consumption,
        stage1_consumption_path=stage1_consumption_path,
    )
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
    if safe_plan["promotion_receipt_hash"] != profile.get("promotion_receipt_hash"):
        raise ExecutionError("Stage 2 plan promotion receipt does not match profile")
    if content_hash(api_graph) != safe_plan["source_api_graph_hash"]:
        raise ExecutionError("Stage 2 plan source graph does not match API graph")

    executable = _multiview_executable_from_plan(api_graph, safe_plan)
    if content_hash(executable) != safe_plan["executable_api_graph_hash"]:
        raise ExecutionError("Stage 2 executable graph does not match approved plan")
    if safe_plan["patches"] != _multiview_patches(
        safe_plan["uploaded_filename"], safe_artifact["content_hash"]
    ):
        raise ExecutionError("Stage 2 exact dual patches do not match source artifact")

    safe_consumption = _validate_approval_consumption_evidence(
        safe_plan, approval_consumption, consumption_path
    )
    if not isinstance(submission, dict) or set(submission) != {
        "schema_version", "submission_type", "plan_hash", "draft_hash", "approval_id",
        "consumption_id", "enqueue_request_id", "source_api_graph_hash",
        "executable_api_graph_hash", "api_graph", "submission_hash",
    }:
        raise ExecutionError("Stage 2 submission evidence schema is invalid")
    unsigned_submission = dict(submission)
    claimed_submission_hash = unsigned_submission.pop("submission_hash")
    if claimed_submission_hash != content_hash(unsigned_submission):
        raise ExecutionError("Stage 2 submission evidence hash is invalid")
    expected_submission = {
        "schema_version": "1.0",
        "submission_type": "character-multiview-enqueue",
        "plan_hash": safe_plan["plan_hash"],
        "draft_hash": safe_plan["draft_hash"],
        "approval_id": safe_plan["approval_id"],
        "consumption_id": safe_consumption["consumption_id"],
        "enqueue_request_id": safe_consumption["enqueue_request_id"],
        "source_api_graph_hash": safe_plan["source_api_graph_hash"],
        "executable_api_graph_hash": safe_plan["executable_api_graph_hash"],
        "api_graph": executable,
        "submission_hash": claimed_submission_hash,
    }
    if submission != expected_submission:
        raise ExecutionError("Stage 2 submission does not match consumed approved plan")
    safe_enqueue_receipt = _validate_enqueue_receipt(
        submission,
        safe_consumption,
        enqueue_receipt,
        enqueue_receipt_path,
    )

    if not isinstance(prompt_id, str) or not prompt_id:
        raise ExecutionError("prompt_id is required for a terminal Stage 2 RunRecord")
    if terminal_status not in _TERMINAL_STATUSES:
        raise ExecutionError("Stage 2 terminal status must be succeeded or failed")
    history_status, history_outputs = _parse_history(
        history, prompt_id, terminal_status, executable
    )
    if safe_enqueue_receipt["prompt_id"] != prompt_id:
        raise ExecutionError("Stage 2 history prompt_id does not match enqueue receipt")
    if _history_enqueue_request_id(history, prompt_id) != safe_consumption["enqueue_request_id"]:
        raise ExecutionError("Stage 2 history enqueue request does not match consumed approval")
    root_text = str(output_root)
    root = Path(root_text)
    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExecutionError("Stage 2 output root must be an existing canonical directory") from exc
    if root_text != str(resolved_root) or not resolved_root.is_dir():
        raise ExecutionError("Stage 2 output root must be an existing canonical directory")
    safe_outputs: dict[str, str] = {}
    for descriptor in history_outputs:
        if descriptor["type"] == "output":
            descriptor_root = resolved_root
        elif descriptor["type"] == "temp":
            descriptor_root = resolved_root.parent / "temp"
            try:
                descriptor_root = descriptor_root.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise ExecutionError("Stage 2 temporary artifact root is missing") from exc
            if not descriptor_root.is_dir():
                raise ExecutionError("Stage 2 temporary artifact root is invalid")
        else:
            raise ExecutionError("Stage 2 history artifacts must be output or temp PNG files")
        candidate = descriptor_root / descriptor["subfolder"] / descriptor["filename"]
        try:
            physical_path = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ExecutionError("Stage 2 history artifact file is missing") from exc
        if not physical_path.is_file() or not physical_path.is_relative_to(descriptor_root):
            raise ExecutionError("Stage 2 history artifact escapes its canonical output root")
        _validate_png_file(physical_path)
        safe_outputs[descriptor["filename"]] = _file_sha256(physical_path)

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
        artifact["hash_verified"] = True
        # Selecting a Stage 3 reference remains an explicit acceptance action.
        artifact["accepted"] = False

    record = {
        "schema_version": "1.0",
        "stage": _MULTIVIEW_STAGE,
        "task_context_hash": content_hash(safe_context),
        "upstream_record_hash": safe_stage1["record_hash"],
        "source_artifact_hash": safe_artifact["content_hash"],
        "lineage_id": safe_artifact["lineage_id"],
        "promotion_receipt_hash": safe_plan["promotion_receipt_hash"],
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
        "artifact_hashes_verified": True,
        "approval_consumption_id": safe_consumption["consumption_id"],
        "enqueue_request_id": safe_consumption["enqueue_request_id"],
        "submission_hash": claimed_submission_hash,
        "enqueue_receipt_hash": safe_enqueue_receipt["receipt_hash"],
        "enqueue_receipt_path": str(Path(enqueue_receipt_path).resolve()),
        "output_hashes": safe_outputs,
        "artifacts": artifacts,
    }
    record["record_hash"] = content_hash(record)
    return record
