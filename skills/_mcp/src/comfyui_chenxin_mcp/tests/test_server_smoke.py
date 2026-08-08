"""Full integration smoke test: spawn the real MCP server subprocess.

Verifies end-to-end:
- ``python -m comfyui_chenxin_mcp.server`` starts and speaks JSON-RPC over stdio
- initialize handshake completes and advertises the expected serverInfo
- tools/list discovers the 4 camera-image tools (entry-point discovery works)
- tools/call describe_camera_config returns a valid config descriptor
"""
import json
import subprocess
import sys

import pytest


SERVER_CMD = [sys.executable, "-m", "comfyui_chenxin_mcp.server"]


@pytest.fixture
def server_proc():
    proc = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _send(proc: subprocess.Popen, msg: dict) -> dict:
    """Send a JSON-RPC message and read one response line back."""
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        stderr = proc.stderr.read() if proc.stderr else ""
        pytest.fail(
            f"server closed stdout before responding to {msg.get('method')!r}"
            f"\nstderr:\n{stderr}"
        )
    return json.loads(line)


def _send_notification(proc: subprocess.Popen, msg: dict) -> None:
    """Send a JSON-RPC notification (no response expected)."""
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def test_server_handshake_lists_tools(server_proc):
    """initialize -> notifications/initialized -> tools/list -> 4 camera tools."""
    init = _send(server_proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05",
                   "capabilities": {},
                   "clientInfo": {"name": "test", "version": "0"}},
    })
    assert init["jsonrpc"] == "2.0"
    assert init["id"] == 1
    assert init["result"]["serverInfo"]["name"] == "comfyui-chenxin-mcp"
    assert init["result"]["protocolVersion"] == "2024-11-05"

    _send_notification(server_proc, {
        "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
    })

    lst = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    })
    names = [t["name"] for t in lst["result"]["tools"]]
    assert "describe_camera_config" in names
    assert "validate_camera_config" in names
    assert "run_t2i_camera" in names
    assert "run_i2i_camera" in names


def test_describe_camera_config_via_server(server_proc):
    """initialize -> tools/call describe_camera_config -> assert stage + slots."""
    _send(server_proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05",
                   "capabilities": {},
                   "clientInfo": {"name": "t", "version": "0"}},
    })
    _send_notification(server_proc, {
        "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
    })
    out = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "describe_camera_config",
                   "arguments": {"stage": "t2i-camera"}},
    })
    assert out["jsonrpc"] == "2.0"
    assert out["id"] == 2
    assert "error" not in out, f"tool call returned error: {out.get('error')}"
    text = json.loads(out["result"]["content"][0]["text"])
    assert text["stage"] == "t2i-camera"
    assert "sampling" in text["slots"]
