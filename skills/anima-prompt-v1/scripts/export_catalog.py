from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anima_prompt_v1.catalog import Catalog

MAX_EXPORT_LIMIT = 100_000


def export_hits(catalog: Catalog, *, query: str = "", mode: str = "auto", categories=(), facets=(), sources=(), limit: int = 1000):
    if limit < 1 or limit > MAX_EXPORT_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_EXPORT_LIMIT}")
    if not query.strip() and not (categories or facets or sources):
        raise ValueError("export requires a query or an explicit category, facet, or source scope")
    if query.strip():
        return catalog.search(query, mode=mode, categories=tuple(categories), facets=tuple(facets), sources=tuple(sources), limit=limit)
    return catalog.browse(categories=tuple(categories), facets=tuple(facets), sources=tuple(sources), limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--mode", choices=("auto", "exact", "prefix", "alias", "fuzzy", "related"), default="auto")
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--facet", action="append", default=[])
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--format", choices=("jsonl", "csv"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        hits = export_hits(Catalog(args.database), query=args.query, mode=args.mode, categories=args.category, facets=args.facet, sources=args.source, limit=args.limit)
    except ValueError as error:
        parser.error(str(error))
    rows = [hit.__dict__ for hit in hits]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "jsonl":
        args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    else:
        fields = sorted({key for row in rows for key in row})
        with args.output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
