# comfyui-chenxin-mcp

MCP server that exposes the comfyui-chenxin plugin skills (camera-image,
camera-multiview, camera-video, ...) over the Model Context Protocol stdio
transport.

## Install

```bash
pip install -e ./skills/_mcp
```

The server auto-discovers any installed skill package that declares the
`comfyui_chenxin_mcp.skills` entry-point group; no hardcoded skill names
live in this package.

## Run

```bash
comfyui-chenxin-mcp-server
```

The server speaks JSON-RPC 2.0 + MCP 2024-11-05 on stdin/stdout. It is
intended to be launched by an MCP-compatible host (Claude Desktop, Codex,
Codex CLI, etc.) rather than invoked manually.

## Tools (placeholder — full list in Task 6)

The actual tool surface is provided by individual skill packages. Each
skill installs an `mcp_bridge.py` module whose `register(server)` binds
its handlers onto the server.