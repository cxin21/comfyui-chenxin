"""Tag validation against bundled Anima dictionary.

Reads knowledge/anima/tags.sqlite, returns canonical form + frequency + verified.

Usage:
    from scripts.tag_validate import validate_tag
    info = validate_tag("male")  # -> {"canonical": "male_focus", "verified": True, ...}
"""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path


_DICT_PATH = Path(__file__).parent.parent / "knowledge" / "anima" / "tags.sqlite"

# Cached connection
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        if not _DICT_PATH.exists():
            _conn = None
            return None
        _conn = sqlite3.connect(str(_DICT_PATH))
        _conn.row_factory = sqlite3.Row
    return _conn


def validate_tag(tag: str) -> dict:
    """Look up tag in the bundled dictionary.

    Returns:
        {"canonical": str, "frequency": int, "verified": bool, "alias": bool}
    """
    tag = tag.strip().lower()
    conn = _get_conn()
    if conn is None:
        return {"canonical": tag, "frequency": 0, "verified": False, "alias": False}

    # Exact match first
    row = conn.execute(
        "SELECT canonical, frequency FROM tags WHERE canonical = ?", (tag,)
    ).fetchone()
    if row:
        return {
            "canonical": row["canonical"],
            "frequency": row["frequency"],
            "verified": True,
            "alias": False,
        }

    # Alias match
    row = conn.execute(
        "SELECT canonical, frequency FROM aliases WHERE alias = ?", (tag,)
    ).fetchone()
    if row:
        return {
            "canonical": row["canonical"],
            "frequency": row["frequency"],
            "verified": True,
            "alias": True,
        }

    # Not found
    return {"canonical": tag, "frequency": 0, "verified": False, "alias": False}