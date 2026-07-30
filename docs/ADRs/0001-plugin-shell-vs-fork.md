# ADR 0001 — Plugin shell rather than fork

**Status**: Accepted
**Date**: 2026-07-30
**Phase**: P2.2

## Context

We needed to add 4 L2-augmenting tools (`auto_launch`, `vram_decide`, `template_get`, `gui_save`) to the existing `comfyui-mcp` MCP driver. Two options:

1. **Fork** `comfyui-mcp`, add the 4 tools as new MCP tools, fork the npm package and release cadence.
2. **Standalone plugin-shell CLIs**: ship a Python stdlib CLI per tool, agent invokes via Bash, output as JSON on stdout.

## Decision

We chose option 2: standalone Python CLIs.

## Rationale

- **Surface mismatch**: 3 of 4 tools (`auto_launch`, `gui_save`, `vram_decide`) don't fit JSON-RPC cleanly. `auto_launch` is a long-running child process; `gui_save` writes to ComfyUI's user dir; `vram_decide` is a pure local read.
- **Cost of a fork**: takes on the upstream release cadence (security review, Node toolchain, MCP protocol churn) for 4 marginal capabilities.
- **Audit trail**: each CLI is a separate process. Adversarial review can be done command-by-command without negotiating a forked npm package.
- **Idempotency**: same input → same output, trivially observable.
- **Migration path is reversible**: if a future capability requires deep integration with `comfyui-mcp`'s reactive protocol, the same code can be re-exported as an MCP tool.

## Consequences

- **Agent responsibility**: every consumer must `subprocess.run` the CLI each call. P95 cost is sub-1ms; not a real bottleneck.
- **Schema drift**: each CLI owns its own JSON output. Centralized schema would require a coordination layer we don't have.
- **`vram_decide` lost Nuance**: it reads `hardware/<vram>.json` only; doesn't know about per-model overrides yet. P0.3's `hardware_decide.py` adds recipe override but stays in the same subprocess CLI mental model.

## Alternatives considered

- **Option 3**: write everything against the SlavaSexton `comfyui-agent-kit` style (fork + patch + npm publish). Rejected because it locks us into their release cadence.
- **Option 4**: use CLI scripts + JSON-RPC wrapper for HTTP integration. Rejected as YAGNI — no current consumer needs HTTP.
