from __future__ import annotations

import hashlib
import json

import pytest

from comfyui_chenxin_mcp.engine import build_log
from comfyui_chenxin_mcp.engine.prompt_forge import validate_prompt_artifact


def register(
    task: str,
    model: str,
    prompt: dict[str, str],
    *,
    references=(),
    duration: float | None = None,
) -> str:
    """Register a BuildLog and return its ref id."""
    audit = {"reference_context": list(references)}
    if duration is not None:
        audit["shots"] = [{"end_seconds": duration}]
    value = {
        "artifact_version": 1,
        "status": "production_ready",
        "task": task,
        "model": model,
        "prompt": prompt,
        "facts": [],
        "trace": {},
        "token_report": {},
        "audit": audit,
        "compression": [],
        "conflict": None,
        "sacrificed_facts": [],
        "token_count_verified": True,
        "knowledge_manifest_sha256": "a" * 64,
    }
    value["artifact_sha256"] = hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return build_log.register(**value)


def test_accepts_only_exact_verified_production_artifact() -> None:
    ref_id = register("anima", "circlestone-labs/Anima", {"positive": "1girl", "negative": ""})
    assert validate_prompt_artifact(ref_id, expected_task="anima")["positive"] == "1girl"
    for field, replacement in (("status", "quality_rejected"), ("token_count_verified", False)):
        log = build_log.get(ref_id)
        log[field] = replacement
        with pytest.raises(ValueError):
            validate_prompt_artifact(ref_id, expected_task="anima")


def test_task_model_prompt_and_hash_must_match() -> None:
    ref_id = register("h3_t2va", "MiniMaxAI/MiniMax-H3", {"text": "hello"})
    with pytest.raises(ValueError, match="task"):
        validate_prompt_artifact(ref_id, expected_task="h3_ref2va")
    log = build_log.get(ref_id)
    log["prompt"] = {"text": "changed"}
    with pytest.raises(ValueError, match="hash"):
        validate_prompt_artifact(ref_id, expected_task="h3_t2va")


def test_ref2va_reference_context_is_bound_to_stage_count() -> None:
    refs = ({"reference_id": "Picture 1", "owner": "subject_1", "resized_width": 1024, "resized_height": 1024},)
    ref_id = register("h3_ref2va", "MiniMaxAI/MiniMax-H3", {"text": "ref"}, references=refs)
    validate_prompt_artifact(ref_id, expected_task="h3_ref2va", expected_reference_count=1)
    with pytest.raises(ValueError, match="reference"):
        validate_prompt_artifact(ref_id, expected_task="h3_ref2va", expected_reference_count=3)
    log = build_log.get(ref_id)
    log["audit"]["reference_context"][0]["resized_width"] = 512
    with pytest.raises(ValueError, match="hash"):
        validate_prompt_artifact(ref_id, expected_task="h3_ref2va", expected_reference_count=1)


def test_h3_duration_is_bound_to_audited_timeline() -> None:
    ref_id = register(
        "h3_t2va",
        "MiniMaxAI/MiniMax-H3",
        {"text": "timeline"},
        duration=5,
    )
    validate_prompt_artifact(ref_id, expected_task="h3_t2va", expected_duration=5)
    with pytest.raises(ValueError, match="duration"):
        validate_prompt_artifact(ref_id, expected_task="h3_t2va", expected_duration=8)
