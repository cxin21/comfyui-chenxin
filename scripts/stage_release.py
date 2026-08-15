"""Stage the post-P7 plugin release tree.

P8 final gate. The release tree no longer carries Codex MCP artifacts
(``mcp_server/``, ``.mcp.json``, ``.codex-plugin/``). It does ship:

* ``skills/`` (5 Skills),
* ``runtime/comfyui_http/`` (the neutral HTTP transport),
* ``.claude-plugin/`` (Claude Code marketplace plugin manifest),
* ``tests/cli_protocol/`` and ``tests/test_release_no_mcp.py``
  (the in-repo regression gate),
* ``scripts/`` (install, verify, stage, smoke),
* ``docs/`` + top-level README/LICENSE,
* ``.gitattributes``.

Venv caches, ``__pycache__``, ``.pytest_cache``, and any vendored
fixture tree under ``tests/e2e/fixtures`` are pruned.

Run:

    python scripts/stage_release.py --source-root . --destination-root /tmp/release
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


INCLUDE = (
    "skills",
    "runtime",
    "tests",
    ".claude-plugin",
    "scripts",
    "docs",
    ".gitattributes",
    "LICENSE",
    "README.md",
    "README.en.md",
)

IGNORE = shutil.ignore_patterns(
    "__pycache__",
    ".pytest_cache",
    ".pytest-*",
    ".venv",
    ".codegraph",
    ".superpowers",
    "*.pyc",
    "tests/e2e/fixtures",
)


def _stage_one(source: Path, destination_root: Path) -> None:
    if not source.exists():
        return
    destination = destination_root / source.name
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=IGNORE)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination-root", type=Path, required=True)
    args = parser.parse_args()

    if not args.source_root.is_dir():
        print(
            f"[stage_release][error] source-root {args.source_root} is not a directory",
            file=sys.stderr,
        )
        return 2

    if args.destination_root.exists():
        shutil.rmtree(args.destination_root)
    args.destination_root.mkdir(parents=True, exist_ok=True)

    for name in INCLUDE:
        _stage_one(args.source_root / name, args.destination_root)

    print(f"[stage_release] staged {args.destination_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
