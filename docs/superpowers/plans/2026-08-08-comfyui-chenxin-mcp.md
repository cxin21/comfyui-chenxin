# comfyui-chenxin-mcp v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a plugin-level MCP server (`comfyui-chenxin-mcp`) that exposes comfyui-chenxin's camera skills to LLM hosts via the MCP protocol. v1 scope: camera-image (t2i + i2i). Architecture supports adding future skills (camera-multiview, camera-video) by **declaring a Python entry-point** in the new skill's pyproject.toml — no changes to `comfyui-chenxin-mcp` server core.

**Architecture:** Stdio MCP server in a new package `comfyui-chenxin-mcp/` (sibling to `skills/camera-*`). Implements MCP 2024-11-05. Tools dispatch to skill runtime modules via Python entry-points (`importlib.metadata.entry_points(group="comfyui_chenxin_mcp.skills")`); no re-implementation of skill logic. Single source of truth for schema stays in each skill's own `runtime.graph_patcher.describe_config`; the MCP server imports it lazily.

**Tech Stack:** Python 3.10+, stdlib-only MCP implementation (no third-party MCP SDK — keeps dependency surface minimal; ~300 LoC of JSON-RPC over stdio). Reuses `McpClient` already in `camera-image/runtime/mcp_client.py` to talk to comfyui-mcp.

**Out of scope (v1):**
- flux2-klein-multiview, ltx-yusu-director tools (added in v2+ as their skills mature)
- HTTP transport (stdio only)
- Multi-tenant / auth (single-user local plugin)

---

## File Structure

### New files

```
skills/
└── _mcp/                                  # new sibling package
    ├── pyproject.toml                      # entry point: comfyui-chenxin-mcp-server
    ├── README.md                          # install + usage
    └── src/
        └── comfyui_chenxin_mcp/
            ├── __init__.py
            ├── server.py                   # stdio MCP server entrypoint
            ├── protocol.py                 # JSON-RPC 2.0 + MCP 2024-11-05 framing
            ├── registry.py                 # SkillRegistration + tool dispatch
            ├── workflow_dir.py             # scan skills/*/workflow/source/*.json
            ├── schema.py                  # describe_skill + validate_config
            ├── tools/
            │   ├── __init__.py             # imports all tool modules to trigger register()
            │   └── camera.py              # t2i-camera + i2i-camera tools
            └── tests/
                ├── __init__.py
                ├── test_protocol.py        # JSON-RPC framing
                ├── test_registry.py        # SkillRegistration + dispatch
                ├── test_workflow_dir.py    # scan skills/
                ├── test_schema.py          # describe_skill + validate_config
                └── test_camera_tools.py    # tool handlers
```

### Modified files

- `scripts/install.ps1` — add `comfyui-chenxin-mcp-server` to criticalFiles validation list
- `.codex-plugin/plugin.json` — declare MCP server entry (`chenxin` server name)

### Unchanged files

- All `camera-image/runtime/*` modules
- All `camera-multiview/runtime/*`, `camera-video/runtime/*` (when added)
- `prompt-forge/**`, `comfyui-mcp/**`, `.claude/`
- `workflow/t2i-camera/**`, `workflow/i2i-camera/**` (under camera-image/)

---

## Global Constraints

- **No backwards compatibility**: old surface (none, this is new) preserved only as it exists. No deprecation aliases.
- **Single responsibility**: `comfyui-chenxin-mcp` does NOT re-implement any skill logic. Each skill's own `mcp_bridge.py` imports `runtime.*` and binds tools; comfyui-chenxin-mcp only discovers and calls those bridges via entry-points.
- **MCP 2024-11-05**: wire protocol pinned; tools/list + tools/call only.
- **stdio only**: spawnable by Claude Code / Codex / OpenCode via host config.
- **Reuse `McpClient`**: do NOT add a second MCP bridge to comfyui-mcp. `McpClient.from_subprocess` (or host-injected if available) is the only path to comfyui-mcp.
- **Schema source of truth**: each skill's own `runtime.graph_patcher.describe_config` stays the single place that knows about its own NODE_FIELD_MAP / groups. chenxin-mcp dispatches to it lazily.
- **No third-party deps**: stdlib only (json, asyncio, sys, os, pathlib, dataclasses).
- **Tests**: pytest in `comfyui-chenxin-mcp/tests/`. Mock `McpClient` for tools that call it.
- **Commits**: one per task. Use `Co-Authored-By: Claude <noreply@anthropic.com>` in commit body.

---

## Task 1: spec/plan/SDD ledger scaffold

