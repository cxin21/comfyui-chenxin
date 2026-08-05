"""Exact, registry-backed prompt dialect lookup."""

from __future__ import annotations

import copy
import json
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
DIALECTS_DIR = SKILL_DIR / "dialects"
INDEX_PATH = DIALECTS_DIR / "index.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def lookup_dialect(query: str, modality: str | None = None) -> dict:
    """Return one exact canonical/approved-alias dialect.

    Matching is case-insensitive after surrounding whitespace is removed, but
    never uses substrings or fuzzy scores. Unknown, ambiguous, malformed, and
    modality-mismatched requests all fail closed with ``ValueError``.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("dialect query must be a non-empty string")
    if modality is not None and modality not in {"image", "video"}:
        raise ValueError(f"unsupported modality: {modality!r}")

    normalized = query.strip().casefold()
    candidates: set[str] = set()
    for row in _read_json(INDEX_PATH)["dialects"]:
        canonical = row["id"]
        aliases = row.get("aliases", [])
        if not isinstance(aliases, list):
            raise ValueError(f"invalid alias list for dialect {canonical!r}")
        names = [canonical, *aliases]
        if any(isinstance(name, str) and name.casefold() == normalized for name in names):
            candidates.add(canonical)

    if not candidates:
        raise ValueError(f"unknown dialect: {query!r}")
    if len(candidates) != 1:
        joined = ", ".join(sorted(candidates))
        raise ValueError(f"ambiguous dialect {query!r}: {joined}")

    canonical_id = next(iter(candidates))
    matches = [
        entry
        for filename in ("image.json", "video.json")
        for entry in _read_json(DIALECTS_DIR / filename)["dialects"]
        if entry["id"] == canonical_id
    ]
    if len(matches) != 1:
        raise ValueError(f"registry does not contain exactly one dialect {canonical_id!r}")

    dialect = matches[0]
    if modality is not None and dialect["modality"] != modality:
        raise ValueError(
            f"dialect {canonical_id!r} has modality {dialect['modality']!r}, not {modality!r}"
        )
    return copy.deepcopy(dialect)
