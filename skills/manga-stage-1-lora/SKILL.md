---
name: manga-stage-1-lora
description: "[GAP — port deferred] Original `~/.claude/skills/manga-stage-1-lora/` does not exist on disk. LoRA orchestration is currently covered by the sibling `lora-trainer` skill (v2.2). This placeholder exists only so the application-inventory contract is symmetric across all 7 expected skill slots. Re-run P1.1 once the source directory appears."
version: 0.0.1
author: Claude Code
status: deferred
allowed-tools: Bash, Read
---

# manga-stage-1-lora — GAP, port deferred

> **Plugin path**: `skills/manga-stage-1-lora/SKILL.md`
> **Status**: SKIPPED during P1.1 (2026-07-30)
>
> The expected source at `~/.claude/skills/manga-stage-1-lora/` was not present
> on disk at port time. Per the P1.1 task contract: "If any of the source skills
> is missing or unreadable, skip it and document the gap in your report. Don't
> invent."

## 1. Why this skill slot exists

The chenxin-core L4 routing recipe (P0.3 SKILL.md step 7) names `manga-stage-1-lora`
as one of the manga pipeline entry points. For symmetry with the 7-slot inventory
declared in P1.1, this directory + stub SKILL.md is shipped — but contains **no
ported content**. Do NOT route traffic through it until the source materializes.

## 2. Current functional substitute

The actual LoRA orchestration responsibility is already covered by the sibling
`skills/lora-trainer/SKILL.md` (v2.3, ported in this P1.1 commit). `lora-trainer`
targets Anima 1.0 via the standalone trainer; manga-orchestrator step 1 already
delegates to it.

If `manga-stage-1-lora` later surfaces as a separate skill with a distinct scope
(e.g. dataset curation, caption prompting, or non-Anima trainers), this slot
should be filled with a fresh port — not aliased to `lora-trainer`.

## 3. Action item

- [ ] Run `ls ~/.claude/skills/manga-stage-1-lora/` in a future session.
- [ ] If the directory now exists, port its SKILL.md into this slot with the
      standard P1.1 adapter (add `chenxin-core` upstream pointer to description,
      normalize paths to plugin-relative form).
- [ ] Update `application-inventory.md` to flip this row from `skipped` → `ported`.
- [ ] Re-run `tests/test_applications.sh` and confirm 7/7 pass.

## 4. Version

- v0.0.1（2026-07-30）：placeholder created during P1.1 — source skill was missing
