# Context Graph — how chenxin-core layers compose (L1 → L8)

This file is the single-page map of the chenxin data flow. It exists so that
any contributor can answer "where does X live?" without reading the whole
codebase.

## The eight layers

| Layer | Name                | Owns                                              | Path(s)                                                              |
|-------|---------------------|---------------------------------------------------|----------------------------------------------------------------------|
| L1    | ComfyUI runtime     | The graph execution engine                        | External (user's `~/ComfyUI`)                                        |
| L2    | MCP driver          | 108 tools (`mcp__comfyui-mcp-server__*`)         | User-side MCP install                                                |
| L3    | Knowledge substrate | 80 recipes, 662 templates, 8 GB hardware matrix   | `skills/chenxin-core/recipes/`, `templates_index.json`, `hardware/`  |
| L4    | **Mega-skill (this layer)** | Routing keyword → which L2/L3/L5 tool to invoke | `skills/chenxin-core/SKILL.md` + `internals/*.py`                    |
| L5    | Application logic   | Stage 0–6 manga pipeline, etc.                    | `skills/<app>/SKILL.md` (future P1.1)                                |
| L6    | Plugin shell        | Slash commands, agents, hooks                     | `commands/`, `agents/`, `hooks/`                                     |
| L7    | Install / scripts   | One-shot installer, smoke tests                   | `scripts/`, `tests/`                                                 |
| L8    | Distribution        | Plugin manifest + marketplace                     | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`      |

## Canonical example — user says "出动漫角色"

Trace a single request through the layers to see the wiring:

```
1. User: "用 Anima 出一个动漫角色"
2. Claude Code sees SKILL.md frontmatter (L4) → matches keywords "anima" + "出" + "动漫角色" → loads L4.
3. L4 routes:
     - "anima"          → L3 lookup via internals/recipe_lookup.py  → dialect block
     - "出" / 8 GB      → L3 lookup via internals/hardware_decide.py → quant + sampler defaults
     - "出动漫角色"    → L5 application (manga-stage-2-panels, P1.1) or L2 generate_image
4. L4 composes the prompt: dialect block from L3 + VRAM-safe defaults from L3.
5. L4 calls L2 (mcp__comfyui__generate_image) → L1 (ComfyUI) renders.
6. L2 returns asset_id → L4 returns control to user with the image.
7. L6 hooks fire PostToolUse → optionally L7 obsidian-sync.sh writes a
   decision note to the user's vault.
```

## What L4 owns vs. doesn't

| Concern                                              | Owned by | Why                                                  |
|------------------------------------------------------|----------|------------------------------------------------------|
| Keyword → tool routing                               | L4       | One entry point must own the dispatch table         |
| Sampler / quant defaults per model                   | L3       | Recipe is the source of truth for dialect + settings |
| Hardware matrix (which models fit on 8 GB)           | L3       | Owned by `skills/chenxin-core/hardware/8gb.json`     |
| ComfyUI workflow execution                           | L1       | Engine-level; out of scope for chenxin               |
| Slash command ergonomics (`/chenxin-build`)          | L6       | Plugin-shell layer                                   |
| Self-update cadence (`/chenxin-update`)              | L7+L6    | Script-level; commands just trigger                  |
| Manga end-to-end pipeline                            | L5       | App-specific orchestration (future P1.1)             |

## Hard rule

> If a piece of knowledge belongs in two layers, it belongs in L3 and L4
> re-reads it on demand. Do not duplicate knowledge into L4.

Examples:
- Sampler defaults per model: L3 only (recipe). L4 looks them up.
- Plugin version: L8 only (manifest). L7 scripts may read but never write.
- Keyword trigger phrases: L4 only (SKILL.md frontmatter).