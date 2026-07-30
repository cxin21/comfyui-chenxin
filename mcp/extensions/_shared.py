"""Shared helpers for comfyui-chenxin MCP extension CLIs.

Stdlib-only (Python 3.11+). No external imports.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ----- exit code conventions ----------------------------------------------- #

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_MISSING = 3
EXIT_TIMEOUT = 4

# ----- project layout ------------------------------------------------------- #

# chenxin root: parent of mcp/ where this file lives.
_THIS = Path(__file__).resolve()
MCP_DIR = _THIS.parent
REPO_ROOT = MCP_DIR.parent.parent  # mcp/extensions/_shared.py -> repo root

HARDWARE_DIR = REPO_ROOT / "skills" / "chenxin-core" / "hardware"
TEMPLATES_INDEX = REPO_ROOT / "skills" / "chenxin-core" / "templates_index.json"

# ----- I/O helpers ---------------------------------------------------------- #


def emit_json(payload: dict) -> None:
    """Write a JSON payload to stdout (machine-readable contract)."""
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()


def emit_human(line: str) -> None:
    """Write a human-readable status line to stderr (so stdout stays clean)."""
    sys.stderr.write(line.rstrip() + "\n")
    sys.stderr.flush()


def err_exit(code: int, message: str, **extra) -> None:
    """Emit a JSON error to stdout and exit with the given code."""
    payload = {"error": message, "code": code}
    payload.update(extra)
    emit_json(payload)
    sys.exit(code)


# ----- HTTP helpers --------------------------------------------------------- #


def http_get_json(url: str, timeout: float = 5.0) -> tuple[int, dict]:
    """GET a URL, return (status_code, parsed_json_or_empty_dict)."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return resp.status, {}
    except urllib.error.HTTPError as e:
        return e.code, {}
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return 0, {}


def http_get_status(url: str, timeout: float = 5.0) -> int:
    """GET a URL and return only the status code (0 means network failure)."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return 0


# ----- networking ----------------------------------------------------------- #


def wait_for_port(host: str, port: int, timeout_s: float = 60.0, poll_s: float = 1.0) -> bool:
    """Poll host:port until a TCP connection succeeds or timeout. Returns True if ready."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=poll_s):
                return True
        except OSError:
            time.sleep(poll_s)
    return False


def wait_for_http(url: str, timeout_s: float = 60.0, poll_s: float = 1.0) -> bool:
    """Poll an HTTP URL until it returns 200 or timeout. Returns True if ready."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if http_get_status(url, timeout=poll_s) == 200:
            return True
        time.sleep(poll_s)
    return False


# ----- file helpers --------------------------------------------------------- #


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_hardware(vram_gb: int) -> dict:
    """Load skills/chenxin-core/hardware/<vram_gb>.json. Returns {} if missing.

    The hardware JSON layout is owned by the P0.1 worker; we only consume it.

    Accepts multiple filename conventions (in priority order) so that workers
    and future schemas cannot drift apart silently:
        1. hardware/<vram_gb>.json      (preferred canonical name)
        2. hardware/<vram_gb>gb.json    (legacy / human-readable variant)
    """
    vram = int(vram_gb)
    candidates = [HARDWARE_DIR / f"{vram}.json", HARDWARE_DIR / f"{vram}gb.json"]
    tried: list[str] = []
    for path in candidates:
        tried.append(path.name)
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            emit_human(f"[warn] failed to read hardware profile {path}: {e}")
            continue
    emit_human(f"[info] no hardware profile for vram_gb={vram} (tried: {', '.join(tried)})")
    return {}


def load_templates_index() -> dict:
    """Load skills/chenxin-core/templates_index.json. Returns {} if missing.

    P0.1 builds this file; if it does not yet exist when this CLI runs, we
    fall back to an empty index so callers do not have to handle the missing
    case specially.
    """
    if not TEMPLATES_INDEX.exists():
        return {}
    try:
        with TEMPLATES_INDEX.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        emit_human(f"[warn] failed to read templates_index.json: {e}")
        return {}


def resolve_comfyui_path() -> Path:
    """Resolve the local ComfyUI install path.

    Priority:
      1. $COMFYUI_PATH env var
      2. ~/ComfyUI default
    """
    env = os.environ.get("COMFYUI_PATH", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / "ComfyUI").resolve()


# ----- CLI plumbing --------------------------------------------------------- #


def require_python_311() -> None:
    if sys.version_info < (3, 11):
        err_exit(EXIT_MISSING, "Python 3.11+ required", found=sys.version)