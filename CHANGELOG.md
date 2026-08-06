# Changelog

All notable changes to comfyui-chenxin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — current state on disk

### P1 production hardening (2026-08-06)

- Add `runtime.preflight.run_preflight()` with a stable JSON contract: four checks (version_stamp, comfyui_reachable, fixed_assets_integrity, host_mcp_tools) plus a `blockers` list and per-check `remediation`. New CLI subcommands: `preflight`, `--version`.
- Add `runtime.attempt_state` (file `%USERPROFILE%\.codex\state\comfyui-chenxin\attempts.jsonl`, env override `COMFYUI_CHENXIN_STATE_DIR`) for cross-attempt state. New CLI subcommands: `attempt-state read-last`, `attempt-state record`.
- Add `runtime.run_stage.run_character_base()` as the single production entry: chains preflight -> capability report -> execution draft, returning a draft awaiting human approval. New CLI subcommand: `run-stage --stage character-base --package <path> --run-dir <dir>`.
- Extend `runtime.errors.make_fault` with a `remediation` field (falls back to `next_action` if omitted). ExecutionError payloads now carry human-readable repair steps.
- Update `skills/character-video-pipeline/SKILL.md` with two mandatory rules: Step 0 (run preflight, surface blockers, no code-level workarounds) and Step 0b (read `attempt-state read-last` before authoring).
- Add `runtime/tests/test_preflight.py` and `runtime/tests/test_attempt_state.py`.
- Bump `.codex-plugin/plugin.json` to `0.0.0+codex.20260806131727`.

### Distribution and install hardening (2026-08-06)

- Make MCP registration portable across machines: switch bundled MCP specs (`mcp/mcp_servers.json`, `.mcp.json`) from a hardcoded absolute `node <clone>/dist/index.js` launch to `npx -y comfyui-mcp@0.41.0 --full --comfyui-url <url>`. Pin the same version the local clone is built from so behaviour matches.
- `scripts/install.ps1` and `scripts/install.sh` now register the plugin AND its MCP server for both Claude Code and Codex, install the plugin into Codex's `plugins/cache/personal/comfyui-chenxin/<version>` directory (backing up any prior version), and verify the MCP server actually starts via a real handshake (`scripts/verify_mcp.py`).
- Choose `-Mode npx` (portable default, recommended) or `-Mode local` for offline / pinned local clones. The script backs up Codex's `config.toml` once per run and refuses to delete anything outside its declared cache root.
- Bump `.codex-plugin/plugin.json` to `0.0.0+codex.20260806121851`.

### Boundary and naming migration (2026-08-04)

- Split the active surface into the side-effect-free `prompt-forge` compiler and the approval-gated `character-video-pipeline` production skill.
- Move the ComfyUI runtime, profiles, adapters, MCP bridge, execution contracts and runtime tests under `skills/character-video-pipeline/runtime/`.
- Remove deprecated skill directories and superseded design/plan files from the shipped tree.
- Rewrite README, usage, architecture, inventory, troubleshooting, MCP docs and plugin metadata around the two-skill boundary.
- Preserve existing `prompt-forge-*` receipt and artifact machine identifiers for local evidence compatibility.

### Controlled production pipeline (2026-08-04)

- Add host-neutral `runtime.mcp_bridge.McpBridge` integration for profile-pinned workflow discovery and local submission.
- Enforce PromptBuild, profile, workflow fingerprint, approval, one-time consumption, raw history, artifact hash and RunRecord handoffs across four stages.
- Keep live ComfyUI tests explicit opt-in; unit tests and compile checks remain the default verification path.

### Prompt compiler (2026-08-02)

- Add PromptIntent 6.1 and PromptBuild 1.0 contracts with provenance, locked facts, reference/output constraints and model-specific dialect validation.
- Add deterministic recipe, alias, tag, scene and timeline checks plus balanced prompt/build evaluation corpora.
- Keep compilation side-effect-free; production execution requires the separate character video pipeline skill.

### Distribution

- `.claude-plugin/plugin.json` and `marketplace.json` register the plugin and `mcp/mcp_servers.json`.
- `scripts/install.sh` and `scripts/install.ps1` register MCP configuration and provide host setup examples.
- `scripts/bootstrap.sh` checks the local ComfyUI endpoint and reports basic hardware guidance.

### Removed from current package

The current package no longer contains deprecated skills, stale stage-specific entry points, superseded plans/specs, or claims about missing automation directories. Historical implementation details are retained only in Git history, not as routable files or authoritative usage instructions.

## License

MIT.