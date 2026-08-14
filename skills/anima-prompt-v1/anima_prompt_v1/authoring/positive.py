"""Positive-channel author: preserves facts and renders explicit relations."""

from __future__ import annotations

from ..catalog import Catalog
from ..domain import Fact, LockedSegment, PromptBrief, RelationClaim
from ..draft import PromptSegment
from .protocol import fact_priority

_TAG_DOMAINS = frozenset(("subject", "appearance", "clothing", "expression", "hair", "pose", "style", "quality", "safety", "meta"))
_RELATION_WORDS = {
    "has_attribute": "has",
    "performs": "performs",
    "located_at": "is located at",
    "interacts_with": "interacts with",
    "occludes": "occludes",
    "faces": "faces",
    "contains": "contains",
    "uses_style": "uses the style",
    "uses_lighting": "uses the lighting",
    "uses_camera": "uses the camera",
    "receives_or_is_target_of": "is the target of",
    "left_of": "is left of",
    "right_of": "is right of",
    "in_front_of": "is in front of",
    "behind": "is behind",
    "near": "is near",
    "far": "is far from",
    "not_interacting": "does not interact with",
}


def build_positive_segments(
    brief: PromptBrief,
    catalog: Catalog,
    route: str,
) -> tuple[PromptSegment, ...]:
    segments: list[PromptSegment] = []
    relation_ids = _relation_ids_by_fact(brief)
    for index, locked in enumerate(brief.locked_segments):
        segments.append(_locked_segment(locked, index))
    explicit_subject_labels = {fact.value for fact in brief.facts if fact.domain == "subject"}
    for subject in brief.subjects:
        if subject.label not in explicit_subject_labels:
            segments.append(PromptSegment(
                f"subject:{subject.subject_id}", "positive", subject.label,
                "user", "tag", False, 0, None, subject.subject_id,
            ))
    existing = {segment.segment_id for segment in segments}
    for fact in brief.facts:
        if fact.fact_id not in existing:
            segments.append(fact_segment(fact, "positive", catalog, route, relation_ids.get(fact.fact_id, ()), brief.source_priority))
    labels = _labels(brief)
    for claim in brief.relations:
        segment = relation_segment(claim, labels)
        if segment.segment_id not in existing:
            segments.append(segment)
    return tuple(segments)


def fact_segment(
    fact: Fact,
    channel: str,
    catalog: Catalog,
    route: str,
    relation_ids: tuple[str, ...] = (),
    source_priority: tuple[str, ...] = ("user", "local_model", "official", "community", "default"),
) -> PromptSegment:
    representation = representation_for(fact, route)
    hit = resolve_tag(catalog, fact.value) if representation == "tag" else None
    return PromptSegment(
        fact.fact_id,
        channel,
        fact.value,
        origin_for_source(fact.source),
        representation,
        fact.locked,
        fact_priority(fact, source_priority),
        fact.fact_id,
        fact.subject_id,
        hit.record_id if hit else None,
        hit.canonical_name if hit else None,
        hit.matched_name if hit else None,
        hit.match_type if hit else None,
        hit.source if hit else None,
        hit.source_version if hit else None,
        hit.score if hit else None,
        fact.kind,
        fact.source,
        fact.user_text,
        fact.notes,
        relation_ids,
        hit.provenance if hit else (),
    )


def relation_segment(claim: RelationClaim, labels: dict[str, str]) -> PromptSegment:
    from_label = labels.get(claim.from_id, claim.from_id)
    to_label = labels.get(claim.to_id, claim.to_id)
    verb = _RELATION_WORDS[claim.relation_type]
    text = f"{from_label} {verb} {to_label}"
    return PromptSegment(
        segment_id=f"relation:{claim.relation_id}",
        channel="positive",
        text=text,
        origin="user" if claim.explicit else "model",
        representation="prose",
        locked=False,
        priority=560,
        fact_id=claim.source_fact_id,
        subject_id=claim.from_id if claim.from_id.startswith("subject:") else None,
        relation_ids=(claim.relation_id,),
    )


def _labels(brief: PromptBrief) -> dict[str, str]:
    labels = {subject.subject_id: subject.label for subject in brief.subjects}
    labels.update({fact.fact_id: fact.value for fact in (*brief.facts, *brief.exclusions)})
    return labels


def _relation_ids_by_fact(brief: PromptBrief) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {}
    for relation in brief.relations:
        if relation.source_fact_id is not None:
            result.setdefault(relation.source_fact_id, []).append(relation.relation_id)
    return {fact_id: tuple(ids) for fact_id, ids in result.items()}


def representation_for(fact: Fact, route: str) -> str:
    if fact.representation_hint != "auto":
        return fact.representation_hint
    if route == "natural-language-led":
        return "prose"
    if route in {"tag-led", "hybrid"}:
        return "tag" if fact.domain in _TAG_DOMAINS else "prose"
    raise ValueError(f"invalid route: {route!r}")


def resolve_tag(catalog: Catalog | None, value: str):
    if catalog is None:
        return None
    hits = catalog.search(value, mode="auto", limit=1)
    if not hits or hits[0].match_type == "fuzzy":
        return None
    return hits[0]


def origin_for_source(source: str) -> str:
    if source == "user":
        return "user"
    if source in {"official", "community"}:
        return "catalog"
    if source == "local_model":
        return "model"
    return "default"


def _locked_segment(segment: LockedSegment, index: int) -> PromptSegment:
    return PromptSegment(segment.segment_id, "positive", segment.text, "user", segment.representation, True, -1000 + index)
