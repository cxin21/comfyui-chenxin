# Changelog

All notable changes to comfyui-chenxin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — current state on disk

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