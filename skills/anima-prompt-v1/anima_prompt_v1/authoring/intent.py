"""Validated boundary between parsed intent and the immutable domain ledger."""

from __future__ import annotations

from dataclasses import dataclass
import re

from ..catalog import Catalog
from ..domain import Fact, FactDomain, FactKind, FactSource, LockedSegment, PromptBrief, RelationClaim, RepresentationHint, Subject


@dataclass(frozen=True)
class IntentClause:
    fact_id: str
    value: str
    domain: FactDomain
    kind: FactKind
    source: FactSource
    locked: bool = False
    confidence: float | None = None
    user_text: str | None = None
    subject_id: str | None = None
    representation_hint: RepresentationHint = "auto"
    notes: tuple[str, ...] = ()

    def to_fact(self) -> Fact:
        return Fact(
            fact_id=self.fact_id, value=self.value, domain=self.domain, kind=self.kind,
            source=self.source, locked=self.locked, confidence=self.confidence,
            user_text=self.user_text, subject_id=self.subject_id,
            representation_hint=self.representation_hint, notes=self.notes,
        )


class IntentParser:
    def __init__(self, catalog: Catalog | None = None) -> None:
        self.catalog = catalog or Catalog()

    def parse(
        self,
        *,
        subjects: tuple[Subject, ...],
        facts: tuple[IntentClause, ...] = (),
        exclusions: tuple[IntentClause, ...] = (),
        relations: tuple[RelationClaim, ...] = (),
        locked_segments: tuple[LockedSegment, ...] = (),
        source_priority: tuple[FactSource, ...] = ("user", "local_model", "official", "community", "default"),
    ) -> PromptBrief:
        return PromptBrief(
            facts=tuple(clause.to_fact() for clause in facts), subjects=tuple(subjects),
            relations=tuple(relations), exclusions=tuple(clause.to_fact() for clause in exclusions),
            locked_segments=tuple(locked_segments), source_priority=tuple(source_priority),
        )

    def parse_text(
        self,
        text: str,
        *,
        subjects: tuple[Subject, ...] = (),
        exclusions: tuple[str, ...] = (),
        subject_id: str | None = None,
    ) -> PromptBrief:
        facts = tuple(self._text_clause(value, index, subject_id) for index, value in enumerate(_split_clauses(text)))
        excluded = tuple(self._text_clause(value, index, subject_id, exclusion=True) for index, value in enumerate(exclusions))
        return PromptBrief(facts=facts, subjects=tuple(subjects), exclusions=excluded)

    def _text_clause(self, value: str, index: int, subject_id: str | None, *, exclusion: bool = False) -> Fact:
        normalized = value.strip()
        if not normalized:
            raise ValueError("intent clauses must not be empty")
        hits = self.catalog.search(normalized, mode="auto", limit=1)
        accepted_hit = hits[0] if hits and hits[0].match_type != "fuzzy" else None
        if accepted_hit is not None:
            domain = _domain_for_category(accepted_hit.category)
            representation: RepresentationHint = "tag"
            kind: FactKind = "explicit"
        elif any(character.isspace() for character in normalized):
            domain = "scene"
            representation = "prose"
            kind = "explicit"
        else:
            domain = "appearance"
            representation = "tag"
            kind = "unknown"
        prefix = "exclusion" if exclusion else "fact"
        return Fact(
            fact_id=f"{prefix}:text:{index}", value=normalized, domain=domain, kind=kind, source="user",
            user_text=normalized, subject_id=subject_id, representation_hint=representation,
        )


def _split_clauses(text: str) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return tuple(value.strip() for value in re.split(r"[,，;；\n]+", text) if value.strip())


def _domain_for_category(category: str) -> FactDomain:
    if category == "character":
        return "subject"
    if category in {"artist", "copyright", "style"}:
        return "style"
    if category in {"quality", "meta"}:
        return "quality"
    if category == "clothing":
        return "clothing"
    if category == "hair":
        return "hair"
    if category == "expression":
        return "expression"
    return "appearance"
