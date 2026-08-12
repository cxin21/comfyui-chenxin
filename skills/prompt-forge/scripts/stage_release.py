"""Stage the explicit plugin release file set without development residue."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Iterator


class ReleaseStagingError(ValueError):
    """The source or destination violates the release staging boundary."""


_RELEASE_FILES = (
    Path(".codex-plugin/plugin.json"),
    Path(".mcp.json"),
    Path("LICENSE"),
    Path("README.md"),
)
_RELEASE_TREES = (Path("skills"), Path("mcp_server"))
_EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "tests",
    }
)
_EXCLUDED_FILE_SUFFIXES = (".pyc", ".pyo")


def stage_release(source_root: Path, destination_root: Path) -> dict[str, int]:
    """Copy one clean, deterministic release tree into an existing empty directory."""

    source = source_root.resolve()
    destination = destination_root.resolve()
    if source == destination or source in destination.parents:
        raise ReleaseStagingError("destination must be outside the source tree")
    if not source.is_dir():
        raise ReleaseStagingError("source root must be a directory")
    if not destination.is_dir() or any(destination.iterdir()):
        raise ReleaseStagingError("destination must be an existing empty directory")

    copied = 0
    for relative in _RELEASE_FILES:
        source_file = source / relative
        if not source_file.is_file():
            continue
        _copy_file(source_file, destination / relative)
        copied += 1

    for relative in _RELEASE_TREES:
        tree = source / relative
        if not tree.is_dir():
            continue
        for source_file in _iter_release_files(tree):
            target = destination / source_file.relative_to(source)
            _copy_file(source_file, target)
            copied += 1

    if copied == 0:
        raise ReleaseStagingError("release file set is empty")
    return {"files": copied}


def _iter_release_files(root: Path) -> Iterator[Path]:
    for current, directory_names, file_names in os.walk(root, topdown=True):
        current_path = Path(current)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if not _excluded_directory(name)
            and not (current_path / name).is_symlink()
        )
        for name in sorted(file_names):
            path = current_path / name
            if path.is_symlink() or name.endswith(_EXCLUDED_FILE_SUFFIXES):
                continue
            yield path


def _excluded_directory(name: str) -> bool:
    return name in _EXCLUDED_DIRECTORY_NAMES or name.endswith(".egg-info")


def _copy_file(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise ReleaseStagingError(f"release file cannot be a symbolic link: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination-root", type=Path, required=True)
    args = parser.parse_args()
    report = stage_release(args.source_root, args.destination_root)
    print(f"staged_files={report['files']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseStagingError as exc:
        raise SystemExit(f"release staging failed: {exc}")
