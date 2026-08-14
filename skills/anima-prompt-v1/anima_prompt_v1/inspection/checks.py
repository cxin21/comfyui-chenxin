"""Pure, non-blocking inspection orchestration."""

from __future__ import annotations

from typing import Callable

from ..authoring.relation_graph import VisualRelationGraph
from ..authoring.routing import ModelProfile, required_quality_terms
from ..domain import PromptBrief
from ..draft import PromptDraft
from .conflicts import inspect_conflicts, inspect_duplicates
from .token_estimate import estimate_tokens
from .types import InspectionIssue, InspectionReport
from .weights import inspect_weights


def inspect_draft(
    draft: PromptDraft,
    *,
    brief: PromptBrief | None = None,
    graph: VisualRelationGraph | None = None,
    tokenizer: Callable[[str], int] | None = None,
) -> InspectionReport:
    issues: list[InspectionIssue] = []
    issues.extend(inspect_weights(draft.positive_text))
    issues.extend(inspect_weights(draft.negative_text))
    issues.extend(inspect_conflicts(draft.positive_text, draft.negative_text))
    issues.extend(inspect_duplicates(draft.positive_text))
    issues.extend(inspect_duplicates(draft.negative_text))
    if not draft.positive_text.strip():
        issues.append(InspectionIssue("empty_positive", "warning", "positive prompt is empty"))
    for segment in draft.segments:
        target = draft.positive_text if segment.channel == "positive" else draft.negative_text
        if segment.text not in target:
            issues.append(InspectionIssue("segment_missing", "conflict" if segment.locked else "warning", f"segment is missing: {segment.text}", segment.segment_id))
    if brief is not None:
        present = {segment.segment_id for segment in draft.segments}
        for fact in (*brief.facts, *brief.exclusions):
            if fact.fact_id not in present:
                issues.append(InspectionIssue("fact_missing", "conflict" if fact.locked else "warning", f"fact is missing: {fact.value}", fact.fact_id))
        for locked in brief.locked_segments:
            segment = next((item for item in draft.segments if item.segment_id == locked.segment_id), None)
            if segment is None:
                issues.append(InspectionIssue("locked_segment_missing", "conflict", f"locked segment is missing: {locked.text}", locked.segment_id))
            else:
                target = draft.positive_text if segment.channel == "positive" else draft.negative_text
                if segment.text != locked.text or segment.representation != locked.representation or locked.text not in target:
                    issues.append(InspectionIssue("locked_segment_changed", "conflict", f"locked {locked.representation} was changed: {locked.text}", locked.segment_id))
        segments_by_fact = {segment.fact_id: segment for segment in draft.segments if segment.fact_id is not None}
        for relation in brief.relations:
            if relation.source_fact_id is not None:
                segment = segments_by_fact.get(relation.source_fact_id)
                if segment is None or relation.relation_id not in segment.relation_ids:
                    issues.append(InspectionIssue("relation_provenance_missing", "warning", f"relation is not attached to its source fact: {relation.relation_id}", relation.source_fact_id))
    if graph is not None:
        issues.extend(InspectionIssue("action_without_actor", "warning", action_id) for action_id in graph.actions_without_actor())
        issues.extend(InspectionIssue(advisory.code, "warning", advisory.message, ",".join(advisory.node_ids)) for advisory in graph.relation_advisories())
    issues.extend(inspect_model_profile(draft, draft.model_profile, tokenizer=tokenizer))
    text = f"{draft.positive_text}\n{draft.negative_text}"
    token_estimate = estimate_tokens(text, tokenizer)
    if tokenizer is not None and token_estimate is None:
        issues.append(InspectionIssue("token_estimate_unavailable", "warning", "token estimate is unavailable"))
    return InspectionReport(tuple(issues), token_estimate)


def inspect_model_profile(draft: PromptDraft, profile: ModelProfile, *, tokenizer: Callable[[str], int] | None = None) -> tuple[InspectionIssue, ...]:
    issues: list[InspectionIssue] = []
    positive = _normalize(draft.positive_text)
    for trigger in profile.trigger_words:
        if _normalize(trigger) not in positive:
            issues.append(InspectionIssue("missing_model_trigger", "warning", f"configured model trigger is not present: {trigger}", suggestion="add it explicitly if the model requires this trigger"))
    quality_policy = required_quality_terms(profile.variant)
    required_positive = quality_policy["positive"]
    required_negative = quality_policy["negative"]
    for term in required_positive:
        segment = _find_quality_segment(draft, "positive", term)
        if segment is None:
            issues.append(InspectionIssue("missing_required_positive_quality", "conflict", f"required positive quality term is missing: {term}", suggestion=f"add the official Anima quality term: {term}"))
        else:
            issues.extend(_inspect_quality_provenance(segment, term))
    for term in required_negative:
        segment = _find_quality_segment(draft, "negative", term)
        if segment is None:
            issues.append(InspectionIssue("missing_required_negative_quality", "conflict", f"required negative quality term is missing: {term}", suggestion=f"add the official Anima negative quality term: {term}"))
        else:
            issues.extend(_inspect_quality_provenance(segment, term))
    if profile.token_limit is not None:
        estimated = estimate_tokens(f"{draft.positive_text}\n{draft.negative_text}", tokenizer)
        if estimated is not None and estimated > profile.token_limit:
            issues.append(InspectionIssue("token_limit_exceeded", "warning", f"estimated tokens {estimated} exceed model limit {profile.token_limit}"))
    negative_count = sum(1 for segment in draft.segments if segment.channel == "negative")
    if profile.negative_tolerance == "concise" and negative_count > 8:
        issues.append(InspectionIssue("negative_too_long", "warning", f"turbo profile has {negative_count} negative segments; concise mode recommends at most 8"))
    return tuple(issues)


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


def _find_quality_segment(draft: PromptDraft, channel: str, term: str):
    normalized = _normalize(term)
    return next(
        (
            segment
            for segment in draft.segments
            if segment.channel == channel
            and _normalize(segment.text) == normalized
            and "required_by_anima_variant" in segment.fact_notes
        ),
        None,
    )


def _inspect_quality_provenance(segment, term: str) -> tuple[InspectionIssue, ...]:
    issues: list[InspectionIssue] = []
    if segment.fact_source != "official" or segment.catalog_match_type not in {"canonical", "exact", "alias"}:
        issues.append(InspectionIssue("quality_provenance_missing", "conflict", f"required quality term is not resolved from the official catalog: {term}", segment.segment_id))
    if not any("official_anima" in value for value in segment.catalog_provenance):
        issues.append(InspectionIssue("quality_provenance_missing", "conflict", f"required quality term lacks official_anima provenance: {term}", segment.segment_id))
    return tuple(issues)
