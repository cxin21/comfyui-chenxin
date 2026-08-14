"""Read-only weight and special syntax checks."""

from __future__ import annotations

import re

from .types import InspectionIssue


def inspect_weights(text: str) -> tuple[InspectionIssue, ...]:
    issues: list[InspectionIssue] = []
    if text.count("(") != text.count(")"):
        issues.append(InspectionIssue("unbalanced_parentheses", "warning", "weight parentheses are unbalanced"))
    for value in re.findall(r":\s*([-+]?\d+(?:\.\d+)?)\s*\)?", text):
        if abs(float(value)) > 4:
            issues.append(InspectionIssue("abnormal_weight", "warning", f"weight {value} is unusually large"))
    return tuple(issues)
