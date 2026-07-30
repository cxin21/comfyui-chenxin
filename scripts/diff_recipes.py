#!/usr/bin/env python3
"""diff_recipes.py — structural diff for chenxin-core/recipes/MODELS.md.

Parses two MODELS.md files (old + new) and returns added/removed/changed
recipe entries, where a "recipe" is a top-level `## <heading>` section
that contains a YAML frontmatter block (between `---` fences) at the top
of the section body.

This is stdlib-only: no PyYAML. The YAML blocks we read here are
flat-ish (id / family / modality / prompt_dialect / negative_prompt /
trigger_tokens / license / sample_prompt), so we parse them with a tiny
line-oriented walker instead of pulling in a full YAML library.

CLI:
    python3 scripts/diff_recipes.py OLD NEW [--json]

Output (default): unified-diff-style report to stdout.
Output (--json): structured JSON for programmatic use by check_updates.py.

Exit codes:
    0   always (diff is informational; check_updates.py decides action)
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# A "section" is a Markdown `## ` heading whose body opens with a fenced
# YAML block (--- ... ---). We index by the lowercased heading text.
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^---\s*$")
KEYVAL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
LIST_RE = re.compile(r"^\s*-\s+(.*)$")
TRIGGER_LINE = re.compile(r"^trigger_tokens\s*:")


@dataclass
class Recipe:
    heading: str
    frontmatter: dict = field(default_factory=dict)
    body: str = ""  # everything after the closing fence

    @property
    def key(self) -> str:
        # The `id:` field is canonical; fall back to heading.
        return str(self.frontmatter.get("id") or self.heading).strip().lower()


def parse_frontmatter(lines: list[str]) -> tuple[dict, int]:
    """Parse a fenced YAML block; return (flat_dict, lines_consumed)."""
    if not lines or not FENCE_RE.match(lines[0]):
        return {}, 0
    out: dict = {}
    i = 1
    current_list_key: str | None = None
    while i < len(lines) and not FENCE_RE.match(lines[i]):
        line = lines[i].rstrip("\n")
        if LIST_RE.match(line):
            if current_list_key:
                out.setdefault(current_list_key, []).append(
                    LIST_RE.match(line).group(1).strip().strip('"').strip("'")
                )
            i += 1
            continue
        m = KEYVAL_RE.match(line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val == "" or val is None:
                # Could be the start of a list — remember the key.
                current_list_key = key
                out.setdefault(key, [])
            else:
                current_list_key = None
                # Strip wrapping quotes.
                out[key] = val.strip().strip('"').strip("'")
        i += 1
    # i is the index of the closing fence (or end of list).
    if i < len(lines):
        i += 1
    return out, i


def parse_recipes(text: str) -> dict[str, Recipe]:
    """Split a MODELS.md into recipes keyed by id/heading.

    Sections without a frontmatter block are ignored — we only diff
    structured recipes, not free-form prose.
    """
    out: dict[str, Recipe] = {}
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        m = HEADING_RE.match(lines[i])
        if not m:
            i += 1
            continue
        heading = m.group(1).strip()
        # Collect body until next `## ` heading.
        j = i + 1
        body_lines: list[str] = []
        while j < n and not HEADING_RE.match(lines[j]):
            body_lines.append(lines[j])
            j += 1
        # Body must start with a `---` fence.
        if body_lines and FENCE_RE.match(body_lines[0]):
            fm, consumed = parse_frontmatter(body_lines)
            rec = Recipe(heading=heading, frontmatter=fm, body="\n".join(body_lines[consumed:]))
        else:
            rec = Recipe(heading=heading, body="\n".join(body_lines))
        out[rec.key] = rec
        i = j
    return out


def structural_diff(old: dict[str, Recipe], new: dict[str, Recipe]) -> dict:
    """Compare two recipe dicts; return added/removed/changed/unchanged lists."""
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    common = sorted(set(old) & set(new))
    changed: list[dict] = []
    unchanged: list[str] = []
    for k in common:
        o, n = old[k], new[k]
        if o.frontmatter == n.frontmatter and o.body == n.body:
            unchanged.append(k)
        else:
            # Build a unified diff for the body, summarize frontmatter changes.
            fm_diff: dict = {}
            for fk in set(o.frontmatter) | set(n.frontmatter):
                if o.frontmatter.get(fk) != n.frontmatter.get(fk):
                    fm_diff[fk] = {
                        "old": o.frontmatter.get(fk),
                        "new": n.frontmatter.get(fk),
                    }
            body_diff = list(
                difflib.unified_diff(
                    o.body.splitlines(keepends=True),
                    n.body.splitlines(keepends=True),
                    fromfile=f"a/{k}",
                    tofile=f"b/{k}",
                    n=1,
                )
            )
            changed.append(
                {
                    "key": k,
                    "heading": n.heading,
                    "frontmatter_diff": fm_diff,
                    "body_unified_diff": "".join(body_diff)[:2000],
                }
            )
    return {
        "added": [{"key": k, "heading": new[k].heading} for k in added],
        "removed": [{"key": k, "heading": old[k].heading} for k in removed],
        "changed": changed,
        "unchanged": unchanged,
    }


def render_unified_report(old_path: Path, new_path: Path, diff: dict) -> str:
    out: list[str] = []
    out.append(f"--- diff: {old_path.name} → {new_path.name} ---")
    out.append(f"added:   {len(diff['added'])}")
    out.append(f"removed: {len(diff['removed'])}")
    out.append(f"changed: {len(diff['changed'])}")
    out.append(f"unchanged: {len(diff['unchanged'])}")
    for a in diff["added"]:
        out.append(f"  + {a['key']}  ({a['heading']})")
    for r in diff["removed"]:
        out.append(f"  - {r['key']}  ({r['heading']})")
    for c in diff["changed"]:
        out.append(f"  ~ {c['key']}  ({c['heading']})")
        if c["frontmatter_diff"]:
            for fk, v in c["frontmatter_diff"].items():
                out.append(f"      fm[{fk}]: {v['old']!r} -> {v['new']!r}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("old", type=Path, help="Path to OLD MODELS.md")
    ap.add_argument("new", type=Path, help="Path to NEW MODELS.md (or '-' for stdin)")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of report")
    args = ap.parse_args(argv)

    if not args.old.is_file():
        print(f"diff_recipes: OLD file not found: {args.old}", file=sys.stderr)
        return 2
    if str(args.new) == "-":
        new_text = sys.stdin.read()
    elif args.new.is_file():
        new_text = args.new.read_text(encoding="utf-8")
    else:
        print(f"diff_recipes: NEW file not found: {args.new}", file=sys.stderr)
        return 2

    old_recipes = parse_recipes(args.old.read_text(encoding="utf-8"))
    new_recipes = parse_recipes(new_text)
    diff = structural_diff(old_recipes, new_recipes)
    diff["stats"] = {
        "old_count": len(old_recipes),
        "new_count": len(new_recipes),
        "added": len(diff["added"]),
        "removed": len(diff["removed"]),
        "changed": len(diff["changed"]),
        "unchanged": len(diff["unchanged"]),
    }
    if args.json:
        json.dump(diff, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(render_unified_report(args.old, args.new, diff))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
