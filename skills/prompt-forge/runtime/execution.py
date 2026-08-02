"""Fail-closed execution plans and immutable runtime provenance records."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone

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
_PATCH_KEYS = frozenset(("slot", "input", "value"))
_TERMINAL_STATUSES = frozenset(("succeeded", "failed"))
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PLAN_KEYS = frozenset(
    (
        "schema_version",
        "stage",
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
        "plan_hash",
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


def build_execution_plan(
    stage: str,
    prompt_build: dict,
    workflow_profile_id: str,
    workflow_fingerprint: str,
    patches: list,
    execution_approved: bool,
    *,
    capability_report: dict | None = None,
    profile: dict | None = None,
    actual_ui_workflow: dict | None = None,
    api_graph: dict | None = None,
) -> dict:
    """Build a character-base plan from independently recomputed local evidence."""
    if execution_approved is not True:
        raise ExecutionError("current explicit execution approval is required")
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

    plan = {
        "schema_version": "1.0",
        "stage": "character-base",
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
        "execution_approved": True,
    }
    plan["plan_hash"] = content_hash(plan)
    return plan


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
    if not isinstance(plan, dict) or set(plan) != _PLAN_KEYS:
        raise ExecutionError("ExecutionPlan lineage is incomplete")
    if plan.get("schema_version") != "1.0" or plan.get("stage") != "character-base":
        raise ExecutionError("ExecutionPlan is not a Stage 1 character-base plan")
    if plan.get("workflow_profile_id") != _CHARACTER_BASE_PROFILE_ID:
        raise ExecutionError("ExecutionPlan profile is not camera-anima-v1")
    if plan.get("local_only") is not True or plan.get("execution_approved") is not True:
        raise ExecutionError("ExecutionPlan must be local-only and approved")
    if plan.get("expected_outputs") != _CHARACTER_BASE_OUTPUTS:
        raise ExecutionError("ExecutionPlan must expect exactly image/png")
    if plan.get("immutable_inputs") != []:
        raise ExecutionError("ExecutionPlan immutable_inputs contract is invalid")
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
    for field in (
        "profile_hash",
        "workflow_fingerprint",
        "capability_report_hash",
        "source_api_graph_hash",
        "executable_api_graph_hash",
        "prompt_build_id",
    ):
        if not isinstance(plan[field], str) or not _SHA256_RE.fullmatch(plan[field]):
            raise ExecutionError("ExecutionPlan lineage hashes must be lowercase SHA-256 digests")
    expected_preflight = _derived_preflight(
        plan["workflow_fingerprint"],
        plan["source_api_graph_hash"],
        plan["executable_api_graph_hash"],
        plan["capability_report_hash"],
        plan["profile_hash"],
        _CHARACTER_BASE_SLOTS,
    )
    if plan.get("preflight") != expected_preflight:
        raise ExecutionError("ExecutionPlan preflight lineage is not self-consistent")
    unsigned = dict(plan)
    claimed_hash = unsigned.pop("plan_hash")
    if not isinstance(claimed_hash, str) or claimed_hash != content_hash(unsigned):
        raise ExecutionError("ExecutionPlan plan_hash is not self-consistent")


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
