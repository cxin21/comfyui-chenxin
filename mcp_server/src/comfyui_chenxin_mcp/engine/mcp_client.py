"""Thin wrapper around MCP tool calls for camera runs.

Two construction modes:
- McpClient(call_tool): wraps a host-injected MCP bridge (production use)
- McpClient.from_subprocess(command, args, timeout, comfyui_url): spawns its
  own MCP stdio subprocess and performs the JSON-RPC handshake (standalone
  CLI / install-time smoke test). `comfyui_url` is stored so we can hit
  ComfyUI's HTTP API directly when the MCP wrapper would otherwise add a
  markdown layer (e.g. ``get_history``).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Optional


class McpClientError(RuntimeError):
    """Raised when MCP tool call or handshake fails."""


class McpClient:
    """Wraps MCP tool calls for camera operations."""

    def __init__(
        self,
        call_tool: Callable[..., Any],
        comfyui_url: str = "http://127.0.0.1:8188",
    ):
        self._call = call_tool
        self._proc: Optional[subprocess.Popen] = None
        self._comfyui_url = comfyui_url.rstrip("/")

    @classmethod
    def from_subprocess(
        cls,
        command: str,
        args: list[str],
        timeout: float = 60.0,
        comfyui_url: str = "http://127.0.0.1:8188",
    ) -> "McpClient":
        """Spawn MCP stdio server, complete handshake, return client.

        On Windows, ``shell=True`` is needed to resolve ``npx.cmd`` /
        ``npx`` shims via PATHEXT, but it strips quoting around the
        command path. A command path with spaces (e.g.
        ``C:\\Program Files\\nodejs\\npx.cmd``) then gets truncated at
        the first space and cmd.exe reports "not recognized as a
        command". We side-step this by:

          - resolving the command via ``shutil.which`` first (so we have
            the full path, no shell needed for PATH lookup), and
          - passing argv as a list (Windows kernel quotes each arg
            properly), keeping ``shell=False``.

        The only remaining reason to use ``shell=True`` is when the user
        passes a shell metachar-prefixed command (e.g. ``"npm exec..."``)
        that genuinely needs shell parsing — not our case.
        """
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        use_shell = False
        resolved = shutil.which(command) if os.name == "nt" else command
        argv: list[str]
        if resolved is not None:
            argv = [resolved, *args]
        else:
            # Fall back to letting the OS resolve (PATH lookup via list argv).
            argv = [command, *args]
        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                shell=use_shell,
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
        client._comfyui_url = comfyui_url.rstrip("/")
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
        # comfyui-mcp ≥ 0.49.0 folded list_local_models into an action-parameterized
        # tool. `action="list"` with an optional `model_type` filter is the live API.
        return self._call("list_local_models", {"action": "list", "model_type": "loras"})

    def check_runtime(self, graph: dict) -> Any:
        """Check that every node in the graph is available in the local runtime."""
        raw = self._call("check_workflow_runtime", {"graph": graph})
        result = _extract_json_object(raw)
        if not isinstance(result, dict):
            raise McpClientError("check_workflow_runtime did not return a structured result")
        return result

    def enqueue(self, graph: dict) -> Any:
        """Submit one validated API graph to ComfyUI."""
        return self._call("enqueue_workflow", {"workflow": graph})

    def get_history_raw(self, prompt_id: str) -> dict:
        """Fetch raw history from ComfyUI's HTTP API.

        Bypasses comfyui-mcp's ``get_history`` tool, which wraps the response
        in a markdown summary string. ComfyUI's ``GET /history/<prompt_id>``
        endpoint returns the same JSON the engine wants to parse — keyed by
        ``prompt_id``, with ``status.status_str`` and ``outputs``.
        """
        url = f"{self._comfyui_url}/history/{prompt_id}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Prompt not yet committed to history — return empty so
                # the polling loop in ``_wait_for_completion`` keeps waiting.
                return {}
            raise

    def get_image(self, filename: str, subfolder: str = "", image_type: str = "output") -> Any:
        """Fetch image content from ComfyUI.

        Returns the raw MCP `tools/call` content list (NOT just the first
        text block). comfyui-mcp returns:
            [{"type": "text", "text": "Saved to: ..."},
             {"type": "image", "data": "<base64>", "mimeType": "image/png"}]
        Downstream consumers (e.g. t2i_camera._download_artifact) inspect
        the list for the image block and base64-decode `data`.
        """
        # comfyui-mcp ≥ 0.49.0: get_image requires action="get" + filename +
        # optional subfolder/type.
        return self._call("get_image", {
            "action": "get",
            "filename": filename, "subfolder": subfolder, "type": image_type,
        })

    def upload_image(self, source_path: str) -> Any:
        """Upload a local file to ComfyUI's input/ directory.

        comfyui-mcp ≥ 0.49.0 returns the result as a text block of the shape
        ``"Uploaded via HTTP.\\n\\nFilename: <filename>\\n\\nUse \\"<filename>\\" ..."``.
        The engine's stage-image step consumes ``{"name": ..., "subfolder": ...}``,
        so we parse the filename out of the text and return that dict directly.
        Empty/non-text responses fall through as ``{"name": None}`` so the
        caller can raise a structured error.
        """
        raw = self._call("upload_image", {
            "action": "image",
            "source_path": source_path,
        })
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            filename: str | None = None
            for line in raw.splitlines():
                stripped = line.strip()
                if stripped.startswith("Filename:"):
                    filename = stripped.split(":", 1)[1].strip()
                    break
            return {"name": filename, "subfolder": ""}
        return {"name": None}

    def health(self) -> Any:
        # Returns {"queue": {"running": [...], "pending": [...]}} via the
        # upstream server's get_system_stats tool (action="health").
        return self._call("get_system_stats", {"action": "health"})

    def strip_workflow(self, graph: dict) -> dict:
        """Convert the pinned UI workflow graph to ComfyUI API format."""
        raw = self._call("strip_workflow", {"graph": graph, "format": "api"})
        result = _extract_json_object(raw)
        if not isinstance(result, dict) or not result:
            raise McpClientError("strip_workflow did not return an API graph")
        return result

    def validate_workflow(self, graph: dict) -> dict:
        """Validate an API graph and return a normalized result."""
        raw = self._call("validate_workflow", {"workflow": graph})
        if isinstance(raw, dict) and "valid" in raw:
            return raw
        text = _extract_text(raw)
        valid = "## Workflow is valid" in text and "## Workflow has" not in text
        return {"valid": valid, "errors": [] if valid else [text], "raw": text}


def _make_stdio_caller(proc: subprocess.Popen, timeout: float) -> Callable[..., Any]:
    """Build a call_tool closure for a stdio MCP subprocess."""
    # Tools whose MCP response includes image / audio / video blocks. For
    # these we return the full content list (with binary base64 blocks)
    # instead of extracting only the first text block. Match by exact
    # tools/call name (which mirrors McpClient method names).
    _RAW_CONTENT_TOOLS = frozenset({
        "get_image", "strip_workflow", "validate_workflow", "check_workflow_runtime",
    })
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
                "clientInfo": {"name": "camera-image", "version": "1.0"},
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
                if name in _RAW_CONTENT_TOOLS:
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


def _extract_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "\n".join(
            item.get("text", "") for item in raw
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    if isinstance(raw, dict):
        if isinstance(raw.get("text"), str):
            return raw["text"]
        if isinstance(raw.get("content"), list):
            return _extract_text(raw["content"])
    return ""


def _extract_json_object(raw: Any) -> Any:
    if isinstance(raw, dict):
        if isinstance(raw.get("content"), list):
            return _extract_json_object(raw["content"])
        if "runtime" in raw or "valid" in raw:
            return raw
        if raw and all(isinstance(value, dict) for value in raw.values()):
            return raw
    if isinstance(raw, list):
        for item in reversed(raw):
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                try:
                    parsed = json.loads(item["text"])
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None
