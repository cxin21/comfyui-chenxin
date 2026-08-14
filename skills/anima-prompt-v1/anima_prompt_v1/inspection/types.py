"""Shared immutable diagnostic types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["info", "warning", "conflict"]


@dataclass(frozen=True)
class InspectionIssue:
    code: str
    severity: Severity
    message: str
    location: str | None = None
    suggestion: str | None = None


@dataclass(frozen=True)
class InspectionReport:
    issues: tuple[InspectionIssue, ...]
    token_estimate: int | None = None
