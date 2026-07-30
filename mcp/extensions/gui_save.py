#!/usr/bin/env python3
"""gui_save — save a workflow JSON graph under <ComfyUI>/user/default/workflows/.

Stdlib only. Returns JSON on stdout.

Usage:
    python gui_save.py --graph /tmp/my.json --name my_workflow
    python gui_save.py --graph - --name my_workflow  # read JSON from stdin

Output JSON:
    {
      "saved_to": "<absolute path>",
      "byte_size": int,
      "sha256": "...",
      "name": "my_workflow",
      "timestamp": "20260730-153045",
      "workflows_dir": "<absolute dir>",
      "sidecar": "<absolute path or null>",
      "manifest": {...} or null
    }

If ~/.claude/skills/<context> exists (a skill is "installed" with a directory
named <context>), we drop a `_manifest.json` sidecar next to the workflow
listing what generated this graph.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

from _shared import (
    EXIT_OK,
    EXIT_USAGE,
    compute_sha256,
    emit_human,
    emit_json,
    err_exit,
    require_python_311,
    resolve_comfyui_path,
)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _read_graph(path_arg: str) -> bytes:
    """Read the workflow graph from a file path or from stdin if path_arg is '-'."""
    if path_arg == "-":
        return sys.stdin.buffer.read()
    p = Path(path_arg)
    if not p.exists():
        err_exit(EXIT_USAGE, f"--graph file does not exist: {path_arg}")
    if not p.is_file():
        err_exit(EXIT_USAGE, f"--graph is not a regular file: {path_arg}")
    return p.read_bytes()


def _safe_name(raw: str) -> str:
    raw = raw.strip() or "workflow"
    cleaned = _SAFE_NAME.sub("_", raw)
    return cleaned[:120] or "workflow"


def _detect_skill_context() -> str | None:
    """Return the name of an installed skill under ~/.claude/skills/ if any.

    Heuristic: list ~/.claude/skills/<name> directories. We pick the first
    one that exists. This is intentionally simple — callers should pass an
    explicit context via $CHENXIN_CONTEXT if they need a specific one.
    """
    skills_root = Path.home() / ".claude" / "skills"
    if not skills_root.is_dir():
        return None
    candidates = [p for p in sorted(skills_root.iterdir()) if p.is_dir()]
    if not candidates:
        return None
    env_ctx = os.environ.get("CHENXIN_CONTEXT", "").strip()
    if env_ctx:
        target = skills_root / env_ctx
        if target.is_dir():
            return env_ctx
    return candidates[0].name


def _build_manifest(graph_bytes: bytes, sha: str, name: str, ts: str, context: str) -> dict:
    return {
        "schema_version": "1.0",
        "saved_by": "mcp.extensions.gui_save",
        "context": context,
        "workflow_name": name,
        "timestamp": ts,
        "byte_size": len(graph_bytes),
        "sha256": sha,
        "generator": "comfyui-chenxin/mcp/extensions/gui_save.py",
    }


def main(argv: list[str] | None = None) -> int:
    require_python_311()
    parser = argparse.ArgumentParser(
        prog="gui_save",
        description="Save a workflow JSON graph under <ComfyUI>/user/default/workflows/.",
    )
    parser.add_argument("--graph", required=True, help="Path to the graph JSON, or '-' for stdin")
    parser.add_argument("--name", required=True, help="Workflow name (sanitized for filename)")
    parser.add_argument(
        "--no-sidecar",
        action="store_true",
        help="Skip writing _manifest.json even if a skill context is detected",
    )
    args = parser.parse_args(argv)

    graph_bytes = _read_graph(args.graph)

    # Validate JSON parseability — we don't want to write garbage.
    try:
        json.loads(graph_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        err_exit(EXIT_USAGE, f"graph is not valid UTF-8 JSON: {e}")

    sha = compute_sha256(graph_bytes)
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = _safe_name(args.name)
    filename = f"{ts}_{safe}.json"

    comfyui = resolve_comfyui_path()
    workflows_dir = comfyui / "user" / "default" / "workflows"
    try:
        workflows_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        err_exit(EXIT_USAGE, f"failed to create workflows dir {workflows_dir}: {e}")

    saved_path = workflows_dir / filename
    try:
        saved_path.write_bytes(graph_bytes)
    except OSError as e:
        err_exit(EXIT_USAGE, f"failed to write {saved_path}: {e}")

    sidecar_path = None
    manifest = None
    if not args.no_sidecar:
        ctx = _detect_skill_context()
        if ctx:
            sidecar_path = workflows_dir / f"{ts}_{safe}._manifest.json"
            manifest = _build_manifest(graph_bytes, sha, safe, ts, ctx)
            try:
                sidecar_path.write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError as e:
                emit_human(f"[warn] failed to write sidecar {sidecar_path}: {e}")
                sidecar_path = None
                manifest = None

    emit_human(f"saved {len(graph_bytes)} bytes to {saved_path}")
    emit_json(
        {
            "saved_to": str(saved_path.resolve()),
            "byte_size": len(graph_bytes),
            "sha256": sha,
            "name": safe,
            "timestamp": ts,
            "workflows_dir": str(workflows_dir.resolve()),
            "sidecar": str(sidecar_path.resolve()) if sidecar_path else None,
            "manifest": manifest,
        }
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())