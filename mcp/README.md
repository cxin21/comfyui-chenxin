# MCP registration

This directory contains host registration examples for the upstream
`comfyui-mcp` stdio server. It does not implement an MCP server, install
ComfyUI custom nodes, manage models, or discover runtime workflows.

The project server is `skills/_mcp`; it exposes the four unified project tools
and invokes the upstream ComfyUI MCP client during `run_skill`.

## Registration

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

The active runtime contract is documented in
[`docs/MCP_BRIDGE.md`](../docs/MCP_BRIDGE.md) and
[`docs/camera-image-flow.md`](../docs/camera-image-flow.md).

## Boundaries

- `prompt-forge` never calls MCP.
- `camera-image` supplies semantic config and a fixed UI source.
- `comfyui-chenxin-mcp` owns project tool dispatch and execution sequencing.
- `comfyui-mcp` owns ComfyUI protocol operations and UI-to-API strip conversion.
- ComfyUI owns node execution and history.

Missing capability or version mismatch is a hard failure. Do not substitute an
older tool contract or emulate a missing conversion operation.
