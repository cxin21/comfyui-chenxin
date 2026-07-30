#!/usr/bin/env python3
"""auto_launch — detect ComfyUI down, start it, wait for readiness.

Stdlib only. Returns JSON on stdout.

Usage:
    python auto_launch.py [--port 8188] [--timeout 60] [--host 127.0.0.1]

Output JSON:
    {
      "started": bool,          # True if we (re)launched the process
      "port": 8188,
      "uptime_s": int,          # 0 if not started by us
      "system_stats": {...},    # raw /system_stats payload (empty if not ready)
      "elapsed_s": float        # total wall time spent
    }
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from _shared import (
    EXIT_OK,
    EXIT_TIMEOUT,
    emit_human,
    emit_json,
    err_exit,
    http_get_json,
    http_get_status,
    require_python_311,
    wait_for_http,
    wait_for_port,
)


def _stats_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/system_stats"


def _is_alive(host: str, port: int) -> bool:
    """Return True if ComfyUI responds 200 on /system_stats."""
    return http_get_status(_stats_url(host, port), timeout=1.5) == 200


def _port_in_use(port: int) -> bool:
    """Return True if something is bound to 127.0.0.1:port (refused counts as free)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _launch_subprocess(port: int) -> subprocess.Popen:
    """Spawn `python -m comfyui.cmd.main --listen 127.0.0.1 --port <port> --gpu-only`.

    Detached: we deliberately do NOT wait for it; readiness is polled via HTTP.
    """
    cmd = [
        sys.executable,
        "-m",
        "comfyui.cmd.main",
        "--listen",
        "127.0.0.1",
        "--port",
        str(port),
        "--gpu-only",
    ]
    # On Windows, CREATE_NEW_PROCESS_GROUP lets the child survive our exit
    # if the parent script is killed early. On POSIX, start_new_session does
    # the equivalent.
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


def main(argv: list[str] | None = None) -> int:
    require_python_311()
    parser = argparse.ArgumentParser(
        prog="auto_launch",
        description="Detect ComfyUI down on :port; if so, launch it and wait for readiness.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="ComfyUI host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8188, help="ComfyUI port (default 8188)")
    parser.add_argument("--timeout", type=float, default=60.0, help="Readiness timeout in seconds")
    parser.add_argument(
        "--poll",
        type=float,
        default=1.0,
        help="Polling interval in seconds",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Do NOT launch ComfyUI; only probe readiness (useful for health checks)",
    )
    args = parser.parse_args(argv)

    url = _stats_url(args.host, args.port)
    started_at = time.monotonic()

    # 1. Already up?
    if _is_alive(args.host, args.port):
        emit_human(f"ComfyUI already up at {url}")
        _, stats = http_get_json(url, timeout=2.0)
        emit_json(
            {
                "started": False,
                "port": args.port,
                "uptime_s": 0,
                "system_stats": stats,
                "elapsed_s": round(time.monotonic() - started_at, 2),
            }
        )
        return EXIT_OK

    if args.no_launch:
        emit_human("ComfyUI down and --no-launch set; nothing to do")
        emit_json(
            {
                "started": False,
                "port": args.port,
                "uptime_s": 0,
                "system_stats": {},
                "elapsed_s": round(time.monotonic() - started_at, 2),
                "note": "down, no-launch",
            }
        )
        return EXIT_OK

    # 2. Down. Should we launch?
    emit_human(f"ComfyUI down at {url}; launching")

    # If the port is occupied by something that is NOT ComfyUI, bail early
    # rather than spawning a second instance that would collide on bind.
    if _port_in_use(args.port):
        emit_human(f"port {args.port} is occupied by something other than ComfyUI")
        emit_json(
            {
                "started": False,
                "port": args.port,
                "uptime_s": 0,
                "system_stats": {},
                "elapsed_s": round(time.monotonic() - started_at, 2),
                "error": "port_in_use",
            }
        )
        return EXIT_TIMEOUT

    _launch_subprocess(args.port)

    # 3. Wait for port (cheap) then for /system_stats 200 (definitive).
    if not wait_for_port(args.host, args.port, timeout_s=args.timeout, poll_s=args.poll):
        emit_human(f"timed out waiting for {args.host}:{args.port} to bind")
        emit_json(
            {
                "started": True,
                "port": args.port,
                "uptime_s": 0,
                "system_stats": {},
                "elapsed_s": round(time.monotonic() - started_at, 2),
                "error": "port_bind_timeout",
            }
        )
        return EXIT_TIMEOUT

    if not wait_for_http(url, timeout_s=args.timeout, poll_s=args.poll):
        emit_human(f"timed out waiting for {url} to return 200")
        emit_json(
            {
                "started": True,
                "port": args.port,
                "uptime_s": 0,
                "system_stats": {},
                "elapsed_s": round(time.monotonic() - started_at, 2),
                "error": "http_ready_timeout",
            }
        )
        return EXIT_TIMEOUT

    elapsed = time.monotonic() - started_at
    _, stats = http_get_json(url, timeout=2.0)
    emit_human(f"ComfyUI ready in {elapsed:.1f}s")
    emit_json(
        {
            "started": True,
            "port": args.port,
            "uptime_s": int(elapsed),
            "system_stats": stats,
            "elapsed_s": round(elapsed, 2),
        }
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())