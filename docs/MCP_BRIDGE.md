# Prompt Forge MCP Bridge

Prompt Forge Runtime is host-neutral. Codex, Claude, a local MCP client, or a
test harness can provide the same `McpBridge` invoker; the runtime never calls
a host SDK directly.

```python
from runtime.mcp_bridge import McpBridge
from runtime.local_orchestrator import submit_stage_via_local_rest

bridge = McpBridge(
    # The host owns this function. It must call the negotiated MCP tool and
    # return a JSON-compatible result.
    lambda tool_name, arguments: host_call_tool(tool_name, arguments),
    tool_names={
        "get_workflow": "mcp__comfyui-mcp__get_workflow",
        "strip_workflow": "mcp__comfyui-mcp__strip_workflow",
        "validate_workflow": "mcp__comfyui-mcp__validate_workflow",
        "check_workflow_runtime": "mcp__comfyui-mcp__check_workflow_runtime",
    },
    host_id="codex",  # or "claude", "local-mcp", etc.
    host_version="host-version",
)

# The same bridge can be passed to build_multiview_draft_with_mcp(...,
# mcp_bridge=bridge) for production workflow conversion, or injected into the
# approved/consumed local submission boundary below. It supplies fresh
# workflow callables and returns a hash-based receipt.
result = submit_stage_via_local_rest(
    approved_plan,
    source_api_graph,
    consumption,
    consumption_path,
    profile=profile,
    capability_report=capability_report,
    mcp_bridge=bridge,
)
```

## Boundary rules

- `McpBridge` adapts tool names, validates JSON responses, and records logical
  tool names, host names, argument hashes, response hashes, and timestamps.
- `workflow_tools()` returns the four callables required by workflow discovery:
  `get_workflow`, `strip_workflow`, `validate_workflow`, and
  `check_workflow_runtime`.
- The bridge does not implement UI-to-API conversion, invent conversion
  receipts, or select a fallback workflow.
- Side-effect calls are disabled by default. A caller may enable them only
  after Prompt Forge approval and one-time consumption have been validated;
  ordinary planning and fresh workflow reads remain read-only.
- Passing both a raw callable map and a bridge is rejected to prevent two
  competing host authorities.
- The local orchestrator still verifies profile hashes, graph hashes, fresh UI
  fingerprints, queue state, idempotency sentinels, and raw history. The bridge
  does not replace those checks.

The host-specific layer is therefore limited to one small function:
`host_call_tool(tool_name, arguments) -> JSON-compatible result`. No Claude or
Codex package is imported by the runtime.
