"""Fail-closed execution plans and immutable runtime provenance records."""

from __future__ import annotations

import copy
import re
from datetime import datetime

from .capabilities import report_is_fresh
from .contracts import ContractError, content_hash, validate_task_context
from .prompt_quality import validate_anima_prompt_build
from .workflow_profile import ProfileError, structure_fingerprint


class ExecutionError(ValueError):
    """Raised when execution evidence does not satisfy the runtime boundary."""


_CHARACTER_BASE_PROFILE_ID = "camera-anima-v1"
_CHARACTER_BASE_OUTPUTS = ["image/png"]
_CHARACTER_BASE_SLOTS = {"positive_prompt": 24, "negative_prompt": 25}
_PATCH_KEYS = frozenset(("slot", "input", "value"))
_TERMINAL_EVIDENCE_KEYS = frozenset(
    ("source", "prompt_id", "status", "plan_hash", "api_graph_hash", "output_hashes")
)
_TERMINAL_STATUSES = frozenset(("succeeded", "failed", "cancelled"))
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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
        if not isinstance(selector, dict) or selector.get("id") != node_id:
            raise ExecutionError(f"character-base profile slot '{slot_name}' must be node {node_id}")


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


def _expected_preflight(
    workflow_fingerprint: str,
    api_graph_hash: str,
    capability_report_hash: str,
    profile_hash: str,
) -> dict:
    return {
        "nodes": {"status": "pass", "workflow_fingerprint": workflow_fingerprint},
        "models": {"status": "pass", "api_graph_hash": api_graph_hash},
        "resources": {
            "status": "pass",
            "capability_report_hash": capability_report_hash,
        },
        "policy": {"status": "pass", "profile_hash": profile_hash},
    }


def _validate_preflight(preflight: object, expected: dict) -> None:
    if not isinstance(preflight, dict) or set(preflight) != set(expected):
        raise ExecutionError("preflight evidence has an invalid schema")
    for branch, expected_evidence in expected.items():
        if preflight.get(branch) != expected_evidence:
            evidence_name = next(key for key in expected_evidence if key != "status")
            raise ExecutionError(
                f"preflight {branch}.{evidence_name} does not match recomputed evidence"
            )


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
    now: datetime | None = None,
    preflight: dict | None = None,
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
    if not isinstance(now, datetime):
        raise ExecutionError("current UTC time is required")
    _require_idle_local_capability(capability_report, now)
    if not isinstance(api_graph, dict):
        raise ExecutionError("actual API graph must be an object")

    try:
        actual_fingerprint = structure_fingerprint(actual_ui_workflow)
        graph_hash = content_hash(api_graph)
        report_hash = content_hash(capability_report)
        profile_hash = content_hash(profile)
    except (ProfileError, TypeError, ValueError) as exc:
        raise ExecutionError(f"execution evidence is invalid: {exc}") from exc
    if workflow_fingerprint != actual_fingerprint:
        raise ExecutionError("workflow fingerprint does not match the actual UI workflow")

    if not isinstance(patches, list) or any(
        not isinstance(item, dict) or set(item) != _PATCH_KEYS for item in patches
    ):
        raise ExecutionError("character-base requires the exact four prompt patches")
    expected_patches = _character_base_patches(prompt_build)
    if patches != expected_patches:
        raise ExecutionError("character-base requires the exact four prompt-derived patches")

    expected_preflight = _expected_preflight(
        actual_fingerprint, graph_hash, report_hash, profile_hash
    )
    _validate_preflight(preflight, expected_preflight)

    plan = {
        "schema_version": "1.0",
        "stage": "character-base",
        "prompt_build_id": content_hash(prompt_build),
        "capability_report_hash": report_hash,
        "workflow_profile_id": _CHARACTER_BASE_PROFILE_ID,
        "profile_hash": profile_hash,
        "workflow_fingerprint": actual_fingerprint,
        "api_graph_hash": graph_hash,
        "patches": copy.deepcopy(expected_patches),
        "immutable_inputs": [],
        "local_only": True,
        "preflight": copy.deepcopy(expected_preflight),
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
    required = {
        "prompt_build_id",
        "api_graph_hash",
        "workflow_profile_id",
        "profile_hash",
        "workflow_fingerprint",
        "capability_report_hash",
        "plan_hash",
    }
    if not isinstance(plan, dict) or not required.issubset(plan):
        raise ExecutionError("ExecutionPlan lineage is incomplete")
    if plan.get("execution_approved") is not True:
        raise ExecutionError("RunRecord requires an approved ExecutionPlan")
    if plan["prompt_build_id"] != content_hash(prompt_build):
        raise ExecutionError("ExecutionPlan prompt_build_id does not match PromptBuild")
    if plan["api_graph_hash"] != content_hash(api_graph):
        raise ExecutionError("ExecutionPlan api_graph_hash does not match API graph")
    for field in (
        "profile_hash",
        "workflow_fingerprint",
        "capability_report_hash",
        "api_graph_hash",
        "prompt_build_id",
    ):
        if not isinstance(plan[field], str) or not _SHA256_RE.fullmatch(plan[field]):
            raise ExecutionError("ExecutionPlan lineage hashes must be lowercase SHA-256 digests")
    unsigned = dict(plan)
    claimed_hash = unsigned.pop("plan_hash")
    if not isinstance(claimed_hash, str) or claimed_hash != content_hash(unsigned):
        raise ExecutionError("ExecutionPlan plan_hash is not self-consistent")


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
    terminal_evidence: dict,
) -> dict:
    """Record execution only when matching ComfyUI history proves a terminal run."""
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
        raise ExecutionError("terminal status must be succeeded, failed or cancelled")
    safe_inputs = _validated_hashes(input_hashes, "input")
    safe_outputs = _validated_hashes(output_hashes, "output")
    if terminal_status == "succeeded" and not safe_outputs:
        raise ExecutionError("succeeded RunRecord requires output hashes")

    if not isinstance(terminal_evidence, dict) or set(terminal_evidence) != _TERMINAL_EVIDENCE_KEYS:
        raise ExecutionError("terminal evidence has an invalid schema")
    expected_evidence = {
        "source": "comfyui_history",
        "prompt_id": prompt_id,
        "status": terminal_status,
        "plan_hash": execution_plan["plan_hash"],
        "api_graph_hash": execution_plan["api_graph_hash"],
        "output_hashes": safe_outputs,
    }
    if terminal_evidence != expected_evidence:
        raise ExecutionError("terminal evidence does not match the runtime lineage")

    record = {
        "schema_version": "1.0",
        "task_context_hash": content_hash(safe_context),
        "prompt_build_hash": content_hash(prompt_build),
        "prompt_build": copy.deepcopy(prompt_build),
        "api_graph_hash": execution_plan["api_graph_hash"],
        "execution_plan_hash": content_hash(execution_plan),
        "execution_plan": copy.deepcopy(execution_plan),
        "prompt_id": prompt_id,
        "terminal_status": terminal_status,
        "terminal_evidence": copy.deepcopy(expected_evidence),
        "execution_performed": True,
        "input_hashes": safe_inputs,
        "output_hashes": safe_outputs,
    }
    record["record_hash"] = content_hash(record)
    return record
