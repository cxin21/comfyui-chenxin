"""Strict Prompt Forge authoring bridge.

author_* build a PromptArtifact, register it in the server-side
BuildLog registry, and return only a slim {ref_id, prompt} dict.
Callers carry the 32-character ref id across turns; they fetch the
full audit log on demand via build_log.get(ref_id).

This replaces the earlier "return the full 14-field artifact dict"
pattern that forced the LLM to carry the certificate as a payload.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from . import build_log
from .build_log import register as _register_build


PROMPT_FORGE_ROOT = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "skills"
    / "prompt-forge"
)
# One registry per authoring task: the release model, the model-native
# prompt keys it produces, and the authoring symbol exposed by the
# prompt-forge package. Adding a new model means adding one entry here,
# plus the coerce function in server.py — the MCP tool surface does not
# grow.
_TASKS: dict[str, dict[str, Any]] = {
    "anima": {
        "model": "circlestone-labs/Anima",
        "prompt_keys": frozenset({"positive", "negative"}),
        "author": "author_anima_prompt",
    },
    "h3_t2va": {
        "model": "MiniMaxAI/MiniMax-H3",
        "prompt_keys": frozenset({"text"}),
        "author": "author_h3_t2va_prompt",
    },
    "h3_ref2va": {
        "model": "MiniMaxAI/MiniMax-H3",
        "prompt_keys": frozenset({"text"}),
        "author": "author_h3_ref2va_prompt",
    },
}


def _ensure_prompt_forge_on_path() -> None:
    root = str(PROMPT_FORGE_ROOT)
    if not (PROMPT_FORGE_ROOT / "prompt_forge").is_dir():
        raise FileNotFoundError(
            f"prompt-forge module is missing at {PROMPT_FORGE_ROOT}; "
            "run scripts/install.ps1 to synchronize the plugin source"
        )
    if root not in sys.path:
        sys.path.insert(0, root)


def _build_to_slim(artifact_dict: dict[str, Any]) -> dict[str, Any]:
    """Register the full artifact in the BuildLog registry and return
    only the slim {ref_id, prompt} dict that callers carry.
    """
    ref_id = _register_build(
        artifact_version=artifact_dict.get("artifact_version", 1),
        task=artifact_dict["task"],
        model=artifact_dict["model"],
        prompt=artifact_dict["prompt"],
        facts=tuple(artifact_dict["facts"] or ()),
        trace=dict(artifact_dict["trace"] or {}),
        token_report=dict(artifact_dict["token_report"] or {}),
        audit=dict(artifact_dict["audit"] or {}),
        compression=tuple(artifact_dict["compression"] or ()),
        conflict=artifact_dict.get("conflict"),
        sacrificed_facts=tuple(artifact_dict.get("sacrificed_facts") or ()),
        token_count_verified=bool(artifact_dict.get("token_count_verified", False)),
        knowledge_manifest_sha256=str(artifact_dict.get("knowledge_manifest_sha256", "")),
        artifact_sha256=str(artifact_dict.get("artifact_sha256", "")),
        status=str(artifact_dict.get("status", "")),
    )
    return {
        "ref_id": ref_id,
        "prompt": artifact_dict["prompt"],
    }


def author_prompt(task: str, request: Any) -> dict[str, Any]:
    """Run one Prompt Forge authoring task and return its slim BuildLog.

    `task` is a key of ``_TASKS`` (anima | h3_t2va | h3_ref2va). The
    matching ``author_<task>_prompt`` symbol is resolved from the
    prompt-forge package, so a new model needs only a ``_TASKS`` entry.
    """
    if task not in _TASKS:
        raise ValueError(
            f"unsupported Prompt Forge task: {task!r}; supported: {sorted(_TASKS)}"
        )
    _ensure_prompt_forge_on_path()
    import importlib

    prompt_forge = importlib.import_module("prompt_forge")
    author_fn = getattr(prompt_forge, _TASKS[task]["author"])
    return _build_to_slim(author_fn(request).to_dict())


def validate_prompt_artifact(
    ref_id: str,
    *,
    expected_task: str,
    expected_reference_count: int | None = None,
    expected_duration: float | None = None,
) -> dict[str, str]:
    """Resolve a BuildLog ref id and return its prompt dict or fail closed.

    The BuildLog must exist, have `status == production_ready`, match
    the expected_task, pass task-specific content checks, and have a
    valid content hash. Returns the resolved prompt dict on success.
    """
    if expected_task not in _TASKS:
        raise ValueError(
            f"unsupported Prompt Forge task: {expected_task!r}; supported: {sorted(_TASKS)}"
        )
    log = build_log.get(ref_id)
    if log is None:
        raise ValueError(f"unknown BuildLog ref_id: {ref_id!r}")
    if log["status"] != "production_ready":
        raise ValueError(f"BuildLog {ref_id} status is {log['status']!r}, not production_ready")
    if log["task"] != expected_task:
        raise ValueError(
            f"BuildLog {ref_id} task is {log['task']!r}, expected {expected_task!r}"
        )
    if log["model"] != _TASKS[expected_task]["model"]:
        raise ValueError(f"BuildLog {ref_id} model does not match its task")
    if log["token_count_verified"] is not True:
        raise ValueError(f"BuildLog {ref_id} token_count_verified is false")
    if log["sacrificed_facts"]:
        raise ValueError(f"BuildLog {ref_id} has non-empty sacrificed_facts")
    if log["conflict"] is not None:
        raise ValueError(f"BuildLog {ref_id} has unresolved conflict")
    prompt = log["prompt"]
    if not isinstance(prompt, dict) or set(prompt) != _TASKS[expected_task]["prompt_keys"]:
        raise ValueError(f"BuildLog {ref_id} prompt has the wrong model-native fields")
    if any(not isinstance(value, str) for value in prompt.values()):
        raise ValueError(f"BuildLog {ref_id} prompt values must be strings")
    required_text = prompt["positive"] if expected_task == "anima" else prompt["text"]
    if not required_text.strip():
        raise ValueError(f"BuildLog {ref_id} executable prompt must be non-empty")
    if len(log["knowledge_manifest_sha256"]) != 64:
        raise ValueError(f"BuildLog {ref_id} knowledge hash must be SHA-256")
    expected_hash = _log_hash(log)
    if log["artifact_sha256"] != expected_hash:
        raise ValueError(f"BuildLog {ref_id} content hash is invalid")
    if expected_task == "h3_ref2va":
        _validate_reference_context(log, expected_reference_count)
    elif expected_reference_count not in (None, 0):
        raise ValueError("non-reference task cannot bind reference images")
    if expected_task.startswith("h3_") and expected_duration is not None:
        _validate_duration(log, expected_duration)
    return prompt


def _log_hash(log: dict[str, Any]) -> str:
    # Hash the stored content excluding the two bookkeeping fields
    # (ref_id and the stored artifact_sha256 itself) so the stored
    # artifact_sha256 is the digest of everything else — matching the
    # create_prompt_artifact semantics from the prompt-forge library.
    base = {
        key: value
        for key, value in log.items()
        if key not in ("ref_id", "artifact_sha256")
    }
    raw = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_reference_context(
    log: dict[str, Any],
    expected_reference_count: int | None,
) -> None:
    audit = log.get("audit")
    references = audit.get("reference_context") if isinstance(audit, dict) else None
    if not isinstance(references, list) or not references:
        raise ValueError("Ref2VA BuildLog requires verified reference_context")
    if expected_reference_count is not None and len(references) != expected_reference_count:
        raise ValueError("BuildLog reference count does not match the execution stage")
    for index, reference in enumerate(references, start=1):
        if not isinstance(reference, dict):
            raise ValueError("BuildLog reference_context entries must be objects")
        if set(reference) != {"reference_id", "owner", "resized_width", "resized_height"}:
            raise ValueError("BuildLog reference_context fields are invalid")
        if reference["reference_id"] != f"Picture {index}":
            raise ValueError("BuildLog reference order is invalid")
        if not isinstance(reference["owner"], str) or not reference["owner"].strip():
            raise ValueError("BuildLog reference owner is invalid")
        for dimension in ("resized_width", "resized_height"):
            value = reference[dimension]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("BuildLog reference dimensions are invalid")


def _validate_duration(log: dict[str, Any], expected_duration: float) -> None:
    if isinstance(expected_duration, bool) or not isinstance(expected_duration, (int, float)):
        raise TypeError("expected H3 duration must be numeric")
    audit = log.get("audit")
    shots = audit.get("shots") if isinstance(audit, dict) else None
    if not isinstance(shots, list) or not shots:
        raise ValueError("H3 BuildLog requires an audited shot timeline")
    final_end = shots[-1].get("end_seconds") if isinstance(shots[-1], dict) else None
    if not isinstance(final_end, (int, float)) or float(final_end) != float(expected_duration):
        raise ValueError("BuildLog duration does not match execution duration")
