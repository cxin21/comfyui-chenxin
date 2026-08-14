"""Plain H3 prompt result with audit findings."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class PromptResult:
    text: str
    findings: tuple[str, ...] = ()
