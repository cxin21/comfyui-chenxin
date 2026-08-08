# comfyui-chenxin-mcp v1 Specification

**Date:** 2026-08-08
**Status:** implemented (in progress, v1)

## Context

Each `camera-*` skill (`camera-image`, `camera-multiview`, `camera-video`) has its own CLI surface, but LLM hosts (Claude Code, Codex, OpenCode) want MCP-native tool access. A plugin-level MCP server provides self-describing tools (`tools/list`) so LLMs don't need to read SKILL.md / docs before invoking capabilities.

## Decisions

1. **v1 scope:** `camera-image` only (`t2i-camera` + `i2i-camera`). `camera-multiview` and `camera-video` are added in v2+ by each skill declaring its own entry-point.
2. **Package name:** `comfyui-chenxin-mcp`
3. **Entry point:** `comfyui-chenxin-mcp-server`
4. **Transport:** stdio
5. **Skill registry via Python entry-points:** each skill declares a `comfyui_chenxin_mcp.skills` entry-point in its own `pyproject.toml` pointing at `register(mcp)`. The MCP server iterates entry-points at startup — adding a new skill = pip-install the new skill package; no MCP server code changes.
6. **Schema source of truth:** each skill's own `runtime.graph_patcher.describe_config`. MCP server dispatches to it lazily; never duplicates the field map.
7. **`validate_config` is a separate MCP tool** (not a CLI subcommand) so LLM gets structured errors before invoking `run-*`.

## Architecture

Stdio JSON-RPC 2.0 server, MCP 2024-11-05 framing. Tools dispatch to existing `runtime.*` modules. `comfyui-mcp` is a downstream dependency reached via `McpClient`.

## Components

| Module | Responsibility |
|--------|---------------|
| `protocol.py` | JSON-RPC 2.0 / MCP 2024-11-05 framing |
| `registry.py` | Skill registration + tool dispatch |
| `workflow_dir.py` | Asset scan |
| `schema.py` | Schema + validation |
| `tools/camera.py` | `t2i-camera` / `i2i-camera` tool handlers |
| `server.py` | Entrypoint |

## Data Flow

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

## Testing

- Per-tool unit tests with mocked `McpClient`
- Protocol framing tests
- Registry dispatch test

## Scope

**In scope (v1):**

- `comfyui-chenxin-mcp` Python package with stdio JSON-RPC 2.0 server
- `comfyui-chenxin-mcp-server` entry point
- Entry-point-based skill registry; `camera-image` shipped as a separate package declaring its `register(mcp)` entry-point
- Tools: `describe_camera_config`, `validate_camera_config`, `run_t2i_camera`, `run_i2i_camera`
- Lazy dispatch to `runtime.graph_patcher.describe_config` (single source of truth)
- Structured validation errors before `run-*` invocations
- Downstream `McpClient` integration with `comfyui-mcp`

**Out of scope:**

- `camera-multiview` and `camera-video` skills (added in v2+ via entry-point registration)
- `flux2-klein-multiview` skill
- `ltx-yusu-director` skill
- HTTP / SSE transport
- Auth / multi-tenant
- A non-MCP CLI subcommand surface

## Self-Review Checklist

1. Does the spec clearly state v1 ships only `camera-image` and explicitly defer `camera-multiview` / `camera-video` to v2+?
2. Is the skill-registry mechanism defined as Python entry-points (not a hard-coded list, not a YAML config)?
3. Is the schema source of truth identified as `runtime.graph_patcher.describe_config` with the MCP server dispatching lazily and never duplicating the field map?
4. Is `validate_config` defined as a separate MCP tool (not a CLI subcommand) so LLMs get structured errors before `run-*`?
5. Is the transport pinned to stdio and the framing to JSON-RPC 2.0 / MCP 2024-11-05?
6. Are all six components (`protocol.py`, `registry.py`, `workflow_dir.py`, `schema.py`, `tools/camera.py`, `server.py`) listed with distinct responsibilities?
7. Is the data-flow code block end-to-end (LLM host → `tools/list` → describe → validate → run) and does each `run-*` step name the specific `runtime.*` module invoked?
8. Is the testing strategy concrete (per-tool unit tests with mocked `McpClient`, protocol framing tests, registry dispatch test) rather than "tests exist"?
9. Are both scope items and out-of-scope items explicit (in-scope lists what ships; out-of-scope lists the deferred skills plus HTTP, auth, and CLI subcommand surface)?
10. Are the package name (`comfyui-chenxin-mcp`) and entry point (`comfyui-chenxin-mcp-server`) named verbatim?
11. Is `comfyui-mcp` identified as a downstream dependency reached via `McpClient`, and is it clear the new server does not reimplement that client?
