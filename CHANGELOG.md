# Changelog

All notable changes to comfyui-chenxin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — current state on disk

The numbers below reflect **what is actually shipped on `main`**, not what the roadmap once
planned. Earlier "Planned" items that did not materialise (e.g. `templates_index.json`,
`check_updates.py`, `obsidian-sync.sh`) are listed in the **Roadmap** section so the gap
is visible.

### Shipped (verified on disk)

- **P0.1** — Knowledge substrate: 80 model prompt recipes in `skills/prompt-forge/recipes/MODELS.md` (YAML frontmatter, 2462 lines).
- **P0.1** — Hardware VRAM decision matrix: `skills/prompt-forge/hardware/8gb.json` (15 allowed quantizations, sampler defaults, memory budget).
- **P0.3** — `prompt-forge` mega-skill v4.0 (L4): keyword-routed prompt composition with 11-step self-check.
- **P1.1** — L5 application skills ported into the plugin tree: `manga-orchestrator`, `manga-stage-1-lora` (stub), `manga-stage-2-panels`, `manga-stage-3-review`, `manga-stage-4-motion`, `ffmpeg-pipeline`, `lora-trainer`. The 2026-07-30 cleanup hard-deleted the previous `~/.claude/skills/` originals.

### Shipped — distribution

- `.claude-plugin/plugin.json` + `marketplace.json` (only the `mcpServers` path is wired; `commands/`, `agents/`, `hooks/` paths were removed because the directories do not exist on disk).
- `scripts/install.sh` (POSIX) and `scripts/install.ps1` (Windows) — register the plugin, copy `mcp/mcp_servers.json` to `~/.claude/mcp_servers/comfyui-chenxin.json`, and attempt a global `npm install -g comfyui-mcp`. Either installer's failure is non-fatal (Claude Code falls back to `npx -y comfyui-mcp` on first invocation).
- `scripts/bootstrap.sh` — health-checks ComfyUI on `:8188` (auto-launching it if down, with detached subprocess + `/system_stats` poll) and prints the machine block (recommended quant for anima / wan / sdxl / flux on the probed VRAM tier). Both responsibilities were formerly `mcp/extensions/auto_launch.py` and `mcp/extensions/vram_decide.py`; they were inlined into bootstrap.sh in 2026-08 to drop the stdlib CLI layer.

### Refactors

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