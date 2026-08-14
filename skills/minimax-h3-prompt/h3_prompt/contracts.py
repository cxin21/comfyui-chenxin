"""MiniMax-H3-only authoring records."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

FactOrigin = Literal["user_locked", "user_explicit", "necessary_inference", "agent_embellishment"]
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
    priority: float = 1.0
    adherence_risk: float = 0.5
    source_confidence: float = 1.0
@dataclass(frozen=True)
class H3ReferenceImage:
    reference_id: str
    owner: str
    resized_width: int
    resized_height: int
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
