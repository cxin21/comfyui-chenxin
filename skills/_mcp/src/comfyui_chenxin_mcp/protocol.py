"""JSON-RPC 2.0 + MCP 2024-11-05 framing over stdio.

Minimal stdlib-only implementation. Two responsibilities:
- parse newline-delimited JSON requests from stdin
- dispatch to a tool handler by name; capture return value or exception
- emit newline-delimited JSON responses (or notifications) to stdout

MCP protocol messages used:
- request:  {"jsonrpc": "2.0", "id": N, "method": "...", "params": {...}}
- response: {"jsonrpc": "2.0", "id": N, "result": ...} | {"error": {"code":..., "message":...}}
- notification: {"jsonrpc": "2.0", "method": "...", "params": {...}}  (no id)

MCP methods handled:
- initialize (returns serverInfo)
- notifications/initialized (no-op)
- tools/list (returns tool descriptors)
- tools/call (dispatches to handler)
- ping (returns {})
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Awaitable, Callable


class ProtocolError(Exception):
    """Raised when a JSON-RPC or MCP request is malformed."""


class Server:
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self._tools: dict[str, dict[str, Any]] = {}
        self._initialized = False

    def tool(self, *, name: str, description: str, input_schema: dict[str, Any]):
        """Decorator registering an async tool handler."""
        def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            self._tools[name] = {
                "description": description,
                "input_schema": input_schema,
                "handler": fn,
            }
            return fn
        return deco

    async def _handle_initialize(self, params: dict) -> dict:
        self._initialized = True
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": self.name, "version": self.version},
        }

    async def _handle_tools_list(self, params: dict) -> dict:
        return {
            "tools": [
                {
                    "name": n,
                    "description": meta["description"],
                    "inputSchema": meta["input_schema"],
                }
                for n, meta in sorted(self._tools.items())
            ]
        }

    async def _handle_tools_call(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments", {}) or {}
        meta = self._tools.get(name)
        if not meta:
            raise ProtocolError(f"unknown tool: {name!r}")
        try:
            result = await meta["handler"](**arguments)
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": f"error: {exc!r}"}],
                "isError": True,
            }
        return {
            "content": [
                {"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}
            ]
        }

    async def _dispatch(self, msg: dict) -> dict | None:
        method = msg.get("method")
        params = msg.get("params", {})
        if method == "initialize":
            return await self._handle_initialize(params)
        if method == "tools/list":
            return await self._handle_tools_list(params)
        if method == "tools/call":
            return await self._handle_tools_call(params)
        if method == "ping":
            return {}
        if method == "notifications/initialized":
            return None
        raise ProtocolError(f"unknown method: {method!r}")

    async def serve_stdio(self) -> None:
        """Drive the server over stdin/stdout until EOF or fatal error.

        Reads newline-delimited JSON requests via a thread-pool blocking
        ``sys.stdin.readline`` (``loop.run_in_executor``), dispatches through
        ``self._dispatch``, and writes JSON-RPC responses via synchronous
        ``sys.stdout`` writes.

        Thread-pool reads + synchronous writes are used instead of
        ``connect_read_pipe`` / ``connect_write_pipe`` because on Windows
        (ProactorEventLoop) both pipe transports fail when stdin/stdout are
        subprocess pipes (``WinError 6``, or indefinite hang). This approach
        is cross-platform safe and works for the MCP stdio protocol which is
        strictly request-response (no concurrent I/O contention).
        """
        loop = asyncio.get_running_loop()

        def _emit(data: dict) -> None:
            """Write one JSON-RPC message line to stdout."""
            sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
            sys.stdout.flush()

        while True:
            # Read in a thread to avoid blocking the event loop; this also
            # sidesteps Windows ProactorEventLoop pipe-transport bugs.
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break  # stdin EOF
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as exc:
                _emit({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"parse error: {exc}"},
                })
                continue
            msg_id = msg.get("id")
            is_notif = msg_id is None
            try:
                result = await self._dispatch(msg)
            except ProtocolError as exc:
                if not is_notif:
                    _emit({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32600, "message": str(exc)},
                    })
                continue
            except Exception as exc:
                if not is_notif:
                    _emit({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32603, "message": f"internal error: {exc!r}"},
                    })
                continue
            if not is_notif and result is not None:
                _emit({"jsonrpc": "2.0", "id": msg_id, "result": result})