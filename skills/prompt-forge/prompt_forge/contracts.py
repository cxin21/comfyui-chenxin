"""Immutable contracts shared by the three explicit authoring paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FactOrigin = Literal[
    "user_locked",
    "user_explicit",
    "necessary_inference",
    "agent_embellishment",
]
ArtifactStatus = Literal[
    "production_ready",
    "budget_conflict",
    "quality_rejected",
]
TaskKind = Literal["anima", "h3_t2va", "h3_ref2va"]


@dataclass(frozen=True)
class Fact:
    fact_id: str
    value: str
    origin: FactOrigin
    locked: bool
    owner: str
    dimension: str


@dataclass(frozen=True)
class AuthoredSegment:
    segment_id: str
    field: str
    text: str
    fact_ids: tuple[str, ...]
    priority: float
    adherence_risk: float
    source_confidence: float
    render_weight: float | None = None


@dataclass(frozen=True)
class Complexity:
    subjects: int
    explicit_relations: int
    complex_actions: int
    environment_clusters: int
    natural_language_bridges: int


@dataclass(frozen=True)
class H3ReferenceImage:
    reference_id: str
    owner: str
    resized_width: int
    resized_height: int


@dataclass(frozen=True)
class AnimaAuthoringRequest:
    facts: tuple[Fact, ...]
    positive_segments: tuple[AuthoredSegment, ...]
    complexity: Complexity
    negative_segments: tuple[AuthoredSegment, ...] = ()
    exclusion_groups: int = 0
    variant: Literal["base", "aesthetic", "turbo"] = "base"


@dataclass(frozen=True)
class H3T2VAAuthoringRequest:
    facts: tuple[Fact, ...]
    duration_seconds: float
    shot_count: int
    integrated_multimodal_description: tuple[AuthoredSegment, ...]
    overall_soundscape: tuple[AuthoredSegment, ...] = ()
    non_diegetic_music: tuple[AuthoredSegment, ...] = ()


@dataclass(frozen=True)
class H3Ref2VAAuthoringRequest:
    facts: tuple[Fact, ...]
    duration_seconds: float
    shot_count: int
    references: tuple[H3ReferenceImage, ...]
    subject_definitions: tuple[AuthoredSegment, ...]
    summary: tuple[AuthoredSegment, ...]
    retention_analysis: tuple[AuthoredSegment, ...]
    detailed_description: tuple[AuthoredSegment, ...]
    overall_soundscape: tuple[AuthoredSegment, ...] = ()
    non_diegetic_music: tuple[AuthoredSegment, ...] = ()