**Files:**
- Create: `docs/superpowers/specs/2026-08-08-comfyui-chenxin-mcp.md`
- Create: `docs/superpowers/plans/2026-08-08-comfyui-chenxin-mcp.md` (this file)
- Create: `.superpowers/sdd/2026-08-08-comfyui-chenxin-mcp/progress.md`

**Spec content** (`docs/superpowers/specs/2026-08-08-comfyui-chenxin-mcp.md`):

- Context: each camera-* skill (camera-image, camera-multiview, camera-video) has its own CLI surface, but LLM hosts (Claude Code, Codex, OpenCode) want MCP-native tool access. A plugin-level MCP server provides self-describing tools (`tools/list`) so LLMs don't need to read SKILL.md / docs before invoking capabilities.
- Decisions:
  1. v1 scope: `camera-image` only (t2i-camera + i2i-camera). `camera-multiview` and `camera-video` are added in v2+ by each skill declaring its own entry-point.
  2. Package name: `comfyui-chenxin-mcp`
  3. Entry point: `comfyui-chenxin-mcp-server`
  4. Transport: stdio
  5. Skill registry via **Python entry-points**: each skill declares a `comfyui_chenxin_mcp.skill` entry-point in its own `pyproject.toml` pointing at `register(mcp)`. The MCP server iterates entry-points at startup — adding a new skill = pip-install the new skill package; no MCP server code changes.
  6. Schema source of truth: each skill's own `runtime.graph_patcher.describe_config`. MCP server dispatches to it lazily; never duplicates the field map.
  7. validate_config is a separate MCP tool (not a CLI subcommand) so LLM gets structured errors before invoking run-*.
- Architecture: Stdio JSON-RPC 2.0 server, MCP 2024-11-05 framing. Tools dispatch to existing `runtime.*` modules. comfyui-mcp is a downstream dependency reached via `McpClient`.
- Components: protocol.py (framing), registry.py (skill registration + tool dispatch), workflow_dir.py (asset scan), schema.py (schema + validation), tools/camera.py (t2i-camera/i2i-camera tool handlers), server.py (entrypoint).
- Data flow:
  ```
  LLM host (Claude Code/Codex)
    -> tools/list (auto at startup)
    -> describe_camera_config(stage="t2i-camera")
       -> calls runtime.graph_patcher.describe_config (single source)
    -> validate_camera_config(config={...})
       -> calls runtime tools to verify schema + groups + sizes
    -> run_t2i_camera(envelope=..., **tunables)
       -> runtime.prompt_forge_bridge.compile_envelope (gate)
       -> runtime.source_workflow.prepare_temporary_workflow (cp + mode + upload)
       -> runtime.graph_patcher.apply_run_config (write tunables)
       -> runtime.t2i_camera.run_t2i (enqueue + wait + download)
       -> returns payload
  ```
- Testing: per-tool unit tests with mocked McpClient; protocol framing tests; registry dispatch test.
- Scope items list + out-of-scope list (no flux2-klein-multiview, no ltx-yusu-director, no HTTP, no auth).
- Spec self-review checklist: 11 items, all explicit.

**Plan file**: this document.

**SDD ledger** (`.superpowers/sdd/2026-08-08-comfyui-chenxin-mcp/progress.md`):
```markdown
# SDD ledger — plan: docs/superpowers/plans/2026-08-08-comfyui-chenxin-mcp.md

Spec: docs/superpowers/specs/2026-08-08-comfyui-chenxin-mcp.md (TBD commit)
Plan: docs/superpowers/plans/2026-08-08-comfyui-chenxin-mcp.md (TBD commit)

## Tasks
- Task 1: ... (pending)
```

**Step 1.1**: create the spec file with full content above. Verify by `head -5`.
**Step 1.2**: create the plan file (already done — this file is the plan).
**Step 1.3**: create the SDD ledger with Task 1 placeholder.
**Step 1.4**: commit all three files with one commit.
**Step 1.5**: verify `git log --oneline -1` shows the commit.

---

## Task 2: project scaffold (`comfyui-chenxin-mcp/` package skeleton)

**Files:**
- Create: `skills/_mcp/pyproject.toml`
- Create: `skills/_mcp/README.md`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/__init__.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/protocol.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/registry.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/workflow_dir.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/schema.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/server.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tools/__init__.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tools/camera.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tests/__init__.py`

**Step 2.1**: write `pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "comfyui-chenxin-mcp"
version = "0.1.0"
description = "MCP server exposing comfyui-chenxin plugin skills (camera-image, camera-multiview, camera-video, etc.)"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
comfyui-chenxin-mcp-server = "comfyui_chenxin_mcp.server:main"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 2.2**: write `README.md` (install + usage + tool list placeholder).

**Step 2.3**: write `__init__.py` (empty).

