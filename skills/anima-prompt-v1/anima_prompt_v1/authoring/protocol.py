"""Small authoring seams shared by the positive and negative channels."""

from __future__ import annotations

from typing import Protocol

from ..catalog import Catalog
from ..domain import Fact, PromptBrief
from ..draft import PromptSegment


class SegmentAuthor(Protocol):
    def __call__(self, brief: PromptBrief, catalog: Catalog, route: str) -> tuple[PromptSegment, ...]: ...


def fact_priority(fact: Fact, source_priority: tuple[str, ...] = ("user", "local_model", "official", "community", "default")) -> int:
    domain_priority = {
        "subject": 10,
        "appearance": 20,
        "clothing": 30,
        "hair": 35,
        "expression": 40,
        "action": 50,
        "region": 55,
        "scene": 60,
        "style": 70,
        "lighting": 80,
        "camera": 90,
        "pose": 45,
        "object": 45,
        "quality": 100,
        "safety": 105,
        "meta": 110,
    }[fact.domain]
    source_rank = source_priority.index(fact.source) if fact.source in source_priority else len(source_priority)
    return domain_priority * 10 + source_rank
