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

THRESHOLD = 0.45


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
    """Parse the scene table; non-table frontmatter is ignored by construction."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("|") and not line.strip().startswith("|---")
    ]
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
            "keyword_phrases": set(kw_parts),
            "lighting": row.get("lighting", ""),
            "composition": row.get("composition", ""),
            "color": row.get("color", ""),
        })
    return entries


def match(scenes: list[dict], query: str, top: int = 3,
         presets_path: Path | None = PRESETS_MD) -> list[dict]:
    """Match exact phrases/tokens using specificity-weighted evidence."""
    q_tokens = set(re.findall(r"[a-z0-9_]+", query.lower()))
    q_text = query.lower().strip()
    if not q_text:
        return _presets_fallback(presets_path, top)

    scored: list[dict] = []
    for s in scenes:
        phrases: set[str] = s.get("keyword_phrases", set())
        if not phrases:
            continue
        evidence: list[tuple[str, float]] = []
        for phrase in phrases:
            has_cjk = bool(re.search(r"[\u4e00-\u9fff]", phrase))
            if has_cjk:
                if len(phrase) == 1 and q_text != phrase:
                    continue
                if phrase in q_text:
                    evidence.append((phrase, min(1.0, 0.35 + 0.15 * len(phrase))))
                continue
            words = re.findall(r"[a-z0-9_]+", phrase)
            if len(words) > 1 and phrase in q_text:
                evidence.append((phrase, min(1.0, 0.55 + 0.1 * len(words))))
            elif len(words) == 1 and words[0] in q_tokens:
                # Single generic English adjectives are weak evidence; two or
                # more independent hits can still form a confident match.
                evidence.append((phrase, 0.35))
        if not evidence:
            continue
        overlap = {phrase for phrase, _ in evidence}
        score = min(1.0, sum(weight for _, weight in evidence))
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
    """Return explicit choices; never silently select a biased first preset."""
    if path is None or not path.exists():
        return [{"scene": "_no_fallback", "score": 0}]
    text = path.read_text(encoding="utf-8")
    rows: list[dict] = []
    in_presets = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("| 预设 |"):
            in_presets = True
            continue
        if not in_presets:
            continue
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) < 4:
            break
        name, lighting, color, mood = cells[:4]
        rows.append({
            "scene": f"_preset:{name}",
            "preset": name,
            "recipes": {"lighting": lighting, "composition": "", "color": color},
            "mood": mood,
            "score": 0,
            "fallback": True,
        })
    choices = rows[:top]
    if not choices:
        return [{"scene": "_no_scene_match", "score": 0, "fallback": True, "choices": []}]
    return [{
        "scene": "_no_scene_match",
        "score": 0,
        "fallback": True,
        "requires_selection": True,
        "choices": choices,
    }]


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