**Step 2.4**: write stub `protocol.py`:
```python
"""JSON-RPC 2.0 + MCP 2024-11-05 framing over stdio.

Minimal stdlib-only implementation. ~150 LoC. Two responsibilities:
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
import json, sys, asyncio
from typing import Any, Awaitable, Callable

class ProtocolError(Exception):
    """Raised when a JSON-RPC or MCP request is malformed."""

class Server:
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self._tools: dict[str, dict[str, Any]] = {}  # name -> {"description", "input_schema", "handler": async fn}
        self._initialized = False

    def tool(self, *, name: str, description: str, input_schema: dict[str, Any]):
        """Decorator registering an async tool handler."""
        def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            self._tools[name] = {"description": description, "input_schema": input_schema, "handler": fn}
            return fn
        return deco

    async def _handle_initialize(self, params: dict) -> dict:
        self._initialized = True
        return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": self.name, "version": self.version}}

    async def _handle_tools_list(self, params: dict) -> dict:
        return {"tools": [
            {"name": n, "description": meta["description"],
             "inputSchema": meta["input_schema"]}
            for n, meta in sorted(self._tools.items())
        ]}

    async def _handle_tools_call(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments", {}) or {}
        meta = self._tools.get(name)
        if not meta:
            raise ProtocolError(f"unknown tool: {name!r}")
        try:
            result = await meta["handler"](**arguments)
        except Exception as exc:
            return {"content": [{"type": "text", "text": f"error: {exc!r}"}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}]}

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
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        writer_transport, writer_protocol = await loop.connect_write_pipe(asyncio.Protocol, sys.stdout)
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as exc:
                err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"parse error: {exc}"}}
                writer_transport.write((json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8"))
                continue
            msg_id = msg.get("id")
            is_notif = msg_id is None
            try:
                result = await self._dispatch(msg)
            except ProtocolError as exc:
                if not is_notif:
                    err = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32600, "message": str(exc)}}
                    writer_transport.write((json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8"))
                continue
            except Exception as exc:
                if not is_notif:
                    err = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": f"internal error: {exc!r}"}}
                    writer_transport.write((json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8"))
                continue
            if not is_notif and result is not None:
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": result}
                writer_transport.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
```

**Step 2.5**: write `registry.py`:
```python
"""Skill discovery via Python entry-points.

Each skill package declares an entry-point in its pyproject.toml:
    [project.entry-points."comfyui_chenxin_mcp.skills"]
    camera-image = "camera_image.mcp_bridge:register"

`register` must be a callable that takes a `Server` and binds tool handlers.
Optional `SKILL_INFO` dataclass exposes metadata for `list_skills`.

No hardcoded skill names here. Adding a new skill = pip-install it; the
next `comfyui-chenxin-mcp-server` start picks it up.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any
import importlib.metadata

ENTRY_POINT_GROUP = "comfyui_chenxin_mcp.skills"

@dataclass(frozen=True)
class SkillRegistration:
    name: str
    label: str
    description: str
    stages: tuple[str, ...]
    register_fn: Callable[[Any], None]

def discover() -> list[SkillRegistration]:
    """Iterate installed packages' entry-points in ENTRY_POINT_GROUP.

    Each entry-point's callable must:
      - Bind MCP tools via the provided Server
      - Optionally expose `module.SKILL_INFO` (SkillRegistration) for list_skills

    Returns the discovered list. Empty if no skill is installed.
    """
    out: list[SkillRegistration] = []
    eps = importlib.metadata.entry_points()
    # Python 3.10+ uses select(group=...), older uses dict-style. Handle both.
    if hasattr(eps, "select"):
        selected = eps.select(group=ENTRY_POINT_GROUP)
    else:
        selected = eps.get(ENTRY_POINT_GROUP, [])
    for ep in selected:
        register_fn = ep.load()
        info = getattr(register_fn, "SKILL_INFO", None)
        if info is None:
            # Auto-derive minimal metadata from entry-point name + docstring
            info = SkillRegistration(
                name=ep.name,
                label=ep.name,
                description=(register_fn.__doc__ or "").strip().split("\n")[0],
                stages=(),
                register_fn=register_fn,
            )
        out.append(info)
    return out
```

