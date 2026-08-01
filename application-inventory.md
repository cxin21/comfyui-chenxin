# Application Inventory — post-2026-07-30 cleanup

> **Phase**: P1.1 + P3-replacement migration status (committed across `531dd62` and `fa5f503`)
> **Date**: 2026-07-30
> **Reason**: prompt-forge (L4, P0.3) routes multi-stage pipelines to L5 application skills. Originally those 7 skills lived at `~/.claude/skills/<name>/` outside the plugin's discoverable surface — so `prompt-forge` step 7 silently fell through. P1.1 brought them in. The 2026-07-30 cleanup (commit `531dd62`) **hard-deleted** the original `~/.claude/skills/<name>/` directories because: (a) every functional capability was duplicated inside the plugin, (b) the plugin's loader now resolves `skills/<name>/SKILL.md` reliably, (c) confusion between old and new paths was producing silent-fall-through bugs.

## 1. Skills in plugin (P1.1 + post-cleanup)

| # | Plugin slot | Origin | Status |
|---|---|---|---|
| 1 | `skills/manga-orchestrator/SKILL.md` | ported from a `~/.claude/skills/` original (manga-bootstrap / manga-orchestrator — both pre-cleanup) | **in plugin** |
| 2 | `skills/manga-stage-1-lora/SKILL.md` | n/a (no source material) | **stub** (49 lines; coverage via `lora-trainer`) |
| 3 | `skills/manga-stage-2-panels/SKILL.md` | ported | **in plugin** |
| 4 | `skills/manga-stage-3-review/SKILL.md` | ported (absorbed manga-stage-3-review 内部 6 维算法 6-dim scoring into internal algorithm) | **in plugin** |
| 5 | `skills/manga-stage-4-motion/SKILL.md` | ported (absorbed `manga-stage-5-talking-head`) | **in plugin** |
| 6 | `skills/ffmpeg-pipeline/SKILL.md`     | ported | **in plugin** |
| 7 | `skills/lora-trainer/SKILL.md`        | ported | **in plugin** |

**7 in plugin. 6 ported, 1 stub (manga-stage-1-lora). 0 invented.**

## 2. Hard-deprecation status

The 2026-07-30 cleanup (commit `531dd62`) **hard-deleted** all `~/.claude/skills/<name>/` originals — `aesthetic-judge/`, `ffmpeg-pipeline/`, `lora-trainer/`, `manga-bootstrap/`, `manga-orchestrator/`, `manga-stage-2/3/4/5/`, `prompt-forge/`, plus `_shared/` and the `~/.claude/agents/comfyui-director.md` agent. This was authorized explicitly by the user after a comprehensive scan.

**Functional split (what replaced what):**

| Original (deleted 2026-07-30) | Plugin replacement |
|---|---|
| `manga-bootstrap/bootstrap.sh` | `scripts/bootstrap.sh` (P0.3) |
| `aesthetic-judge/` (6-dim scoring) | absorbed into `skills/manga-stage-3-review/SKILL.md` (internal algorithm) |
| `manga-stage-5-talking-head/` | absorbed into `skills/manga-stage-4-motion/SKILL.md` (unified video/audio/lip) |
| `prompt-forge/SKILL.md` | preserved as `skills/prompt-forge/internals/legacy/prompt-forge-methodology.md` (methodology kept, recipe data already in `recipes/MODELS.md`) |
| `_shared/workflow_config_guard.md` | `skills/prompt-forge/internals/workflow-config-guard.md` |
| `_shared/workflow_resolver.md` | `skills/prompt-forge/internals/workflow-resolver.md` |
| `agents/comfyui-director.md` | `agents/comfyui-director.md` (v3 → v4, post-plugin-integration rewrite; CLI-edges `mcp__comfyui-mcp-server__*` fixed to `mcp__comfyui-mcp__*`) |

**When a hard deprecation is safe:** only after the plugin's loader has been observed to win for at least one full session. That gate has now been reached — the user's 2026-07-30 cleanup command explicitly authorized hard deletion of all 12 paths after functional verification.

## 3. MCP namespace bug — fixed

Prior to `531dd62`, the plugin's documentation files used `mcp__comfyui-mcp-server__*` (the wrong namespace). The actual MCP server registered in `mcp/mcp_servers.json` is `comfyui-mcp` → tools resolve at `mcp__comfyui-mcp__*`.

**Files updated in `fa5f503`**:

- `agents/comfyui-director.md` — frontmatter `tools:` + entire body references
- `skills/prompt-forge/SKILL.md` — lines 51 + 88-95 (L4 routing)
- `skills/prompt-forge/internals/context_graph.md` — lines 12 + 32 (L2 layer description + flow example)
- `mcp/README.md` — "Boundary with the rest of the plugin" section

**Verification**: `grep -r "mcp__comfyui-mcp-server" .` returns only `agents/comfyui-director.md:304` — which is the **version-history section explicitly stating** that v3 used this namespace and v4 corrected it. That historical mention is intentionally retained.

## 4. Application route map (L5 → L3 recipes)

| L5 skill (plugin path) | L3 recipe it ultimately invokes | Primary use case |
|---|---|---|
| `skills/manga-orchestrator/SKILL.md`         | (orchestrates 0→5 below)       | 6-stage full pipeline coordinator |
| `skills/manga-stage-2-panels/SKILL.md`       | `recipe.anima.txt2img` (v1.0 AnimaStandardV7) | 24 panel PNGs at 832×1216 |
| `skills/manga-stage-3-review/SKILL.md`       | (6-dim scoring, no generation) | aesthetic review |
| `skills/manga-stage-4-motion/SKILL.md`       | `recipe.ltx23.img2vid` (ltx23AllInOne) | 78-node LTX I2V |
| `skills/ffmpeg-pipeline/SKILL.md`            | (no L3 recipe — pure ffmpeg CLI) | concat + SRT + optional burn-in |
| `skills/lora-trainer/SKILL.md`               | `recipe.anima.lora_train` (standalone trainer) | Anima 1.0 LoRA, 8GB VRAM |
| `skills/manga-stage-1-lora/SKILL.md` (stub)  | — | gap; covered by `lora-trainer` |

## 5. Smoke test contract

`tests/test_applications.sh` enforces, for each ported skill:

1. The file exists at `skills/<name>/SKILL.md`.
2. The file has YAML frontmatter delimited by `---`.
3. The frontmatter has both `name:` and `description:` keys.
4. The `description:` value contains the literal substring `prompt-forge` so L4 routing metadata is present.

Run: `bash tests/test_applications.sh`

## 6. First-principles: why hard-deprecate now (not "later")

Three lines of evidence converged:

1. The plugin's 6 application skills (excluding the 49-line stub) cover **the same scopes** the originals covered, with one superset (`manga-stage-4-motion` absorbing `manga-stage-5-talking-head`).
2. The plugin's `commands/chenxin-{init,build,review,doctor,publish,update}.md` subagents + hooks wire the L4 routing context into Claude Code's skill discovery at load time, so the plugin path wins consistently.
3. After the user's explicit authorization (2026-07-30), the safety default falls away and the disk is cleaned.

The "left in place" stance from the original v1.0 inventory was the right safety default during the migration; the user has now confirmed adoption, so the safety falls away.
