# Plugin Boundary Cleanup Implementation Plan

> **For agentic workers:** Execute each task in order and run the listed checks before moving on.

**Goal:** Make Prompt Forge the only production skill entry point for the controlled character-to-video flow, retire conflicting legacy skill triggers, and publish an accurate Chinese README.

**Architecture:** Keep the existing Prompt Forge runtime and host-neutral MCP bridge as the production core. Legacy manga, LoRA-training, and ffmpeg skills remain readable but become explicitly non-routable documentation-only compatibility files; the empty Stage 1 stub is removed. Documentation is rewritten around the four stages: prompt generation + camera base, Flux multiview, camera img2img shot, and Yusu Director video.

**Tech Stack:** Markdown/YAML frontmatter, Python stdlib runtime, pytest, Ruff, Git.

## Global Constraints

- Production routing must enter through `skills/prompt-forge/SKILL.md`.
- No legacy skill may retain an active trigger for the new four-stage flow.
- Do not change workflow profiles, graph hashes, approval, consumption, or enqueue contracts except where documentation needs to reference them.
- Preserve legacy files unless they are empty placeholders; do not delete user data or generated artifacts.
- Chinese README must describe only verified repository paths and commands.

---

### Task 1: Audit and freeze legacy skill boundaries

**Files:**
- Modify: `skills/manga-orchestrator/SKILL.md`
- Modify: `skills/manga-stage-2-panels/SKILL.md`
- Modify: `skills/manga-stage-3-review/SKILL.md`
- Modify: `skills/manga-stage-4-motion/SKILL.md`
- Modify: `skills/ffmpeg-pipeline/SKILL.md`
- Modify: `skills/lora-trainer/SKILL.md`
- Delete: `skills/manga-stage-1-lora/SKILL.md`

- [ ] Add frontmatter `status: legacy` and a clear “not a production route” notice to the six retained legacy skills.
- [x] Remove active trigger lists from those six files or replace them with an empty list so the host cannot select them before Prompt Forge.
- [x] Delete the 49-line empty Stage 1 placeholder; record the replacement boundary in `application-inventory.md`.
- [x] Run a repository search proving no new-flow trigger is owned by a legacy skill.

### Task 2: Rewrite authoritative Chinese documentation

**Files:**
- Rewrite: `README.md`
- Rewrite: `docs/USAGE.md`
- Rewrite: `docs/architecture.md`
- Rewrite: `application-inventory.md`
- Modify: `docs/TROUBLESHOOTING.md`

- [x] Document the four-stage pipeline and its handoff artifacts.
- [x] State the minimum install prerequisites and the host-neutral MCP bridge boundary.
- [x] Remove references to absent paths and retired implementation details from authoritative usage docs.
- [x] Keep legacy capabilities in a compatibility section, clearly outside the production flow.

### Task 3: Update English/index metadata to match the boundary

**Files:**
- Modify: `README.en.md`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `mcp/README.md`
- Modify: `skills/prompt-forge/SKILL.md`

- [x] Make the four-stage Prompt Forge flow the primary description.
- [x] Link to `docs/MCP_BRIDGE.md` and state that host-specific invokers are required.
- [x] Remove obsolete counts and missing-directory claims.

### Task 4: Validate, stage, and commit

**Files:**
- No new source files beyond the documents above.

- [ ] Run `pytest -q skills/prompt-forge` with `PYTHONPATH=skills/prompt-forge` (not available in the bundled runtime: `pytest` is not installed; previous implementation baseline was 607 passed, 4 skipped).
- [x] Run `python -m compileall -q skills/prompt-forge/runtime`.
- [ ] Run Ruff on changed Python files (not available in the current environment).
- [x] Run reference scans for absent paths and legacy triggers. Run `git diff --check` with the repository CRLF policy.
- [x] Stage only the intended changes and commit with a descriptive message.
