# Prompt Forge Boundary and Naming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the plugin into a pure `prompt-forge` compiler and a `character-video-pipeline` production skill, then remove deprecated skills and obsolete documentation.

**Architecture:** Move the existing ComfyUI runtime, profiles, adapters, MCP bridge, execution contracts, and runtime tests under `skills/character-video-pipeline/runtime/`. Keep prompt dictionaries, recipes, internals, aesthetics, and pure compiler tests under `skills/prompt-forge/`. Preserve machine-readable `prompt-forge-*` receipt/artifact identifiers during this first migration.

**Tech Stack:** Markdown/YAML frontmatter, Python stdlib runtime, pytest, JSON profiles, PowerShell filesystem operations, Git.

## Global Constraints

- Only `skills/prompt-forge/SKILL.md` and `skills/character-video-pipeline/SKILL.md` may be active skills.
- `prompt-forge` must not describe or invoke MCP, ComfyUI enqueue, approval, consumption, or artifact submission.
- `character-video-pipeline` owns the only MCP, ComfyUI, approval, consumption, and RunRecord side-effect boundary.
- Do not delete models, Custom Nodes, saved workflows, `.live-artifacts`, `.superpowers`, ComfyUI output, or existing local evidence.
- Preserve existing machine identifiers beginning with `prompt-forge-` until a separately versioned schema migration.
- Delete only the exact legacy and historical paths listed in the approved design spec.

---

### Task 1: Add migration boundary tests before moving files

**Files:**
- Create: `skills/character-video-pipeline/runtime/tests/test_skill_boundaries.py`
- Modify: `skills/prompt-forge/runtime/tests/test_skill_boundaries.py` only if required by the move

- [x] Write tests asserting exactly two active `SKILL.md` files and their names.
- [x] Write tests asserting `prompt-forge/SKILL.md` contains no MCP/enqueue/approval side-effect claims.
- [x] Write tests asserting `character-video-pipeline/SKILL.md` is the only owner of runtime/MCP/submit terms.
- [x] Run the boundary test and record the expected failure before implementation.

### Task 2: Create the new production skill and move runtime ownership

**Files:**
- Create: `skills/character-video-pipeline/SKILL.md`
- Move: `skills/prompt-forge/runtime/` → `skills/character-video-pipeline/runtime/`
- Modify: moved runtime tests and path-sensitive CLI references

- [x] Move the runtime directory without changing Python package name `runtime`.
- [x] Create a concise production skill entry describing the four stages, profile pins, MCP bridge, approval/consume boundary, and RunRecord evidence.
- [x] Update runtime tests and CLI path construction from `skills/prompt-forge/runtime` to `skills/character-video-pipeline/runtime`.
- [x] Keep all `prompt-forge-*` machine identifiers unchanged.
- [ ] Run compileall and the runtime unit suite after the move.

### Task 3: Reduce `prompt-forge` to the pure compiler boundary

**Files:**
- Modify: `skills/prompt-forge/SKILL.md`
- Modify: `skills/prompt-forge/SPEC.md`
- Modify: `skills/prompt-forge/internals/` only where documentation or imports still claim runtime ownership

- [x] Rewrite the frontmatter and entry text around PromptIntent → PromptBuild, recipe/dialect selection, deterministic validation, and side-effect-free output.
- [x] Remove stage execution, MCP, ComfyUI, approval, consumption, enqueue, artifact, and RunRecord instructions from the skill entry.
- [x] Update the spec so deterministic components refer only to pure compiler code; point production execution users to `character-video-pipeline`.
- [ ] Run the pure compiler tests and prompt corpus/schema checks.

### Task 4: Update docs, metadata, and installer-facing descriptions

**Files:**
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `application-inventory.md`
- Modify: `docs/USAGE.md`
- Modify: `docs/architecture.md`
- Modify: `docs/TROUBLESHOOTING.md`
- Modify: `docs/MCP_BRIDGE.md`
- Modify: `mcp/README.md`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `CHANGELOG.md`

- [x] Document the two active skills and their non-overlapping permissions.
- [x] Change runtime paths and test commands to `skills/character-video-pipeline/runtime`.
- [x] Remove compatibility-skill tables, old-directory claims, and stale roadmap descriptions.
- [x] Remove obsolete manga/LoRA/ffmpeg keywords from plugin metadata.
- [x] Keep current four-stage profiles and host-neutral MCP contract authoritative.

### Task 5: Delete the approved deprecated paths

**Files:**
- Delete: the six legacy skill directories from the approved design spec
- Delete: the v5/v6/v7 historical plans and specs from the approved design spec
- Delete: the two untracked 2026-08-04 pipeline plans

- [x] Enumerate each exact target and verify it is a file/directory inside the worktree.
- [x] Delete only the enumerated targets; do not use broad recursive workspace cleanup.
- [x] Run repository scans proving no authoritative document references deleted paths.

### Task 6: Verify the two-skill package

- [x] Run JSON parsing for plugin and MCP manifests and every runtime profile.
- [x] Run `python -m compileall -q skills/prompt-forge skills/character-video-pipeline/runtime`.
- [ ] Run pure compiler tests and pipeline runtime tests with `PYTHONPATH` set to the correct skill roots.
- [x] Run boundary, stale-reference, and Git diff checks.
- [x] Review the final diff for accidental deletion of user artifacts.
## 验证记录

- 已通过 bundled Python `compileall`、runtime 23 模块导入 smoke、runtime CLI `--help`、两技能边界测试、Prompt Forge recipe lookup、scene match、recipe schema 和 14 个 JSON 文件解析。
- 已通过 stale-reference 扫描和 `git -c core.whitespace=cr-at-eol diff --cached --check`；runtime 迁移被 Git 识别为重命名。
- 当前运行时未提供 `pytest`/`ruff`，因此完整单元测试和 lint 未执行；未安装额外依赖。
- `build_tag_index.py --check` 按设计报告 CSV 比生成索引更新；本次未重建大型生成索引，避免把数据刷新混入边界迁移。