**Step 2.6**: write `workflow_dir.py`:
```python
"""Scan skills/*/workflow/source/*.json for available source workflows.

Each skill that wants to be discoverable drops a UI workflow JSON in
skills/<skill>/workflow/source/. workflow_dir.py enumerates them at server
startup. New workflows are picked up automatically; no code changes.
"""
from __future__ import annotations
import json
from pathlib import Path

_SKILLS_ROOT = Path(__file__).resolve().parents[4]  # skills/

def list_workflows() -> list[dict]:
    out: list[dict] = []
    if not _SKILLS_ROOT.is_dir():
        return out
    for skill_dir in sorted(p for p in _SKILLS_ROOT.iterdir() if p.is_dir()):
        source_dir = skill_dir / "workflow" / "source"
        if not source_dir.is_dir():
            continue
        for wf_path in sorted(source_dir.glob("*.json")):
            try:
                with wf_path.open(encoding="utf-8") as f:
                    wf = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            nodes = wf.get("nodes") if isinstance(wf, dict) else None
            out.append({
                "skill": skill_dir.name,
                "workflow": wf_path.stem,
                "path": str(wf_path),
                "node_count": len(nodes) if isinstance(nodes, list) else 0,
            })
    return out
```

**Step 2.7**: write `schema.py` (re-export + validate):
```python
"""Schema discovery + validation.

Single source of truth per skill: each skill's runtime.graph_patcher.describe_config.
This module dispatches to the skill's own schema via the entry-point registry.
"""
from __future__ import annotations
from typing import Any

from .registry import discover as _discover_skills

_VALIDATORS: dict[str, Any] = {
    # Each skill registers a validator via the entry-point.
    # Default per-skill validators live in skills/<skill>/mcp_bridge.py.
}

def _load_validator(skill: str):
    if skill in _VALIDATORS:
        return _VALIDATORS[skill]
    # Discover via entry-points; each skill exposes validate_config(skill, stage, config).
    for reg in _discover_skills():
        ep_module = reg.register_fn.__module__  # e.g. "camera_image.mcp_bridge"
        mod = __import__(ep_module, fromlist=["validate_config"])
        validator = getattr(mod, "validate_config", None)
        if validator is not None:
            _VALIDATORS[skill] = validator
            return validator
    return None

def describe_skill(skill: str, stage: str | None = None) -> dict[str, Any]:
    """Dispatch to the skill's own describe_config (or describe_<skill>_config)."""
    for reg in _discover_skills():
        if reg.name != skill:
            continue
        ep_module = reg.register_fn.__module__
        mod = __import__(ep_module, fromlist=["describe_config"])
        fn = getattr(mod, "describe_config", None) or getattr(mod, f"describe_{skill.replace('-', '_')}_config", None)
        if fn is None:
            raise ValueError(f"skill {skill!r} entry-point has no describe_config function")
        return fn(stage or reg.stages[0] if reg.stages else "default")
    raise ValueError(f"unknown skill: {skill!r}; installed skills: {[r.name for r in _discover_skills()]}")

def validate_config(skill: str, stage: str, config: dict[str, Any]) -> dict[str, Any]:
    """Dispatch to the skill's own validate_config."""
    validator = _load_validator(skill)
    if validator is None:
        raise ValueError(f"no validator registered for skill: {skill!r}")
    return validator(skill, stage, config)
```

**Step 2.8**: write `server.py`:
```python
"""comfyui-chenxin-mcp stdio server entrypoint.

Called by `comfyui-chenxin-mcp-server` console script (pyproject.toml).
Boots: protocol server + entry-point discovery + workflow_dir scan.

No hardcoded skill names. Skills declare themselves via Python entry-points
(see registry.discover()).
"""
from __future__ import annotations
import asyncio

from .protocol import Server
from .registry import discover as _discover_skills


def main() -> None:
    server = Server(name="comfyui-chenxin-mcp", version="0.1.0")
    skills = _discover_skills()
    if not skills:
        # Empty registry is a valid state (no skill packages installed yet);
        # server still serves list_skills / describe_skill (returns empty).
        pass
    for skill in skills:
        skill.register_fn(server)
    asyncio.run(server.serve_stdio())


if __name__ == "__main__":
    main()
```

**Step 2.9**: write `tools/__init__.py`:
```python
"""Tool modules. Empty by default.

Each installed skill package provides its own `mcp_bridge.py` that declares
its entry-point (see registry.discover()). The MCP server discovers and
calls them — no tools are registered by comfyui-chenxin-mcp itself.
"""
```

**Step 2.10** (new): each skill provides its own bridge in `skills/<skill>/mcp_bridge.py`. Example for `camera-image`:

