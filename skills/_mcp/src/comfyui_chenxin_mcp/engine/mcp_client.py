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
        """Spawn MCP stdio server, complete handshake, return client."""
        creationflags = 0
        use_shell = False
        # On Windows, subprocess.Popen with a list-form argv does NOT consult
        # PATHEXT/PATH to resolve commands like `npx` (no extension) or `.cmd`
        # shims. Without `shell=True` the kernel reports FileNotFoundError even
        # when `where npx` succeeds from the same shell. POSIX shells already
        # resolve via PATH, so we only flip the flag on Windows.
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW
            use_shell = True
        argv: list[str] | str
        if use_shell:
            argv = " ".join([command, *(str(a) for a in args)])
        else:
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
        # comfyui-mcp ≥ 0.50.0 deprecated check_workflow_runtime. The replacement
        # is list_packs (action:"check_runtime") which accepts either a pack name
        # or a graph. Best-effort: callers should treat None as "unknown".
        return self._call("list_packs", {"action": "check_runtime", "graph": graph})

    def enqueue(self, graph: dict) -> Any:
        # comfyui-mcp ≥ 0.50.0 requires an `action` discriminator on enqueue_workflow.
        # `action="enqueue"` is the new-headless-submit entry point; same workflow
        # shape (API-format dict) is forwarded under the `workflow` key.
        return self._call("enqueue_workflow", {"action": "enqueue", "workflow": graph})

    def get_history(self, prompt_id: str) -> dict:
        """Compatibility shim: delegates to ``get_history_raw``.

        Historical callers used the comfyui-mcp ``get_history`` tool, which
        returns a markdown-formatted summary string. Modern callers want the
        raw dict that ComfyUI itself returns. We expose both names so older
        test suites keep working while new code reaches for the raw form.
        """
        return self.get_history_raw(prompt_id)

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
            # Forward-compat: if the server ever returns a structured dict, use it as-is.
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

    def save_workflow(self, filename: str, workflow: dict) -> Any:
        """Upload a workflow JSON to the ComfyUI user library.

        Used by ``source_workflow.prepare_temporary_workflow`` to hand a
        UI workflow (with G1/G2 mode adjustments) to the ComfyUI server
        so ``strip_workflow`` can read it server-side.
        """
        # comfyui-mcp ≥ 0.49.0: save_workflow requires action="save" + filename +
        # workflow (Web UI format JSON preferred; API-format is auto-converted
        # server-side).
        return self._call("save_workflow", {
            "action": "save",
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
        # comfyui-mcp ≥ 0.49.0: get_workflow requires action="get" + filename +
        # optional format (api | ui | raw).
        return self._call("get_workflow", {
            "action": "get",
            "filename": filename, "format": format,
        })

    def health(self) -> Any:
        # comfyui-mcp ≥ 0.50.0 deprecated `health_check`. The replacement is
        # `get_system_stats (action:"health")` which still exposes a `queue`
        # field with `running`/`pending` arrays — same shape the engine reads.
        return self._call("get_system_stats", {"action": "health"})


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
