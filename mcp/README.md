# MCP 注册与桥接

本目录只注册上游 `comfyui-mcp` stdio server，不实现 MCP server、不安装 Custom Nodes、不管理模型和工作流实体。

## 注册

`mcp_servers.json`：

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

## 与两层技能的边界

- `skills/prompt-forge/` 只编译 PromptPackage，不调用 MCP；
- `skills/character-video-pipeline/runtime/` 通过 `McpBridge` 读取受信 workflow 并执行 approval-gated 提交；
- bridge 默认只读，不实现 UI→API converter，不绕过 approval、consumption、queue 或 idempotency；
- 宿主提供 `host_call_tool(tool_name, arguments) -> JSON-compatible result`，runtime 不依赖 Claude 或 Codex SDK。

接口示例见 [`docs/MCP_BRIDGE.md`](../docs/MCP_BRIDGE.md)。安装脚本只注册配置并可选安装上游 npm 包，不验证本机模型、节点、工作流和 GPU。

上游包来源和许可证见 [`ATTRIBUTION.md`](../ATTRIBUTION.md)。