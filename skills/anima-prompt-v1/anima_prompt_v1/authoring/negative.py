"""Negative-channel author with explicit layers and no hidden defaults."""

from __future__ import annotations

from ..catalog import Catalog
from ..domain import PromptBrief
from ..draft import PromptSegment
from .positive import fact_segment


def build_negative_segments(
    brief: PromptBrief,
    catalog: Catalog,
    route: str,
    *,
    structural_defects: tuple[PromptSegment, ...] = (),
) -> tuple[PromptSegment, ...]:
    relation_ids = _relation_ids_by_fact(brief)
    explicit = tuple(
        fact_segment(fact, "negative", catalog, route, relation_ids.get(fact.fact_id, ()), brief.source_priority)
        for fact in brief.exclusions
    )
    return select_negative_segments(
        explicit,
        structural_defects,
    )


def select_negative_segments(
    explicit_exclusions: tuple[PromptSegment, ...],
    structural_defects: tuple[PromptSegment, ...],
) -> tuple[PromptSegment, ...]:
    """Compose mandatory model quality exclusions before user exclusions."""
    required = [
        segment for segment in explicit_exclusions
        if segment.fact_source == "official" and "required_by_anima_variant" in segment.fact_notes
    ]
    user = [segment for segment in explicit_exclusions if segment not in required]
    return tuple((*required, *user, *structural_defects))


def _relation_ids_by_fact(brief: PromptBrief) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {}
    for relation in brief.relations:
        if relation.source_fact_id is not None:
            result.setdefault(relation.source_fact_id, []).append(relation.relation_id)
    return {fact_id: tuple(ids) for fact_id, ids in result.items()}
