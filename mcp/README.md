# MCP 注册与桥接

本目录只负责注册上游 `comfyui-mcp` stdio server，不实现 MCP server、不安装 Custom Nodes、不管理模型和工作流实体。

## 注册文件

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

Claude Code 安装脚本会把它复制到自己的 MCP 配置目录；Codex 或其他宿主需要按各自配置格式注册同一个 stdio server。

## 与 Prompt Forge 的边界

- 上游 MCP 负责 ComfyUI 工具调用；
- `runtime.mcp_bridge.McpBridge` 负责宿主实际工具名到逻辑工具名的适配、JSON 校验和哈希证据；
- Prompt Forge runtime 负责 profile、工作流证据、审批、一次性消费、enqueue intent、history 和 artifact 校验；
- MCP bridge 默认只读，不实现 UI→API converter，不绕过 approval，不替代 queue/idempotency 合同；
- 宿主必须提供 `host_call_tool(tool_name, arguments) -> JSON-compatible result`，runtime 不依赖 Claude 或 Codex SDK。

详细接口见 [`docs/MCP_BRIDGE.md`](../docs/MCP_BRIDGE.md)。

## 安装

`scripts/install.sh` 和 `scripts/install.ps1` 会尝试安装 npm 包 `comfyui-mcp`；失败时可由宿主使用 `npx -y comfyui-mcp` 或其等价方式启动。安装脚本不会验证本机模型、节点、工作流和 GPU 是否满足 profile。

## 归属

上游包来源和许可证见 [`ATTRIBUTION.md`](../ATTRIBUTION.md)。