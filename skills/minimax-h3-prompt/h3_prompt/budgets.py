"""Exact H3 context accounting."""
from __future__ import annotations
from dataclasses import dataclass
from math import ceil, floor
@dataclass(frozen=True)
class H3Context:
    visual_tokens: int
    text_tokens: int
    available_tokens: int
def max_shots(duration_seconds: float) -> int:
    return 1 + floor((duration_seconds - 1) / 3)
def visual_tokens(width: int, height: int) -> int:
    if width <= 0 or height <= 0 or width * height < 65_536 or width * height > 16_777_216:
        raise ValueError("reference dimensions must contain 65,536..16,777,216 pixels")
    return ceil(width / 32) * ceil(height / 32)
