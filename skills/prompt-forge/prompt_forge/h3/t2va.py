"""MiniMax-H3 T2VA deterministic prompt compiler."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from math import floor
from pathlib import Path

from ..artifacts import PromptArtifact, create_prompt_artifact
from ..budgets import BudgetPolicyError, plan_h3_t2va_budget
from ..compression import CompressionResult, compress_to_budget
from ..contracts import AuthoredSegment, H3T2VAAuthoringRequest
from ..facts import FactLedger
from ..token_counting import TokenCounter
from .common import (
    H3AuditError,
    audit_dialogue_and_visible_text,
    audit_shot_execution,
    audit_sound_music_separation,
    parse_shots,
    plan_h3_context,
)


_MODEL = "MiniMaxAI/MiniMax-H3"
_ROOT = Path(__file__).resolve().parents[2]
_TOKENIZER = _ROOT / "knowledge" / "tokenizers" / "h3-qwen3-vl"
_POLICY = _ROOT / "knowledge" / "h3-t2va-budget-policy.json"


def author_h3_t2va_prompt(request: H3T2VAAuthoringRequest) -> PromptArtifact:
    ledger = FactLedger(request.facts)
    original_segments = (
        *request.integrated_multimodal_description,
        *request.overall_soundscape,
        *request.non_diegetic_music,
    )
    ledger.validate_segments(original_segments)
    ledger.trace_rendering(original_segments)
    counter = TokenCounter.load(_TOKENIZER, "h3-qwen3-vl")
    dialogue_tokens = sum(
        counter.count(fact.value) for fact in request.facts if fact.dimension == "dialogue"
    )
    hard_codes: list[str] = []
    try:
        budget = plan_h3_t2va_budget(
            request.duration_seconds,
            request.shot_count,
            dialogue_tokens,
        )
    except BudgetPolicyError:
        hard_codes.append("timeline")
        safe_duration = _safe_duration(request.duration_seconds)
        safe_shots = max(
            1,
            min(
                request.shot_count if isinstance(request.shot_count, int) else 1,
                1 + floor((safe_duration - 1) / 3),
            ),
        )
        budget = plan_h3_t2va_budget(
            safe_duration,
            safe_shots,
            dialogue_tokens,
        )

    compressed = _compress(original_segments, ledger, counter, budget.text.soft_limit, budget.text.quality_limit)
    grouped = _group_segments(compressed.segments)
    description = " ".join(segment.text for segment in grouped["description"])
    soundscape = " ".join(segment.text for segment in grouped["soundscape"]) or "N/A"
    music = " ".join(segment.text for segment in grouped["music"]) or "N/A"
    rendered = _render(description, soundscape, music)
    actual = counter.count(rendered)
    context = plan_h3_context(
        counter,
        (),
        text_quality_limit=budget.text.quality_limit,
        special_tokens=0,
        runtime_safety_margin=4096,
    )
    token_report = {
        "text": {
            "target": budget.text.target,
            "soft_limit": budget.text.soft_limit,
            "quality_limit": budget.text.quality_limit,
            "hard_limit": budget.text.hard_limit,
            "actual": actual,
            "dialogue_tokens": dialogue_tokens,
        },
        "context": asdict(context),
    }
    trace = ledger.trace_rendering(compressed.segments)
    if compressed.conflict is not None or actual > context.effective_quality_limit:
        conflict = (
            asdict(compressed.conflict)
            if compressed.conflict is not None
            else _render_overhead_conflict(actual, context.effective_quality_limit)
        )
        return _artifact(
            "budget_conflict",
            request,
            None,
            trace,
            token_report,
            {"release_blocking": True, "hard_gate_codes": ["token_quality_limit"]},
            compressed,
            conflict,
        )

    shots = ()
    try:
        shots = parse_shots(
            description,
            duration_seconds=request.duration_seconds,
            declared_shot_count=request.shot_count,
        )
        audit_shot_execution(shots, ledger)
    except H3AuditError:
        hard_codes.append("timeline")
    try:
        audit_dialogue_and_visible_text(description, ledger)
    except H3AuditError:
        hard_codes.append("exact_dialogue_or_visible_text")
    try:
        audit_sound_music_separation(soundscape, music)
    except H3AuditError:
        hard_codes.append("sound_music_separation")
    if not description:
        hard_codes.append("integrated_multimodal_description")
    hard_codes = list(dict.fromkeys(hard_codes))
    audit = {
        "release_blocking": bool(hard_codes),
        "hard_gate_codes": hard_codes,
        "shots": [asdict(shot) for shot in shots],
        "official_field_order": [
            "integrated_multimodal_description",
            "overall_soundscape",
            "non_diegetic_music",
        ],
    }
    if hard_codes:
        return _artifact(
            "quality_rejected",
            request,
            None,
            trace,
            token_report,
            audit,
            compressed,
            None,
        )
    return _artifact(
        "production_ready",
        request,
        {"text": rendered},
        trace,
        token_report,
        audit,
        compressed,
        None,
    )


def _compress(
    segments: tuple[AuthoredSegment, ...],
    ledger: FactLedger,
    counter: TokenCounter,
    soft_limit: int,
    quality_limit: int,
) -> CompressionResult:
    if not segments:
        return CompressionResult("within_budget", (), 0, (), None)
    return compress_to_budget(
        segments=segments,
        ledger=ledger,
        counter=counter,
        soft_limit=soft_limit,
        quality_limit=quality_limit,
        structure="h3_t2va",
    )


def _group_segments(
    segments: tuple[AuthoredSegment, ...],
) -> dict[str, tuple[AuthoredSegment, ...]]:
    sound_fields = {"overall_soundscape", "shot_global_soundscape"}
    music_fields = {"non_diegetic_music", "shot_non_diegetic_music"}
    return {
        "description": tuple(
            segment
            for segment in segments
            if segment.field not in sound_fields | music_fields
        ),
        "soundscape": tuple(segment for segment in segments if segment.field in sound_fields),
        "music": tuple(segment for segment in segments if segment.field in music_fields),
    }


def _render(description: str, soundscape: str, music: str) -> str:
    return (
        f"integrated_multimodal_description: {description}\n\n"
        f"overall_soundscape: {soundscape}\n\n"
        f"non_diegetic_music: {music}"
    )


def _render_overhead_conflict(actual: int, quality_limit: int) -> dict[str, object]:
    return {
        "actual_tokens": actual,
        "quality_limit": quality_limit,
        "mandatory_tokens": actual,
        "agent_optional_tokens": 0,
        "excess_tokens": actual - quality_limit,
        "protected_causes": [],
        "user_choices": [],
        "sacrificed_facts": [],
    }


def _safe_duration(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 2.0
    return min(15.0, max(2.0, float(value)))


def _artifact(
    status: str,
    request: H3T2VAAuthoringRequest,
    prompt: dict[str, str] | None,
    trace: dict[str, tuple[str, ...]],
    token_report: dict[str, object],
    audit: dict[str, object],
    compression: CompressionResult,
    conflict: dict[str, object] | None,
) -> PromptArtifact:
    return create_prompt_artifact(
        status=status,  # type: ignore[arg-type]
        task="h3_t2va",
        model=_MODEL,
        prompt=prompt,
        facts=request.facts,
        trace=trace,
        token_report=token_report,
        audit=audit,
        compression=compression.operations,
        conflict=conflict,
        token_count_verified=True,
        knowledge_manifest_sha256=_knowledge_hash(),
    )


def _knowledge_hash() -> str:
    digest = hashlib.sha256()
    digest.update((_TOKENIZER / "manifest.json").read_bytes())
    digest.update(_POLICY.read_bytes())
    return digest.hexdigest()
