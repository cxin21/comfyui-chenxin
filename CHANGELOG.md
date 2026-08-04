# Changelog

All notable changes to comfyui-chenxin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — current state on disk

The numbers below reflect **what is actually shipped on `main`**, not what the roadmap once
planned. Earlier "Planned" items that did not materialise (e.g. `templates_index.json`,
`check_updates.py`, `obsidian-sync.sh`) are listed in the **Roadmap** section so the gap
is visible.

### Boundary cleanup (2026-08-04)

- Make `skills/prompt-forge/SKILL.md` the only active production skill for the controlled four-stage character-to-video flow.
- Add the host-neutral `runtime.mcp_bridge.McpBridge` integration for Stage 2 conversion and Stage 1/3/4 local submission.
- Mark historical manga, LoRA-training and ffmpeg skills as `status: legacy` with empty trigger lists; remove the unimplemented `manga-stage-1-lora` stub.
- Rewrite the Chinese README, usage guide, architecture, troubleshooting and inventory so they describe only verified paths and boundaries.
### Shipped (verified on disk)

- **P0.1** — Knowledge substrate: 80 model prompt recipes in `skills/prompt-forge/recipes/MODELS.md` (YAML frontmatter, 2462 lines).
- **P0.1** — Hardware VRAM decision matrix: `skills/prompt-forge/hardware/8gb.json` (15 allowed quantizations, sampler defaults, memory budget).
- **P0.3** — `prompt-forge` mega-skill v4.0 (L4): keyword-routed prompt composition with 11-step self-check.
- **P1.1** — L5 application skills ported into the plugin tree: `manga-orchestrator`, `manga-stage-2-panels`, `manga-stage-3-review`, `manga-stage-4-motion`, `ffmpeg-pipeline`, and `lora-trainer` as legacy compatibility files. The unimplemented `manga-stage-1-lora` placeholder is no longer shipped.

### Shipped — distribution

- `.claude-plugin/plugin.json` + `marketplace.json` (only the `mcpServers` path is wired; `commands/`, `agents/`, `hooks/` paths were removed because the directories do not exist on disk).
- `scripts/install.sh` (POSIX) and `scripts/install.ps1` (Windows) — register the plugin, copy `mcp/mcp_servers.json` to `~/.claude/mcp_servers/comfyui-chenxin.json`, and attempt a global `npm install -g comfyui-mcp`. Either installer's failure is non-fatal (Claude Code falls back to `npx -y comfyui-mcp` on first invocation).
- `scripts/bootstrap.sh` — health-checks ComfyUI on `:8188` (auto-launching it if down, with detached subprocess + `/system_stats` poll) and prints the machine block (recommended quant for anima / wan / sdxl / flux on the probed VRAM tier). Both responsibilities were formerly `mcp/extensions/auto_launch.py` and `mcp/extensions/vram_decide.py`; they were inlined into bootstrap.sh in 2026-08 to drop the stdlib CLI layer.

### Refactors

- **prompt-forge v6.1 (2026-08-02)** — replace the draft translation pipeline with
  a provenance-preserving image/video intent compiler. Add PromptIntent 6.1 and
  PromptBuild 1.0 contracts, locked facts, reference/output constraints, video
  camera-motion-timeline dimensions, side-effect-free final compilation, exact tag
  validation, specificity-weighted scene matching, explicit preset choices, and
  balanced trigger/build evaluation corpora. Compilation is now the default;
  generation requires an explicit user request and a ready build. Preserve the v5
  single-query recipe/tag/scene CLI surfaces.

- **Remove `mcp/extensions/` (2026-08)** — The 5-file stdlib-only Python CLI layer (`__init__.py`, `_shared.py`, `auto_launch.py`, `vram_decide.py`, `test_smoke.sh`) is gone. `auto_launch`'s ComfyUI bring-up and `vram_decide`'s hardware-aware recommendation are inlined into `scripts/bootstrap.sh`. `mcp/` now ships only `mcp_servers.json` and a slimmer `README.md`. The test suite's `mcp/extensions/test_smoke.sh` entry was also removed (it referenced two never-shipped CLIs and would have failed on a fresh clone).

### Shipped — tests

- `scripts/validate-plugin-schema.sh` and `scripts/validate-marketplace.sh` are described in the README test tables but **are not on disk**; see Roadmap.

## Roadmap (planned but not on disk)

- `templates_index.json` (planned 500+ workflow templates; the file does not exist).
- `check_updates.py` weekly upstream diff daemon (does not exist; no scheduler job either).
- `diff_recipes.py` per-recipe dialect delta (does not exist).
- `obsidian-sync.sh` Obsidian vault writer and its `tests/test_obsidian_sync.sh` (neither exists).
- `tests/test_check_updates.sh` and `tests/test_applications.sh` (the `tests/` directory does not exist).
- `validate-plugin-schema.sh` / `validate-marketplace.sh` JSON schema validators.
- `phase-next.sh` / `find-next-phase.sh` git-as-orchestrator helpers.
- `self-update.sh` cadence driver.
- `agents/chenxin-doctor.md`, `agents/comfyui-director.md`, `agents/chenxin-reviewer.md` (the `agents/` directory does not exist).
- `commands/chenxin-{init,build,review,doctor,publish,update}.md` (the `commands/` directory does not exist).
- `hooks/hooks.json` (the `hooks/` directory does not exist).
- `docs/vault-bridge/` and `docs/OBSIDIAN_SYNC.md` (neither exists).
- `lora-trainer/scripts/train-anima-standalone.sh` (the `lora-trainer/scripts/` directory does not exist; `lora-trainer/SKILL.md` references it as the entry command — see SKILL.md for the gap note).
