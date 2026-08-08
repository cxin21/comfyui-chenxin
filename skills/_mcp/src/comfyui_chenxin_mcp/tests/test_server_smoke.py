"""Server smoke test - spawn real server, verify 4 unified tools."""
import json
import subprocess
import sys
import pytest


@pytest.fixture
def server_proc():
    proc = subprocess.Popen(
        [sys.executable, "-m", "comfyui_chenxin_mcp.server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _send(proc, msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        stderr = proc.stderr.read()
        pytest.fail(f"server stdout closed. stderr: {stderr[:500]}")
    return json.loads(line)


def _initialize(proc):
    _send(proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05",
                   "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
    })
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
    }) + "\n")
    proc.stdin.flush()


def test_server_handshake_lists_unified_tools(server_proc):
    _initialize(server_proc)
    lst = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    })
    names = [t["name"] for t in lst["result"]["tools"]]
    assert "list_skills" in names
    assert "describe_config" in names
    assert "validate_config" in names
    assert "run_skill" in names
    assert "describe_camera_config" not in names
    assert "run_t2i_camera" not in names


def test_list_skills_returns_camera_image(server_proc):
    _initialize(server_proc)
    out = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "list_skills", "arguments": {}},
    })
    text = json.loads(out["result"]["content"][0]["text"])
    assert any(s["name"] == "camera-image" for s in text["skills"])


def test_describe_config_returns_schema(server_proc):
    _initialize(server_proc)
    out = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "describe_config",
                   "arguments": {"skill": "camera-image", "stage": "t2i-camera"}},
    })
    text = json.loads(out["result"]["content"][0]["text"])
    assert text["stage"] == "t2i-camera"
    assert "sampling" in text["slots"]


def test_validate_config_returns_ok(server_proc):
    _initialize(server_proc)
    out = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "validate_config",
                   "arguments": {"skill": "camera-image", "stage": "t2i-camera",
                                 "config": {"draft": {"positive": "1girl", "negative": "lowres"}}}},
    })
    text = json.loads(out["result"]["content"][0]["text"])
    assert text["ok"] is True
