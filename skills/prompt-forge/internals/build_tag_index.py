#!/usr/bin/env python3
"""build_tag_index — build tag-index.json from danbooru.csv + wd14-tags.csv.

One-shot script (CI-style). Produces a deterministic JSON index that
tag_lookup.py loads at runtime for fast (≤100ms) tag queries.

Usage:
    python build_tag_index.py                # build (overwrites tag-index.json)
    python build_tag_index.py --check        # exit 1 if CSV newer than index
    python build_tag_index.py --stats        # print row counts, alias ratios

Output: dictionary/tag-index.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
DICT_DIR = SKILL_DIR / "dictionary"
DANBOORU_CSV = DICT_DIR / "danbooru.csv"
WD14_CSV = DICT_DIR / "wd14-tags.csv"
INDEX_JSON = DICT_DIR / "tag-index.json"

INDEX_VERSION = "2026-08-01"


def parse_danbooru_csv(path: Path) -> list[dict]:
    """Parse danbooru.csv: name,category,count,aliases.

    aliases is a CSV-escaped quoted list like '"/lh,longhair"'.
    The CSV has no header row; columns are positional.
    """
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for r in reader:
            if not r:
                continue
            name = (r[0] if len(r) > 0 else "").strip()
            category_raw = r[1] if len(r) > 1 else "0"
            count_raw = r[2] if len(r) > 2 else "0"
            aliases_field = r[3] if len(r) > 3 else ""
            try:
                count = int(count_raw)
            except (ValueError, TypeError):
                count = 0
            try:
                category = int(category_raw)
            except (ValueError, TypeError):
                category = 0
            aliases: list[str] = []
            if aliases_field:
                if aliases_field.startswith('"') and aliases_field.endswith('"'):
                    inner = aliases_field[1:-1]
                else:
                    inner = aliases_field
                aliases = [a.strip() for a in inner.split(",") if a.strip()]
            rows.append({
                "name": name,
                "category": category,
                "count": count,
                "aliases": aliases,
            })
    return rows


def build_index(rows: list[dict], version: str) -> dict:
    """Build the index dict from parsed danbooru rows."""
    by_canonical: dict[str, dict] = {}
    by_alias: dict[str, list[str]] = {}
    for r in rows:
        name = r["name"]
        if not name:
            continue
        by_canonical[name] = {
            "cat": r["category"],
            "count": r["count"],
            "aliases": r["aliases"],
        }
        for a in r["aliases"]:
            by_alias.setdefault(a, []).append(name)
    return {
        "_meta": {
            "source": "danbooru.csv",
            "version": version,
            "row_count": len(rows),
            "built_at_epoch": int(time.time()),
        },
        "by_canonical": by_canonical,
        "by_alias": by_alias,
    }


def write_index(idx: dict, path: Path) -> None:
    """Atomically write index to path."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _is_csv_newer_than_index() -> bool:
    if not INDEX_JSON.exists():
        return True
    idx_mtime = INDEX_JSON.stat().st_mtime
    for csv in (DANBOORU_CSV, WD14_CSV):
        if csv.exists() and csv.stat().st_mtime > idx_mtime:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_tag_index")
    parser.add_argument("--check", action="store_true", help="Exit 1 if CSV is newer than index")
    parser.add_argument("--stats", action="store_true", help="Print row/alias counts and exit")
    args = parser.parse_args(argv)

    if not DANBOORU_CSV.exists():
        print(f"[build_tag_index] missing {DANBOORU_CSV}", file=sys.stderr)
        return 3

    if args.stats:
        rows = parse_danbooru_csv(DANBOORU_CSV)
        idx = build_index(rows, INDEX_VERSION)
        total = sum(len(v) for v in idx["by_alias"].values())
        print(f"rows={idx['_meta']['row_count']} aliases={total} categories={len(set(r['category'] for r in rows))}")
        return 0

    if args.check:
        if _is_csv_newer_than_index():
            print("[build_tag_index] CSV newer than index — rebuild needed", file=sys.stderr)
            return 1
        print("[build_tag_index] index is fresh")
        return 0

    rows = parse_danbooru_csv(DANBOORU_CSV)
    idx = build_index(rows, INDEX_VERSION)
    write_index(idx, INDEX_JSON)
    total = sum(len(v) for v in idx["by_alias"].values())
    print(f"[build_tag_index] wrote {INDEX_JSON} rows={idx['_meta']['row_count']} aliases={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
