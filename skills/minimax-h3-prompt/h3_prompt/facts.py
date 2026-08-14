"""MiniMax-H3 fact ledger."""
from __future__ import annotations
from .contracts import Fact, AuthoredSegment
class FactLedger:
    def __init__(self, facts):
        self.facts = tuple(facts)
        self._by_id = {fact.fact_id: fact for fact in self.facts}
        if len(self._by_id) != len(self.facts): raise ValueError("fact_id values must be unique")
    def get(self, fact_id):
        try: return self._by_id[fact_id]
        except KeyError as exc: raise ValueError(f"unknown fact_id: {fact_id}") from exc
    def validate_segments(self, segments):
        for segment in segments:
            if not segment.text.strip(): raise ValueError(f"segment {segment.segment_id} is empty")
            for fact_id in segment.fact_ids: self.get(fact_id)
    def trace_rendering(self, segments):
        trace = {fact.fact_id: [] for fact in self.facts}
        for segment in segments:
            for fact_id in segment.fact_ids: trace.setdefault(fact_id, []).append(segment.segment_id)
        return {key: tuple(value) for key, value in trace.items()}
