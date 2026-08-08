"""Thin wrapper around MCP tool calls for camera runs.

Two construction modes:
- McpClient(call_tool): wraps a host-injected MCP bridge (production use)
- McpClient.from_subprocess(command, args, timeout): spawns its own MCP
  stdio subprocess and performs the JSON-RPC handshake (standalone CLI /
  install-time smoke test).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, Callable, Optional


class McpClientError(RuntimeError):
    """Raised when MCP tool call or handshake fails."""


class McpClient:
    """Wraps MCP tool calls for camera operations."""

    def __init__(self, call_tool: Callable[..., Any]):
        self._call = call_tool
        self._proc: Optional[subprocess.Popen] = None

    @classmethod
    def from_subprocess(
        cls,
        command: str,
        args: list[str],
        timeout: float = 60.0,
    ) -> "McpClient":
        """Spawn MCP stdio server, complete handshake, return client."""
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.Popen(
                [command, *args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                bufsize=1,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise McpClientError(f"MCP command not found: {command}") from exc

        client = cls.__new__(cls)
        client._proc = proc
        client._call = None  # type: ignore[assignment]
        # Use a closure that holds the proc
        client._send_counter = 0
        client._timeout = timeout
        client._call = _make_stdio_caller(proc, timeout)
        return client

    def close(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
            self._proc = None

    def __enter__(self) -> "McpClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def list_loras(self) -> Any:
        return self._call("list_local_models", {"model_type": "loras"})

    def validate_workflow(self, graph: dict) -> Any:
        return self._call("validate_workflow", {"workflow": graph})

    def check_runtime(self, graph: dict) -> Any:
        return self._call("check_workflow_runtime", {"graph": graph})

    def enqueue(self, graph: dict) -> Any:
        return self._call("enqueue_workflow", {"workflow": graph})

    def get_history(self, prompt_id: str) -> Any:
        return self._call("get_history", {"prompt_id": prompt_id})

    def get_image(self, filename: str, subfolder: str = "", image_type: str = "output") -> Any:
        """Fetch image content from ComfyUI.

        Returns the raw MCP `tools/call` content list (NOT just the first
        text block). comfyui-mcp returns:
            [{"type": "text", "text": "Saved to: ..."},
             {"type": "image", "data": "<base64>", "mimeType": "image/png"}]
        Downstream consumers (e.g. t2i_camera._download_artifact) inspect
        the list for the image block and base64-decode `data`.
        """
        return self._call("get_image", {
            "filename": filename, "subfolder": subfolder, "type": image_type,
        })

    def upload_image(self, source_path: str) -> Any:
        return self._call("upload_image", {"source_path": source_path})

    def save_workflow(self, filename: str, workflow: dict) -> Any:
        """Upload a workflow JSON to the ComfyUI user library.

        Used by ``source_workflow.prepare_temporary_workflow`` to hand a
        UI workflow (with G1/G2 mode adjustments) to the ComfyUI server
        so ``strip_workflow`` can read it server-side.
        """
        return self._call("save_workflow", {
            "filename": filename,
            "workflow": workflow,
        })

    def get_workflow(self, filename: str, format: str = "api") -> Any:
        """Download a saved workflow from the ComfyUI user library.

        Used by ``source_workflow.prepare_temporary_workflow`` to retrieve
        the API-format JSON of a freshly uploaded temp workflow. Returns
        a dict (api format) when format="api", or a dict (ui format)
        when format="ui".
        """
        return self._call("get_workflow", {"filename": filename, "format": format})

    def health(self) -> Any:
        return self._call("health_check", {})


def _make_stdio_caller(proc: subprocess.Popen, timeout: float) -> Callable[..., Any]:
    """Build a call_tool closure for a stdio MCP subprocess."""
    # Tools whose MCP response includes image / audio / video blocks. For
    # these we return the full content list (with binary base64 blocks)
    # instead of extracting only the first text block. Match by exact
    # tools/call name (which mirrors McpClient method names).
    _MULTIMODAL_TOOLS = frozenset({"get_image"})
    """Build a call_tool closure for a stdio MCP subprocess."""
    next_id = [1]
    lock = __import__("threading").Lock()

    def _send(method: str, params: dict | None = None, *, is_notification: bool = False) -> int | None:
        msg: dict = {"jsonrpc": "2.0", "method": method}
        if is_notification:
            if params is not None:
                msg["params"] = params
        else:
            with lock:
                msg["id"] = next_id[0]
                next_id[0] += 1
            if params is not None:
                msg["params"] = params
        line = json.dumps(msg, ensure_ascii=False)
        proc.stdin.write(line + "\n")
        proc.stdin.flush()
        return msg.get("id")

    def _recv(expected_id: int, deadline: float) -> dict:
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    stderr = ""
                    try:
                        stderr = proc.stderr.read(4096) or ""
                    except Exception:
                        stderr = ""
                    raise McpClientError(f"MCP process exited (code={proc.returncode}) stderr={stderr[:500]}")
                continue
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == expected_id:
                return msg
        raise McpClientError(f"timed out waiting for MCP response id={expected_id}")

    def call_tool(name: str, arguments: dict) -> Any:
        deadline = time.monotonic() + timeout
        # Lazy init on first call
        if not getattr(call_tool, "_initialized", False):
            init_id = _send("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "character-video-pipeline", "version": "1.0"},
            })
            _recv(init_id, deadline)
            _send("notifications/initialized", is_notification=True)
            call_tool._initialized = True  # type: ignore[attr-defined]
        call_id = _send("tools/call", {"name": name, "arguments": arguments or {}})
        resp = _recv(call_id, deadline)
        if "error" in resp:
            err = resp["error"]
            raise McpClientError(f"tools/call {name} error: {err}")
        result = resp.get("result", {})
        # tools/call returns a content array. For most tools we extract the
        # first text block (and JSON-parse it when possible). For tools whose
        # payload includes an image/audio block (e.g. get_image) the consumer
        # needs the full list, so we skip text extraction on those names.
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            if isinstance(content, list) and content:
                if name in _MULTIMODAL_TOOLS:
                    return content
                first = content[0]
                if isinstance(first, dict) and "text" in first:
                    text = first["text"]
                    if isinstance(text, str):
                        stripped = text.strip()
                        if stripped.startswith("{") or stripped.startswith("["):
                            try:
                                return json.loads(text)
                            except json.JSONDecodeError:
                                pass
                    return text
        return result

    return call_tool
