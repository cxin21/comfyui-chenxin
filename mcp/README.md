# mcp/ — Layer-2 registration for the upstream `comfyui-mcp` driver

> **Status (2026-08)**: This directory contains only `mcp_servers.json` (the
> upstream MCP server registration). The previously-shipped stdlib-only Python
> CLI extensions (`auto_launch.py`, `vram_decide.py`, `_shared.py`) were
> removed; their capabilities are now inlined into `scripts/bootstrap.sh`.
> See CHANGELOG "Refactor: remove mcp/extensions/".

## What this layer does

`mcp/mcp_servers.json` registers **one stdio MCP server** for Claude Code to
spawn:

```json
{
  "mcpServers": {
    "comfyui-mcp": {
      "type": "stdio",
      "command": "comfyui-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

`comfyui-mcp` is the upstream npm package (source:
[`github.com/artokun/comfyui-mcp`](https://github.com/artokun/comfyui-mcp),
see `ATTRIBUTION.md`). It exposes **~108 tools** to agents under the
namespace `mcp__comfyui-mcp__*` — e.g. `mcp__comfyui-mcp__generate_image`,
`mcp__comfyui-mcp__enqueue_workflow`, `mcp__comfyui-mcp__list_models`,
`mcp__comfyui-mcp__health_check`, etc.

## How the driver is installed

`scripts/install.sh` (POSIX) and `scripts/install.ps1` (Windows) both attempt
`npm install -g comfyui-mcp`. If npm is missing or the global install fails,
Claude Code falls back to `npx -y comfyui-mcp` on first invocation. Neither
behavior depends on anything in this directory.

## Boundary with the rest of the plugin

- **`mcp_servers.json` is the only thing this plugin ships that the MCP host
  reads.** It is copied to `~/.claude/mcp_servers/comfyui-chenxin.json` by
  the installer.
- **The plugin never forks `comfyui-mcp`.** When a capability is awkward or
  impossible to express through the upstream JSON-RPC surface — namely,
  anything that *starts a subprocess* (bring up ComfyUI on demand) or that
  *reads the local knowledge substrate* (the prompt-forge hardware JSON
  profiles) — it lives in the appropriate layer instead. As of 2026-08,
  those responsibilities are inlined into `scripts/bootstrap.sh` (a
  shell-level sibling of this directory), not packaged as separate
  `mcp/extensions/*.py` scripts.
- **`.claude-plugin/plugin.json` points at this file** via the `mcpServers`
  field, so Claude Code auto-loads it on plugin install.

## What is **not** here

- No custom node definitions (those live under `<comfyui>/custom_nodes/`).
- No MCP server implementation (the only registered server is the upstream
  npm binary).
- No CLI tooling — ComfyUI bring-up and hardware-aware recommendations are
  done inline by `scripts/bootstrap.sh`.