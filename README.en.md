# comfyui-chenxin

> **Local-first ComfyUI mega-skill for Claude Code.** 80 model prompt recipes, 662 workflow templates, hardware-aware model selection, self-updating knowledge substrate, manga end-to-end pipeline.
>
> Looking for the Chinese version? See [`README.md`](README.md).

[![License: MIT](https://img.shields.io/badge/License-MIT-FFD27D.svg)](LICENSE)
[![Claude Code: required](https://img.shields.io/badge/Claude_Code-plugin-5BAEE3.svg)](https://claude.com/claude-code)
[![ComfyUI: required](https://img.shields.io/badge/ComfyUI-local--GPU-9aa3b2.svg)](https://www.comfy.org/)
[![GitHub release](https://img.shields.io/github/v/release/cxin21/comfyui-chenxin)](https://github.com/cxin21/comfyui-chenxin/releases)

---

## 🚀 Quickstart

```bash
# 1. Install the plugin in Claude Code
/plugin marketplace add cxin21/comfyui-chenxin
/plugin install comfyui@chenxin

# 2. (One-time, per machine) Bootstrap the knowledge base
/chenxin-init

# 3. Generate — example: a 5-second Wan 2.2 video of a golden-haired mage
"Use Wan 2.2 to render a 5-second video: a golden-haired elf mage
unleashing world-ending magic, with dialogue + post-audio, 8GB VRAM friendly"
```

**Prerequisite**: local ComfyUI on `http://127.0.0.1:8188` + ≥ 8 GB VRAM.
The plugin auto-launches ComfyUI if not running (see [`auto_launch.py`](mcp/extensions/auto_launch.py)).

---

## 🧭 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ L8  Distribution (npm + Claude Code plugin marketplace)     │
├─────────────────────────────────────────────────────────────┤
│ L7  ~~Cross-CLI adapters~~  → not built (Claude Code only) │
├─────────────────────────────────────────────────────────────┤
│ L6  Telemetry / Health / SLO                               │
├─────────────────────────────────────────────────────────────┤
│ L5  Application Layer (manga orchestrator + 6 siblings)    │
├─────────────────────────────────────────────────────────────┤
│ L4  Skill Orchestrator (prompt-forge — mega-skill)         │
├─────────────────────────────────────────────────────────────┤
│ L3  Knowledge Substrate (80 recipes + 662 templates + hw)  │
├─────────────────────────────────────────────────────────────┤
│ L2  MCP Driver (comfyui-mcp 108 tools + 4 CLI extensions)  │
├─────────────────────────────────────────────────────────────┤
│ L1  ComfyUI Core (your local GPU + custom_nodes)           │
└─────────────────────────────────────────────────────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) for details.

---

## 📚 Full Inventory

### Skills (11 files) — `skills/`

| Skill | Path | Purpose | Trigger keywords |
|---|---|---|---|
| **prompt-forge** | `skills/prompt-forge/SKILL.md` | L4 mega-skill; routes keywords → tools/recipes/workflows | "comfyui" / "出视频" / "anima" / "wan" / "ltx" etc. |
| **manga-orchestrator** | `skills/manga-orchestrator/SKILL.md` | Stage 0: 6-stage pipeline coordinator | "全自动漫剧" / "auto manga" |
| **manga-stage-1-lora** | `skills/manga-stage-1-lora/SKILL.md` | LoRA training orchestration (stub, covered by lora-trainer) | "训 LoRA" |
| **manga-stage-2-panels** | `skills/manga-stage-2-panels/SKILL.md` | Stage 2: Locked `AnimaStandardV7.json` panel generator | "生成分镜" / "stage 2" |
| **manga-stage-3-review** | `skills/manga-stage-3-review/SKILL.md` | Stage 3: 6-dim aesthetic review (absorbed `aesthetic-judge`) | "审查分镜" / "judge images" |
| **manga-stage-4-motion** | `skills/manga-stage-4-motion/SKILL.md` | Stage 4: Locked `ltx23AllInOneWorkflowForRTX_v44.json` I2V + talking | "生成分镜视频" / "图生视频" / "talking head" |
| **ffmpeg-pipeline** | `skills/ffmpeg-pipeline/SKILL.md` | Stage 5: Concat + SRT + optional burn-in | "加字幕" / "concat" |
| **lora-trainer** | `skills/lora-trainer/SKILL.md` | Anima Standalone-Trainer wrapper; 8 GB VRAM-friendly | "训 Anima LoRA" / "lora training" |
| prompt-forge internals (3 files) | `skills/prompt-forge/internals/{recipe_yaml.py,recipe_lookup.py,hardware_decide.py,context_graph.md,workflow-{config-guard,resolver}.md}` | Library helpers | (auto-loaded) |
| prompt-forge internals/legacy (1 file) | `internals/legacy/prompt-forge-methodology.md` | Preserved v3.1 prompt engineering methodology (preserved post hard-delete of `~/.claude/skills/prompt-forge/`) | (read-only) |

### MCP (9 files) — `mcp/`

| File | Purpose |
|---|---|
| `mcp/README.md` | Layer-2 driver documentation. Explains 4 CLI extensions + workflow integration. |
| `mcp/mcp_servers.json` | Registers upstream `comfyui-mcp` (npm, ~108 tools) under `mcpServers.comfyui-mcp` key → agents see `mcp__comfyui-mcp__*`. |
| `mcp/extensions/_shared.py` | Helpers: `wait_for_port`, `wait_for_http`, `load_hardware` (with `8.json` OR `8gb.json` fallback), `load_templates_index`, `resolve_comfyui_path`, JSON-on-stdout contract. |
| `mcp/extensions/auto_launch.py` | Bring up ComfyUI on demand; polls `/system_stats` until 200. |
| `mcp/extensions/vram_decide.py` | Read `hardware/<vram>.json`; emit quant + sampler defaults + block flag. |
| `mcp/extensions/template_get.py` | Filter `templates_index.json` by use_case / modality / category. |
| `mcp/extensions/gui_save.py` | Save workflow JSON to ComfyUI `user/default/workflows/` with `_manifest.json` sidecar. |
| `mcp/extensions/test_smoke.sh` | Smoke test all 4 CLIs (13/13 pass). |
| `mcp/extensions/__init__.py` | Package marker. |

### Agents (7 files) — `agents/`

| Agent | Purpose |
|---|---|
| `chenxin-orchestrator.md` | Sonnet, Tool:Read/Bash/Grep/Glob/Task. Reads `SPEC.md`, finds next unchecked phase, spawns builder + reviewer. |
| `chenxin-builder.md` | Sonnet, Tool:Write/Edit/Read/Bash/Grep/Glob/Skill. Implements one phase scope. |
| `chenxin-reviewer.md` | Sonnet, Tool:Read/Bash/Grep/Glob/Task. **5-dim adversarial review** (code / security / workflow-JSON / VRAM / recipe). |
| `chenxin-doctor.md` | Haiku. VRAM + health diagnostics + bridge `mcp__comfyui-mcp__health_check`. |
| `chenxin-update-bot.md` | Haiku. Weekly upstream diff (SlavaSexton + Comfy-Org templates + HF blog RSS). |
| `chenxin-publisher.md` | Sonnet. Bumps version, opens release PR, creates GitHub Release. |
| `comfyui-director.md` | Sonnet. **ComfyUI 文生图 / 视频导演** — orchestrator-level. 6-stage pipeline with locked workflow + node white-lists (v4 rewrite). |

### Commands (6 files) — `commands/`

Slash commands available once installed:

| Command | Description |
|---|---|
| `/chenxin-init` | One-shot install + bootstrap machine block (`scripts/install.{ps1,sh}` + `scripts/bootstrap.sh`). |
| `/chenxin-build [phase]` | Run next unchecked phase via `chenxin-orchestrator`. |
| `/chenxin-review` | Manually trigger 5-dim adversarial review on staged diff. Supports `--strict` flag. |
| `/chenxin-doctor` | Health check via `chenxin-doctor` subagent + smoke tests. |
| `/chenxin-publish` | Bump version + generate CHANGELOG + open release PR. |
| `/chenxin-update` | Pull latest L3 substrate deltas via `chenxin-update-bot`. |

### Hooks (4 files) — `hooks/`

| File | Trigger | Action |
|---|---|---|
| `hooks/hooks.json` | defines 3 event-matchers | (config) |
| `hooks/scripts/on-session-start.sh` | `SessionStart` | Prints current phase from `SPEC.md` + suggested next command. |
| `hooks/scripts/on-write-sync-vault.sh` | `PostToolUse[Write|Edit]` | If target ∈ {`SPEC.md`,`plugin.json`,`marketplace.json`}, runs `scripts/obsidian-sync.sh`. |
| `hooks/scripts/on-stop-phase-gate.sh` | `Stop` | Checks `git status` and prints PR-template-friendly hint if dirty. |

### Scripts (11 files) — `scripts/`

| Script | Purpose |
|---|---|
| `install.ps1` / `install.sh` | One-shot installer (cross-platform). |
| `bootstrap.sh` | Health check + machine-block read on first run. |
| `check_updates.py` | Weekly daemon — 4 upstream sources (SlavaSexton, Comfy-Org/templates, Comfy-Org/skills, HF blog RSS). |
| `diff_recipes.py` | Per-recipe dialect delta vs upstream. |
| `phase-next.sh` / `find-next-phase.sh` | Git-as-orchestrator helpers. |
| `obsidian-sync.sh` | Writes decision note to user's Obsidian vault (whitelist-sanitized EVENT). |
| `self-update.sh` | Self-update cadence driver. |
| `validate-plugin-schema.sh` / `validate-marketplace.sh` | JSON schema validators (run in CI + pre-publish). |

### Knowledge Substrate (L3) — `skills/prompt-forge/`

| File | Lines | Purpose |
|---|---|---|
| `recipes/MODELS.md` | 2462 | 80 model prompt recipes with YAML frontmatter (each recipe has id/family/modality/dialect/license/triggers). |
| `templates_index.json` | 6651 | 662 workflow templates by category (3d=11 api=242 archived=23 audio=22 conditioning=26 get_started=5 image=92 upscale=22 utility=138 video=81) and modality (3d=36 image=435 video=152 audio=32 vector=2 mixed=5). |
| `hardware/8gb.json` | 58 | VRAM decision matrix: 15 allowed_quant, swap_blocks=40, sampler_defaults=euler/4/1.0, preference=[lightning_x2v, lightx2v, fcn, native]. |

---

## 🧪 Tests (all real, not mock)

> Every test in this plugin invokes actual scripts/CLIs/binaries against actual data. **No mocking**. Test suite proves component behavior end-to-end (modulo hardware-dependent ComfyUI server, which the plugin does not require).

| Test | Result | What it actually exercises |
|---|---|---|
| `mcp/extensions/test_smoke.sh` | **13/13 PASS** | Calls 4 CLI tools (auto_launch, vram_decide, template_get, gui_save) — verifies CLI surface, JSON-on-stdout, exit-code grammar (0/2/3/4), and that vram_decide returns `blocked=true` for non-existent models. |
| `tests/test_obsidian_sync.sh` | **4/4 PASS** | Runs `scripts/obsidian-sync.sh` against a real `/tmp/obsidian-sync-sandbox-$$` vault; verifies path-traversal sanitization (hostile EVENT arg → safe filename), event-default-to-unknown, missing-vault non-fatal exit-0. |
| `tests/test_check_updates.sh` | **17/17 PASS** | Calls `check_updates.py` and `diff_recipes.py` against actual `~/.cache` and `git ls-remote`; verifies JSON envelope shape, --help exit-0, idempotent self-diff (finds 13 unchanged recipes). |
| `tests/test_applications.sh` | **7/7 PASS** | Reads each SKILL.md from disk via `awk`; verifies YAML frontmatter delimiter, presence of `name:` and `description:`, `description` contains literal substring `prompt-forge`. |
| `scripts/validate-plugin-schema.sh` | **OK** | Parses `.claude-plugin/plugin.json` and `marketplace.json`; verifies name matches slug + dependencies path exist. |
| `scripts/validate-marketplace.sh` | **OK** | Same for `marketplace.json` (cross-checks `plugin.json` name presence + slug regex). |

Run all:

```bash
bash mcp/extensions/test_smoke.sh
bash tests/test_obsidian_sync.sh
bash tests/test_check_updates.sh
bash tests/test_applications.sh
bash scripts/validate-plugin-schema.sh
bash scripts/validate-marketplace.sh
```

---

## 🔗 Obsidian Vault Integration

The plugin writes one trace file per material change to the user's Obsidian vault. The contract is enforced via hook + idempotent script.

- **Vault default**: `D:/ObsidianWorkSpace/workspace/00-Inbox/processed/`
- **Override**: `OBSIDIAN_VAULT_PATH=/path/to/vault bash scripts/obsidian-sync.sh <event>`
- **Disable**: `OBSIDIAN_VAULT_PATH=/dev/null`
- **Read full contract**: see [`docs/OBSIDIAN_SYNC.md`](docs/OBSIDIAN_SYNC.md)
- **Troubleshoot**: see [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)

### Vault → Git reverse bridge

Critical vault decisions are mirrored into `docs/vault-bridge/` in this repo (see [`docs/vault-bridge/README.md`](docs/vault-bridge/README.md)), so the team can search them via `git grep` without needing vault access.

---

---

## 🤝 Contributing

1. Fork + branch (`phase/PX.Y-task-name`).
2. Implement + commit (`scripts/install.sh`).
3. Open PR using `.github/PULL_REQUEST_TEMPLATE.md` (auto-populated checkboxes).
4. Wait for 5-dim adversarial review (`agents/chenxin-reviewer.md`) → human approval.
5. Auto-merge via `phase-gate.yml` opens the next phase branch.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full conventions.

---

## 📜 License

MIT — see [`LICENSE`](LICENSE).

Third-party attributions: [`ATTRIBUTION.md`](ATTRIBUTION.md).

---

## 🔗 Links

- GitHub: https://github.com/cxin21/comfyui-chenxin
- Inspiration: [SlavaSexton/ComfyUI-Agent-Kit](https://github.com/SlavaSexton/ComfyUI-Agent-Kit)
- Underlying MCP: [artokun/comfyui-mcp](https://github.com/artokun/comfyui-mcp)
- Knowledge upstream: [Comfy-Org/workflow_templates](https://github.com/Comfy-Org/workflow_templates)
- Claude Code: https://claude.com/claude-code
- Vault (Obsidian): `~/.claude/rules/obsidian-workflow.md` (workspace rule)
