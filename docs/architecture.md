# comfyui-chenxin Architecture (Quick Ref)

> TL;DR for engineers. Full spec → [superpowers/specs/2026-07-30-comfyui-chenxin-design.md](superpowers/specs/2026-07-30-comfyui-chenxin-design.md).

```
┌─────────────────────────────────────────────────────────────┐
│ L8  Distribution (npm + Claude Code plugin marketplace)     │
├─────────────────────────────────────────────────────────────┤
│ L7  ~~Cross-CLI adapters~~  → not built (Claude Code only) │
├─────────────────────────────────────────────────────────────┤
│ L6  Telemetry / Health / SLO                               │
├─────────────────────────────────────────────────────────────┤
│ L5  Application Layer (manga-orchestrator + 6 sibling apps)│
├─────────────────────────────────────────────────────────────┤
│ L4  Skill Orchestrator (chenxin-core — mega-skill)         │
├─────────────────────────────────────────────────────────────┤
│ L3  Knowledge Substrate (74 recipes + 578 templates + hw)  │
├─────────────────────────────────────────────────────────────┤
│ L2  MCP Driver (comfyui-mcp 108 tools)                      │
├─────────────────────────────────────────────────────────────┤
│ L1  ComfyUI Core (your local GPU + custom_nodes)           │
└─────────────────────────────────────────────────────────────┘
```

## Layer contracts

| Layer | Owner | Interface | Tests |
|-------|-------|-----------|-------|
| L1 | user's local install | HTTP at `127.0.0.1:8188` | health_check |
| L2 | this repo (mcp/) | MCP tools | integration |
| L3 | this repo (recipes/) | YAML + JSON files | unit |
| L4 | this repo (skills/chenxin-core/) | SKILL.md | e2e |
| L5 | this repo (skills/manga-*/) | SKILL.md | e2e |
| L6 | this repo (agents/chenxin-doctor.md) | slash + agent | unit |
| L8 | this repo (.claude-plugin/) | plugin.json | schema |

## Data flow

```
user message
    ↓ L7/L4 route by keyword
L4 pick L3 dialect
    ↓
L3 ask L2 which template + which model
    ↓
L2 vram_decide (L3 hardware matrix)
    ↓
L2 enqueue workflow (comfyui-mcp)
    ↓
L1 ComfyUI run
    ↓ output to output/
L2 gui_save graph to user/default/workflows/<ts>_<name>.json
    ↓
L4 optional aesthetic-judge
    ↓
result returned to user
```
