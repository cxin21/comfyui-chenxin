"""Channel-aware immutable prompt drafts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .domain import PromptBrief
from .authoring.routing import ModelProfile, Route

Channel = Literal["positive", "negative"]
Origin = Literal["user", "catalog", "model", "default"]
Representation = Literal["tag", "prose", "trigger", "wildcard", "weight", "text"]


@dataclass(frozen=True)
class PromptSegment:
    segment_id: str
    channel: Channel
    text: str
    origin: Origin
    representation: Representation
    locked: bool = False
    priority: int = 0
    fact_id: str | None = None
    subject_id: str | None = None
    catalog_record_id: str | None = None
    catalog_canonical: str | None = None
    catalog_matched_text: str | None = None
    catalog_match_type: str | None = None
    catalog_source: str | None = None
    catalog_source_version: str | None = None
    catalog_score: float | None = None
    fact_kind: str | None = None
    fact_source: str | None = None
    fact_user_text: str | None = None
    fact_notes: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    catalog_provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.segment_id.strip() or not self.text.strip():
            raise ValueError("segment_id and text must be non-empty")
        if self.channel not in {"positive", "negative"}:
            raise ValueError(f"invalid channel: {self.channel!r}")
        if self.origin not in {"user", "catalog", "model", "default"}:
            raise ValueError(f"invalid origin: {self.origin!r}")
        if self.representation not in {"tag", "prose", "trigger", "wildcard", "weight", "text"}:
            raise ValueError(f"invalid representation: {self.representation!r}")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise ValueError("priority must be an integer")
        if self.catalog_score is not None and (isinstance(self.catalog_score, bool) or not isinstance(self.catalog_score, (int, float))):
            raise ValueError("catalog_score must be numeric when provided")
        if self.fact_kind is not None and self.fact_kind not in {"explicit", "inferred", "unknown"}:
            raise ValueError("invalid fact_kind")
        if self.fact_source is not None and self.fact_source not in {"user", "local_model", "official", "community", "default"}:
            raise ValueError("invalid fact_source")
        if not isinstance(self.fact_notes, tuple) or any(not isinstance(note, str) or not note.strip() for note in self.fact_notes):
            raise ValueError("fact_notes must be a tuple of non-empty strings")
        if not isinstance(self.relation_ids, tuple) or any(not isinstance(value, str) or not value.strip() for value in self.relation_ids):
            raise ValueError("relation_ids must be a tuple of non-empty strings")
        if not isinstance(self.catalog_provenance, tuple) or any(not isinstance(value, str) or not value.strip() for value in self.catalog_provenance):
            raise ValueError("catalog_provenance must be a tuple of non-empty strings")


@dataclass(frozen=True)
class PromptPlan:
    segments: tuple[PromptSegment, ...]
    route: Route
    model_profile: ModelProfile
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.segments, tuple) or not isinstance(self.provenance, tuple):
            raise ValueError("plan collections must be tuples")
        if any(not isinstance(segment, PromptSegment) for segment in self.segments):
            raise ValueError("plan segments must contain PromptSegment values")
        ids = [segment.segment_id for segment in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("segment ids must be unique")


@dataclass(frozen=True)
class PromptDraft:
    segments: tuple[PromptSegment, ...]
    positive_text: str
    negative_text: str
    route: Route
    model_profile: ModelProfile
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.segments, tuple) or not isinstance(self.provenance, tuple):
            raise ValueError("draft collections must be tuples")
        if any(not isinstance(segment, PromptSegment) for segment in self.segments):
            raise ValueError("draft segments must contain PromptSegment values")
        if self.positive_text != render_channel(self.segments, "positive"):
            raise ValueError("positive_text does not match positive segments")
        if self.negative_text != render_channel(self.segments, "negative"):
            raise ValueError("negative_text does not match negative segments")

    def assert_immutable(self) -> None:
        self.__post_init__()


def order_segments(segments: tuple[PromptSegment, ...], channel: Channel) -> tuple[PromptSegment, ...]:
    selected = tuple(segment for segment in segments if segment.channel == channel)
    required_policy = tuple(
        segment for segment in selected
        if "required_by_anima_variant" in segment.fact_notes or "required_by_anima_safety" in segment.fact_notes
    )
    locked = tuple(segment for segment in selected if segment.locked)
    ordinary = tuple(sorted(
        (segment for segment in selected if not segment.locked and segment not in required_policy),
        key=lambda segment: segment.priority,
    ))
    required_policy = tuple(sorted(
        required_policy,
        key=lambda segment: 0 if "required_by_anima_variant" in segment.fact_notes else 1,
    ))
    return required_policy + locked + ordinary


def render_channel(segments: tuple[PromptSegment, ...], channel: Channel) -> str:
    return ", ".join(segment.text for segment in order_segments(segments, channel))


def build_draft(plan: PromptPlan, brief: PromptBrief) -> PromptDraft:
    draft = PromptDraft(
        plan.segments,
        render_channel(plan.segments, "positive"),
        render_channel(plan.segments, "negative"),
        plan.route,
        plan.model_profile,
        plan.provenance,
    )
    draft.assert_immutable()
    return draft