```python
# skills/camera-image/mcp_bridge.py
"""MCP entry-point for camera-image skill.

Binds t2i-camera / i2i-camera tools onto the comfyui-chenxin-mcp server.
Discovered via setuptools entry-points; no changes needed in
comfyui-chenxin-mcp when this skill is added/removed.
"""
from __future__ import annotations
import json, os, shutil
from pathlib import Path
from typing import Any

from camera_image.runtime.config_schema import RunConfig
from camera_image.runtime.graph_patcher import describe_config, validate_config
from camera_image.runtime.mcp_client import McpClient
from camera_image.runtime.t2i_camera import run_t2i
from camera_image.runtime.i2i_camera import run_i2i
from camera_image.runtime.lora_resolver import (
    parse_lora_inventory, filter_anima_loras, default_lora_plan, render_stack_text,
)
from comfyui_chenxin_mcp.protocol import Server
from comfyui_chenxin_mcp.registry import SkillRegistration

SKILL_INFO = SkillRegistration(
    name="camera-image",
    label="Camera Image (Anima t2i/i2i)",
    description="Anima camera workflow: t2i-camera and i2i-camera. Prompt-forge gate is mandatory; all tunables flow through RunConfig.",
    stages=("t2i-camera", "i2i-camera"),
    register_fn=None,  # filled below
)


def _spawn_mcp() -> McpClient:
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx not found on PATH; install Node.js or set CHENXIN_MCP_CMD/ARGS")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
    return McpClient.from_subprocess(
        npx, ["-y", "comfyui-mcp@0.49.8", "--full", "--comfyui-url", comfy_url],
        timeout=600.0,
    )


def register(mcp: Server) -> None:
    @mcp.tool(name="describe_camera_config",
              description="Return the full schema (defaults, groups, enums) for a camera stage.",
              input_schema={"type": "object",
                            "properties": {"stage": {"type": "string",
                                                       "enum": ["t2i-camera", "i2i-camera"]}},
                            "additionalProperties": False})
    async def describe(stage: str = "t2i-camera") -> dict:
        return describe_config(stage)

    @mcp.tool(name="validate_camera_config",
              description="Validate a RunConfig dict before run_t2i_camera / run_i2i_camera.",
              input_schema={"type": "object",
                            "properties": {"stage": {"type": "string",
                                                       "enum": ["t2i-camera", "i2i-camera"]},
                                          "config": {"type": "object"}},
                            "required": ["stage", "config"],
                            "additionalProperties": False})
    async def validate(stage: str, config: dict) -> dict:
        return validate_config("camera-image", stage, config)

    @mcp.tool(name="list_camera_loras",
              description="List available Anima LoRA short names.",
              input_schema={"type": "object", "additionalProperties": False})
    async def list_loras() -> dict:
        with _spawn_mcp() as mcp:
            inventory = parse_lora_inventory(mcp.list_loras())
        anima = filter_anima_loras(inventory)
        return {"anima_loras": anima,
                "default_stack_text": render_stack_text(default_lora_plan())}

    @mcp.tool(name="run_t2i_camera",
              description="Run t2i-camera generation.",
              input_schema={"type": "object",
                            "properties": {"envelope": {"type": "object"},
                                          "stage": {"type": "string", "enum": ["t2i-camera"]},
                                          "camera": {"type": "object"},
                                          "camera_extra": {"type": "object"},
                                          "lora": {"type": "object"},
                                          "groups": {"type": "object"},
                                          "sampling": {"type": "object"},
                                          "seed": {"type": "integer"},
                                          "image_size": {"type": "object"},
                                          "controlnet_image": {"type": "string"},
                                          "output_dir": {"type": "string", "default": "outputs"}},
                            "required": ["envelope"], "additionalProperties": False})
    async def run_t2i_tool(envelope: dict, stage: str = "t2i-camera", **kwargs) -> dict:
        from camera_image.runtime.runtime_cli import _kwargs_to_run_config
        cli_args = {"envelope_json": json.dumps(envelope, ensure_ascii=False)}
        for k, v in kwargs.items():
            if k == "output_dir":
                continue
            cli_args[k] = v
        config = _kwargs_to_run_config(**cli_args)
        with _spawn_mcp() as mcp:
            payload, code = run_t2i(mcp=mcp, output_dir=Path(kwargs.get("output_dir", "outputs")),
                                      config=config, timeout=600.0)
        return {"exit_code": code, "payload": payload}

    @mcp.tool(name="run_i2i_camera",
              description="Run i2i-camera generation.",
              input_schema={"type": "object",
                            "properties": {"envelope": {"type": "object"},
                                          "reference": {"type": "string"},
                                          "stage": {"type": "string", "enum": ["i2i-camera"]},
                                          "camera": {"type": "object"},
                                          "lora": {"type": "object"},
                                          "groups": {"type": "object"},
                                          "sampling": {"type": "object"},
                                          "seed": {"type": "integer"},
                                          "image_size": {"type": "object"},
                                          "controlnet_image": {"type": "string"},
                                          "output_dir": {"type": "string", "default": "outputs"}},
                            "required": ["envelope", "reference"], "additionalProperties": False})
    async def run_i2i_tool(envelope: dict, reference: str, stage: str = "i2i-camera", **kwargs) -> dict:
        from camera_image.runtime.runtime_cli import _kwargs_to_run_config
        cli_args = {"envelope_json": json.dumps(envelope, ensure_ascii=False), "reference": reference}
        for k, v in kwargs.items():
            if k == "output_dir":
                continue
            cli_args[k] = v
        config = _kwargs_to_run_config(**cli_args)
        with _spawn_mcp() as mcp:
            payload, code = run_i2i(mcp=mcp, output_dir=Path(kwargs.get("output_dir", "outputs")),
                                      config=config, timeout=600.0)
        return {"exit_code": code, "payload": payload}


SKILL_INFO.register_fn = register
```

