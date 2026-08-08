"""MCP JSON-RPC framing + dispatch tests."""
import json, pytest
from comfyui_chenxin_mcp.protocol import Server, ProtocolError


@pytest.mark.asyncio
async def test_initialize_returns_server_info():
    s = Server(name="test", version="0.0.1")
    result = await s._handle_initialize({})
    assert result["protocolVersion"] == "2024-11-05"
    assert result["serverInfo"] == {"name": "test", "version": "0.0.1"}


@pytest.mark.asyncio
async def test_tools_list_empty():
    s = Server(name="t", version="0")
    out = await s._handle_tools_list({})
    assert out == {"tools": []}


@pytest.mark.asyncio
async def test_tool_decorator_registers():
    s = Server(name="t", version="0")

    @s.tool(name="hello", description="greet", input_schema={"type": "object"})
    async def hello(name: str = "world") -> dict:
        return {"greeting": f"hi {name}"}

    out = await s._handle_tools_list({})
    assert any(t["name"] == "hello" for t in out["tools"])


@pytest.mark.asyncio
async def test_tools_call_dispatches_to_handler():
    s = Server(name="t", version="0")

    @s.tool(name="echo", description="", input_schema={"type": "object"})
    async def echo(text: str) -> dict:
        return {"echo": text}

    out = await s._handle_tools_call({"name": "echo", "arguments": {"text": "hi"}})
    assert out == {"content": [{"type": "text", "text": json.dumps({"echo": "hi"}, ensure_ascii=False)}]}


@pytest.mark.asyncio
async def test_tools_call_returns_isError_on_handler_exception():
    s = Server(name="t", version="0")

    @s.tool(name="boom", description="", input_schema={"type": "object"})
    async def boom() -> dict:
        raise RuntimeError("kapow")

    out = await s._handle_tools_call({"name": "boom", "arguments": {}})
    assert out["isError"] is True
    assert "kapow" in out["content"][0]["text"]


@pytest.mark.asyncio
async def test_unknown_tool_raises():
    s = Server(name="t", version="0")
    with pytest.raises(ProtocolError):
        await s._handle_tools_call({"name": "nope", "arguments": {}})


@pytest.mark.asyncio
async def test_unknown_method_raises():
    s = Server(name="t", version="0")
    with pytest.raises(ProtocolError):
        await s._dispatch({"method": "nope", "params": {}})


@pytest.mark.asyncio
async def test_non_dict_json_returns_32600_error():
    """Non-dict JSON (e.g. 42) returns -32600 instead of crashing with AttributeError."""
    from unittest.mock import patch, MagicMock

    s = Server(name="t", version="0")

    lines = iter(["42\n", ""])
    fake_stdin = MagicMock()
    fake_stdin.readline = MagicMock(side_effect=lambda: next(lines))
    fake_stdout = MagicMock()

    with patch("sys.stdin", fake_stdin), patch("sys.stdout", fake_stdout):
        await s.serve_stdio()

    written = "".join(call.args[0] for call in fake_stdout.write.call_args_list)
    assert "-32600" in written
    assert "expected JSON object" in written
