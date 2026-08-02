"""Fail-closed execution plans and immutable runtime provenance records."""

from __future__ import annotations

import copy
import re
from datetime import datetime

from .capabilities import report_is_fresh
from .contracts import content_hash
from .prompt_quality import validate_anima_prompt_build


class ExecutionError(ValueError):
    """Raised when execution evidence does not satisfy the runtime boundary."""


_PREFLIGHT_KEYS = frozenset(("nodes", "models", "resources", "policy"))
_PATCH_KEYS = frozenset(("slot", "input", "value"))
_TERMINAL_STATUSES = frozenset(("succeeded", "failed", "cancelled"))
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _validated_patches(patches: object, allowed_mutations: object) -> list[dict]:
    if not isinstance(allowed_mutations, list) or not all(
        isinstance(item, str) and item for item in allowed_mutations
    ):
        raise ExecutionError("profile allowlist must be a string list")
    if not isinstance(patches, list):
        raise ExecutionError("patches must be a list")

    allowed = set(allowed_mutations)
    result: list[dict] = []
    for patch in patches:
        if not isinstance(patch, dict) or set(patch) != _PATCH_KEYS:
            raise ExecutionError("each patch must contain only slot, input and value")
        slot = patch["slot"]
        input_name = patch["input"]
        if not isinstance(slot, str) or not slot or not isinstance(input_name, str) or not input_name:
            raise ExecutionError("patch slot and input must be non-empty strings")
        if f"{slot}.{input_name}" not in allowed:
            raise ExecutionError(f"patch is outside the profile allowlist: {slot}.{input_name}")
        result.append(copy.deepcopy(patch))
    return result


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
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in (running, pending)):
        raise ExecutionError("CapabilityReport queue counts must be non-negative integers")
    if running or pending:
        raise ExecutionError("one ComfyUI job at a time is allowed")


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
) -> dict:
    """Build a local-only plan from current evidence; never submit the graph."""
    if execution_approved is not True:
        raise ExecutionError("current explicit execution approval is required")
    if not isinstance(stage, str) or not stage:
        raise ExecutionError("stage must be a non-empty string")
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

    if not isinstance(profile, dict) or profile.get("schema_version") != "1.0":
        raise ExecutionError("a versioned workflow profile is required")
    if not isinstance(workflow_profile_id, str) or not workflow_profile_id:
        raise ExecutionError("workflow profile id is required")
    if profile.get("profile_id") != workflow_profile_id:
        raise ExecutionError("workflow profile id does not match the selected profile")
    if profile.get("runtime_classification") != "local":
        raise ExecutionError("workflow profile must require a local runtime")
    if not isinstance(workflow_fingerprint, str) or not workflow_fingerprint:
        raise ExecutionError("workflow fingerprint is required")
    if not isinstance(now, datetime):
        raise ExecutionError("current UTC time is required")
    _require_idle_local_capability(capability_report, now)

    if not isinstance(preflight, dict) or set(preflight) != _PREFLIGHT_KEYS:
        raise ExecutionError("preflight must contain nodes, models, resources and policy")
    if any(preflight[key] != "pass" for key in _PREFLIGHT_KEYS):
        raise ExecutionError("all preflight checks must pass")

    safe_patches = _validated_patches(patches, profile.get("allowed_mutations"))
    expected_outputs = profile.get("expected_outputs")
    if not isinstance(expected_outputs, list) or not all(
        isinstance(item, str) and item for item in expected_outputs
    ):
        raise ExecutionError("profile expected_outputs must be a string list")

    return {
        "schema_version": "1.0",
        "stage": stage,
        "prompt_build_id": content_hash(prompt_build),
        "capability_report_hash": content_hash(capability_report),
        "workflow_profile_id": workflow_profile_id,
        "workflow_profile_hash": content_hash(profile),
        "workflow_fingerprint": workflow_fingerprint,
        "patches": safe_patches,
        "immutable_inputs": [],
        "local_only": True,
        "preflight": copy.deepcopy(preflight),
        "expected_outputs": list(expected_outputs),
        "execution_approved": True,
    }


def _validated_hashes(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ExecutionError(f"{label} hashes must be an object")
    result: dict[str, str] = {}
    for name, digest in value.items():
        if not isinstance(name, str) or not name:
            raise ExecutionError(f"{label} hash names must be non-empty strings")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise ExecutionError(f"{label} hashes must be SHA-256 digests")
        result[name] = digest.lower()
    return result


def build_run_record(
    task_context: dict,
    prompt_build: dict,
    api_graph: dict,
    execution_plan: dict,
    prompt_id: str,
    terminal_status: str,
    input_hashes: dict,
    output_hashes: dict,
) -> dict:
    """Record completed runtime evidence and derive, rather than accept, performed."""
    if not isinstance(prompt_build, dict) or not isinstance(prompt_build.get("execution"), dict):
        raise ExecutionError("RunRecord requires a PromptBuild execution object")
    if prompt_build["execution"].get("performed") is not False:
        raise ExecutionError("PromptBuild execution.performed must remain false")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise ExecutionError("prompt_id is required for a terminal RunRecord")
    if terminal_status not in _TERMINAL_STATUSES:
        raise ExecutionError("terminal status must be succeeded, failed or cancelled")
    if not isinstance(execution_plan, dict) or execution_plan.get("execution_approved") is not True:
        raise ExecutionError("RunRecord requires an approved ExecutionPlan")

    safe_inputs = _validated_hashes(input_hashes, "input")
    safe_outputs = _validated_hashes(output_hashes, "output")
    if terminal_status == "succeeded" and not safe_outputs:
        raise ExecutionError("succeeded RunRecord requires output hashes")

    try:
        record = {
            "schema_version": "1.0",
            "task_context_hash": content_hash(task_context),
            "prompt_build_hash": content_hash(prompt_build),
            "prompt_build": copy.deepcopy(prompt_build),
            "api_graph_hash": content_hash(api_graph),
            "execution_plan_hash": content_hash(execution_plan),
            "execution_plan": copy.deepcopy(execution_plan),
            "prompt_id": prompt_id,
            "terminal_status": terminal_status,
            "execution_performed": True,
            "input_hashes": safe_inputs,
            "output_hashes": safe_outputs,
        }
        record["record_hash"] = content_hash(record)
    except (TypeError, ValueError) as exc:
        raise ExecutionError(f"RunRecord inputs must be canonical JSON: {exc}") from exc
    return record