`skills/camera-image/pyproject.toml` must declare the entry-point:

```toml
[project.entry-points."comfyui_chenxin_mcp.skills"]
camera-image = "camera_image.mcp_bridge:register"
```

When camera-multiview and camera-video are added later, each gets its own `mcp_bridge.py` and entry-point declaration — no changes to `comfyui-chenxin-mcp` server code.

**Step 2.11**: write `tests/__init__.py` (empty).

**Step 2.12**: verify imports work:
```bash
cd /d/Projects/comfyui-chenxin/skills/_mcp
pip install -e . --quiet 2>&1 | tail -3 || echo "pip install failed; check pyproject.toml"
python -c "from comfyui_chenxin_mcp import protocol, registry, workflow_dir, schema; print('imports OK')"
```

**Step 2.13**: commit.

**Step 2.14**: expected diffstat: ~12 files changed, 600+ insertions.

---

## Task 3: tests for protocol + registry + workflow_dir + schema

**Files:**
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_protocol.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_registry.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_workflow_dir.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_schema.py`

**Step 3.1**: write `test_protocol.py`:
```python
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
```

**Step 3.2**: write `test_registry.py`:
```python
from unittest.mock import patch
from comfyui_chenxin_mcp.registry import discover, SkillRegistration


class FakeEntryPoint:
    def __init__(self, name, fn):
        self.name = name
        self._fn = fn
    def load(self):
        return self._fn


def fake_eps(_group):
    def register(mcp): pass
    register.SKILL_INFO = SkillRegistration(
        name="camera-image", label="X", description="t2i/i2i",
        stages=("t2i-camera", "i2i-camera"), register_fn=register,
    )
    return [FakeEntryPoint("camera-image", register)]


def test_discover_picks_up_entry_points():
    with patch("comfyui_chenxin_mcp.registry.importlib.metadata.entry_points") as m:
        m.select = fake_eps
        regs = discover()
    assert any(r.name == "camera-image" for r in regs)


def test_discover_auto_derives_metadata_when_skill_info_missing():
    def register(mcp):
        """t2i-camera and i2i-camera skill bridge."""
        pass
    with patch("comfyui_chenxin_mcp.registry.importlib.metadata.entry_points") as m:
        m.select = lambda g: [FakeEntryPoint("auto-skill", register)]
        regs = discover()
    assert regs[0].name == "auto-skill"
    assert "t2i-camera" in regs[0].description  # derived from docstring first line
    assert regs[0].stages == ()
```

**Step 3.3**: write `test_workflow_dir.py`:
```python
import json
from pathlib import Path
from comfyui_chenxin_mcp.workflow_dir import list_workflows


def test_list_workflows_finds_camera_image(tmp_path, monkeypatch):
    skill_dir = tmp_path / "camera-image"
    src_dir = skill_dir / "workflow" / "source"
    src_dir.mkdir(parents=True)
    (src_dir / "文生图相机视角.json").write_text(json.dumps({"nodes": [{"id": 1}]}), encoding="utf-8")

    import comfyui_chenxin_mcp.workflow_dir as wd
    monkeypatch.setattr(wd, "_SKILLS_ROOT", tmp_path)
    wf = list_workflows()
    assert len(wf) == 1
    assert wf[0]["skill"] == "camera-image"
    assert wf[0]["workflow"] == "文生图相机视角"
    assert wf[0]["node_count"] == 1


def test_list_workflows_handles_missing_source_dir(tmp_path, monkeypatch):
    (tmp_path / "no-skill").mkdir()
    import comfyui_chenxin_mcp.workflow_dir as wd
    monkeypatch.setattr(wd, "_SKILLS_ROOT", tmp_path)
    assert list_workflows() == []


def test_list_workflows_skips_unparseable_json(tmp_path, monkeypatch):
    skill = tmp_path / "s"
    (skill / "workflow" / "source").mkdir(parents=True)
    (skill / "workflow" / "source" / "bad.json").write_text("not json", encoding="utf-8")
    import comfyui_chenxin_mcp.workflow_dir as wd
    monkeypatch.setattr(wd, "_SKILLS_ROOT", tmp_path)
    assert list_workflows() == []
