"""Deterministic high-quality Anima prompt compiler."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path

from ..artifacts import PromptArtifact, create_prompt_artifact
from ..budgets import BudgetWindow, plan_anima_budget
from ..compression import CompressionOperation, CompressionResult, compress_to_budget
from ..contracts import AnimaAuthoringRequest, AuthoredSegment
from ..facts import FactLedger
from ..token_counting import TokenCounter
from .audit import AnimaAuditReport, audit_anima_prompt
from .protocol import semantic_form


_MODEL = "circlestone-labs/Anima"
_SKILL_ROOT = Path(__file__).resolve().parents[2]
_TOKENIZER = _SKILL_ROOT / "knowledge" / "tokenizers" / "anima-qwen3-0.6b"
_MANIFEST = _SKILL_ROOT / "knowledge" / "anima" / "manifest.json"
_FIELD_RANK = {
    "protocol_prefix": 0,
    "count": 1,
    "character": 2,
    "series": 3,
    "artist": 4,
    "appearance": 5,
    "general": 6,
    "environment": 7,
    "scene_description": 8,
}
_NEGATIVE_FIELDS = {
    "quality_baseline",
    "anatomy_and_structure",
    "technical_defects",
    "user_exclusions",
}
_BRIDGE_DIMENSIONS = frozenset(
    {"ownership", "spatial_relation", "causal_action", "action_result", "relation"}
)


def author_anima_prompt(request: AnimaAuthoringRequest) -> PromptArtifact:
    ledger = FactLedger(request.facts)
    all_segments = (*request.positive_segments, *request.negative_segments)
    ledger.validate_segments(all_segments)
    ledger.trace_rendering(all_segments)
    budget = plan_anima_budget(request.complexity, request.exclusion_groups)
    counter = TokenCounter.load(_TOKENIZER, "anima-qwen3-0.6b")
    hard_codes: list[str] = []

    indexed = list(enumerate(request.positive_segments))
    unknown_fields = sorted(
        {segment.field for _, segment in indexed if segment.field not in _FIELD_RANK}
    )
    if unknown_fields:
        hard_codes.append("unsupported_positive_field")
    unknown_negative = sorted(
        {segment.field for segment in request.negative_segments if segment.field not in _NEGATIVE_FIELDS}
    )
    if unknown_negative:
        hard_codes.append("unsupported_negative_field")

    ordered_positive = tuple(
        segment
        for _, segment in sorted(
            indexed,
            key=lambda item: (_FIELD_RANK.get(item[1].field, 99), item[0]),
        )
    )
    if not any(segment.field == "protocol_prefix" for segment in ordered_positive):
        hard_codes.append("missing_protocol_prefix")
    bridges = tuple(
        segment for segment in ordered_positive if segment.field == "scene_description"
    )
    tag_segments = tuple(
        segment for segment in ordered_positive if segment.field != "scene_description"
    )
    if len(bridges) != request.complexity.natural_language_bridges or len(bridges) > 1:
        hard_codes.append("natural_language_bridge_count")
    tag_fact_ids = {fact_id for segment in tag_segments for fact_id in segment.fact_ids}
    bridge_fact_ids = {fact_id for segment in bridges for fact_id in segment.fact_ids}
    if tag_fact_ids.intersection(bridge_fact_ids):
        hard_codes.append("tag_bridge_fact_overlap")
    if any(
        ledger.get(fact_id).dimension not in _BRIDGE_DIMENSIONS
        for fact_id in bridge_fact_ids
    ):
        hard_codes.append("unsupported_bridge_semantic")

    positive_result = _compress_stream(
        tag_segments + bridges,
        ledger,
        counter,
        budget.positive,
    )
    negative_result = _compress_stream(
        request.negative_segments,
        ledger,
        counter,
        budget.negative,
    )
    compressed_positive = positive_result.segments
    compressed_tags = tuple(
        segment for segment in compressed_positive if segment.field != "scene_description"
    )
    compressed_bridges = tuple(
        segment for segment in compressed_positive if segment.field == "scene_description"
    )
    positive_text = _render_positive(compressed_tags, compressed_bridges)
    negative_text = ", ".join(_render_segment(segment) for segment in negative_result.segments)
    positive_tokens = counter.count(positive_text)
    negative_tokens = counter.count(negative_text)
    trace = ledger.trace_rendering(
        (*positive_result.segments, *negative_result.segments)
    )
    token_report = {
        "positive": _token_report(budget.positive, positive_tokens),
        "negative": _token_report(budget.negative, negative_tokens),
    }
    compression = (*positive_result.operations, *negative_result.operations)

    # Audit the compressed streams *before* the budget-conflict short-circuit.
    # Protocol findings are compression-independent, so an over-budget build
    # still surfaces every hard error in one pass instead of forcing the author
    # to fix the budget first and only then discover the next gate.
    positive_audit = audit_anima_prompt(
        tuple(segment.text for segment in compressed_tags),
        " ".join(segment.text for segment in compressed_bridges),
        ledger,
    )
    negative_audit = (
        audit_anima_prompt(
            tuple(segment.text for segment in negative_result.segments),
            "",
            ledger,
        )
        if negative_result.segments
        else None
    )
    audit_error_codes = _audit_error_codes(positive_audit, negative_audit)

    conflict = positive_result.conflict or negative_result.conflict
    if conflict is not None:
        conflict_codes = list(
            dict.fromkeys(
                ("token_quality_limit", *hard_codes, *audit_error_codes)
                + (
                    ("positive_negative_contradiction",)
                    if _contradicts(compressed_tags, negative_result.segments)
                    else ()
                )
            )
        )
        return _artifact(
            status="budget_conflict",
            request=request,
            prompt=None,
            trace=trace,
            token_report=token_report,
            audit={
                "release_blocking": True,
                "hard_gate_codes": conflict_codes,
                "positive": _audit_payload(positive_audit),
                "negative": _audit_payload(negative_audit) if negative_audit else None,
            },
            compression=compression,
            conflict=asdict(conflict),
        )

    hard_codes.extend(audit_error_codes)
    if _contradicts(compressed_tags, negative_result.segments):
        hard_codes.append("positive_negative_contradiction")
    if positive_tokens > budget.positive.quality_limit:
        hard_codes.append("positive_token_quality_limit")
    if negative_tokens > budget.negative.quality_limit:
        hard_codes.append("negative_token_quality_limit")
    hard_codes = list(dict.fromkeys(hard_codes))
    audit_payload = {
        "release_blocking": bool(hard_codes),
        "hard_gate_codes": hard_codes,
        "positive": _audit_payload(positive_audit),
        "negative": _audit_payload(negative_audit) if negative_audit else None,
        "unknown_positive_fields": unknown_fields,
        "unknown_negative_fields": unknown_negative,
    }
    if hard_codes:
        return _artifact(
            status="quality_rejected",
            request=request,
            prompt=None,
            trace=trace,
            token_report=token_report,
            audit=audit_payload,
            compression=compression,
            conflict=None,
        )
    return _artifact(
        status="production_ready",
        request=request,
        prompt={"positive": positive_text, "negative": negative_text},
        trace=trace,
        token_report=token_report,
        audit=audit_payload,
        compression=compression,
        conflict=None,
    )


def _compress_stream(
    segments: tuple[AuthoredSegment, ...],
    ledger: FactLedger,
    counter: TokenCounter,
    budget: BudgetWindow,
) -> CompressionResult:
    if not segments:
        return CompressionResult("within_budget", (), 0, (), None)
    fact_ids = tuple(
        dict.fromkeys(fact_id for segment in segments for fact_id in segment.fact_ids)
    )
    stream_ledger = FactLedger(tuple(ledger.get(fact_id) for fact_id in fact_ids))
    return compress_to_budget(
        segments=segments,
        ledger=stream_ledger,
        counter=counter,
        soft_limit=budget.soft_limit,
        quality_limit=budget.quality_limit,
        structure="anima",
    )


def _render_segment(segment: AuthoredSegment) -> str:
    if segment.render_weight is None:
        return segment.text
    return f"({segment.text}:{segment.render_weight:g})"


def _render_positive(
    tags: tuple[AuthoredSegment, ...],
    bridges: tuple[AuthoredSegment, ...],
) -> str:
    tag_text = ", ".join(_render_segment(segment) for segment in tags)
    bridge_text = " ".join(_render_segment(segment) for segment in bridges)
    if not bridge_text:
        return tag_text
    if not tag_text:
        return bridge_text
    separator = " " if tag_text.endswith((".", "!", "?")) else ". "
    return f"{tag_text}{separator}{bridge_text}"


def _token_report(window: BudgetWindow, actual: int) -> dict[str, int]:
    return {
        "target": window.target,
        "soft_limit": window.soft_limit,
        "quality_limit": window.quality_limit,
        "hard_limit": window.hard_limit,
        "actual": actual,
    }


def _audit_payload(report: AnimaAuditReport) -> dict[str, object]:
    return {
        "release_blocking": report.release_blocking,
        "entries": [asdict(entry) for entry in report.entries],
        "findings": [asdict(finding) for finding in report.findings],
    }


def _audit_error_codes(
    positive: AnimaAuditReport,
    negative: AnimaAuditReport | None,
) -> list[str]:
    """Collect release-blocking finding codes across both audited streams."""
    codes: list[str] = []
    for report in (positive, negative):
        if report is None:
            continue
        codes.extend(
            finding.code
            for finding in report.findings
            if finding.severity == "error" or finding.code == "possible_binding_conflict"
        )
    return list(dict.fromkeys(codes))


def _contradicts(
    positive: tuple[AuthoredSegment, ...],
    negative: tuple[AuthoredSegment, ...],
) -> bool:
    positive_semantics = {semantic_form(segment.text) for segment in positive}
    negative_semantics = {semantic_form(segment.text) for segment in negative}
    return bool((positive_semantics - {""}).intersection(negative_semantics))


def _artifact(
    *,
    status: str,
    request: AnimaAuthoringRequest,
    prompt: dict[str, str] | None,
    trace: dict[str, tuple[str, ...]],
    token_report: dict[str, object],
    audit: dict[str, object],
    compression: tuple[CompressionOperation, ...],
    conflict: dict[str, object] | None,
) -> PromptArtifact:
    return create_prompt_artifact(
        status=status,  # type: ignore[arg-type]
        task="anima",
        model=_MODEL,
        prompt=prompt,
        facts=request.facts,
        trace=trace,
        token_report=token_report,
        audit=audit,
        compression=compression,
        conflict=conflict,
        token_count_verified=True,
        knowledge_manifest_sha256=_sha256(_MANIFEST),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
