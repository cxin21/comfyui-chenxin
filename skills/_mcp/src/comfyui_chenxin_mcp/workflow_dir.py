"""Scan installed skill packages for ``workflow/source/*.json``.

Each installed skill package ships its own ``workflow/source/`` directory.
This module introspects registered entry-points, finds each skill's package
on disk, and enumerates the source workflows.

Picking up a new workflow = dropping a JSON into the skill package's
``workflow/source/``; no code changes required.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from .registry import discover as _discover_skills


def _resolve_package_dir(module_name: str) -> Path | None:
    """Return the filesystem path of the package that owns ``module_name``."""
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        return None
    mod_file = getattr(mod, "__file__", None)
    if not mod_file:
        return None
    p = Path(mod_file).resolve()
    # For a package `foo.bar.baz`, __file__ points at foo/bar/baz.py; the
    # package directory is foo/bar. Walk up until we find a directory
    # containing an __init__.py (or stop at the top-level package).
    parts = module_name.split(".")
    # Walk back from the file: `foo.bar.baz` -> foo/bar -> foo
    target_pkg = parts[0]
    cur = p
    # If __file__ points at a __init__.py, the package root is cur.parent.
    if cur.name == "__init__.py":
        cur = cur.parent
    # For dotted modules inside a package, ascend by the dotted depth.
    depth = len(parts) - 1  # number of subpackage levels below top-level
    for _ in range(depth):
        cur = cur.parent
    if not cur.is_dir():
        return None
    # Sanity check: directory should be named after the top-level package.
    if cur.name != target_pkg:
        # Fall back to walking up until we find a matching name.
        for ancestor in cur.parents:
            if ancestor.name == target_pkg:
                return ancestor
        return cur
    return cur


def list_workflows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for reg in _discover_skills():
        module_name = reg.register_fn.__module__
        # The entry-point module is `<pkg>.mcp_bridge`; the package root
        # is one level up from there.
        parts = module_name.split(".")
        pkg_module_name = parts[0]
        pkg_dir = _resolve_package_dir(pkg_module_name)
        if pkg_dir is None:
            continue
        source_dir = pkg_dir / "workflow" / "source"
        if not source_dir.is_dir():
            continue
        for wf_path in sorted(source_dir.glob("*.json")):
            try:
                with wf_path.open(encoding="utf-8") as f:
                    wf = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            nodes = wf.get("nodes") if isinstance(wf, dict) else None
            out.append({
                "skill": reg.name,
                "workflow": wf_path.stem,
                "path": str(wf_path),
                "node_count": len(nodes) if isinstance(nodes, list) else 0,
            })
    return out