"""The immutable fact ledger that feeds every later module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FactKind = Literal["explicit", "inferred", "unknown"]
FactSource = Literal["user", "local_model", "official", "community", "default"]
FactDomain = Literal[
    "subject", "appearance", "clothing", "expression", "hair", "pose",
    "action", "scene", "style", "lighting", "camera", "region", "object", "quality", "safety", "meta",
]
RepresentationHint = Literal["auto", "tag", "prose"]
RelationType = Literal[
    "has_attribute", "performs", "located_at", "interacts_with", "occludes", "faces",
    "contains", "uses_style", "uses_lighting", "uses_camera", "receives_or_is_target_of",
    "left_of", "right_of", "in_front_of", "behind", "near", "far", "not_interacting",
]

_KINDS = frozenset(("explicit", "inferred", "unknown"))
_SOURCES = frozenset(("user", "local_model", "official", "community", "default"))
_DOMAINS = frozenset((
    "subject", "appearance", "clothing", "expression", "hair", "pose", "action",
    "scene", "style", "lighting", "camera", "region", "object", "quality", "safety", "meta",
))
_RELATIONS = frozenset((
    "has_attribute", "performs", "located_at", "interacts_with", "occludes", "faces",
    "contains", "uses_style", "uses_lighting", "uses_camera", "receives_or_is_target_of",
    "left_of", "right_of", "in_front_of", "behind", "near", "far", "not_interacting",
))


def _nonempty(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


@dataclass(frozen=True)
class Fact:
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

    def __post_init__(self) -> None:
        _nonempty(self.fact_id, "fact_id")
        _nonempty(self.value, "value")
        if self.domain not in _DOMAINS:
            raise ValueError(f"invalid fact domain: {self.domain!r}")
        if self.kind not in _KINDS:
            raise ValueError(f"invalid fact kind: {self.kind!r}")
        if self.source not in _SOURCES:
            raise ValueError(f"invalid fact source: {self.source!r}")
        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
                raise ValueError("confidence must be a number between 0 and 1")
        if self.representation_hint not in {"auto", "tag", "prose"}:
            raise ValueError(f"invalid representation hint: {self.representation_hint!r}")
        if not isinstance(self.notes, tuple) or any(not isinstance(note, str) or not note.strip() for note in self.notes):
            raise ValueError("notes must be a tuple of non-empty strings")


@dataclass(frozen=True)
class Subject:
    subject_id: str
    label: str

    def __post_init__(self) -> None:
        _nonempty(self.subject_id, "subject_id")
        _nonempty(self.label, "label")


@dataclass(frozen=True)
class RelationClaim:
    relation_id: str
    relation_type: RelationType
    from_id: str
    to_id: str
    explicit: bool
    source_fact_id: str | None = None

    def __post_init__(self) -> None:
        _nonempty(self.relation_id, "relation_id")
        _nonempty(self.from_id, "from_id")
        _nonempty(self.to_id, "to_id")
        if self.relation_type not in _RELATIONS:
            raise ValueError(f"invalid relation type: {self.relation_type!r}")


@dataclass(frozen=True)
class LockedSegment:
    segment_id: str
    text: str
    representation: Literal["text", "tag", "trigger", "wildcard", "weight"] = "text"

    def __post_init__(self) -> None:
        _nonempty(self.segment_id, "segment_id")
        _nonempty(self.text, "text")
        if self.representation not in {"text", "tag", "trigger", "wildcard", "weight"}:
            raise ValueError(f"invalid locked representation: {self.representation!r}")


@dataclass(frozen=True)
class PromptBrief:
    facts: tuple[Fact, ...]
    subjects: tuple[Subject, ...]
    relations: tuple[RelationClaim, ...] = ()
    exclusions: tuple[Fact, ...] = ()
    locked_segments: tuple[LockedSegment, ...] = ()
    source_priority: tuple[FactSource, ...] = ("user", "local_model", "official", "community", "default")

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        collections = (self.facts, self.subjects, self.relations, self.exclusions, self.locked_segments, self.source_priority)
        if any(not isinstance(value, tuple) for value in collections):
            raise ValueError("PromptBrief collections must be tuples")
        if any(not isinstance(value, Fact) for value in (*self.facts, *self.exclusions)):
            raise ValueError("facts and exclusions must contain Fact values")
        if any(not isinstance(value, Subject) for value in self.subjects):
            raise ValueError("subjects must contain Subject values")
        if any(not isinstance(value, RelationClaim) for value in self.relations):
            raise ValueError("relations must contain RelationClaim values")
        if any(not isinstance(value, LockedSegment) for value in self.locked_segments):
            raise ValueError("locked_segments must contain LockedSegment values")
        ids = [fact.fact_id for fact in (*self.facts, *self.exclusions)]
        if len(ids) != len(set(ids)):
            raise ValueError("fact ids must be unique")
        subject_ids = [subject.subject_id for subject in self.subjects]
        if len(subject_ids) != len(set(subject_ids)):
            raise ValueError("subject ids must be unique")
        locked_ids = [segment.segment_id for segment in self.locked_segments]
        if len(locked_ids) != len(set(locked_ids)):
            raise ValueError("locked segment ids must be unique")
        known_ids = set(ids) | set(subject_ids)
        if any(fact.subject_id is not None and fact.subject_id not in subject_ids for fact in (*self.facts, *self.exclusions)):
            raise ValueError("fact subject_id must refer to a known subject")
        if any(relation.from_id not in known_ids or relation.to_id not in known_ids for relation in self.relations):
            raise ValueError("relation endpoints must refer to a known subject or fact")
        if any(relation.source_fact_id is not None and relation.source_fact_id not in ids for relation in self.relations):
            raise ValueError("relation source_fact_id must refer to a known fact")
        if any(source not in _SOURCES for source in self.source_priority):
            raise ValueError("source_priority contains an unknown source")

    def explicit_facts(self) -> tuple[Fact, ...]:
        return tuple(fact for fact in self.facts if fact.kind == "explicit")

    @property
    def scene(self) -> tuple[Fact, ...]:
        return tuple(fact for fact in self.facts if fact.domain == "scene")

    @property
    def style(self) -> tuple[Fact, ...]:
        return tuple(fact for fact in self.facts if fact.domain == "style")

    @property
    def lighting(self) -> tuple[Fact, ...]:
        return tuple(fact for fact in self.facts if fact.domain == "lighting")

    @property
    def camera(self) -> tuple[Fact, ...]:
        return tuple(fact for fact in self.facts if fact.domain == "camera")

    @property
    def inferred(self) -> tuple[Fact, ...]:
        return tuple(fact for fact in (*self.facts, *self.exclusions) if fact.kind == "inferred")

    @property
    def unknowns(self) -> tuple[Fact, ...]:
        return tuple(fact for fact in (*self.facts, *self.exclusions) if fact.kind == "unknown")

    @property
    def notes(self) -> tuple[str, ...]:
        return tuple(note for fact in (*self.facts, *self.exclusions) for note in fact.notes)
