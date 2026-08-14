"""Conflict and duplicate checks kept independent from rendering."""

from __future__ import annotations

from .types import InspectionIssue


def inspect_conflicts(positive: str, negative: str) -> tuple[InspectionIssue, ...]:
    pos = {value.strip().lower() for value in positive.split(",") if value.strip()}
    neg = {value.strip().lower() for value in negative.split(",") if value.strip()}
    overlap = sorted(pos & neg)
    if not overlap:
        return ()
    return (InspectionIssue("positive_negative_conflict", "conflict", f"same phrase appears in positive and negative: {overlap[0]}"),)


def inspect_duplicates(text: str) -> tuple[InspectionIssue, ...]:
    values = [value.strip().lower() for value in text.split(",") if value.strip()]
    seen: set[str] = set()
    issues: list[InspectionIssue] = []
    for value in values:
        if value in seen:
            issues.append(InspectionIssue("duplicate_segment", "warning", f"duplicate segment: {value}"))
        seen.add(value)
    return tuple(issues)
