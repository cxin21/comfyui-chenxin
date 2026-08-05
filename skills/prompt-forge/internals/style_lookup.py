"""Advisory visual-style lookup and dialect-aware rendering."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
STYLES_DIR = SKILL_DIR / "styles"
INDEX_PATH = STYLES_DIR / "index.json"
STYLE_PATH = STYLES_DIR / "visual-language.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE))


def _style_rows() -> tuple[list[dict], dict[str, list[str]]]:
    styles = _read_json(STYLE_PATH)["styles"]
    aliases = {
        row["id"]: list(row.get("aliases", []))
        for row in _read_json(INDEX_PATH)["styles"]
    }
    return styles, aliases


def suggest_styles(query: str, limit: int = 3) -> list[dict]:
    """Return deterministic style advice; never select or inject a style."""
    if not isinstance(query, str) or not query.strip():
        return []
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    if limit == 0:
        return []

    normalized = query.strip().casefold()
    query_tokens = _tokens(query)
    styles, aliases_by_id = _style_rows()
    suggestions: list[dict] = []

    for style in styles:
        style_id = style["id"]
        aliases = aliases_by_id.get(style_id, [])
        if normalized == style_id.casefold():
            suggestions.append({"id": style_id, "score": 1.0, "evidence": [f"canonical:{style_id}"]})
            continue
        exact_aliases = sorted(alias for alias in aliases if normalized == alias.casefold())
        if exact_aliases:
            suggestions.append({"id": style_id, "score": 0.95, "evidence": [f"alias:{exact_aliases[0]}"]})
            continue

        evidence: set[str] = set()
        matched: set[str] = set()
        searchable: list[tuple[str, str]] = [("id", style_id)]
        searchable.extend(("alias", alias) for alias in aliases)
        for axis, values in style.get("axes", {}).items():
            searchable.extend((f"axis.{axis}", value) for value in values)
        searchable.extend(("fingerprint", value) for value in style.get("visual_fingerprint", []))
        searchable.extend(("rendering", value) for value in style.get("renderings", []))
        for field, value in searchable:
            overlap = query_tokens & _tokens(value)
            for token in overlap:
                matched.add(token)
                evidence.add(f"{field}:{token}")
        if matched:
            score = round(0.8 * len(matched) / max(len(query_tokens), 1), 6)
            suggestions.append({"id": style_id, "score": score, "evidence": sorted(evidence)})

    suggestions.sort(key=lambda row: (-row["score"], row["id"]))
    return suggestions[:limit]


def render_style(style: dict, dialect: dict) -> dict:
    """Render visual language for a dialect without adding creative facts."""
    if not isinstance(style, dict) or not isinstance(style.get("axes"), dict):
        raise ValueError("style must contain an axes mapping")
    if not isinstance(dialect, dict) or not dialect.get("id") or not dialect.get("prompt_form"):
        raise ValueError("dialect must contain id and prompt_form")

    is_tag_dialect = "tag" in str(dialect["prompt_form"]).casefold()
    fragments: list[str] = []
    for axis in sorted(style["axes"]):
        values = list(style["axes"][axis])
        if is_tag_dialect:
            fragments.extend(value.replace("-", "_").replace(" ", "_") for value in values)
        else:
            fragments.append(f"{axis}: {', '.join(values)}")

    return {
        "style_id": style.get("id"),
        "dialect_id": dialect["id"],
        "modality": dialect.get("modality"),
        "prompt_form": dialect["prompt_form"],
        "visual_fingerprint": copy.deepcopy(style.get("visual_fingerprint", [])),
        "renderings": copy.deepcopy(style.get("renderings", [])),
        "incompatible_styles": copy.deepcopy(style.get("incompatible_styles", [])),
        "visual_language": {
            "mode": "tags" if is_tag_dialect else "natural_language",
            "fragments": fragments,
        },
    }
