#!/usr/bin/env python3
"""recipe_lookup — read-only consumer for recipes/MODELS.md.

Parses the YAML-frontmatter-bearing recipes (the format produced by
`recipe_yaml.py`) and returns a JSON object describing the matching recipe:
its dialect block (heading + N body lines) plus the frontmatter fields.

Used by `chenxin-core` to pipe a model's dialect into a prompt without
re-parsing markdown by hand.

Stdlib only (Python 3.11+).

Usage:
    python recipe_lookup.py --model <id-or-substring> [--n 30]

Output JSON:
    {
      "matched_id": "flux_1",
      "heading": "### FLUX.1 (Black Forest Labs)",
      "frontmatter": { "id": ..., "family": ..., ... },
      "dialect_block": "### FLUX.1 ...\\n- **Prompt style:** ...\\n..."
    }

If no exact id match is found, a case-insensitive substring search is run
across both id and family fields. If still nothing matches, an empty
result with `"matched": false` is emitted (exit code 0).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent))

import recipe_yaml as _yaml  # sibling module; shares the parser

_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
MODELS_PATH = SKILL_DIR / "recipes" / "MODELS.md"


def _require_python_311() -> None:
    if sys.version_info < (3, 11):
        sys.stderr.write("Python 3.11+ required\n")
        sys.exit(3)


_RECIPE_BLOCK_RE = re.compile(
    r"^---\n(?P<yaml>.*?)\n---\n+(?P<body>.*?)(?=\n---\n|\Z)",
    re.M | re.S,
)


def _parse_recipes(text: str) -> list[dict]:
    """Parse MODELS.md into a list of {frontmatter, heading, body_lines} dicts."""
    recipes: list[dict] = []
    for m in _RECIPE_BLOCK_RE.finditer(text):
        yaml_text = m.group("yaml")
        body = m.group("body")
        try:
            fm = _yaml._parse_yaml_block(yaml_text)
        except Exception as e:
            sys.stderr.write(f"[recipe_lookup] failed to parse yaml block: {e}\n")
            continue
        # Find the heading line — first line that starts with `### `.
        body_lines = body.splitlines()
        heading_line = ""
        idx = 0
        while idx < len(body_lines):
            ln = body_lines[idx]
            if ln.startswith("### "):
                heading_line, body_glued = _yaml._split_heading_body(ln)
                if body_glued.strip():
                    body_lines[idx] = body_glued
                else:
                    body_lines = body_lines[idx + 1:]
                break
            idx += 1
        if not heading_line:
            continue
        recipes.append({
            "frontmatter": fm,
            "heading": heading_line,
            "body_lines": body_lines,
        })
    return recipes


def _format_dialect(heading: str, body_lines: list[str], n: int) -> str:
    """Format the dialect block: heading + first N body lines."""
    block = [heading]
    block.extend(body_lines[:n])
    return "\n".join(block)


def _match(recipes: list[dict], query: str) -> dict | None:
    """Find a recipe by exact id match, then substring across id/family."""
    q = query.strip().lower()
    if not q:
        return None
    # 1) Exact id match.
    for r in recipes:
        if str(r["frontmatter"].get("id", "")).lower() == q:
            return r
    # 2) Substring across id / family / heading.
    for r in recipes:
        fm = r["frontmatter"]
        hay = " ".join([
            str(fm.get("id", "")),
            str(fm.get("family", "")),
            str(fm.get("modality", "")),
            r["heading"],
        ]).lower()
        if q in hay:
            return r
    return None


def main(argv: list[str] | None = None) -> int:
    _require_python_311()
    parser = argparse.ArgumentParser(
        prog="recipe_lookup",
        description="Look up a recipe by id (or substring) and emit its dialect block as JSON.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Recipe id (exact) or substring to match against id / family / heading.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=30,
        help="Maximum body lines to include in the dialect block (default 30).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=MODELS_PATH,
        help=f"Path to MODELS.md (default: {MODELS_PATH})",
    )
    args = parser.parse_args(argv)

    if not args.path.exists():
        sys.stderr.write(f"[recipe_lookup] file not found: {args.path}\n")
        return 3

    text = args.path.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    r = _match(recipes, args.model)

    if r is None:
        sys.stderr.write(f"[recipe_lookup] no match for: {args.model}\n")
        json.dump({"matched": False, "query": args.model}, sys.stdout)
        sys.stdout.write("\n")
        return 0

    dialect = _format_dialect(r["heading"], r["body_lines"], args.n)
    payload = {
        "matched": True,
        "matched_id": r["frontmatter"].get("id", ""),
        "heading": r["heading"],
        "frontmatter": r["frontmatter"],
        "dialect_block": dialect,
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())