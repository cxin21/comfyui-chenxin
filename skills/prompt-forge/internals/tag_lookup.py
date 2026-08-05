#!/usr/bin/env python3
"""Exact tag validation against the checked-in lexical index."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
INDEX_JSON = _THIS.parent.parent / "dictionary" / "tag-index.json"
_CONTROL_TOKEN_RE = re.compile(r"^(?:BREAK|score_[0-9]+(?:_up)?)$")


def load_index(path: Path = INDEX_JSON) -> dict:
    if not path.exists():
        print(f"[tag_lookup] missing {path} - verify checked-in tag-index.json", file=sys.stderr)
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("by_canonical"), dict):
        raise ValueError("tag index must contain by_canonical")
    return data


def _approved_aliases(index: dict, aliases: dict | None) -> dict[str, str | list[str]]:
    if aliases is not None:
        return {str(key): value for key, value in aliases.items()}
    result: dict[str, str | list[str]] = {}
    for canonical, entry in index.get("by_canonical", {}).items():
        for alias in entry.get("aliases", []):
            if isinstance(alias, str):
                result.setdefault(alias, []).append(canonical)
    for alias, targets in index.get("by_alias", {}).items():
        if isinstance(alias, str):
            result[alias] = list(targets) if isinstance(targets, list) else targets
    return result


def validate_tags(tags: list[str], index: dict, aliases: dict | None = None) -> dict:
    """Validate exact canonical tags and approved aliases; fail closed otherwise."""
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError("tags must be a list of strings")
    canonical = index.get("by_canonical", {})
    approved = _approved_aliases(index, aliases)
    validated: list[str] = []
    rejected: list[str] = []
    duplicates: list[str] = []
    controls: list[str] = []
    seen: set[str] = set()
    rejected_seen: set[str] = set()
    for raw in tags:
        tag = raw.strip()
        if _CONTROL_TOKEN_RE.fullmatch(tag):
            if tag not in controls:
                controls.append(tag)
            elif tag not in duplicates:
                duplicates.append(tag)
            continue
        target: str | None = tag if tag in canonical else None
        if target is None and tag in approved:
            candidate = approved[tag]
            if isinstance(candidate, str) and candidate in canonical:
                target = candidate
            elif isinstance(candidate, list) and len(candidate) == 1 and candidate[0] in canonical:
                target = candidate[0]
        if target is None:
            if tag in rejected_seen:
                if raw not in duplicates:
                    duplicates.append(raw)
            else:
                rejected.append(raw)
                rejected_seen.add(tag)
            continue
        if target in seen:
            if target not in duplicates:
                duplicates.append(target)
            continue
        seen.add(target)
        validated.append(target)
    return {"validated": validated, "rejected": rejected, "duplicates": duplicates, "recipe_control_tokens": controls}


def lookup(idx: dict, query: str, limit: int | None = None, category: int | None = None, exact: bool = False) -> list[dict]:
    """Return lexical suggestions; final validation must use validate_tags."""
    q = query.casefold().strip()
    if not q:
        return []
    by_canonical = idx.get("by_canonical", {})
    by_alias = idx.get("by_alias", {})
    results: list[dict] = []
    seen: set[str] = set()

    def add(name: str, score: float) -> None:
        if name in seen or name not in by_canonical:
            return
        entry = by_canonical[name]
        if category is not None and entry.get("cat") != category:
            return
        seen.add(name)
        results.append({"canonical": name, "category": entry.get("cat"), "count": entry.get("count"), "aliases": entry.get("aliases", []), "score": score})

    if q in by_canonical:
        add(q, 1.0)
    for canonical_name in by_alias.get(q, []):
        add(canonical_name, 0.95)
    if not exact:
        matches = []
        for name, entry in by_canonical.items():
            if name not in seen and q in name:
                matches.append((0.6 + min(0.3, entry.get("count", 0) / 10_000_000), name))
        for score, name in sorted(matches, reverse=True):
            add(name, score)
    return results[:limit] if limit else results


def lookup_many(idx: dict, queries: list[str], limit: int | None = None, category: int | None = None, exact: bool = False) -> list[dict]:
    return [{"query": query, "results": lookup(idx, query, limit=limit, category=category, exact=exact)} for query in queries]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tag_lookup")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--query")
    source.add_argument("--queries", nargs="+")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--category", type=int)
    parser.add_argument("--exact", action="store_true")
    parser.add_argument("--index", type=Path, default=INDEX_JSON)
    args = parser.parse_args(argv)
    index = load_index(args.index)
    result = lookup(index, args.query, args.limit, args.category, args.exact) if args.query is not None else lookup_many(index, args.queries, args.limit, args.category, args.exact)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
