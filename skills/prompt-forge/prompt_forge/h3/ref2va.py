"""MiniMax-H3 Ref2VA deterministic prompt compiler."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, replace
from math import floor
from pathlib import Path

from ..artifacts import PromptArtifact, create_prompt_artifact
from ..budgets import BudgetPolicyError, plan_h3_ref2va_budget
from ..compression import CompressionResult, compress_to_budget
from ..contracts import AuthoredSegment, H3Ref2VAAuthoringRequest
from ..facts import FactLedger
from ..token_counting import TokenCounter
from .common import (
    H3AuditError,
    audit_dialogue_and_visible_text,
    audit_reference_labels,
    audit_shot_execution,
    audit_sound_music_separation,
    parse_shots,
    plan_h3_context,
)


_MODEL = "MiniMaxAI/MiniMax-H3"
_ROOT = Path(__file__).resolve().parents[2]
_TOKENIZER = _ROOT / "knowledge" / "tokenizers" / "h3-qwen3-vl"
_POLICY = _ROOT / "knowledge" / "h3-ref2va-budget-policy.json"
_FIELD_ORDER = (
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
)
_SUMMARY_PREFIX = re.compile(r"^\s*\[[^\]\r\n]+\]")


def author_h3_ref2va_prompt(request: H3Ref2VAAuthoringRequest) -> PromptArtifact:
    ledger = FactLedger(request.facts)
    segments = _normalize_fields(request)
    ledger.validate_segments(segments)
    ledger.trace_rendering(segments)
    counter = TokenCounter.load(_TOKENIZER, "h3-qwen3-vl")
    dialogue_tokens = sum(
        counter.count(fact.value) for fact in request.facts if fact.dimension == "dialogue"
    )
    hard_codes: list[str] = []
    if not request.references:
        hard_codes.append("reference_binding")
    if any(reference.owner not in {fact.owner for fact in request.facts} for reference in request.references):
        hard_codes.append("reference_ownership")
    if _stable_appearance_outside_definitions(request, ledger):
        hard_codes.append("stable_appearance_scope")

    try:
        budget = plan_h3_ref2va_budget(
            request.duration_seconds,
            request.shot_count,
            len(request.references),
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
        budget = plan_h3_ref2va_budget(
            safe_duration,
            safe_shots,
            max(1, len(request.references)),
            dialogue_tokens,
        )

    compressed = _compress(
        segments,
        ledger,
        counter,
        budget.text.soft_limit,
        budget.text.quality_limit,
    )
    grouped = _group_segments(compressed.segments)
    rendered_fields = {
        "subject_definitions": "\n".join(
            segment.text for segment in grouped["subject_definitions"]
        ),
        "summary": " ".join(segment.text for segment in grouped["summary"]),
        "retention_analysis": "\n".join(
            segment.text for segment in grouped["retention_analysis"]
        ),
        "detailed_description": " ".join(
            segment.text for segment in grouped["detailed_description"]
        ),
        "overall_soundscape": " ".join(
            segment.text for segment in grouped["overall_soundscape"]
        ) or "N/A",
        "non_diegetic_music": " ".join(
            segment.text for segment in grouped["non_diegetic_music"]
        ) or "N/A",
    }
    rendered = _render(rendered_fields)
    actual = counter.count(rendered)
    context_verified = True
    try:
        context = asdict(
            plan_h3_context(
                counter,
                request.references,
                text_quality_limit=budget.text.quality_limit,
                special_tokens=0,
                runtime_safety_margin=4096,
            )
        )
        effective_quality_limit = int(context["effective_quality_limit"])
    except H3AuditError as exc:
        context_verified = False
        effective_quality_limit = budget.text.quality_limit
        hard_codes.append("context_verification")
        context = {
            "verified": False,
            "error": str(exc),
            "text_quality_limit": budget.text.quality_limit,
            "effective_quality_limit": None,
        }
    token_report = {
        "text": {
            "target": budget.text.target,
            "soft_limit": budget.text.soft_limit,
            "quality_limit": budget.text.quality_limit,
            "hard_limit": budget.text.hard_limit,
            "actual": actual,
            "dialogue_tokens": dialogue_tokens,
        },
        "context": context,
    }
    trace = ledger.trace_rendering(compressed.segments)
    if compressed.conflict is not None or actual > effective_quality_limit:
        conflict = (
            asdict(compressed.conflict)
            if compressed.conflict is not None
            else _render_overhead_conflict(actual, effective_quality_limit)
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
            context_verified,
        )

    definitions = rendered_fields["subject_definitions"]
    summary = rendered_fields["summary"]
    retention = rendered_fields["retention_analysis"]
    detail = rendered_fields["detailed_description"]
    usage = "\n".join((summary, retention, detail))
    shots = ()
    try:
        audit_reference_labels(definitions, usage, request.references)
        _audit_retention_bindings(retention, len(request.references))
    except H3AuditError:
        hard_codes.append("reference_binding")
    if not _SUMMARY_PREFIX.match(summary):
        hard_codes.append("summary_grammar")
    try:
        shots = parse_shots(
            detail,
            duration_seconds=request.duration_seconds,
            declared_shot_count=request.shot_count,
        )
        audit_shot_execution(shots, ledger)
    except H3AuditError:
        hard_codes.append("timeline")
    try:
        audit_dialogue_and_visible_text(detail, ledger)
    except H3AuditError:
        hard_codes.append("exact_dialogue_or_visible_text")
    try:
        audit_sound_music_separation(
            rendered_fields["overall_soundscape"],
            rendered_fields["non_diegetic_music"],
        )
    except H3AuditError:
        hard_codes.append("sound_music_separation")
    if not definitions:
        hard_codes.append("subject_definitions")
    if not retention:
        hard_codes.append("retention_analysis")
    if not detail:
        hard_codes.append("detailed_description")
    hard_codes = list(dict.fromkeys(hard_codes))
    audit = {
        "release_blocking": bool(hard_codes),
        "hard_gate_codes": hard_codes,
        "shots": [asdict(shot) for shot in shots],
        "official_field_order": list(_FIELD_ORDER),
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
            context_verified,
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
        context_verified,
    )


def _normalize_fields(request: H3Ref2VAAuthoringRequest) -> tuple[AuthoredSegment, ...]:
    groups = (
        ("subject_definitions", request.subject_definitions),
        ("summary", request.summary),
        ("retention_analysis", request.retention_analysis),
        ("detailed_description", request.detailed_description),
        ("overall_soundscape", request.overall_soundscape),
        ("non_diegetic_music", request.non_diegetic_music),
    )
    return tuple(
        replace(segment, field=field)
        for field, group in groups
        for segment in group
    )


def _stable_appearance_outside_definitions(
    request: H3Ref2VAAuthoringRequest,
    ledger: FactLedger,
) -> bool:
    other_segments = (
        *request.summary,
        *request.retention_analysis,
        *request.detailed_description,
        *request.overall_soundscape,
        *request.non_diegetic_music,
    )
    return any(
        ledger.get(fact_id).dimension == "stable_appearance"
        for segment in other_segments
        for fact_id in segment.fact_ids
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
        structure="h3_ref2va",
    )


def _group_segments(
    segments: tuple[AuthoredSegment, ...],
) -> dict[str, tuple[AuthoredSegment, ...]]:
    return {
        field: tuple(segment for segment in segments if segment.field == field)
        for field in _FIELD_ORDER
    }


def _render(fields: dict[str, str]) -> str:
    return "\n\n".join(f"{field}: {fields[field]}" for field in _FIELD_ORDER)


def _audit_retention_bindings(retention: str, reference_count: int) -> None:
    for index in range(1, reference_count + 1):
        if f"<Picture {index}>" not in retention:
            raise H3AuditError(
                f"retention_analysis must bind Picture {index} explicitly"
            )


def _safe_duration(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 2.0
    return min(15.0, max(2.0, float(value)))


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


def _artifact(
    status: str,
    request: H3Ref2VAAuthoringRequest,
    prompt: dict[str, str] | None,
    trace: dict[str, tuple[str, ...]],
    token_report: dict[str, object],
    audit: dict[str, object],
    compression: CompressionResult,
    conflict: dict[str, object] | None,
    token_count_verified: bool,
) -> PromptArtifact:
    return create_prompt_artifact(
        status=status,  # type: ignore[arg-type]
        task="h3_ref2va",
        model=_MODEL,
        prompt=prompt,
        facts=request.facts,
        trace=trace,
        token_report=token_report,
        audit=audit,
        compression=compression.operations,
        conflict=conflict,
        token_count_verified=token_count_verified,
        knowledge_manifest_sha256=_knowledge_hash(),
    )


def _knowledge_hash() -> str:
    digest = hashlib.sha256()
    digest.update((_TOKENIZER / "manifest.json").read_bytes())
    digest.update(_POLICY.read_bytes())
    return digest.hexdigest()
