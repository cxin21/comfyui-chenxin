"""verify_mcp.py — spawn the comfyui-mcp server and verify the tool contract.

Performs a real MCP stdio handshake (initialize -> notifications/initialized ->
tools/list) against whatever command the installer registered, then checks that
the tools required by skills/character-video-pipeline are present:

    get_workflow, strip_workflow, validate_workflow,
    check_workflow_runtime, list_local_models

Prints one JSON summary and exits 0 (all required tools present) or 1 (missing),
2 (server did not answer the handshake in time / crashed).

Server args are passed as a JSON array on stdin (NOT argv). This sidesteps
PowerShell's argument-parsing quirks when relaunching via `& { ... }`.

Usage:
    python scripts/verify_mcp.py --command npx --timeout 180
    echo '["-y","comfyui-mcp@0.41.0","--full","--comfyui-url","http://127.0.0.1:8188"]' \
        | python scripts/verify_mcp.py --command npx
"""

import argparse
import collections
import json
import subprocess
import sys
import threading

DEFAULT_REQUIRED = [
    "get_workflow",
    "strip_workflow",
    "validate_workflow",
    "check_workflow_runtime",
    "list_local_models",
]


def emit(payload, code):
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(code)


def read_args_from_stdin():
    try:
        raw = sys.stdin.read()
    except OSError as exc:
        emit({"ok": False, "reason": "stdin_read_failed", "detail": str(exc)}, 2)
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        emit({"ok": False, "reason": "bad_stdin_json", "detail": str(exc)}, 2)
    if not isinstance(loaded, list) or not all(isinstance(x, str) for x in loaded):
        emit({"ok": False, "reason": "stdin_must_be_string_array"}, 2)
    return loaded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--required", default=json.dumps(DEFAULT_REQUIRED))
    opts = parser.parse_args()

    try:
        required = json.loads(opts.required)
    except json.JSONDecodeError as exc:
        emit({"ok": False, "reason": "bad_required", "detail": str(exc)}, 2)

    server_args = read_args_from_stdin()

    try:
        proc = subprocess.Popen(
            [opts.command] + list(server_args),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        emit({"ok": False, "reason": "spawn_failed", "detail": str(exc),
              "command": opts.command}, 2)

    responses = {}
    stderr_tail = collections.deque(maxlen=30)
    got_tools = threading.Event()
    got_init = threading.Event()

    def read_stdout():
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg_id = msg.get("id")
            if msg_id is not None:
                responses[msg_id] = msg
                if msg_id == 1:
                    got_init.set()
                elif msg_id == 2:
                    got_tools.set()

    def read_stderr():
        for line in proc.stderr:
            stderr_tail.append(line.rstrip())

    threading.Thread(target=read_stdout, daemon=True).start()
    threading.Thread(target=read_stderr, daemon=True).start()

    def send(obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    send({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "comfyui-chenxin-setup", "version": "1.0"},
        },
    })

    if not got_init.wait(opts.timeout):
        proc.kill()
        emit({"ok": False, "reason": "initialize_timeout",
              "stderr_tail": list(stderr_tail)}, 2)

    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

    if not got_tools.wait(opts.timeout):
        proc.kill()
        emit({"ok": False, "reason": "tools_list_timeout",
              "stderr_tail": list(stderr_tail)}, 2)

    try:
        proc.terminate()
    except OSError:
        pass

    tools_payload = responses.get(2, {}).get("result", {}).get("tools", [])
    tool_names = sorted({t.get("name") for t in tools_payload if isinstance(t, dict)})
    missing = [name for name in required if name not in tool_names]
    queue_like = [name for name in tool_names if "queue" in name or "submit" in name]

    emit({
        "ok": not missing,
        "reason": "ok" if not missing else "missing_required_tools",
        "server_tool_count": len(tool_names),
        "required": required,
        "missing": missing,
        "queue_like_tools": queue_like,
    }, 0 if not missing else 1)


if __name__ == "__main__":
    main()
