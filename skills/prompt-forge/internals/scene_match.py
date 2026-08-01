#!/usr/bin/env python3
"""scene_match — match scene keywords to aesthetic recipes.

Reads aesthetics/INDEX.md (markdown table: scene | keywords | lighting | composition | color)
and returns top-N scene matches for a user query. Falls back to style-presets.md
when no scene scores above threshold.

Usage:
    python scene_match.py --query "夜景 霓虹"
    python scene_match.py --query "樱花树下" --top 1

Stdlib only. Output: JSON array on stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
INDEX_MD = SKILL_DIR / "aesthetics" / "INDEX.md"
PRESETS_MD = SKILL_DIR / "aesthetics" / "style-presets.md"

THRESHOLD = 0.2


def _tokenize(text: str) -> set[str]:
    """Whitespace-split tokenization preserving CJK words + char unigrams.

    Each whitespace-separated token contributes the whole word (so 夜景 stays
    夜景) plus its CJK unigrams (夜, 景). Latin subwords use [a-z0-9_]+. This
    matches `test_match_clear_hit` which asserts `"夜景" in keywords_matched` —
    a char-only tokenizer would emit [夜, 景] but never the 2-char word.
    """
    text = text.lower().strip()
    tokens: set[str] = set()
    for word in re.split(r"\s+", text):
        if not word:
            continue
        tokens.add(word)
        for c in word:
            if "一" <= c <= "鿿":
                tokens.add(c)
    tokens |= set(re.findall(r"[a-z0-9_]+", text))
    return tokens


def load_index(path: Path = INDEX_MD) -> list[dict]:
    """Parse INDEX.md markdown table into list of scene dicts."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = [l.strip() for l in text.splitlines() if l.strip().startswith("|") and not l.startswith("|---")]
    if len(lines) < 2:
        return []
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    entries: list[dict] = []
    for line in lines[1:]:
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < len(header):
            continue
        row = dict(zip(header, cols))
        keywords_raw = row.get("keywords", "")
        # Split on commas (the brief's table uses 逗号 separator)
        kw_parts = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]
        keywords: set[str] = set()
        for k in kw_parts:
            tokens = _tokenize(k)
            keywords |= tokens
        entries.append({
            "scene": row.get("scene", ""),
            "keywords": keywords,
            "lighting": row.get("lighting", ""),
            "composition": row.get("composition", ""),
            "color": row.get("color", ""),
        })
    return entries


def match(scenes: list[dict], query: str, top: int = 3,
         presets_path: Path | None = PRESETS_MD) -> list[dict]:
    """Match query tokens against scene keyword sets. Returns top-N, or presets fallback."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return _presets_fallback(presets_path, top)

    scored: list[dict] = []
    for s in scenes:
        scene_tokens: set[str] = s["keywords"]
        if not scene_tokens:
            continue
        overlap = q_tokens & scene_tokens
        if not overlap:
            continue
        score = len(overlap) / len(q_tokens)
        if score < THRESHOLD:
            continue
        scored.append({
            "scene": s["scene"],
            "keywords_matched": sorted(overlap),
            "recipes": {
                "lighting": s["lighting"],
                "composition": s["composition"],
                "color": s["color"],
            },
            "score": round(score, 2),
        })

    scored.sort(key=lambda x: (-x["score"], x["scene"]))

    if not scored:
        return _presets_fallback(presets_path, top)
    return scored[:top]


def _presets_fallback(path: Path | None, top: int) -> list[dict]:
    """Read style-presets.md and return top-N preset names as fallback."""
    if path is None or not path.exists():
        return [{"scene": "_no_fallback", "score": 0}]
    text = path.read_text(encoding="utf-8")
    headings = [l.strip().lstrip("#").strip() for l in text.splitlines() if l.strip().startswith("#")]
    return [{"scene": h, "score": 0, "fallback": True} for h in headings[:top]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scene_match")
    parser.add_argument("--query", required=True, help="Scene keyword query")
    parser.add_argument("--top", type=int, default=3, help="Max scenes to return")
    parser.add_argument("--index", type=Path, default=INDEX_MD)
    args = parser.parse_args(argv)

    scenes = load_index(args.index)
    results = match(scenes, args.query, top=args.top)
    json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
