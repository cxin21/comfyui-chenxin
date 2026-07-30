# comfyui-chenxin — Roadmap

## Phase legend

- P0 — Foundation (knowledge, MCP driver, mega-skill consolidation)
- P1 — Application unification (L5 apps, self-update, vault sync)
- P2 — Distribution (marketplace, docs)

## Phase gates

Every phase opens a PR and passes 5-dim adversarial review before merge:

1. **code-reviewer** — quality, naming, <800 lines/file
2. **security-reviewer** — secrets, MCP injection, auth scope
3. **chenxin-doctor** — workflow JSON graph schema (if applicable) — covers the old `aesthetic-judge` role
4. **comfyui-doctor** — VRAM decision accuracy (if model added)
5. **recipe-expert** — prompt dialect accuracy (if recipe added)

PR passes if `blockers == []` AND `passed ≥ 4/5`.

## Acceptance criteria

- **A. Knowledge**: `recipes/MODELS.md` ≥ 74 entries; `templates_index.json` ≥ 500 entries
- **B. 8 GB VRAM**: 1216×832 Anima image + 5 s Wan 2.2 video complete without OOM
- **C. E2E**: `/chenxin-build phase/P0.1` opens PR auto-passes ≥4/5 review
