"""Fixed Anima protocol loading and lexical normalization."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


PROTOCOL_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "anima" / "protocol.json"


@lru_cache(maxsize=1)
def load_protocol() -> Mapping[str, Any]:
    payload = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("bundled Anima protocol must be an object")
    return payload


def canonical_form(tag: str) -> str:
    value = " ".join(tag.strip().lower().lstrip("@").split())
    return value if value.startswith("score_") else value.replace(" ", "_")


def semantic_form(value: str) -> str:
    return " ".join(value.strip().lower().lstrip("@").replace("_", " ").split())
