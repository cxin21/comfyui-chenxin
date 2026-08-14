"""Tokenizer-independent token estimation seam."""

from __future__ import annotations

from typing import Callable


def estimate_tokens(text: str, tokenizer: Callable[[str], int] | None = None) -> int | None:
    if tokenizer is None:
        return None
    try:
        value = tokenizer(text)
    except Exception:
        return None
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
