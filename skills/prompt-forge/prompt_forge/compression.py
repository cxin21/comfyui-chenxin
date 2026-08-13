"""Trace-preserving five-pass compression without token truncation."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

from .budgets import utility_density
from .contracts import AuthoredSegment
from .facts import FactLedger
from .token_counting import TokenCounter


Structure = Literal["anima", "h3_t2va", "h3_ref2va"]


@dataclass(frozen=True)
class CompressionOperation:
    pass_name: Literal[
        "exact_dedupe",
        "semantic_dedupe",
        "structure_extraction",
        "lexical_compression",
        "delete_agent_embellishment",
    ]
    before: str
    after: str
    reason: str
    fact_ids: tuple[str, ...]
    token_saving: int


@dataclass(frozen=True)
class ProtectedCause:
    dimension: str
    tokens: int
    reason: str
    fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class UserChoice:
    choice: str
    estimated_saving: int
    facts_affected: tuple[str, ...]


@dataclass(frozen=True)
class BudgetConflict:
    actual_tokens: int
    quality_limit: int
    mandatory_tokens: int
    agent_optional_tokens: int
    excess_tokens: int
    protected_causes: tuple[ProtectedCause, ...]
    user_choices: tuple[UserChoice, ...]
    sacrificed_facts: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompressionResult:
    status: Literal["within_budget", "budget_conflict"]
    segments: tuple[AuthoredSegment, ...]
    actual_tokens: int
    operations: tuple[CompressionOperation, ...]
    conflict: BudgetConflict | None
    sacrificed_facts: tuple[str, ...] = ()


_PROTECTED_DIMENSIONS = frozenset(
    {
        "dialogue",
        "visible_text",
        "count",
        "negation",
        "timestamp",
        "subject_id",
        "reference_id",
        "position",
        "color",
        "ownership",
        "action_result",
    }
)
_STRUCTURE_FIELDS: dict[Structure, dict[str, str]] = {
    "anima": {},
    "h3_t2va": {
        "shot_global_soundscape": "overall_soundscape",
        "shot_non_diegetic_music": "non_diegetic_music",
    },
    "h3_ref2va": {
        "detailed_stable_appearance": "subject_definitions",
        "shot_global_soundscape": "overall_soundscape",
        "shot_non_diegetic_music": "non_diegetic_music",
    },
}
_FILLER = re.compile(
    r"\b(?:beautiful|highly\s+detailed|atmospheric|very|extremely|stunning|gorgeous)\b",
    re.IGNORECASE,
)


def compress_to_budget(
    *,
    segments: tuple[AuthoredSegment, ...],
    ledger: FactLedger,
    counter: TokenCounter,
    soft_limit: int,
    quality_limit: int,
    structure: Structure,
) -> CompressionResult:
    if structure not in _STRUCTURE_FIELDS:
        raise ValueError(f"unsupported compression structure: {structure}")
    if (
        isinstance(soft_limit, bool)
        or isinstance(quality_limit, bool)
        or not isinstance(soft_limit, int)
        or not isinstance(quality_limit, int)
        or soft_limit < 0
        or quality_limit < soft_limit
    ):
        raise ValueError("limits must be integers with 0 <= soft_limit <= quality_limit")
    ledger.validate_segments(segments)
    ledger.trace_rendering(segments)
    current = list(segments)
    operations: list[CompressionOperation] = []
    actual = _count_segments(counter, current, structure)
    if actual <= soft_limit:
        return CompressionResult(
            "within_budget", tuple(current), actual, (), None
        )

    current, new_operations = _exact_dedupe(current, counter, structure)
    operations.extend(new_operations)
    current, new_operations = _semantic_dedupe(current, counter, structure)
    operations.extend(new_operations)
    current, new_operations = _extract_structure(current, counter, structure)
    operations.extend(new_operations)
    current, new_operations = _compress_lexically(current, ledger, counter)
    operations.extend(new_operations)
    current, new_operations = _delete_agent_embellishment(
        current,
        ledger,
        counter,
        soft_limit,
        structure,
    )
    operations.extend(new_operations)

    ledger.trace_rendering(current)
    actual = _count_segments(counter, current, structure)
    if actual <= quality_limit:
        return CompressionResult(
            "within_budget",
            tuple(current),
            actual,
            tuple(operations),
            None,
        )
    conflict = _build_conflict(
        current,
        ledger,
        counter,
        quality_limit,
        structure,
    )
    return CompressionResult(
        "budget_conflict",
        tuple(current),
        actual,
        tuple(operations),
        conflict,
    )


def _exact_dedupe(
    segments: list[AuthoredSegment],
    counter: TokenCounter,
    structure: Structure,
) -> tuple[list[AuthoredSegment], list[CompressionOperation]]:
    kept: list[AuthoredSegment] = []
    indices: dict[tuple[str, str], int] = {}
    operations: list[CompressionOperation] = []
    for segment in segments:
        key = (segment.field, _dedupe_text(_exact_text(segment.text), structure))
        previous_index = indices.get(key)
        if previous_index is None:
            indices[key] = len(kept)
            kept.append(segment)
            continue
        previous = kept[previous_index]
        fact_ids = tuple(dict.fromkeys((*previous.fact_ids, *segment.fact_ids)))
        kept[previous_index] = replace(previous, fact_ids=fact_ids)
        operations.append(
            CompressionOperation(
                "exact_dedupe",
                segment.text,
                "",
                f"exact duplicate merged into {previous.segment_id}",
                segment.fact_ids,
                counter.count(segment.text),
            )
        )
    return kept, operations


def _semantic_dedupe(
    segments: list[AuthoredSegment],
    counter: TokenCounter,
    structure: Structure,
) -> tuple[list[AuthoredSegment], list[CompressionOperation]]:
    groups: dict[tuple[frozenset[str], str], list[AuthoredSegment]] = {}
    for segment in segments:
        key = (
            frozenset(segment.fact_ids),
            _dedupe_text(_semantic_text(segment.text), structure),
        )
        groups.setdefault(key, []).append(segment)
    removed: set[str] = set()
    operations: list[CompressionOperation] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        winner = min(group, key=lambda item: (counter.count(item.text), item.segment_id))
        for segment in group:
            if segment.segment_id == winner.segment_id:
                continue
            removed.add(segment.segment_id)
            operations.append(
                CompressionOperation(
                    "semantic_dedupe",
                    segment.text,
                    winner.text,
                    "equal fact-ID set has the same normalized semantic",
                    segment.fact_ids,
                    max(0, counter.count(segment.text) - counter.count(winner.text)),
                )
            )
    return [segment for segment in segments if segment.segment_id not in removed], operations


def _extract_structure(
    segments: list[AuthoredSegment],
    counter: TokenCounter,
    structure: Structure,
) -> tuple[list[AuthoredSegment], list[CompressionOperation]]:
    mapping = _STRUCTURE_FIELDS[structure]
    result: list[AuthoredSegment] = []
    operations: list[CompressionOperation] = []
    for segment in segments:
        target = mapping.get(segment.field)
        if target is None:
            result.append(segment)
            continue
        result.append(replace(segment, field=target))
        operations.append(
            CompressionOperation(
                "structure_extraction",
                f"{segment.field}: {segment.text}",
                f"{target}: {segment.text}",
                "move stable or global content to its model-native field",
                segment.fact_ids,
                0,
            )
        )
    return result, operations


def _compress_lexically(
    segments: list[AuthoredSegment],
    ledger: FactLedger,
    counter: TokenCounter,
) -> tuple[list[AuthoredSegment], list[CompressionOperation]]:
    result: list[AuthoredSegment] = []
    operations: list[CompressionOperation] = []
    for segment in segments:
        facts = tuple(ledger.get(fact_id) for fact_id in segment.fact_ids)
        if any(
            fact.origin != "agent_embellishment"
            or fact.dimension in _PROTECTED_DIMENSIONS
            for fact in facts
        ):
            result.append(segment)
            continue
        compressed = _FILLER.sub("", segment.text)
        compressed = re.sub(r"\s+", " ", compressed).strip(" ,;.-")
        if not compressed or compressed == segment.text:
            result.append(segment)
            continue
        result.append(replace(segment, text=compressed))
        operations.append(
            CompressionOperation(
                "lexical_compression",
                segment.text,
                compressed,
                "remove non-semantic agent-authored intensifiers",
                segment.fact_ids,
                max(0, counter.count(segment.text) - counter.count(compressed)),
            )
        )
    return result, operations


def _delete_agent_embellishment(
    segments: list[AuthoredSegment],
    ledger: FactLedger,
    counter: TokenCounter,
    soft_limit: int,
    structure: Structure,
) -> tuple[list[AuthoredSegment], list[CompressionOperation]]:
    current = list(segments)
    candidates: list[tuple[float, str]] = []
    for segment in current:
        facts = tuple(ledger.get(fact_id) for fact_id in segment.fact_ids)
        if not all(fact.origin == "agent_embellishment" for fact in facts):
            continue
        token_cost = counter.count(segment.text)
        candidates.append(
            (
                utility_density(
                    segment.priority,
                    segment.adherence_risk,
                    segment.source_confidence,
                    1.0,
                    token_cost,
                ),
                segment.segment_id,
            )
        )
    operations: list[CompressionOperation] = []
    for _, segment_id in sorted(candidates):
        if _count_segments(counter, current, structure) <= soft_limit:
            break
        index = next(
            (position for position, item in enumerate(current) if item.segment_id == segment_id),
            None,
        )
        if index is None:
            continue
        segment = current.pop(index)
        operations.append(
            CompressionOperation(
                "delete_agent_embellishment",
                segment.text,
                "",
                "remove lowest-utility agent embellishment above the soft limit",
                segment.fact_ids,
                counter.count(segment.text),
            )
        )
    return current, operations


def _build_conflict(
    segments: list[AuthoredSegment],
    ledger: FactLedger,
    counter: TokenCounter,
    quality_limit: int,
    structure: Structure,
) -> BudgetConflict:
    actual = _count_segments(counter, segments, structure)
    mandatory = [
        segment
        for segment in segments
        if any(
            ledger.get(fact_id).origin != "agent_embellishment"
            for fact_id in segment.fact_ids
        )
    ]
    mandatory_tokens = _count_segments(counter, mandatory, structure)
    by_dimension: dict[str, set[str]] = {}
    by_dimension_segments: dict[str, list[AuthoredSegment]] = {}
    for segment in mandatory:
        for fact_id in segment.fact_ids:
            fact = ledger.get(fact_id)
            if fact.origin == "agent_embellishment":
                continue
            by_dimension.setdefault(fact.dimension, set()).add(fact_id)
            by_dimension_segments.setdefault(fact.dimension, []).append(segment)
    causes = tuple(
        ProtectedCause(
            dimension=dimension,
            tokens=_count_segments(counter, _unique_segments(items), structure),
            reason="protected facts in this dimension cannot be changed automatically",
            fact_ids=tuple(sorted(by_dimension[dimension])),
        )
        for dimension, items in sorted(by_dimension_segments.items())
    )
    choices = list(
        UserChoice(
            choice=f"simplify_{cause.dimension}",
            estimated_saving=max(1, ceil_third(cause.tokens)),
            facts_affected=cause.fact_ids,
        )
        for cause in causes
    )
    # Mixed segments (an agent fact and a protected fact on the same segment)
    # are the author's real escape hatch: unlinking the segment from the
    # protected fact moves its tokens into the compressible pool. Name them
    # explicitly so a conflict never forces the author to touch protected facts.
    for segment in mandatory:
        facts = tuple(ledger.get(fact_id) for fact_id in segment.fact_ids)
        protected = tuple(
            fact.fact_id for fact in facts if fact.origin != "agent_embellishment"
        )
        agent = tuple(
            fact.fact_id for fact in facts if fact.origin == "agent_embellishment"
        )
        if not protected or not agent:
            continue
        choices.append(
            UserChoice(
                choice=f"unlink_segment_{segment.segment_id}_from_protected_fact",
                estimated_saving=max(
                    1, ceil_third(_count_segments(counter, [segment], structure))
                ),
                facts_affected=protected,
            )
        )
    return BudgetConflict(
        actual_tokens=actual,
        quality_limit=quality_limit,
        mandatory_tokens=mandatory_tokens,
        agent_optional_tokens=max(0, actual - mandatory_tokens),
        excess_tokens=actual - quality_limit,
        protected_causes=causes,
        user_choices=tuple(choices),
    )


def _count_segments(
    counter: TokenCounter,
    segments: list[AuthoredSegment] | tuple[AuthoredSegment, ...],
    structure: Structure,
) -> int:
    separator = ", " if structure == "anima" else "\n"
    return counter.count(separator.join(segment.text for segment in segments))


def _unique_segments(segments: list[AuthoredSegment]) -> list[AuthoredSegment]:
    by_id = {segment.segment_id: segment for segment in segments}
    return [by_id[key] for key in sorted(by_id)]


def _dedupe_text(text: str, structure: Structure) -> str:
    if structure != "anima":
        return text
    from .anima.protocol import deweight
    return deweight(text)


def _exact_text(text: str) -> str:
    return " ".join(text.split())


def _semantic_text(text: str) -> str:
    words = re.findall(r"[\w@]+", text.lower())
    return " ".join(word for word in words if word not in {"a", "an", "the"})


def ceil_third(value: int) -> int:
    return (value + 2) // 3
