#!/usr/bin/env python3
"""tag_lookup — query danbooru tag dictionary via precomputed index.

Loads dictionary/tag-index.json (built by build_tag_index.py) and exposes
a 3-pass lookup: exact canonical → alias → substring.

Usage:
    python tag_lookup.py --query "long_hair"
    python tag_lookup.py --queries blonde_hair elf cherry_blossoms --exact
    python tag_lookup.py --query "elf" --limit 5
    python tag_lookup.py --query "1girl" --category 0
    python tag_lookup.py --exact "long_hair"

Stdlib only. Output: JSON array on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
INDEX_JSON = SKILL_DIR / "dictionary" / "tag-index.json"


def load_index(path: Path = INDEX_JSON) -> dict:
    if not path.exists():
        print(f"[tag_lookup] missing {path} — run build_tag_index.py first", file=sys.stderr)
        sys.exit(3)
    return json.loads(path.read_text(encoding="utf-8"))


def lookup(idx: dict, query: str, limit: int | None = None,
           category: int | None = None, exact: bool = False) -> list[dict]:
    """3-pass lookup. Returns list of {canonical, category, count, aliases, score}."""
    q = query.lower().strip()
    if not q:
        return []

    by_canonical = idx.get("by_canonical", {})
    by_alias = idx.get("by_alias", {})
    results: list[dict] = []
    seen: set[str] = set()

    def add(name: str, score: float) -> None:
        if name in seen:
            return
        entry = by_canonical.get(name)
        if entry is None:
            return
        cat = entry["cat"]
        if category is not None and cat != category:
            return
        seen.add(name)
        results.append({
            "canonical": name,
            "category": cat,
            "count": entry["count"],
            "aliases": entry["aliases"],
            "score": score,
        })

    # Pass 1: exact canonical name
    if q in by_canonical:
        add(q, 1.0)

    # Pass 2: exact alias match
    if q in by_alias:
        for c in by_alias[q]:
            add(c, 0.95)

    if exact:
        return results[:limit] if limit else results

    # Pass 3: substring match on canonical names, scored by count desc
    matches: list[tuple[float, str]] = []
    for name in by_canonical:
        if name in seen:
            continue
        if q in name:
            count = by_canonical[name]["count"]
            score = 0.6 + min(0.3, count / 10_000_000)
            matches.append((score, name))
    matches.sort(reverse=True)
    for score, name in matches:
        add(name, score)

    return results[:limit] if limit else results


def lookup_many(idx: dict, queries: list[str], limit: int | None = None,
                category: int | None = None, exact: bool = False) -> list[dict]:
    """Validate multiple independent candidates without joining them into one query."""
    return [
        {
            "query": query,
            "results": lookup(idx, query, limit=limit, category=category, exact=exact),
        }
        for query in queries
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tag_lookup")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--query", help="One token to search; preserves the v5 output shape")
    source.add_argument("--queries", nargs="+", help="Validate multiple independent tokens")
    parser.add_argument("--limit", type=int, default=None, help="Max results")
    parser.add_argument("--category", type=int, default=None, help="Filter by category")
    parser.add_argument("--exact", action="store_true", help="Strict canonical match only")
    parser.add_argument("--index", type=Path, default=INDEX_JSON)
    args = parser.parse_args(argv)

    idx = load_index(args.index)
    results = (
        lookup(idx, args.query, limit=args.limit, category=args.category, exact=args.exact)
        if args.query is not None
        else lookup_many(idx, args.queries, limit=args.limit, category=args.category, exact=args.exact)
    )
    json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
