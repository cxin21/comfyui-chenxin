"""Strict Prompt Forge authoring bridge and artifact-consumption gate."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PROMPT_FORGE_ROOT = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "skills"
    / "prompt-forge"
)
_MODELS = {
    "anima": "circlestone-labs/Anima",
    "h3_t2va": "MiniMaxAI/MiniMax-H3",
    "h3_ref2va": "MiniMaxAI/MiniMax-H3",
}
_PROMPT_KEYS = {
    "anima": frozenset({"positive", "negative"}),
    "h3_t2va": frozenset({"text"}),
    "h3_ref2va": frozenset({"text"}),
}
_ARTIFACT_KEYS = frozenset({
    "artifact_version", "status", "task", "model", "prompt", "facts",
    "trace", "token_report", "audit", "compression", "conflict",
    "sacrificed_facts", "token_count_verified", "knowledge_manifest_sha256",
    "artifact_sha256",
})


def _ensure_prompt_forge_on_path() -> None:
    root = str(PROMPT_FORGE_ROOT)
    if not (PROMPT_FORGE_ROOT / "prompt_forge").is_dir():
        raise FileNotFoundError(
            f"prompt-forge module is missing at {PROMPT_FORGE_ROOT}; "
            "run scripts/install.ps1 to synchronize the plugin source"
        )
    if root not in sys.path:
        sys.path.insert(0, root)


def author_anima(request: Any) -> dict[str, Any]:
    _ensure_prompt_forge_on_path()
    from prompt_forge import author_anima_prompt

    return author_anima_prompt(request).to_dict()


def author_h3_t2va(request: Any) -> dict[str, Any]:
    _ensure_prompt_forge_on_path()
    from prompt_forge import author_h3_t2va_prompt

    return author_h3_t2va_prompt(request).to_dict()


def author_h3_ref2va(request: Any) -> dict[str, Any]:
    _ensure_prompt_forge_on_path()
    from prompt_forge import author_h3_ref2va_prompt

    return author_h3_ref2va_prompt(request).to_dict()


def validate_prompt_artifact(
    artifact: Any,
    *,
    expected_task: str,
    expected_reference_count: int | None = None,
    expected_duration: float | None = None,
) -> dict[str, Any]:
    """Return an exact production artifact or fail closed without coercion."""
    if expected_task not in _MODELS:
        raise ValueError(f"unsupported Prompt Forge task: {expected_task!r}")
    if not isinstance(artifact, dict):
        raise TypeError("prompt_artifact must be an object")
    unknown = set(artifact) - _ARTIFACT_KEYS
    missing = _ARTIFACT_KEYS - set(artifact)
    if unknown or missing:
        raise ValueError(
            f"prompt_artifact has unknown fields {sorted(unknown)} or missing fields {sorted(missing)}"
        )
    if artifact["artifact_version"] != 1:
        raise ValueError("prompt_artifact.artifact_version must be 1")
    if artifact["status"] != "production_ready":
        raise ValueError("prompt_artifact.status must be production_ready")
    if artifact["task"] != expected_task:
        raise ValueError(
            f"prompt_artifact.task must be {expected_task!r}, got {artifact['task']!r}"
        )
    if artifact["model"] != _MODELS[expected_task]:
        raise ValueError("prompt_artifact.model does not match its task")
    if artifact["token_count_verified"] is not True:
        raise ValueError("prompt_artifact.token_count_verified must be true")
    if artifact["sacrificed_facts"] != []:
        raise ValueError("prompt_artifact.sacrificed_facts must be empty")
    if artifact["conflict"] is not None:
        raise ValueError("production prompt_artifact cannot contain a conflict")
    prompt = artifact["prompt"]
    if not isinstance(prompt, dict) or set(prompt) != _PROMPT_KEYS[expected_task]:
        raise ValueError("prompt_artifact.prompt has the wrong model-native fields")
    if any(not isinstance(value, str) for value in prompt.values()):
        raise ValueError("prompt_artifact prompt values must be strings")
    required_text = prompt["positive"] if expected_task == "anima" else prompt["text"]
    if not required_text.strip():
        raise ValueError("prompt_artifact executable prompt must be non-empty")
    knowledge_hash = artifact["knowledge_manifest_sha256"]
    if not isinstance(knowledge_hash, str) or len(knowledge_hash) != 64:
        raise ValueError("prompt_artifact knowledge hash must be SHA-256")
    expected_hash = _artifact_hash(artifact)
    if artifact["artifact_sha256"] != expected_hash:
        raise ValueError("prompt_artifact content hash is invalid")
    if expected_task == "h3_ref2va":
        _validate_reference_context(artifact, expected_reference_count)
    elif expected_reference_count not in (None, 0):
        raise ValueError("non-reference task cannot bind reference images")
    if expected_task.startswith("h3_") and expected_duration is not None:
        _validate_duration(artifact, expected_duration)
    return artifact


def _artifact_hash(artifact: dict[str, Any]) -> str:
    base = {key: value for key, value in artifact.items() if key != "artifact_sha256"}
    raw = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_reference_context(
    artifact: dict[str, Any],
    expected_reference_count: int | None,
) -> None:
    audit = artifact.get("audit")
    references = audit.get("reference_context") if isinstance(audit, dict) else None
    if not isinstance(references, list) or not references:
        raise ValueError("Ref2VA prompt_artifact requires verified reference_context")
    if expected_reference_count is not None and len(references) != expected_reference_count:
        raise ValueError("prompt_artifact reference count does not match the execution stage")
    for index, reference in enumerate(references, start=1):
        if not isinstance(reference, dict):
            raise ValueError("prompt_artifact reference_context entries must be objects")
        if set(reference) != {"reference_id", "owner", "resized_width", "resized_height"}:
            raise ValueError("prompt_artifact reference_context fields are invalid")
        if reference["reference_id"] != f"Picture {index}":
            raise ValueError("prompt_artifact reference order is invalid")
        if not isinstance(reference["owner"], str) or not reference["owner"].strip():
            raise ValueError("prompt_artifact reference owner is invalid")
        for dimension in ("resized_width", "resized_height"):
            value = reference[dimension]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("prompt_artifact reference dimensions are invalid")


def _validate_duration(artifact: dict[str, Any], expected_duration: float) -> None:
    if isinstance(expected_duration, bool) or not isinstance(expected_duration, (int, float)):
        raise TypeError("expected H3 duration must be numeric")
    audit = artifact.get("audit")
    shots = audit.get("shots") if isinstance(audit, dict) else None
    if not isinstance(shots, list) or not shots:
        raise ValueError("H3 prompt_artifact requires an audited shot timeline")
    final_end = shots[-1].get("end_seconds") if isinstance(shots[-1], dict) else None
    if not isinstance(final_end, (int, float)) or float(final_end) != float(expected_duration):
        raise ValueError("prompt_artifact duration does not match execution duration")
