"""Fact ownership, protection, and rendering traceability."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Mapping, Sequence

from .contracts import AuthoredSegment, Fact


_ORIGINS = frozenset(
    {
        "user_locked",
        "user_explicit",
        "necessary_inference",
        "agent_embellishment",
    }
)


class FactLedgerError(ValueError):
    """The ledger or its rendering trace is internally inconsistent."""


@dataclass(frozen=True)
class FactLedger:
    facts: tuple[Fact, ...]
    _by_id: Mapping[str, Fact] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        by_id: dict[str, Fact] = {}
        for fact in self.facts:
            _validate_fact(fact)
            if fact.fact_id in by_id:
                raise FactLedgerError(f"duplicate fact_id: {fact.fact_id}")
            by_id[fact.fact_id] = fact
        object.__setattr__(self, "_by_id", MappingProxyType(by_id))

    def get(self, fact_id: str) -> Fact:
        try:
            return self._by_id[fact_id]
        except KeyError as exc:
            raise FactLedgerError(f"unknown fact_id: {fact_id}") from exc

    def validate_segments(self, segments: Sequence[AuthoredSegment]) -> None:
        segment_ids: set[str] = set()
        for segment in segments:
            for attribute in ("segment_id", "field", "text"):
                value = getattr(segment, attribute)
                if not isinstance(value, str) or not value.strip():
                    raise FactLedgerError(f"segment {attribute} must be non-empty")
            if segment.segment_id in segment_ids:
                raise FactLedgerError(f"duplicate segment_id: {segment.segment_id}")
            segment_ids.add(segment.segment_id)
            if not segment.fact_ids:
                raise FactLedgerError(
                    f"segment {segment.segment_id} fact_ids must be non-empty"
                )
            if len(set(segment.fact_ids)) != len(segment.fact_ids):
                raise FactLedgerError(
                    f"segment {segment.segment_id} contains duplicate fact_ids"
                )
            for fact_id in segment.fact_ids:
                if fact_id not in self._by_id:
                    raise FactLedgerError(
                        f"segment {segment.segment_id} references unknown fact_id: {fact_id}"
                    )
            _validate_weight(segment.segment_id, "priority", segment.priority)
            _validate_weight(segment.segment_id, "adherence_risk", segment.adherence_risk)
            _validate_weight(
                segment.segment_id,
                "source_confidence",
                segment.source_confidence,
                maximum=1.0,
            )

    def protected_fact_ids(self) -> frozenset[str]:
        return frozenset(
            fact.fact_id
            for fact in self.facts
            if fact.origin != "agent_embellishment"
        )

    def removable_fact_ids(self) -> frozenset[str]:
        return frozenset(
            fact.fact_id
            for fact in self.facts
            if fact.origin == "agent_embellishment"
        )

    def trace_rendering(
        self,
        segments: Sequence[AuthoredSegment],
    ) -> dict[str, tuple[str, ...]]:
        self.validate_segments(segments)
        rendered: dict[str, list[str]] = {fact.fact_id: [] for fact in self.facts}
        for segment in segments:
            for fact_id in segment.fact_ids:
                rendered[fact_id].append(segment.segment_id)

        missing = sorted(
            fact_id
            for fact_id in self.protected_fact_ids()
            if not rendered[fact_id]
        )
        if missing:
            raise FactLedgerError(f"protected facts are not rendered: {missing}")
        return {fact_id: tuple(segment_ids) for fact_id, segment_ids in rendered.items()}


def trace_rendering(
    ledger: FactLedger,
    segments: Sequence[AuthoredSegment],
) -> dict[str, tuple[str, ...]]:
    return ledger.trace_rendering(segments)


def _validate_fact(fact: Fact) -> None:
    for attribute in ("fact_id", "value", "owner", "dimension"):
        value = getattr(fact, attribute)
        if not isinstance(value, str) or not value.strip():
            raise FactLedgerError(f"fact {attribute} must be non-empty")
    if fact.origin not in _ORIGINS:
        raise FactLedgerError(f"unsupported fact origin: {fact.origin!r}")
    if not isinstance(fact.locked, bool):
        raise FactLedgerError("fact locked must be a boolean")
    if (fact.origin == "user_locked") != fact.locked:
        raise FactLedgerError(
            "locked must be true exactly for facts with origin user_locked"
        )


def _validate_weight(
    segment_id: str,
    name: str,
    value: float,
    *,
    maximum: float | None = None,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FactLedgerError(f"segment {segment_id} {name} must be numeric")
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0:
        raise FactLedgerError(f"segment {segment_id} {name} must be positive and finite")
    if maximum is not None and numeric > maximum:
        raise FactLedgerError(f"segment {segment_id} {name} must be <= {maximum}")
