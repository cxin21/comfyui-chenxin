"""Fail-closed execution boundary for the Stage 3/4 pipeline.

The pure builders in :mod:`runtime.stages` describe intent.  This module binds
that intent to a freshly observed API graph, an idle local runtime, an exact
approval event, a single consumption record, and (optionally) one injected
enqueue callable.  Nothing in the planning path performs an external write or
queue operation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .adapters.camera import (
    CameraAdapterError,
    is_pinned_camera_profile,
    normalize_camera_api_graph,
    patch_img2img_graph,
    verify_img2img_path,
)
from .adapters.yusu_timeline import YusuTimelineError, patch_yusu_timeline, validate_yusu_sync
from .artifacts import verify_video_artifact
from .capabilities import report_is_fresh
from .contracts import canonical_json, content_hash
from .execution import (
    _canonical_consumption_root,
    _utc_now,
    _validate_approval_event,
)
from .workflow_profile import structure_fingerprint
from .multiview_evidence import MultiviewEvidenceError, validate_png_file
from .stages import LTX_BASELINE_OUTPUT_HEIGHT, LTX_BASELINE_OUTPUT_WIDTH, ltx_output_frame_count


class StageExecutionError(ValueError):
    """Raised when Stage 3/4 evidence cannot satisfy the execution contract."""


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PROMPT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_STAGES = frozenset(("shot-image", "video"))
_LTX_PROFILE_ID = "ltx-yusu-director-v1"
_LTX_WORKFLOW_NAME = "LTX全新导演台工作流.json"
_LTX_PROFILE_HASH = "6a5789c245525a1d04607f06f8e029b6ffef398fa49c625832cfd80411a22df9"

_DRAFT_KEYS = frozenset(
    {
        "schema_version",
        "stage",
        "plan_state",
        "execution_approved",
        "local_only",
        "stage_plan_hash",
        "stage_plan",
        "workflow_profile_id",
        "profile_hash",
        "workflow_fingerprint",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "capability_report_hash",
        "patches",
        "g1_path_proof",
        "reference_acceptance_id",
        "expected_outputs",
        "immutable_inputs",
        "draft_hash",
    }
)
_APPROVAL_FIELDS = frozenset({"approval_event", "approval_id", "execution_plan_hash"})
_CONSUMPTION_KEYS = frozenset(
    {
        "schema_version",
        "stage",
        "approval_id",
        "execution_plan_hash",
        "draft_hash",
        "consumption_root",
        "enqueue_request_id",
        "consumed_at",
        "consumption_id",
    }
)
_SUBMISSION_KEYS = frozenset(
    {
        "schema_version",
        "stage",
        "submission_type",
        "execution_plan_hash",
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
    }
)
_SUBMISSION_INTENT_KEYS = frozenset(
    {
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
    }
)
_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "receipt_type",
        "stage",
        "status",
        "execution_plan_hash",
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
    }
)


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise StageExecutionError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StageExecutionError(f"{label} is required")
    return value.strip()


def _stage_plan(plan: object, expected_stage: str | None = None) -> dict:
    if not isinstance(plan, dict):
        raise StageExecutionError("stage plan must be an object")
    stage = plan.get("stage")
    if stage not in _STAGES or (expected_stage is not None and stage != expected_stage):
        raise StageExecutionError("stage plan stage is unsupported")
    if (
        plan.get("plan_state") != "draft"
        or plan.get("execution_approved") is not True
        or plan.get("local_only") is not True
    ):
        raise StageExecutionError("stage plan must be an explicitly approved intent draft")
    claimed = plan.get("plan_hash")
    unsigned = dict(plan)
    unsigned.pop("plan_hash", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise StageExecutionError("stage plan hash is not self-consistent")
    expected_outputs = ["image/png"] if stage == "shot-image" else ["video"]
    if plan.get("expected_outputs") != expected_outputs:
        raise StageExecutionError("stage plan expected outputs are invalid")
    prompt_build = plan.get("prompt_build")
    if not isinstance(prompt_build, dict):
        raise StageExecutionError("stage plan requires the exact PromptBuild")
    prompt_hash_key = "shot_prompt_build_hash" if stage == "shot-image" else "prompt_build_hash"
    if plan.get(prompt_hash_key) != content_hash(prompt_build):
        raise StageExecutionError("stage plan PromptBuild lineage is invalid")
    _sha(plan.get("profile_hash"), "stage plan profile_hash")
    if stage == "shot-image":
        if plan.get("workflow_profile_id") != "camera-anima-v1":
            raise StageExecutionError("Stage 3 requires camera-anima-v1")
        _sha(plan.get("reference_hash"), "stage plan reference_hash")
    else:
        if plan.get("workflow_profile_id") != "ltx-yusu-director-v1":
            raise StageExecutionError("Stage 4 requires ltx-yusu-director-v1")
        _sha(plan.get("workflow_hash"), "stage plan workflow_hash")
        _sha(plan.get("source_shot_hash"), "stage plan source_shot_hash")
        parameters = plan.get("parameters")
        if (
            not isinstance(parameters, dict)
            or parameters.get("frames") != 24
            or parameters.get("output_frames") != ltx_output_frame_count(24)
            or parameters.get("fps") != 24
            or parameters.get("output_width") != LTX_BASELINE_OUTPUT_WIDTH
            or parameters.get("output_height") != LTX_BASELINE_OUTPUT_HEIGHT
        ):
            raise StageExecutionError(
                "Stage 4 requires the fixed 24-frame/25-output-frame/24-fps/1024x704 baseline"
            )
    return copy.deepcopy(plan)


def _require_capability(report: object) -> dict:
    now = _utc_now()
    if not isinstance(report, dict) or report.get("schema_version") != "1.0":
        raise StageExecutionError("a current CapabilityReport is required")
    if not report_is_fresh(report, now):
        raise StageExecutionError("CapabilityReport must be fresh")
    try:
        reachable = report["comfyui"]["reachable"]
        classification = report["adapter"]["runtime_classification"]
        running = report["queue"]["running"]
        pending = report["queue"]["pending"]
    except (KeyError, TypeError) as exc:
        raise StageExecutionError("CapabilityReport is incomplete") from exc
    if reachable is not True or classification != "local":
        raise StageExecutionError("execution requires a reachable local runtime")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in (running, pending)):
        raise StageExecutionError("CapabilityReport queue counts must be non-negative integers")
    if running or pending:
        raise StageExecutionError("one ComfyUI job at a time is allowed")
    return copy.deepcopy(report)


def _profile_hash(profile: object, expected: object) -> str:
    if not isinstance(profile, dict):
        raise StageExecutionError("workflow profile is required")
    actual = content_hash(profile)
    _sha(expected, "stage plan profile_hash")
    if actual != expected:
        raise StageExecutionError("workflow profile does not match the stage plan")
    return actual


def _draft_hash(draft: dict) -> str:
    unsigned = dict(draft)
    unsigned.pop("draft_hash", None)
    return content_hash(unsigned)


def _validate_image_ref(image_ref: object, expected_hash: str) -> dict:
    if not isinstance(image_ref, dict):
        raise StageExecutionError("accepted shot image reference is required")
    if image_ref.get("artifact_type") != "ShotImage" or image_ref.get("accepted") is not True:
        raise StageExecutionError("shot image reference must be an accepted ShotImage")
    _sha(image_ref.get("content_hash"), "shot image content_hash")
    if image_ref["content_hash"] != expected_hash:
        raise StageExecutionError("shot image reference does not match the approved lineage")
    for key in ("imageFile", "imageB64"):
        _text(image_ref.get(key), f"shot image {key}")
    return copy.deepcopy(image_ref)


def _validate_reference_acceptance(reference: object, expected_hash: str) -> dict:
    if not isinstance(reference, dict) or reference.get("accepted") is not True:
        raise StageExecutionError("reference artifact must be explicitly accepted")
    if (
        reference.get("artifact_type") != "CharacterAngleView"
        or not isinstance(reference.get("view_label"), str)
        or not reference["view_label"].strip()
        or reference.get("reference_eligible") is not True
        or reference.get("semantic_conflict") is not False
        or reference.get("hash_verified") is not True
    ):
        raise StageExecutionError("reference artifact is not Stage 3 eligible")
    if reference.get("content_hash") != expected_hash:
        raise StageExecutionError("reference artifact does not match the stage plan")
    acceptance = reference.get("acceptance")
    if not isinstance(acceptance, dict) or set(acceptance) != {
        "schema_version", "artifact_hash", "actor", "accepted_at", "acceptance_id"
    }:
        raise StageExecutionError("reference acceptance evidence is missing")
    if acceptance.get("schema_version") != "1.0" or acceptance.get("artifact_hash") != expected_hash:
        raise StageExecutionError("reference acceptance lineage is invalid")
    _text(acceptance.get("actor"), "reference acceptance actor")
    accepted_at = acceptance.get("accepted_at")
    if not isinstance(accepted_at, str):
        raise StageExecutionError("reference acceptance timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(accepted_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StageExecutionError("reference acceptance timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise StageExecutionError("reference acceptance timestamp must be UTC")
    unsigned = dict(acceptance)
    acceptance_id = unsigned.pop("acceptance_id", None)
    if not isinstance(acceptance_id, str) or acceptance_id != content_hash(unsigned):
        raise StageExecutionError("reference acceptance hash is invalid")
    if reference.get("acceptance_id") != acceptance_id:
        raise StageExecutionError("reference acceptance_id is invalid")
    return copy.deepcopy(reference)


def build_stage_execution_draft(
    stage_plan: dict,
    source_api_graph: dict,
    profile: dict,
    capability_report: dict,
    *,
    ui_workflow: dict | None = None,
    image_name: str | None = None,
    reference_artifact: dict | None = None,
    image_ref: dict | None = None,
) -> dict:
    """Bind a Stage 3/4 intent plan to fresh local evidence, without enqueueing."""
    plan = _stage_plan(stage_plan)
    if not isinstance(source_api_graph, dict):
        raise StageExecutionError("source API graph must be an object")
    report = _require_capability(capability_report)
    profile_digest = _profile_hash(profile, plan.get("profile_hash"))
    source_hash = content_hash(source_api_graph)
    declared_capability_hash = _sha(
        plan.get("capability_report_hash"), "stage plan capability_report_hash"
    )
    if declared_capability_hash != content_hash(report):
        raise StageExecutionError("CapabilityReport does not match the stage plan")

    executable: dict
    path_proof = None
    reference_acceptance_id = None
    workflow_fingerprint = plan.get("workflow_fingerprint")
    if workflow_fingerprint is not None:
        _sha(workflow_fingerprint, "workflow_fingerprint")

    if plan["stage"] == "shot-image":
        if not isinstance(ui_workflow, dict):
            raise StageExecutionError("Stage 3 requires the current camera UI workflow")
        if not is_pinned_camera_profile(profile):
            raise StageExecutionError(
                "Stage 3 requires the pinned camera normalization profile"
            )
        if image_name is None:
            raise StageExecutionError("Stage 3 requires the selected reference image name")
        if workflow_fingerprint is None:
            raise StageExecutionError("Stage 3 requires the current camera UI fingerprint")
        try:
            normalized_source = normalize_camera_api_graph(source_api_graph, ui_workflow, profile)
            if normalized_source != source_api_graph:
                raise StageExecutionError(
                    "Stage 3 source API graph must be normalized with normalize-camera before planning"
                )
            actual_fingerprint = structure_fingerprint(ui_workflow)
            # Stage 3 requires a strict identity pin; it cannot be silently replaced.
            if workflow_fingerprint != actual_fingerprint:
                raise StageExecutionError("camera UI workflow fingerprint does not match the stage plan")
            profile_fingerprint = profile.get("workflow_fingerprint")
            if (
                not isinstance(profile_fingerprint, str)
                or not re.fullmatch(r"[0-9a-f]{64}", profile_fingerprint)
                or profile_fingerprint != actual_fingerprint
            ):
                raise StageExecutionError(
                    "camera UI workflow fingerprint does not match the verified camera profile"
                )
            executable = patch_img2img_graph(
                source_api_graph,
                plan.get("prompt_build"),
                image_name,
                profile,
            )
            path_proof = verify_img2img_path(executable, profile)
        except (CameraAdapterError, TypeError, KeyError) as exc:
            raise StageExecutionError(f"camera img2img graph failed validation: {exc}") from exc
        declared_proof = plan.get("g1_path_proof")
        if isinstance(declared_proof, dict) and declared_proof.get("traversed_node_ids"):
            if declared_proof["traversed_node_ids"] != path_proof["traversed_node_ids"]:
                raise StageExecutionError("G1 path proof does not match the executable graph")
        if reference_artifact is None:
            raise StageExecutionError("Stage 3 requires explicit reference acceptance evidence")
        accepted_reference = _validate_reference_acceptance(reference_artifact, plan.get("reference_hash"))
        reference_acceptance_id = accepted_reference["acceptance_id"]
        expected_outputs = ["image/png"]
        immutable_inputs = {"graph_topology": "source_api_graph_hash"}
    else:
        if not isinstance(image_ref, dict):
            raise StageExecutionError("Stage 4 requires a shot image reference")
        if (
            profile.get("profile_id") != _LTX_PROFILE_ID
            or profile.get("workflow_name") != _LTX_WORKFLOW_NAME
            or profile.get("runtime_classification") != "local"
            or profile.get("generation_modes") != ["image-to-video"]
            or profile.get("output_frame_rule") != "8n+1"
            or profile.get("baseline_output_frames") != ltx_output_frame_count(24)
            or profile.get("effective_output_resolution")
            != {"width": LTX_BASELINE_OUTPUT_WIDTH, "height": LTX_BASELINE_OUTPUT_HEIGHT}
            or profile.get("effective_resize_method") != "maintain aspect ratio"
            or profile.get("output_divisible_by") != 32
        ):
            raise StageExecutionError(
                "Stage 4 requires the exact local LTX Director workflow profile"
            )
        if profile_digest != _LTX_PROFILE_HASH:
            raise StageExecutionError("Stage 4 requires the trusted LTX profile contract")
        profile_fingerprint = profile.get("workflow_fingerprint")
        if (
            workflow_fingerprint is None
            or not re.fullmatch(r"[0-9a-f]{64}", profile_fingerprint or "")
            or workflow_fingerprint != profile_fingerprint
        ):
            raise StageExecutionError("Stage 4 workflow fingerprint does not match the LTX profile")
        _validate_image_ref(image_ref, plan.get("source_shot_hash"))
        try:
            if plan.get("workflow_hash") is not None and plan["workflow_hash"] != source_hash:
                raise StageExecutionError("LTX API graph does not match the stage plan workflow hash")
            executable = patch_yusu_timeline(
                source_api_graph,
                {key: image_ref[key] for key in ("imageFile", "imageB64")},
                plan["prompt_build"]["prompt"],
                plan["parameters"]["frames"],
                plan["parameters"]["fps"],
                profile,
            )
            validate_yusu_sync(executable, profile)
        except (YusuTimelineError, TypeError, KeyError) as exc:
            raise StageExecutionError(f"Yusu Director graph failed validation: {exc}") from exc
        expected_outputs = ["video"]
        immutable_inputs = copy.deepcopy(profile.get("immutable_inputs", {}))

    if content_hash(executable) == source_hash:
        raise StageExecutionError("execution patch produced no graph change")
    draft = {
        "schema_version": "1.0",
        "stage": plan["stage"],
        "plan_state": "draft",
        "execution_approved": False,
        "local_only": True,
        "stage_plan_hash": plan["plan_hash"],
        "stage_plan": plan,
        "workflow_profile_id": plan["workflow_profile_id"],
        "profile_hash": profile_digest,
        "workflow_fingerprint": workflow_fingerprint,
        "source_api_graph_hash": source_hash,
        "executable_api_graph_hash": content_hash(executable),
        "capability_report_hash": content_hash(report),
        "patches": copy.deepcopy(plan.get("patches", [])),
        "g1_path_proof": path_proof,
        "reference_acceptance_id": reference_acceptance_id,
        "expected_outputs": expected_outputs,
        "immutable_inputs": immutable_inputs,
    }
    draft["draft_hash"] = _draft_hash(draft)
    return draft


def _validate_stage_draft(draft: object) -> dict:
    if not isinstance(draft, dict) or set(draft) != _DRAFT_KEYS:
        raise StageExecutionError("StageExecutionDraft schema is incomplete or contains unexpected fields")
    if draft.get("schema_version") != "1.0" or draft.get("stage") not in _STAGES:
        raise StageExecutionError("StageExecutionDraft stage is unsupported")
    if (
        draft.get("plan_state") != "draft"
        or draft.get("execution_approved") is not False
        or draft.get("local_only") is not True
    ):
        raise StageExecutionError("StageExecutionDraft must remain unapproved")
    plan = _stage_plan(draft.get("stage_plan"), draft.get("stage"))
    if draft.get("stage_plan_hash") != plan["plan_hash"]:
        raise StageExecutionError("StageExecutionDraft stage plan lineage is invalid")
    if draft.get("workflow_profile_id") != plan.get("workflow_profile_id"):
        raise StageExecutionError("StageExecutionDraft workflow profile lineage is invalid")
    if draft.get("profile_hash") != plan.get("profile_hash"):
        raise StageExecutionError("StageExecutionDraft profile lineage is invalid")
    if draft.get("capability_report_hash") != plan.get("capability_report_hash"):
        raise StageExecutionError("StageExecutionDraft capability lineage is invalid")
    if draft.get("workflow_fingerprint") != plan.get("workflow_fingerprint"):
        raise StageExecutionError("StageExecutionDraft workflow fingerprint lineage is invalid")
    claimed = draft.get("draft_hash")
    if not isinstance(claimed, str) or claimed != _draft_hash(draft):
        raise StageExecutionError("StageExecutionDraft draft_hash is not self-consistent")
    for field in ("profile_hash", "source_api_graph_hash", "executable_api_graph_hash", "capability_report_hash"):
        _sha(draft.get(field), f"StageExecutionDraft {field}")
    expected_outputs = ["image/png"] if draft["stage"] == "shot-image" else ["video"]
    if draft.get("expected_outputs") != expected_outputs:
        raise StageExecutionError("StageExecutionDraft expected outputs are invalid")
    if draft["stage"] == "shot-image":
        _sha(draft.get("reference_acceptance_id"), "StageExecutionDraft reference_acceptance_id")
        if not isinstance(draft.get("g1_path_proof"), dict):
            raise StageExecutionError("StageExecutionDraft requires G1 path proof")
    elif draft.get("reference_acceptance_id") is not None:
        raise StageExecutionError("video StageExecutionDraft cannot carry reference acceptance")
    elif draft.get("g1_path_proof") is not None:
        raise StageExecutionError("video StageExecutionDraft cannot carry G1 path proof")
    return copy.deepcopy(draft)


def approve_stage_execution_draft(
    draft: dict,
    approval_event: dict,
    consumption_root: str | Path,
) -> dict:
    """Approve one displayed Stage 3/4 draft with an exact fresh event."""
    safe = _validate_stage_draft(draft)
    try:
        event = _validate_approval_event(
            approval_event,
            safe["draft_hash"],
            trusted_now=_utc_now(),
            expected_consumption_root=consumption_root,
        )
    except Exception as exc:
        raise StageExecutionError(str(exc)) from exc
    plan = copy.deepcopy(safe)
    plan["plan_state"] = "approved"
    plan["execution_approved"] = True
    plan["approval_event"] = event
    plan["approval_id"] = content_hash(event)
    unsigned = dict(plan)
    unsigned.pop("execution_plan_hash", None)
    plan["execution_plan_hash"] = content_hash(unsigned)
    return plan


def _validate_approved_stage(plan: object) -> dict:
    if not isinstance(plan, dict) or set(plan) != _DRAFT_KEYS.union(_APPROVAL_FIELDS):
        raise StageExecutionError("approved StageExecutionPlan schema is invalid")
    safe_draft = dict(plan)
    safe_draft.pop("approval_event", None)
    safe_draft.pop("approval_id", None)
    safe_draft.pop("execution_plan_hash", None)
    safe_draft["plan_state"] = "draft"
    safe_draft["execution_approved"] = False
    _validate_stage_draft(safe_draft)
    if plan.get("plan_state") != "approved" or plan.get("execution_approved") is not True:
        raise StageExecutionError("approved StageExecutionPlan is not approved")
    try:
        event = _validate_approval_event(
            plan.get("approval_event"),
            plan["draft_hash"],
            trusted_now=_utc_now(),
            expected_consumption_root=None,
        )
    except Exception as exc:
        raise StageExecutionError(str(exc)) from exc
    if plan.get("approval_id") != content_hash(event):
        raise StageExecutionError("approved StageExecutionPlan approval_id is invalid")
    unsigned = dict(plan)
    claimed = unsigned.pop("execution_plan_hash", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise StageExecutionError("approved StageExecutionPlan hash is invalid")
    return copy.deepcopy(plan)


def build_stage_consumption(approved_plan: dict, enqueue_request_id: str) -> dict:
    """Consume an approved stage exactly once for one enqueue request identity."""
    plan = _validate_approved_stage(approved_plan)
    request_id = _text(enqueue_request_id, "enqueue_request_id")
    if len(request_id) > 256:
        raise StageExecutionError("enqueue_request_id is too long")
    root = _canonical_consumption_root(plan["approval_event"]["consumption_root"], "stage")
    consumed_at = _utc_now()
    event_time = datetime.fromisoformat(plan["approval_event"]["approved_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(plan["approval_event"]["expires_at"].replace("Z", "+00:00"))
    if not event_time <= consumed_at < expires:
        raise StageExecutionError("stage approval is outside its consumption window")
    record = {
        "schema_version": "1.0",
        "stage": plan["stage"],
        "approval_id": plan["approval_id"],
        "execution_plan_hash": plan["execution_plan_hash"],
        "draft_hash": plan["draft_hash"],
        "consumption_root": root,
        "enqueue_request_id": request_id,
        "consumed_at": consumed_at.isoformat().replace("+00:00", "Z"),
    }
    record["consumption_id"] = content_hash(record)
    return record


def _consumption_path(root: str, consumption: dict) -> Path:
    return Path(root) / f"stage-{consumption['stage']}-{consumption['approval_id']}.consumed.json"


def write_stage_consumption(root: str | Path, consumption: dict) -> Path:
    if not isinstance(consumption, dict) or set(consumption) != _CONSUMPTION_KEYS:
        raise StageExecutionError("stage consumption schema is invalid")
    claimed = consumption.get("consumption_id")
    unsigned = dict(consumption)
    unsigned.pop("consumption_id", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise StageExecutionError("stage consumption hash is invalid")
    canonical_root = _canonical_consumption_root(root, "stage")
    if consumption.get("consumption_root") != canonical_root:
        raise StageExecutionError("stage consumption root is not canonical")
    path = _consumption_path(canonical_root, consumption)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(consumption))
            handle.write("\n")
    except FileExistsError as exc:
        raise StageExecutionError(f"stage consumption already exists: {path}") from exc
    return path.resolve()


def _validate_consumption(plan: dict, consumption: object, path: str | Path) -> dict:
    if not isinstance(consumption, dict) or set(consumption) != _CONSUMPTION_KEYS:
        raise StageExecutionError("stage consumption schema is invalid")
    if any(consumption.get(field) != plan.get(field) for field in ("stage", "approval_id", "execution_plan_hash", "draft_hash")):
        raise StageExecutionError("stage consumption does not match the approved plan")
    claimed = consumption.get("consumption_id")
    unsigned = dict(consumption)
    unsigned.pop("consumption_id", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise StageExecutionError("stage consumption hash is invalid")
    root = _canonical_consumption_root(consumption.get("consumption_root"), "stage")
    expected_root = _canonical_consumption_root(
        plan["approval_event"].get("consumption_root"), "stage"
    )
    if root != expected_root:
        raise StageExecutionError("stage consumption root does not match the approval event")
    expected = _consumption_path(root, consumption)
    raw = Path(path)
    try:
        resolved = raw.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StageExecutionError("stage consumption evidence is missing") from exc
    if str(raw) != str(resolved) or resolved != expected:
        raise StageExecutionError("stage consumption evidence path is not canonical")
    try:
        retained = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StageExecutionError("stage consumption evidence is invalid JSON") from exc
    if canonical_json(retained) != canonical_json(consumption):
        raise StageExecutionError("stage consumption evidence does not match the supplied record")
    return copy.deepcopy(consumption)


def build_stage_submission(
    approved_plan: dict,
    source_api_graph: dict,
    consumption: dict,
    consumption_path: str | Path,
    *,
    profile: dict,
    capability_report: dict,
    ui_workflow: dict | None = None,
    reference_image_name: str | None = None,
    reference_artifact: dict | None = None,
    image_ref: dict | None = None,
) -> dict:
    """Build the exact graph/request authorized by one consumed plan."""
    plan = _validate_approved_stage(approved_plan)
    _validate_consumption(plan, consumption, consumption_path)
    _require_capability(capability_report)
    if content_hash(capability_report) != plan["capability_report_hash"]:
        raise StageExecutionError("current CapabilityReport does not match the approved plan")
    _profile_hash(profile, plan["profile_hash"])
    if not isinstance(source_api_graph, dict) or content_hash(source_api_graph) != plan["source_api_graph_hash"]:
        raise StageExecutionError("source API graph does not match the approved plan")
    stage_plan = plan["stage_plan"]
    workflow_fingerprint = plan.get("workflow_fingerprint")
    if not isinstance(workflow_fingerprint, str):
        raise StageExecutionError("stage submission requires the approved workflow fingerprint")
    if ui_workflow is not None:
        if not isinstance(ui_workflow, dict):
            raise StageExecutionError("stage submission UI workflow must be an object")
        try:
            actual_ui_fingerprint = structure_fingerprint(ui_workflow)
        except (TypeError, ValueError, KeyError) as exc:
            raise StageExecutionError("stage submission UI workflow is malformed") from exc
        if actual_ui_fingerprint != workflow_fingerprint:
            raise StageExecutionError("stage submission UI workflow fingerprint does not match the approved plan")
    if plan["stage"] == "shot-image":
        if not isinstance(ui_workflow, dict):
            raise StageExecutionError("Stage 3 submission requires the current camera UI workflow")
        if reference_image_name is None:
            raise StageExecutionError("Stage 3 submission requires a reference image name")
        accepted_reference = _validate_reference_acceptance(reference_artifact, stage_plan.get("reference_hash"))
        if accepted_reference["acceptance_id"] != plan["reference_acceptance_id"]:
            raise StageExecutionError("Stage 3 submission reference acceptance does not match the approved draft")
        try:
            executable = patch_img2img_graph(
                source_api_graph,
                stage_plan.get("prompt_build"),
                reference_image_name,
                profile,
            )
            proof = verify_img2img_path(executable, profile)
        except (CameraAdapterError, TypeError, KeyError) as exc:
            raise StageExecutionError(f"Stage 3 submission graph failed validation: {exc}") from exc
        if proof != plan["g1_path_proof"]:
            raise StageExecutionError("Stage 3 submission G1 proof does not match the approved plan")
    else:
        image = _validate_image_ref(image_ref, stage_plan["source_shot_hash"])
        try:
            executable = patch_yusu_timeline(
                source_api_graph,
                {key: image[key] for key in ("imageFile", "imageB64")},
                stage_plan["prompt_build"]["prompt"],
                stage_plan["parameters"]["frames"],
                stage_plan["parameters"]["fps"],
                profile,
            )
            validate_yusu_sync(executable, profile)
        except (YusuTimelineError, TypeError, KeyError) as exc:
            raise StageExecutionError(f"Stage 4 submission graph failed validation: {exc}") from exc
    if content_hash(executable) != plan["executable_api_graph_hash"]:
        raise StageExecutionError("executable API graph does not match the approved plan")
    request = {
        "prompt": executable,
        "client_id": consumption["enqueue_request_id"],
        "extra_data": {
            "prompt_forge_stage": plan["stage"],
            "prompt_forge_execution_plan_hash": plan["execution_plan_hash"],
            "prompt_forge_consumption_id": consumption["consumption_id"],
            "prompt_forge_enqueue_request_id": consumption["enqueue_request_id"],
            "prompt_forge_workflow_fingerprint": workflow_fingerprint,
        },
    }
    if ui_workflow is not None:
        request["extra_data"]["extra_pnginfo"] = {"workflow": copy.deepcopy(ui_workflow)}
    submission = {
        "schema_version": "1.0",
        "stage": plan["stage"],
        "submission_type": "prompt-forge-stage-enqueue",
        "execution_plan_hash": plan["execution_plan_hash"],
        "draft_hash": plan["draft_hash"],
        "approval_id": plan["approval_id"],
        "consumption_id": consumption["consumption_id"],
        "consumption_root": consumption["consumption_root"],
        "enqueue_request_id": consumption["enqueue_request_id"],
        "source_api_graph_hash": plan["source_api_graph_hash"],
        "executable_api_graph_hash": plan["executable_api_graph_hash"],
        "workflow_fingerprint": workflow_fingerprint,
        "api_graph": executable,
        "request": request,
    }
    submission["submission_hash"] = content_hash(submission)
    return submission


def _stage_submission_intent(submission: dict) -> dict:
    intent = {
        "schema_version": "1.0",
        "intent_type": "prompt-forge-stage-enqueue",
        "status": "in-progress",
        "stage": submission["stage"],
        "consumption_id": submission["consumption_id"],
        "enqueue_request_id": submission["enqueue_request_id"],
        "submission_hash": submission["submission_hash"],
        "submitted_graph_hash": submission["executable_api_graph_hash"],
        "request": copy.deepcopy(submission["request"]),
    }
    intent["intent_hash"] = content_hash(intent)
    return intent


def _write_stage_evidence(path: Path, value: dict, label: str) -> Path:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(value))
            handle.write("\n")
    except FileExistsError as exc:
        raise StageExecutionError(f"{label} already exists: {path}") from exc
    return path.resolve()


def _read_stage_evidence(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StageExecutionError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise StageExecutionError(f"{label} schema is invalid")
    return value


def _validate_stage_submission_intent(value: object, expected: dict) -> dict:
    if not isinstance(value, dict) or set(value) != _SUBMISSION_INTENT_KEYS:
        raise StageExecutionError("existing stage enqueue intent schema is invalid")
    unsigned = dict(value)
    claimed = unsigned.pop("intent_hash", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise StageExecutionError("existing stage enqueue intent hash is invalid")
    if value != expected:
        raise StageExecutionError("existing stage enqueue intent binds a different graph, hash, or request")
    return copy.deepcopy(value)


def submit_stage(
    submission: dict,
    enqueue_callable: Callable[[dict], dict],
    *,
    receipt_path: str | Path,
) -> dict:
    """Invoke one injected local enqueue callable behind an exclusive intent.

    The receipt path is deterministic within the consumed namespace. An
    exclusive intent is written before the callable runs, so a retry,
    concurrent caller, or process recovering from an uncertain POST cannot
    enqueue the same request twice.
    """
    if not isinstance(submission, dict) or set(submission) != _SUBMISSION_KEYS:
        raise StageExecutionError("stage submission is invalid")
    if (
        submission.get("schema_version") != "1.0"
        or submission.get("submission_type") != "prompt-forge-stage-enqueue"
        or submission.get("stage") not in _STAGES
    ):
        raise StageExecutionError("stage submission is invalid")
    for field in (
        "execution_plan_hash",
        "draft_hash",
        "approval_id",
        "consumption_id",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "workflow_fingerprint",
    ):
        _sha(submission.get(field), f"stage submission {field}")
    _text(submission.get("enqueue_request_id"), "stage submission enqueue_request_id")
    if not isinstance(submission.get("api_graph"), dict) or not isinstance(submission.get("request"), dict):
        raise StageExecutionError("stage submission graph and request are required objects")
    _validate_submission_request(submission)
    try:
        root = Path(_canonical_consumption_root(submission.get("consumption_root"), "stage submission"))
    except Exception as exc:
        raise StageExecutionError("stage submission consumption_root is invalid") from exc
    claimed = submission.get("submission_hash")
    unsigned = dict(submission)
    unsigned.pop("submission_hash", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise StageExecutionError("stage submission hash is invalid")
    if not callable(enqueue_callable):
        raise StageExecutionError("an injected enqueue callable is required")
    path = Path(receipt_path)
    if not path.is_absolute():
        raise StageExecutionError("stage receipt path must be absolute")
    try:
        path = path.resolve()
    except (OSError, RuntimeError) as exc:
        raise StageExecutionError("stage receipt path is invalid") from exc
    expected_path = root / f'{submission["consumption_id"]}.stage-enqueue-receipt.json'
    if path != expected_path:
        raise StageExecutionError("stage receipt path must be the canonical consumed-namespace path")
    if not path.parent.is_dir():
        raise StageExecutionError("stage receipt parent directory is missing")
    intent_path = root / f'{submission["consumption_id"]}.stage-enqueue-intent.json'
    if path.is_file() and not intent_path.is_file():
        raise StageExecutionError("stage receipt exists without its submission intent")
    intent = _stage_submission_intent(submission)
    try:
        _write_stage_evidence(intent_path, intent, "stage enqueue intent")
    except StageExecutionError as exc:
        if not intent_path.is_file():
            raise
        _validate_stage_submission_intent(
            _read_stage_evidence(intent_path, "existing stage enqueue intent"), intent
        )
        if path.is_file():
            retained = _read_stage_evidence(path, "existing stage enqueue receipt")
            return _validate_stage_receipt(submission, retained)
        raise StageExecutionError(
            f"stage enqueue already has a retained intent; query server state before retrying: {intent_path}"
        ) from exc
    try:
        response = enqueue_callable(copy.deepcopy(submission["request"]))
    except Exception as exc:
        raise StageExecutionError(f"stage enqueue callable failed: {exc}") from exc
    if (
        not isinstance(response, dict)
        or not isinstance(response.get("prompt_id"), str)
        or not _PROMPT_ID_RE.fullmatch(response.get("prompt_id", ""))
    ):
        raise StageExecutionError("stage enqueue response prompt_id is invalid")
    if response.get("node_errors") not in ({}, None):
        raise StageExecutionError("stage enqueue response contains node errors")
    receipt = {
        "schema_version": "1.0",
        "receipt_type": "prompt-forge-stage-enqueue",
        "stage": submission["stage"],
        "status": "succeeded",
        "execution_plan_hash": submission["execution_plan_hash"],
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
    _write_stage_evidence(path, receipt, "stage enqueue receipt")
    return receipt


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise StageExecutionError("artifact bytes cannot be read") from exc
    return digest.hexdigest()


def _validate_stage_receipt(submission: dict, receipt: object) -> dict:
    if not isinstance(receipt, dict) or set(receipt) != _RECEIPT_KEYS:
        raise StageExecutionError("stage enqueue receipt is invalid")
    unsigned = dict(receipt)
    claimed = unsigned.pop("receipt_hash", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise StageExecutionError("stage enqueue receipt hash is invalid")
    if (
        receipt.get("schema_version") != "1.0"
        or receipt.get("receipt_type") != "prompt-forge-stage-enqueue"
        or receipt.get("stage") != submission.get("stage")
        or receipt.get("status") != "succeeded"
        or receipt.get("execution_plan_hash") != submission.get("execution_plan_hash")
        or receipt.get("enqueue_request_id") != submission.get("enqueue_request_id")
        or receipt.get("orchestrator")
        != {"name": "prompt-forge", "trust_model": "trusted-local-orchestrator"}
    ):
        raise StageExecutionError("stage run requires a succeeded enqueue receipt")
    if receipt.get("submission_hash") != submission.get("submission_hash"):
        raise StageExecutionError("stage enqueue receipt submission_hash does not match submission")
    if receipt.get("consumption_id") != submission.get("consumption_id"):
        raise StageExecutionError("stage enqueue receipt consumption_id does not match submission")
    if receipt.get("submitted_graph_hash") != submission.get("executable_api_graph_hash"):
        raise StageExecutionError("stage enqueue receipt graph does not match submission")
    response = receipt.get("response")
    if (
        not isinstance(response, dict)
        or not isinstance(receipt.get("prompt_id"), str)
        or not _PROMPT_ID_RE.fullmatch(receipt.get("prompt_id", ""))
        or receipt.get("prompt_id") != response.get("prompt_id")
        or response.get("node_errors") not in ({}, None)
    ):
        raise StageExecutionError("stage enqueue receipt prompt_id is invalid")
    if receipt.get("response_digest") != content_hash(response):
        raise StageExecutionError("stage enqueue receipt response digest is invalid")
    if receipt.get("request") != submission.get("request"):
        raise StageExecutionError("stage enqueue receipt request does not match submission")
    return copy.deepcopy(receipt)


def _validate_stage_submission(submission: object, plan: dict) -> dict:
    if not isinstance(submission, dict) or set(submission) != _SUBMISSION_KEYS:
        raise StageExecutionError("stage submission schema is invalid")
    if (
        submission.get("schema_version") != "1.0"
        or submission.get("submission_type") != "prompt-forge-stage-enqueue"
        or submission.get("stage") != plan["stage"]
        or submission.get("execution_plan_hash") != plan["execution_plan_hash"]
        or submission.get("draft_hash") != plan["draft_hash"]
        or submission.get("approval_id") != plan["approval_id"]
        or submission.get("workflow_fingerprint") != plan.get("workflow_fingerprint")
    ):
        raise StageExecutionError("stage submission does not match the approved plan")
    try:
        actual_root = _canonical_consumption_root(submission.get("consumption_root"), "stage submission")
        expected_root = _canonical_consumption_root(
            plan["approval_event"].get("consumption_root"), "stage submission"
        )
    except Exception as exc:
        raise StageExecutionError("stage submission consumption_root is invalid") from exc
    if actual_root != expected_root:
        raise StageExecutionError("stage submission consumption_root does not match the approval event")
    for field in (
        "consumption_id",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "workflow_fingerprint",
    ):
        _sha(submission.get(field), f"stage submission {field}")
    _text(submission.get("enqueue_request_id"), "stage submission enqueue_request_id")
    if not isinstance(submission.get("api_graph"), dict) or not isinstance(submission.get("request"), dict):
        raise StageExecutionError("stage submission graph and request are required objects")
    _validate_submission_request(submission)
    claimed = submission.get("submission_hash")
    unsigned = dict(submission)
    unsigned.pop("submission_hash", None)
    if not isinstance(claimed, str) or claimed != content_hash(unsigned):
        raise StageExecutionError("stage submission hash is invalid")
    return copy.deepcopy(submission)


def _validate_submission_request(submission: dict) -> None:
    request = submission.get("request")
    if not isinstance(request, dict) or set(request) != {"prompt", "client_id", "extra_data"}:
        raise StageExecutionError("stage submission request schema is invalid")
    if canonical_json(request["prompt"]) != canonical_json(submission.get("api_graph")):
        raise StageExecutionError("stage submission request graph does not match api_graph")
    if request.get("client_id") != submission.get("enqueue_request_id"):
        raise StageExecutionError("stage submission request client_id does not match enqueue_request_id")
    expected_extra = {
        "prompt_forge_stage": submission.get("stage"),
        "prompt_forge_execution_plan_hash": submission.get("execution_plan_hash"),
        "prompt_forge_consumption_id": submission.get("consumption_id"),
        "prompt_forge_enqueue_request_id": submission.get("enqueue_request_id"),
        "prompt_forge_workflow_fingerprint": submission.get("workflow_fingerprint"),
    }
    extra_data = request.get("extra_data")
    if not isinstance(extra_data, dict):
        raise StageExecutionError("stage submission request provenance does not match submission")
    if any(extra_data.get(key) != value for key, value in expected_extra.items()):
        raise StageExecutionError("stage submission request provenance does not match submission")
    unexpected = set(extra_data) - set(expected_extra) - {"extra_pnginfo"}
    if unexpected:
        raise StageExecutionError("stage submission request provenance contains unexpected fields")
    pnginfo = extra_data.get("extra_pnginfo")
    if pnginfo is not None and (
        not isinstance(pnginfo, dict) or not isinstance(pnginfo.get("workflow"), dict)
    ):
        raise StageExecutionError("stage submission request UI provenance is invalid")
    if pnginfo is not None:
        try:
            actual_ui_fingerprint = structure_fingerprint(pnginfo["workflow"])
        except (TypeError, ValueError, KeyError) as exc:
            raise StageExecutionError("stage submission request UI workflow is malformed") from exc
        if actual_ui_fingerprint != submission.get("workflow_fingerprint"):
            raise StageExecutionError(
                "stage submission request UI provenance fingerprint does not match the approved workflow"
            )


def _validate_artifact_bytes(
    artifact: dict,
    stage_plan: dict,
    output_root: str | Path | None = None,
) -> dict:
    artifact_type = "ShotImage" if stage_plan["stage"] == "shot-image" else "VideoClip"
    if artifact.get("artifact_type") != artifact_type or artifact.get("accepted") is not True:
        raise StageExecutionError(f"stage artifact must be an accepted {artifact_type}")
    declared_hash = _sha(artifact.get("content_hash"), "artifact content_hash")
    raw_path = artifact.get("artifact_path")
    if not isinstance(raw_path, str) or not Path(raw_path).is_absolute():
        raise StageExecutionError("artifact_path must be an absolute canonical path")
    path = Path(raw_path)
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StageExecutionError("artifact_path does not exist") from exc
    if str(path) != str(resolved) or not resolved.is_file():
        raise StageExecutionError("artifact_path must be an absolute canonical file")
    declared_root = output_root if output_root is not None else artifact.get("artifact_root")
    if declared_root is not None:
        if not isinstance(declared_root, (str, Path)):
            raise StageExecutionError("artifact output root must be an absolute canonical directory")
        root_text = str(declared_root)
        root = Path(root_text)
        if not root.is_absolute():
            raise StageExecutionError("artifact output root must be an absolute canonical directory")
        try:
            resolved_root = root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise StageExecutionError("artifact output root must be an existing canonical directory") from exc
        if str(root) != str(resolved_root) or not resolved_root.is_dir():
            raise StageExecutionError("artifact output root must be an existing canonical directory")
        if not resolved.is_relative_to(resolved_root):
            raise StageExecutionError("artifact_path must remain inside the canonical output root")
    actual_hash = _file_sha256(resolved)
    if actual_hash != declared_hash:
        raise StageExecutionError("artifact bytes do not match content_hash")
    normalized = copy.deepcopy(artifact)
    normalized["artifact_path"] = str(resolved)
    if declared_root is not None:
        normalized["artifact_root"] = str(resolved_root)
    if stage_plan["stage"] == "shot-image":
        if normalized.get("source_reference_hash") != stage_plan.get("reference_hash"):
            raise StageExecutionError("ShotImage reference lineage does not match the plan")
        try:
            validate_png_file(resolved)
        except (MultiviewEvidenceError, OSError) as exc:
            raise StageExecutionError("ShotImage bytes are not a structurally valid PNG") from exc
    else:
        if normalized.get("source_shot_hash") != stage_plan.get("source_shot_hash"):
            raise StageExecutionError("VideoClip shot lineage does not match the plan")
        metadata = normalized.get("metadata")
        if not isinstance(metadata, dict):
            raise StageExecutionError("VideoClip technical metadata is required")
        verified = verify_video_artifact(
            metadata,
            stage_plan["parameters"]["fps"],
            stage_plan["parameters"]["output_frames"],
            expected_width=stage_plan["parameters"]["output_width"],
            expected_height=stage_plan["parameters"]["output_height"],
            source_shot_hash=stage_plan["source_shot_hash"],
            artifact_path=resolved,
        )
        normalized["technical"] = verified
    return normalized


def build_stage_run_record(
    approved_plan: dict,
    submission: dict,
    enqueue_receipt: dict,
    artifact: dict,
    *,
    history: dict | None = None,
    artifact_root: str | Path | None = None,
) -> dict:
    """Create a terminal Stage 3/4 RunRecord from immutable output evidence.

    Raw ComfyUI history is mandatory for a successful record.  A receipt and
    a caller-authored artifact descriptor alone cannot prove that the server
    executed the exact submitted graph.
    """
    plan = _validate_approved_stage(approved_plan)
    safe_submission = _validate_stage_submission(submission, plan)
    receipt = _validate_stage_receipt(safe_submission, enqueue_receipt)
    safe_artifact = _validate_artifact_bytes(artifact, plan["stage_plan"], artifact_root)
    prompt_id = receipt.get("prompt_id")
    if not isinstance(history, dict) or not isinstance(history.get(prompt_id), dict):
        raise StageExecutionError("raw ComfyUI history is missing the stage prompt_id")
    entry = history[prompt_id]
    prompt = entry.get("prompt")
    status = entry.get("status")
    if not isinstance(prompt, list) or len(prompt) < 3 or prompt[1] != prompt_id:
        raise StageExecutionError("raw ComfyUI history prompt tuple is invalid")
    if canonical_json(prompt[2]) != canonical_json(safe_submission["api_graph"]):
        raise StageExecutionError("raw ComfyUI history graph does not match submission")
    if len(prompt) < 4 or not isinstance(prompt[3], dict):
        raise StageExecutionError("raw ComfyUI history enqueue metadata is missing")
    history_extra = prompt[3].get("extra_data")
    if not isinstance(history_extra, dict):
        raise StageExecutionError("raw ComfyUI history enqueue metadata is invalid")
    if history_extra.get("prompt_forge_enqueue_request_id") != safe_submission["enqueue_request_id"]:
        raise StageExecutionError("raw ComfyUI history enqueue request identity does not match submission")
    if status != {"status_str": "success", "completed": True}:
        raise StageExecutionError("raw ComfyUI history status is not succeeded")
    history_verified = True
    stage_plan = plan["stage_plan"]
    lineage = {
        "reference_hash": stage_plan.get("reference_hash") if plan["stage"] == "shot-image" else None,
        "source_shot_hash": stage_plan.get("source_shot_hash") if plan["stage"] == "video" else None,
        "artifact_hash": safe_artifact["content_hash"],
    }
    record = {
        "schema_version": "1.0",
        "stage": plan["stage"],
        "terminal_status": "succeeded",
        "execution_plan_hash": plan["execution_plan_hash"],
        "execution_plan": copy.deepcopy(plan),
        "stage_plan": copy.deepcopy(stage_plan),
        "workflow_profile_id": plan["workflow_profile_id"],
        "workflow_profile_hash": plan["profile_hash"],
        "workflow_fingerprint": plan.get("workflow_fingerprint"),
        "source_api_graph_hash": plan["source_api_graph_hash"],
        "executable_api_graph_hash": plan["executable_api_graph_hash"],
        "capability_report_hash": plan["capability_report_hash"],
        "patches": copy.deepcopy(plan.get("patches", [])),
        "immutable_inputs": copy.deepcopy(plan.get("immutable_inputs", {})),
        "submission_hash": safe_submission["submission_hash"],
        "submission": copy.deepcopy(safe_submission),
        "enqueue_receipt_hash": receipt["receipt_hash"],
        "enqueue_receipt": copy.deepcopy(receipt),
        "prompt_id": prompt_id,
        "artifact": safe_artifact,
        "lineage": lineage,
        "history": copy.deepcopy(history),
        "history_hash": content_hash(history),
        "history_verified": history_verified,
    }
    record["record_hash"] = content_hash(record)
    return record
