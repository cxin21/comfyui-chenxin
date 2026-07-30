#!/usr/bin/env python3
"""template_get — look up workflow templates from templates_index.json.

Stdlib only. Returns JSON on stdout.

Usage:
    python template_get.py --use-case txt2img --modality image
    python template_get.py --use-case img2vid --modality video --category wan

Output JSON:
    {
      "use_case": "txt2img",
      "modality": "image",
      "category": null,
      "matches": [{"id": "...", "name": "...", "category": "...", "modality": "image"}, ...],
      "truncated": false,
      "total_indexed": int,
      "index_present": bool
    }

If templates_index.json does not yet exist (P0.1 worker has not built it),
`matches` is `[]`, `index_present` is `false`, and `truncated` is `false`.
We never crash on a missing index — that is the contract.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from _shared import EXIT_OK, emit_human, emit_json, err_exit, load_templates_index, require_python_311


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _matches(entry: dict, use_case: str, modality: str, category: str | None) -> bool:
    """Return True if an index entry matches the requested filters."""
    eu = _norm(entry.get("use_case", ""))
    em = _norm(entry.get("modality", ""))
    ec = _norm(entry.get("category", ""))

    if use_case and eu != use_case:
        return False
    if modality and em != modality:
        return False
    if category and ec != _norm(category):
        return False
    return True


def _format_match(entry: dict) -> dict:
    return {
        "id": str(entry.get("id", "")),
        "name": str(entry.get("name", "")),
        "category": str(entry.get("category", "")),
        "modality": str(entry.get("modality", "")),
        "use_case": str(entry.get("use_case", "")),
    }


def main(argv: list[str] | None = None) -> int:
    require_python_311()
    parser = argparse.ArgumentParser(
        prog="template_get",
        description="Look up workflow templates from skills/chenxin-core/templates_index.json",
    )
    parser.add_argument("--use-case", default="", help="e.g. txt2img, img2img, img2vid, upscale")
    parser.add_argument("--modality", default="", help="e.g. image, video, audio")
    parser.add_argument("--category", default="", help="e.g. anima, flux, wan, sdxl")
    parser.add_argument("--limit", type=int, default=50, help="Maximum matches to return (default 50)")
    args = parser.parse_args(argv)

    if args.limit < 1 or args.limit > 500:
        err_exit(2, "--limit out of range (1..500)", limit=args.limit)

    use_case = _norm(args.use_case)
    modality = _norm(args.modality)
    category = _norm(args.category) or None

    index = load_templates_index()
    index_present = bool(index)
    entries: list[Any] = []
    if isinstance(index, dict):
        entries = list(index.get("templates", []) or [])
    elif isinstance(index, list):
        # Some producers write a bare list; tolerate it.
        entries = index

    if not isinstance(entries, list):
        entries = []

    raw_matches = [e for e in entries if isinstance(e, dict) and _matches(e, use_case, modality, category)]
    truncated = len(raw_matches) > args.limit
    matches = [_format_match(e) for e in raw_matches[: args.limit]]

    emit_human(
        f"templates_index present={index_present} indexed={len(entries)} "
        f"matched={len(raw_matches)} returned={len(matches)} truncated={truncated}"
    )
    emit_json(
        {
            "use_case": args.use_case,
            "modality": args.modality,
            "category": args.category or None,
            "matches": matches,
            "truncated": truncated,
            "total_indexed": len(entries),
            "index_present": index_present,
        }
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())