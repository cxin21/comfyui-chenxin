from __future__ import annotations

import argparse
import json
from pathlib import Path

from .search import Catalog


def positive_limit(value: str) -> int:
    limit = int(value)
    if limit < 1:
        raise argparse.ArgumentTypeError("limit must be at least 1")
    return limit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="anima-catalog")
    parser.add_argument("--database", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--mode", choices=("auto", "exact", "prefix", "alias", "fuzzy", "related"), default="auto")
    search.add_argument("--category", action="append", default=[])
    search.add_argument("--facet", action="append", default=[])
    search.add_argument("--source", action="append", default=[])
    search.add_argument("--limit", type=positive_limit, default=20)
    search.add_argument("--json", action="store_true")
    related = sub.add_parser("related")
    related.add_argument("record_id")
    related.add_argument("--relation-type")
    related.add_argument("--limit", type=positive_limit, default=50)
    related.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    catalog = Catalog(args.database)
    if args.command == "search":
        hits = catalog.search(args.query, mode=args.mode, categories=tuple(args.category), facets=tuple(args.facet), sources=tuple(args.source), limit=args.limit)
    else:
        hits = catalog.related(args.record_id, relation_type=args.relation_type, limit=args.limit)
    rows = [hit.__dict__ for hit in hits]
    print(json.dumps(rows, ensure_ascii=False) if args.json else "\n".join(json.dumps(row, ensure_ascii=False) for row in rows))
    return 0
