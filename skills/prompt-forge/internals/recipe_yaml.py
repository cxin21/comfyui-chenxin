#!/usr/bin/env python3
"""recipe_yaml — re-format recipes/MODELS.md so every `### Recipe` heading carries
a proper YAML frontmatter block.

Background (P0.1 deferral): the recipes ship as prose with a degraded metadata
block. The block has the right shape (id / family / modality / dialect /
negative_policy / triggers / license / source / sample_prompts) but lacks the
`---` opening delimiter, and the `### Recipe` heading is glued onto the body
without a separating newline. This tool normalizes both.

Idempotency: running twice is a no-op. The output is byte-stable across runs.

Two modes:
    run mode  (default)   rewrite MODELS.md in place if needed
    --check               exit 0 if file is already up-to-date, 1 otherwise

Stdlib only (Python 3.11+).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

# Where the recipes live. Repo root is two levels up from this file.
_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
RECIPES_DIR = SKILL_DIR / "recipes"
MODELS_PATH = RECIPES_DIR / "MODELS.md"

# Canonical YAML field set. Order matters for stable output.
_EXPECTED_FIELDS = (
    "id",
    "family",
    "modality",
    "dialect",
    "negative_policy",
    "triggers",
    "license",
    "source",
    "sample_prompts",
)

_YAML_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")
_YAML_LIST_RE = re.compile(r"^\s+-\s*(.*)$")
_RECIPE_HEADING_LINE_RE = re.compile(r"^### \S")


def _require_python_311() -> None:
    if sys.version_info < (3, 11):
        sys.stderr.write("Python 3.11+ required\n")
        sys.exit(3)


def _strip_outer_quotes(s: str) -> str:
    """Strip one matched pair of outer quote chars; leave content untouched.

    Greedy stripping breaks round-trips when a value contains an apostrophe
    next to a closing quote (e.g. `tags.'"` should round-trip to `tags.'`).
    """
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def _unescape_double(s: str) -> str:
    """Unescape a double-quoted YAML/JSON scalar.

    Reverses json.dumps-style escapes (\\, \\", \\n, \\t, \\r, etc.).
    """
    out: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "r":
                out.append("\r")
            elif nxt == '"':
                out.append('"')
            elif nxt == "\\":
                out.append("\\")
            elif nxt == "0":
                out.append("\0")
            else:
                out.append(nxt)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _parse_yaml_block(text: str) -> dict:
    """Parse a degraded YAML block (no `---` delimiters) into a dict.

    Recognizes keys, scalar values, inline lists (`[a, b]`), and multi-line
    list items (indented `- value`).
    """
    fields: dict = {}
    cur_key: str | None = None
    cur_is_list = False

    def _decode(s: str) -> str:
        # Strip outer quotes; if double-quoted, also unescape escapes.
        stripped = _strip_outer_quotes(s)
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return _unescape_double(stripped)
        return stripped

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if line.strip() == "---":
            cur_key = None
            cur_is_list = False
            continue

        m_key = _YAML_KEY_RE.match(line)
        m_list = _YAML_LIST_RE.match(line)
        if m_key and not line.startswith((" ", "\t")):
            key, value = m_key.group(1), m_key.group(2).strip()
            cur_key = key
            if value == "":
                fields[key] = []
                cur_is_list = True
            elif value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                if inner == "":
                    fields[key] = []
                else:
                    fields[key] = [_decode(v.strip()) for v in inner.split(",")]
                cur_is_list = True
            else:
                fields[key] = _decode(value)
                cur_is_list = False
        elif m_list and cur_key is not None and cur_is_list:
            item = m_list.group(1).strip()
            if item.endswith("---"):
                item = item[:-3].rstrip()
            fields[cur_key].append(_decode(item))
        # else: orphan line — drop silently; legitimate YAML doesn't have any.

    return fields


def _render_frontmatter(fields: dict) -> str:
    """Render the frontmatter block with proper `---` delimiters.

    Field order: `_EXPECTED_FIELDS` first, then any unknown keys in insertion order.
    Scalar values are emitted as plain scalars when safe, or double-quoted
    strings (with json.dumps-style escapes) otherwise. List items are always
    double-quoted.
    """
    import json

    def _fmt_scalar(v) -> str:
        sval = str(v)
        # Plain scalars are safe when they contain no YAML-significant chars.
        special = set(":#&*!|>'\"%@`{}[]\n\r\t")
        if sval == "":
            return '""'
        if not any(c in special for c in sval) and not sval.startswith((" ", "-", "?", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
            return sval
        # json.dumps returns a properly-escaped, double-quoted string.
        return json.dumps(sval, ensure_ascii=False)

    def _fmt_list_item(v) -> str:
        return json.dumps(str(v), ensure_ascii=False)

    lines = ["---"]
    seen = set()
    for key in _EXPECTED_FIELDS:
        if key not in fields:
            continue
        seen.add(key)
        val = fields[key]
        if isinstance(val, list):
            if not val:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in val:
                    lines.append(f"  - {_fmt_list_item(item)}")
        else:
            lines.append(f"{key}: {_fmt_scalar(val)}")
    for key in fields:
        if key in seen:
            continue
        val = fields[key]
        if isinstance(val, list):
            if not val:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in val:
                    lines.append(f"  - {_fmt_list_item(item)}")
        else:
            lines.append(f"{key}: {_fmt_scalar(val)}")
    lines.append("---")
    return "\n".join(lines)


def _detect_recipe_blocks(text: str) -> list[tuple[int, int]]:
    """Find every (start_line, end_line) for the recipe sections.

    A recipe section starts at a `---` line that is immediately followed by an
    `id:` YAML key. The section ends at the next such `---` line (or EOF).
    Both endpoints are inclusive.
    """
    lines = text.splitlines()
    n = len(lines)

    starts: list[int] = []
    for i, ln in enumerate(lines):
        if ln.strip() != "---":
            continue
        j = i + 1
        while j < n and lines[j].strip() == "":
            j += 1
        if j < n and _YAML_KEY_RE.match(lines[j]):
            key = _YAML_KEY_RE.match(lines[j]).group(1)
            if key == "id":
                starts.append(i)

    boundaries: list[tuple[int, int]] = []
    for k, start in enumerate(starts):
        end = starts[k + 1] - 1 if k + 1 < len(starts) else n - 1
        while end > start and lines[end].strip() == "":
            end -= 1
        boundaries.append((start, end))
    return boundaries


def _split_heading_body(heading_line: str) -> tuple[str, str]:
    """Split heading_line into (heading, body_glued).

    Heading ends at the first occurrence of `- **` (body bullet marker).
    Falls back to the first `:` after a heading word for the rare
    `### Heading: prose` form.
    """
    if "- **" in heading_line:
        idx = heading_line.index("- **")
        return heading_line[:idx].rstrip(), heading_line[idx:]
    m = re.match(r"^(### [^:\n]+):\s+(.*)", heading_line)
    if m:
        return m.group(1), m.group(2)
    return heading_line, ""


def _normalize_block(block_lines: list[str]) -> list[str]:
    """Given a recipe block (yaml + heading + body), emit the normalized form."""
    heading_idx = None
    for idx, ln in enumerate(block_lines):
        if _RECIPE_HEADING_LINE_RE.match(ln):
            heading_idx = idx
            break
    if heading_idx is None:
        return list(block_lines)

    yaml_lines = block_lines[:heading_idx]
    body_lines_after = block_lines[heading_idx + 1:]

    yaml_text = "\n".join(yaml_lines)
    fields = _parse_yaml_block(yaml_text)

    heading_line, body_glued = _split_heading_body(block_lines[heading_idx])

    out: list[str] = []
    out.append("---")
    fm = _render_frontmatter(fields)
    out.extend(fm.splitlines()[1:-1])
    out.append("---")
    out.append("")
    out.append(heading_line)
    if body_glued.strip():
        # Heading had glued body — emit it on the same line.
        out.append(body_glued)
        # Preserve the trailing body lines that follow the heading line.
        out.extend(body_lines_after)
    elif body_lines_after:
        # Heading was standalone — preserve the original body verbatim
        # (including any blank-line separation between heading and body).
        out.extend(body_lines_after)
    return out


def normalize(text: str) -> str:
    """Return the normalized MODELS.md text. Idempotent."""
    boundaries = _detect_recipe_blocks(text)
    if not boundaries:
        return text
    lines = text.splitlines()
    new_lines = list(lines)
    for start, end in reversed(boundaries):
        block = lines[start:end + 1]
        new_block = _normalize_block(block)
        new_lines[start:end + 1] = new_block
    result = "\n".join(new_lines)
    if text.endswith("\n"):
        result += "\n"
    return result


def _persist_alias_to_file(aliases_path: Path, alias_norm: str, canonicals_list: list[str]) -> None:
    """Persist `alias_norm` -> `canonicals_list` inside the ALIASES dict of
    `aliases_path` using stdlib ast (no regex text-marker hacks).

    Locates the ALIASES dict literal via ast.parse, then mutates the source
    *within the dict's exact line bounds*:

    - If `alias_norm` already exists as a key, the existing entry is replaced
      in place (idempotent update; multi-line values supported).
    - Otherwise a new entry is inserted just before the dict's closing `}`.

    Because the modification is bounded by the dict literal's source range,
    all surrounding code (module docstring, type annotations, helper
    functions, blank lines, comments) is preserved verbatim.

    Handles both `ALIASES = {...}` (ast.Assign) and
    `ALIASES: dict[str, list[str]] = {...}` (ast.AnnAssign) forms.

    Raises RuntimeError if the file is not valid Python or the ALIASES
    dict cannot be located.
    """
    text = aliases_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeError(f"_aliases.py is not valid Python: {exc}") from exc

    # Find the ALIASES dict literal.
    dict_node = None
    for node in ast.walk(tree):
        value = None
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "ALIASES" for t in node.targets):
                value = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "ALIASES":
                value = node.value
        if isinstance(value, ast.Dict):
            dict_node = value
            break

    if dict_node is None:
        raise RuntimeError("ALIASES dict not found in _aliases.py")

    # Find existing key (if any) for idempotent update.
    existing_key_node = None
    existing_value_end_lineno = None
    for key, val in zip(dict_node.keys, dict_node.values):
        if isinstance(key, ast.Constant) and key.value == alias_norm:
            existing_key_node = key
            existing_value_end_lineno = val.end_lineno
            break

    new_entry_line = f'    "{alias_norm}": {json.dumps(canonicals_list)},\n'
    lines = text.splitlines(keepends=True)

    if existing_key_node is not None and existing_value_end_lineno is not None:
        # Replace existing entry in place (handle multi-line values).
        start_idx = existing_key_node.lineno - 1
        end_idx = existing_value_end_lineno - 1
        lines[start_idx : end_idx + 1] = [new_entry_line]
    else:
        # Insert new entry just before the dict's closing `}`.
        # end_lineno is 1-indexed and points at the `}` line; converting to
        # 0-indexed gives the position the `}` currently occupies. Inserting
        # at that index pushes the `}` down by one line.
        insert_idx = dict_node.end_lineno - 1
        lines.insert(insert_idx, new_entry_line)

    aliases_path.write_text("".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _require_python_311()
    parser = argparse.ArgumentParser(
        prog="recipe_yaml",
        description="Re-format recipes/MODELS.md so every recipe carries proper YAML frontmatter.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check whether the file is already up-to-date; exit 0 if yes, 1 if no.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=MODELS_PATH,
        help=f"Path to MODELS.md (default: {MODELS_PATH})",
    )
    parser.add_argument(
        "--validate-schema",
        action="store_true",
        help="Check that every recipe has required fields (id, dialect). Exits 1 on failure.",
    )
    parser.add_argument(
        "--add-alias",
        metavar="ALIAS=CANONICAL",
        help="Append an alias to internals/_aliases.ALIASES.",
    )
    parser.add_argument(
        "--list-aliases",
        action="store_true",
        help="Dump alias table as JSON.",
    )
    args = parser.parse_args(argv)

    if not args.path.exists():
        sys.stderr.write(f"[recipe_yaml] file not found: {args.path}\n")
        return 3

    if args.list_aliases:
        from _aliases import ALIASES
        json.dump(ALIASES, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 0

    if args.add_alias:
        from _aliases import ALIASES
        if "=" not in args.add_alias:
            print("[recipe_yaml] --add-alias requires ALIAS=CANONICAL", file=sys.stderr)
            return 2
        alias_key, _, canonicals = args.add_alias.partition("=")
        alias_norm = alias_key.lower().strip()
        canonicals_list = [c.strip() for c in canonicals.split(",") if c.strip()]
        if not canonicals_list:
            print("[recipe_yaml] --add-alias requires at least one canonical id", file=sys.stderr)
            return 2
        ALIASES[alias_norm] = canonicals_list
        aliases_path = Path(__file__).resolve().parent / "_aliases.py"
        try:
            _persist_alias_to_file(aliases_path, alias_norm, canonicals_list)
        except RuntimeError as exc:
            print(f"[recipe_yaml] {exc}", file=sys.stderr)
            return 3
        print(f"[recipe_yaml] added alias '{alias_norm}' → {canonicals_list}")
        return 0

    if args.validate_schema:
        text = args.path.read_text(encoding="utf-8") if args.path.exists() else ""
        errors: list[str] = []
        seen_ids: set[str] = set()
        block_re = re.compile(r"^---\n(.*?)\n---\n", re.M | re.S)
        recipe_idx = 0
        for m in block_re.finditer(text):
            yaml_text = m.group(1)
            # Only treat as a recipe if the first non-blank line is an `id:` key.
            # This filters out the file-level frontmatter and markdown sections
            # that use `---` as horizontal rules (mirrors v4 _detect_recipe_blocks).
            first_key = None
            for ln in yaml_text.splitlines():
                if ln.strip() == "":
                    continue
                first_key = ln
                break
            if not first_key or not _YAML_KEY_RE.match(first_key) or _YAML_KEY_RE.match(first_key).group(1) != "id":
                continue
            m_id = re.search(r"^id:\s*(\S+)", yaml_text, re.M)
            if not m_id:
                errors.append(f"recipe #{recipe_idx}: missing 'id' value")
                recipe_idx += 1
                continue
            id_val = m_id.group(1)
            if not re.match(r"^[a-z0-9_-]+$", id_val):
                errors.append(f"recipe '{id_val}': id contains invalid chars")
            if id_val in seen_ids:
                errors.append(f"recipe '{id_val}': duplicate id")
            seen_ids.add(id_val)
            recipe_idx += 1
        if errors:
            for e in errors:
                print(f"[recipe_yaml] {e}", file=sys.stderr)
            print(f"[recipe_yaml] {len(errors)} schema error(s)", file=sys.stderr)
            return 1
        print(f"[recipe_yaml] schema OK ({len(seen_ids)} recipes)")
        return 0

    original = args.path.read_text(encoding="utf-8")
    rewritten = normalize(original)

    if rewritten == original:
        sys.stderr.write(f"[recipe_yaml] up-to-date: {args.path}\n")
        return 0

    if args.check:
        sys.stderr.write(f"[recipe_yaml] needs rewrite: {args.path} ({len(original)} -> {len(rewritten)} bytes)\n")
        return 1

    args.path.write_text(rewritten, encoding="utf-8")
    sys.stderr.write(f"[recipe_yaml] rewrote: {args.path} ({len(original)} -> {len(rewritten)} bytes)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())