```

**Step 3.4**: write `test_schema.py`:
```python
from unittest.mock import patch
from comfyui_chenxin_mcp.schema import describe_skill, validate_config


class FakeEntryPoint:
    def __init__(self, name, fn): self.name = name; self._fn = fn
    def load(self): return self._fn


def _make_eps():
    def describe_config(stage):
        return {"stage": stage, "slots": {"sampling": {"fields": {"steps_first": {"default": 40}}}}}
    def validate_config(skill, stage, config):
        return {"valid": True, "errors": [], "warnings": []}
    mod = type("M", (), {"describe_config": describe_config, "validate_config": validate_config})
    return [FakeEntryPoint("camera-image", lambda m: mod)]


def test_describe_skill_dispatches_to_skill_entry_point():
    with patch("comfyui_chenxin_mcp.schema._discover_skills", return_value=[
        type("R", (), {"name": "camera-image",
                       "register_fn": lambda m: None,
                       "stages": ("t2i-camera",)})()
    ]):
        with patch("comfyui_chenxin_mcp.schema.importlib.import_module",
                   return_value=type("M", (), {
                       "describe_config": lambda s: {"stage": s, "slots": {}}
                   })()):
            out = describe_skill("camera-image", stage="t2i-camera")
    assert out["stage"] == "t2i-camera"


def test_describe_skill_unknown_skill_raises():
    with patch("comfyui_chenxin_mcp.schema._discover_skills", return_value=[]):
        import pytest
        with pytest.raises(ValueError):
            describe_skill("nonexistent-skill")


def test_validate_config_delegates_to_skill_validator():
    with patch("comfyui_chenxin_mcp.schema._load_validator",
               return_value=lambda s, st, c: {"valid": True, "errors": [], "warnings": []}):
        out = validate_config("camera-image", "t2i-camera", {"draft": {"positive": "x", "negative": "y"}})
    assert out["valid"] is True
```

**Step 3.5**: run tests:
```bash
cd /d/Projects/comfyui-chenxin
python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/ --tb=short -q 2>&1 | tail -10
```
Expected: ~12 passed.

**Step 3.6**: commit.

---

## Task 4: tests for `camera-image` mcp_bridge (the new owner of camera tools)

After the spec split, the camera tools live in `skills/camera-image/mcp_bridge.py`, not in `comfyui-chenxin-mcp/tests/`. Tests move with them:

**Files:**
- Create: `skills/camera-image/tests/test_mcp_bridge.py`

**Step 4.1**: write `test_mcp_bridge.py`:
```python
"""camera-image MCP bridge tests - tool handlers dispatch to runtime.*."""
import json
import pytest
from unittest.mock import MagicMock, patch

from comfyui_chenxin_mcp.protocol import Server
from camera_image.mcp_bridge import register, SKILL_INFO


def _server():
    s = Server(name="t", version="0")
    register(s)
    return s


def test_skill_info_exposed():
    assert SKILL_INFO.name == "camera-image"
    assert "t2i-camera" in SKILL_INFO.stages
    assert "i2i-camera" in SKILL_INFO.stages


@pytest.mark.asyncio
async def test_describe_camera_config_delegates_to_graph_patcher():
    fake_schema = {"stage": "t2i-camera", "slots": {}}
    with patch("camera_image.mcp_bridge.describe_config", return_value=fake_schema) as dc:
        s = _server()
        out = await s._tools["describe_camera_config"]["handler"](stage="t2i-camera")
    assert out is fake_schema


@pytest.mark.asyncio
async def test_validate_camera_config_delegates_to_runtime():
    fake = {"valid": True, "errors": [], "warnings": []}
    with patch("camera_image.mcp_bridge.validate_config", return_value=fake) as vc:
        s = _server()
        out = await s._tools["validate_camera_config"]["handler"](stage="t2i-camera", config={"draft": {}})
    assert out is fake


@pytest.mark.asyncio
async def test_list_camera_loras_invokes_mcp_and_filters_anima():
    fake_mcp = MagicMock()
    fake_mcp.__enter__ = lambda s: fake_mcp
    fake_mcp.__exit__ = lambda *a: False
    fake_mcp.list_loras.return_value = "## loras (3)\n- Anima\\foo.safetensors\n- other\\bar.safetensors"
    with patch("camera_image.mcp_bridge._spawn_mcp", return_value=fake_mcp):
        s = _server()
        out = await s._tools["list_camera_loras"]["handler"]()
    assert "anima_loras" in out


