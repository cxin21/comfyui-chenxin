"""Stage the explicit plugin release tree."""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

INCLUDE = ("skills", "mcp_server", "docs", "scripts", "LICENSE", "README.md", "README.en.md", ".mcp.json", ".codex-plugin")
IGNORE = shutil.ignore_patterns(
    "__pycache__", ".pytest_cache", ".pytest-*", ".venv", ".codegraph",
    ".codex-backup-*", ".superpowers", "*.pyc", "tests", "fixtures",
)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination-root", type=Path, required=True)
    args = parser.parse_args()
    args.destination_root.mkdir(parents=True, exist_ok=True)
    for name in INCLUDE:
        source = args.source_root / name
        if not source.exists():
            continue
        destination = args.destination_root / name
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True, ignore=IGNORE)
        else:
            shutil.copy2(source, destination)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
