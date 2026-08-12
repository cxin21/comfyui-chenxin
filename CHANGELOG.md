# Changelog

All notable changes to comfyui-chenxin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — current state on disk

### prompt-forge rewrite: methodology-first + one-pass audit (2026-08-13) — v0.1.19

- **SKILL.md rewritten as a methodology spine and split** into four focused references:
  `authoring-contract`, `budget-ruler`, `dictionary-preflight`, `audit-and-recovery`. Docs now
  teach authoring rules — one tag per segment in **both** streams, reserved namespaces, and
  attribution — instead of pointing at code behavior. Fixes doc-vs-implementation drift that
  made comma-separated negative segments look valid and produced `invalid_protocol_tag`.
- **One-pass audit**: a `budget_conflict` build now runs the tag audit too, so an over-budget
  build surfaces every hard-gate code (budget + protocol) in a single compile instead of
  serial rounds of fix-and-recompile.
- **Conflict escape hatch**: `budget_conflict.user_choices` now names mixed agent/protected
  segments as `unlink_segment_<id>_from_protected_fact`, so an author can free tokens without
  weakening protected facts — previously the only offered choice was simplifying protected
  dimensions.
- **Benchmark baseline regenerated**: the 90-case baseline recorded pre-LF-normalization
  artifact hashes; prompts are byte-identical, hashes refreshed after the tokenizer manifest
  pinning (v0.1.17).
- Doc-contract test asserts the three `task` values (`anima` / `h3_t2va` / `h3_ref2va`)
  instead of the legacy `author_*_prompt` function names, and guards the four new references.

### prompt-forge docs sync (2026-08-12) — v0.1.18

- Bump 0.1.17 → 0.1.18 so the MCP tool contract + aesthetic quality gate
  (commit `98eeae4`, landed after v0.1.17 was installed) actually reach the
  installed plugin cache.
- Root cause: docs/content changed after v0.1.17 shipped without a version
  bump, so `claude plugin update` (version-keyed) saw "already at the latest
  version (0.1.17)" and the runtime-loaded `SKILL.md` stayed on the
  library-API era — missing the request schema, the `origin` enum, the
  one-tag-per-segment rule, and the aesthetic quality gate. Authoring against
  the stale doc failed with `FactLedgerError` / `invalid_protocol_tag`.
- Rule going forward: any change to `skills/*/SKILL.md` or the authoring
  contract must bump the plugin version, or `claude plugin update` cannot
  deliver it.

### MCP server registration fix (2026-08-10) — v0.1.6

- **Switch MCP server config from `.claude-plugin/plugin.json` (which the
  Claude Code plugin loader IGNORES) to plugin-root `.mcp.json` (which
  IS the canonical, loader-read source — same pattern as `ecc` and
  `claude-mem`).**
- Symptom: every plugin version bump from v0.1.2 onward broke MCP tool
  exposure (`mcp__plugin_comfyui-chenxin_comfyui-chenxin-mcp__*`),
  because `installed_plugins.json` was being edited manually and the
  plugin loader only registers MCP servers on the initial
  `claude plugin install` call. Sessions running against v0.1.3+
  silently lost the MCP tools, and assistants fell back to upstream
  `comfyui-mcp` (or, worse, gave up).
- Fix: `.mcp.json` is now the single source of truth. `.claude-plugin/plugin.json`
  no longer declares `mcpServers`. Tool names are now
  `mcp__comfyui-chenxin-mcp__*` (the standard Claude Code naming,
  same shape as `mcp__chrome-devtools__*` from ecc).
- Recovery: on machines where v0.1.5 or earlier is installed, run
  `claude plugin uninstall comfyui-chenxin@comfyui-chenxin` then
  `claude plugin install comfyui-chenxin@comfyui-chenxin` to trigger
  the loader's fresh `.mcp.json` read. On fresh machines, the
  marketplace install handles it automatically.

### Per-LoRA strength (2026-08-10) — v0.1.5

- `lora_resolver.resolve_lora_names` now accepts `list[dict]` per
  selection, with optional `strength_model` / `strength_clip` /
  `active` / `trigger_words` keys. The previous `list[str]` shape was
  truncated — the underlying `LoraSelection` dataclass and
  `render_stack_text` were already strength-aware, but the input layer
  discarded the strength info entirely. Now the user's "GUOMAN 0.8"
  request is honored. See `skills/camera-image/SKILL.md` for the
  new shape and examples.

### Error diagnostics hardening (2026-08-10) — v0.1.3

- `evidence._string_list` error messages now include the received
  type and a truncated repr of the value (root-caused from session
  2c6a0517's 6-attempt `locked_facts` retry loop).
- `comfyui-chenxin-mcp` server tools gain minimum-payload examples in
  their tool descriptions; `run_skill` pre-flights `validate_config`
  before spawning any subprocess; failure payloads carry
  `error_category` (prompt_forge_input | engine_build | comfyui_runtime
  | unknown) so callers can route the fix without reading prose.

### prompt-forge proactive trigger (2026-08-10) — v0.1.4

- `skills/prompt-forge/SKILL.md` description rewritten with explicit
  "INVOKE THIS SKILL BEFORE hand-crafting any image or video prompt"
  trigger (root-caused from session a2fc7837 where the assistant
  skipped the skill for a one-line brief). Plus a clarification that
  CLAUDE.md §10 极简任务 applies to Agent dispatch, not Skill tool
  invocation.

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