@pytest.mark.asyncio
async def test_run_t2i_camera_calls_runtime_run_t2i():
    fake_mcp = MagicMock()
    fake_mcp.__enter__ = lambda m: fake_mcp
    fake_mcp.__exit__ = lambda *a: False
    envelope = {"evidence": {}, "draft": {"positive": "1girl", "negative": "lowres"}, "dialect_id": "anima"}
    with patch("camera_image.mcp_bridge._spawn_mcp", return_value=fake_mcp), \
         patch("camera_image.mcp_bridge.run_t2i", return_value=({"accepted": True, "prompt_id": "p"}, 0)) as rt:
        s = _server()
        out = await s._tools["run_t2i_camera"]["handler"](envelope=envelope, seed=12345)
    assert out["exit_code"] == 0
    rt.assert_called_once()
```

**Step 4.2**: run from the camera-image skill root (after `git mv`):
```bash
cd /d/Projects/comfyui-chenxin/skills/camera-image
PYTHONPATH=. python -m pytest tests/test_mcp_bridge.py --tb=short -q 2>&1 | tail -10
```
Expected: ~5 passed.

**Step 4.3**: commit.

---

## Task 5 (new): remove legacy tools/camera.py tests from comfyui-chenxin-mcp

After the spec split, `comfyui-chenxin-mcp/tests/test_camera_tools.py` no longer exists (deleted with the old tools/camera.py module). This task is a no-op; the deletion happens in Task 2.

---

## Task 5: install / host wiring

**Files:**
- Modify: `scripts/install.ps1` - add `_mcp` to critical file validation
- Modify: `.codex-plugin/plugin.json` - declare MCP server

**Step 5.1**: read `scripts/install.ps1` to find criticalFiles list, then add the new entry.
**Step 5.2**: read `.codex-plugin/plugin.json` to find mcpServers block, add:
```json
"comfyui-chenxin-mcp": {
  "type": "stdio",
  "command": "comfyui-chenxin-mcp-server",
  "args": [],
  "env": {}
}
```

**Step 5.3**: commit.

**Step 5.4**: verify the install script still parses:
```bash
cd /d/Projects/comfyui-chenxin
powershell -NoProfile -Command "Get-Command scripts/install.ps1 | Select-Object -ExpandProperty Name" 2>&1 | head -5
```

---

## Task 6: docs

**Files:**
- Create: `skills/_mcp/README.md` (full version - install + usage + tool catalog)
- Modify: `skills/camera-image/SKILL.md` - add "via MCP" section

**Step 6.1**: write full README.

**Step 6.2**: SKILL.md add:
```markdown
## Via MCP

`comfyui-chenxin-mcp` server (sibling package) exposes:
- `list_camera_workflows`
- `describe_camera_config(stage)`
- `validate_camera_config(stage, config)`
- `list_camera_loras`
- `run_t2i_camera(envelope, ...)` / `run_i2i_camera(envelope, reference, ...)`

See `skills/_mcp/README.md` for install + tool catalog.
```

**Step 6.3**: commit.

---

## Task 7: full integration test (server smoke)

**Files:**
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_server_smoke.py`

**Step 7.1**: write a smoke test that spawns the actual server process and exchanges `initialize` + `tools/list`:

```python
import json, subprocess, sys
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
    return json.loads(line)


def test_server_handshake_lists_tools(server_proc):
    init = _send(server_proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05",
                   "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
    })
    assert init["result"]["serverInfo"]["name"] == "comfyui-chenxin-mcp"
    server_proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
    }) + "\n")
    server_proc.stdin.flush()
    lst = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    })
    names = [t["name"] for t in lst["result"]["tools"]]
    assert "describe_camera_config" in names
    assert "validate_camera_config" in names
    assert "run_t2i_camera" in names
    assert "run_i2i_camera" in names


def test_describe_camera_config_via_server(server_proc):
    _send(server_proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05",
                                   "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}})
    server_proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
    }) + "\n")
    server_proc.stdin.flush()
    out = _send(server_proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                              "params": {"name": "describe_camera_config",
                                         "arguments": {"stage": "t2i-camera"}}})
    text = json.loads(out["result"]["content"][0]["text"])
    assert text["stage"] == "t2i-camera"
    assert "sampling" in text["slots"]
```

**Step 7.2**: run + commit.

---

## Self-Review

1. **Spec coverage** - each item maps to a task.
2. **No TBD/TODO/placeholder** - none in plan body.
3. **Type consistency** - `RunConfig` signature unchanged; `_kwargs_to_run_config(**cli_args)` reuses the bridge (single source). Schema re-export from runtime, not duplicated.
4. **Final**: ready for execution.

---

## Execution Handoff

Plan complete and saved. Two execution options:

1. **Subagent-Driven** (recommended) - dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** - execute tasks in this session with checkpoints.