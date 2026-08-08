"""Cross-attempt state for character-video-pipeline.

Stores one JSON record per attempted run under ``%USERPROFILE%\\.codex\\state\\
comfyui-chenxin\\attempts.jsonl``. The SKILL.md Step 0b rule tells the host
agent to read the most recent attempt before starting work so it can
surface a known unresolved blocker instead of repeating it.

This module never overwrites history. Reads append-only with explicit
record_attempt(); reads return the most recent record (line-by-line
seek-from-end is enough for jsonl).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_DIR_NAME = "comfyui-chenxin"
STATE_FILE_NAME = "attempts.jsonl"
STATE_DIR_ENV = "COMFYUI_CHENXIN_STATE_DIR"


def state_path() -> Path:
    """Resolve the attempts.jsonl path, honoring COMFYUI_CHENXIN_STATE_DIR override."""
    override = os.environ.get(STATE_DIR_ENV)
    if override:
        base = Path(override)
    else:
        user_profile = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
        base = Path(user_profile) / ".codex" / "state" / STATE_DIR_NAME
    return base / STATE_FILE_NAME


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_state_dir() -> Path:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def record_attempt(payload: dict[str, Any]) -> Path:
    """Append one attempt record. Returns the resolved state path."""
    if not isinstance(payload, dict):
        raise TypeError("attempt payload must be an object")
    record = {
        "schema_version": "1.0",
        "recorded_at": _utc_now(),
        **payload,
    }
    path = ensure_state_dir()
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return path


def read_last_attempt() -> dict[str, Any] | None:
    """Return the most recent attempt record, or None if the file is missing or empty."""
    p = state_path()
    if not p.is_file():
        return None
    last = None
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                last = json.loads(line)
            except json.JSONDecodeError:
                continue
    return last


def emit(payload: dict[str, Any] | None) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="camera-image-attempt-state")
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("read-last", help="print the most recent attempt record")
    rec = sub.add_parser(
        "record",
        help="append one attempt record (read JSON from stdin)",
    )
    args = parser.parse_args()
    if args.command == "read-last":
        emit(read_last_attempt())
        sys.exit(0)
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    path = record_attempt(payload)
    emit({"recorded": True, "path": str(path)})
    sys.exit(0)
