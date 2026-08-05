# Character Video Pipeline MCP Bridge

`McpBridge` 是 `character-video-pipeline` 的宿主无关适配层。Codex、Claude Code、其他 MCP 客户端和测试 harness 都只需提供同一个 `host_call_tool(tool_name, arguments)` callable；runtime 不导入任何宿主 SDK。

```python
from runtime.mcp_bridge import McpBridge

bridge = McpBridge(
    host_call_tool,
    tool_names={
        "get_workflow": "mcp__comfyui-mcp__get_workflow",
        "strip_workflow": "mcp__comfyui-mcp__strip_workflow",
        "validate_workflow": "mcp__comfyui-mcp__validate_workflow",
        "check_workflow_runtime": "mcp__comfyui-mcp__check_workflow_runtime",
    },
    host_id="codex",
    host_version="host-version",
)
```

## 边界规则

- bridge 只映射逻辑工具名、校验 JSON、记录参数/响应 hash 和时间戳；
- `workflow_tools()` 返回 workflow discovery 所需的四个只读 callable；
- bridge 不实现 UI→API converter，不选择 fallback，不发明 conversion receipt；
- side effect 默认关闭，只有 pipeline 已完成 approval 和一次性 consumption 后才允许注入提交边界；
- raw callable map 与 bridge 不能同时传入；
- local orchestrator 仍负责 profile、graph、queue、idempotency、history 和 artifact 校验。

详细生产顺序见 [`docs/USAGE.md`](USAGE.md)。