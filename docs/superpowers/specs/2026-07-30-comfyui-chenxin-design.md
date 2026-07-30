# comfyui-chenxin — Design Spec (mirror of vault note)

> Mirror of `D:\ObsidianWorkSpace\workspace\20-Areas\comfyui-chenxin\design-2026-07-30.md` for in-repo reference.

This is the canonical architecture spec. **Edit the vault note** for design changes; re-render here via `obsidian-sync.sh` (P1.3).

## Quick links

- [Architecture overview](#architecture-overview)
- [Phase plan](#phase-plan)
- [5-dim adversarial review spec](#5-dim-adversarial-review)

---

## Architecture overview

8 layers (L1–L8) — full text in vault note. Highlights:

- **L1**: ComfyUI Core (your local GPU + custom_nodes)
- **L2**: MCP Driver (`comfyui-mcp` 108 tools, +4 to add in P0.2)
- **L3**: Knowledge Substrate (74 recipes + 578 templates + hardware matrix)
- **L4**: Skill orchestrator (`chenxin-core` mega-skill)
- **L5**: Application layer (manga orchestrator + 6 sibling apps)
- **L6**: Telemetry / health / SLO
- **L7**: ~~Cross-CLI adapters~~ — **skip per user directive** (Claude Code only)
- **L8**: Distribution (npm + Claude Code plugin marketplace)

## Phase plan

| # | Phase | Goal | 5-dim review focus |
|---|---|---|---|
| P0.1 | Knowledge substrate | 74 recipes + 578 templates index | recipe-expert + aesthetic-judge |
| P0.2 | MCP enhancements | auto-launch, vram-decide, template-get, gui-save | security-reviewer + code-reviewer |
| P0.3 | Mega-skill | `chenxin-core` SKILL.md + 11 skill sun-setting | code-reviewer + recipe-expert |
| P1.1 | L5 decoupling | Apps into `skills/` | code-reviewer + aesthetic-judge |
| P1.2 | Self-update | `check_updates.py` weekly | security-reviewer + code-reviewer |
| P1.3 | Obsidian sync | `obsidian-sync.sh` hook integration | recipe-expert |
| P2.1 | Marketplace publish | `plugin.json` + `marketplace.json` | code-reviewer + security-reviewer |
| P2.2 | Docs | README + CONTRIBUTING + tutorials | code-reviewer |

## 5-dim adversarial review

Spawn these 5 reviewers on every PR (in parallel):

1. **code-reviewer** (general quality)
2. **security-reviewer** (secrets + injection + scope)
3. **chenxin-doctor** (workflow JSON graph schema if applicable) — covers the old `aesthetic-judge` role
4. **comfyui-doctor** (VRAM decision if model added)
5. **recipe-expert** (prompt dialect if recipe added)

`passes = blockers == [] AND passed ≥ 4/5`
