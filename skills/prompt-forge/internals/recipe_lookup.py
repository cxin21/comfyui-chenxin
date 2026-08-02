#!/usr/bin/env python3
"""recipe_lookup — query recipes/MODELS.md by model id (with weighted fuzzy + alias).

Stdlib only. Returns JSON on stdout.

Usage:
    python recipe_lookup.py --model <id>
    python recipe_lookup.py --model <substring> --n 50
    python recipe_lookup.py --check-alias <alias>
    python recipe_lookup.py --list-aliases
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # package import in tests / library callers
    from ._aliases import ALIASES, resolve_alias, all_aliases
except ImportError:  # direct script execution
    from _aliases import ALIASES, resolve_alias, all_aliases

_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
RECIPES_PATH = SKILL_DIR / "recipes" / "MODELS.md"

_RECIPE_BLOCK_RE = re.compile(
    r"^---\n(?P<yaml>.*?)\n---\n+(?P<body>.*?)(?=\n---\n|\Z)",
    re.M | re.S,
)

_FIELD_WEIGHTS = {
    "id": 1.0,
    "family": 0.7,
    "modality": 0.4,
    "heading": 0.3,
    "dialect": 0.5,
}


def _require_python_311() -> None:
    if sys.version_info < (3, 11):
        print("[recipe_lookup] Python 3.11+ required", file=sys.stderr)
        sys.exit(3)


def _parse_yaml_block(yaml_text: str) -> dict:
    """Minimal YAML parser for the subset used in MODELS.md."""
    out: dict = {}
    current_key: str | None = None
    for raw in yaml_text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("  -") or line.startswith("    -"):
            value = line.lstrip().lstrip("-").strip()
            value = value.strip('"').strip("'")
            if current_key and current_key in out:
                if isinstance(out[current_key], list):
                    out[current_key].append(value)
                else:
                    out[current_key] = [value]
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if m:
            key = m.group(1)
            value = m.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1]
                out[key] = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
            elif value:
                out[key] = value.strip('"').strip("'")
            else:
                out[key] = []
            current_key = key
    return out


def _split_heading_body(heading_line: str) -> tuple[str, str]:
    if "- **" in heading_line:
        i = heading_line.index("- **")
        return heading_line[:i].rstrip(), heading_line[i:]
    return heading_line, ""


def _parse_recipes(text: str) -> list[dict]:
    recipes: list[dict] = []
    for m in _RECIPE_BLOCK_RE.finditer(text):
        yaml_text = m.group("yaml")
        body = m.group("body")
        try:
            frontmatter = _parse_yaml_block(yaml_text)
        except Exception as e:
            print(f"[recipe_lookup] skip block (yaml parse failed): {e}", file=sys.stderr)
            continue
        heading = ""
        body_lines: list[str] = []
        for line in body.splitlines():
            if line.startswith("### ") and not heading:
                heading, glued = _split_heading_body(line)
                if glued:
                    body_lines.append(glued)
                continue
            if heading:
                body_lines.append(line)
        # Skip blocks that are not real recipes — boilerplate `---` matches in
        # the intro/outro of MODELS.md produce frontmatter-without-id noise
        # that would otherwise survive weighted-fuzzy matching.
        if not frontmatter.get("id"):
            continue
        recipes.append({
            "frontmatter": frontmatter,
            "heading": heading,
            "body_lines": body_lines,
        })
    return recipes


def _format_dialect(heading: str, body_lines: list[str], n: int) -> str:
    out = [heading] + body_lines[:n]
    return "\n".join(out)


def _score(text: str, query: str, weight: float) -> float:
    """exact=weight, substring=weight*0.6, char-overlap=weight*0.3."""
    t = text.lower()
    q = query.lower()
    if t == q:
        return weight
    if q in t or t in q:
        return weight * 0.6
    common = sum(1 for c in set(q) if c in set(t))
    return weight * (common / max(len(set(q)), 1)) * 0.3


def _build_payload(matched: dict, score: float, path: str, dialect_n: int = 30) -> dict:
    """Build the JSON-ready output dict from an internal recipe row."""
    fm = matched["frontmatter"]
    return {
        "matched": True,
        "matched_id": fm.get("id", ""),
        "heading": matched["heading"],
        "frontmatter": fm,
        "dialect_block": _format_dialect(matched["heading"], matched["body_lines"], dialect_n),
        "score": score,
        "match_path": path,
    }


def _match_recipe(recipes: list[dict], query: str, dialect_n: int = 30) -> tuple[dict | None, float, str]:
    """3-pass match. Returns (output_payload, score, match_path).

    The returned dict matches the CLI JSON shape (matched / matched_id /
    heading / frontmatter / dialect_block / score / match_path) so unit tests
    and CLI callers share one canonical contract.
    """
    q = query.lower().strip()
    if not q:
        return None, 0.0, "none"

    # Pass 1: exact id match
    for r in recipes:
        rid = (r["frontmatter"].get("id") or "").lower()
        if rid == q:
            return _build_payload(r, 1.0, "exact", dialect_n=dialect_n), 1.0, "exact"

    # Pass 2: alias match
    canonical = resolve_alias(query)
    if canonical:
        for r in recipes:
            rid = (r["frontmatter"].get("id") or "").lower()
            if rid == canonical.lower():
                return _build_payload(r, 0.95, "alias", dialect_n=dialect_n), 0.95, "alias"

    # Pass 3: weighted fuzzy across 5 fields
    scored: list[tuple[float, dict]] = []
    for r in recipes:
        fm = r["frontmatter"]
        fuzzy_fields = (
            fm.get("id", ""),
            fm.get("family", ""),
            fm.get("modality", ""),
            r["heading"],
            fm.get("dialect", ""),
        )
        normalized_fields = tuple(field.lower() for field in fuzzy_fields if field)
        if not any(q in field or field in q for field in normalized_fields):
            continue
        score = sum(
            _score(field, q, _FIELD_WEIGHTS[name])
            for name, field in zip(
                ("id", "family", "modality", "heading", "dialect"),
                fuzzy_fields,
            )
        )
        if score >= 0.5:
            scored.append((score, r))
    if scored:
        scored.sort(reverse=True, key=lambda x: x[0])
        best_score, best = scored[0]
        return _build_payload(best, best_score, "weighted_fuzzy", dialect_n=dialect_n), best_score, "weighted_fuzzy"

    return None, 0.0, "none"


def lookup_recipe(
    query: str,
    path: Path = RECIPES_PATH,
    dialect_n: int = 30,
) -> dict | None:
    """Return one canonical recipe payload for library callers.

    The CLI and the prompt compiler share this function so recipe matching has
    one contract and one alias policy.
    """
    recipes = _parse_recipes(path.read_text(encoding="utf-8"))
    matched, _, _ = _match_recipe(recipes, query, dialect_n=dialect_n)
    return matched


def main(argv: list[str] | None = None) -> int:
    _require_python_311()
    parser = argparse.ArgumentParser(prog="recipe_lookup")
    parser.add_argument("--model", help="Recipe id (exact), alias, or substring")
    parser.add_argument("--n", type=int, default=30, help="Max body lines in dialect block")
    parser.add_argument("--path", type=Path, default=RECIPES_PATH)
    parser.add_argument("--check-alias", help="Resolve alias to canonical id")
    parser.add_argument("--list-aliases", action="store_true", help="Dump full alias table")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"[recipe_lookup] missing {args.path}", file=sys.stderr)
        return 3

    if args.list_aliases:
        json.dump(ALIASES, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 0

    if args.check_alias is not None:
        canonical = resolve_alias(args.check_alias)
        json.dump({"alias": args.check_alias, "canonical": canonical}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 0 if canonical else 2

    if not args.model:
        parser.error("--model is required (or use --check-alias / --list-aliases)")

    matched = lookup_recipe(args.model, path=args.path, dialect_n=args.n)

    if matched is None:
        json.dump({"matched": False, "query": args.model, "score": 0.0, "match_path": "none"}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 0

    json.dump(matched, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
