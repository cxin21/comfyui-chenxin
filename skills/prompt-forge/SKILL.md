---
name: prompt-forge
description: Author and audit high-quality model-native prompts for Anima still images and MiniMax-H3 text/reference-to-video-with-audio. Use when creative intent must become a production prompt with exact token budget, preserved subject/reference ownership, and a verified prompt for camera-image or camera-video. Camera-multiview uses a fixed-prompt Flux2-Klein workflow and does NOT take a prompt.
---

# Prompt Forge

Author creative content with the LLM. Deterministic code only counts tokens, looks up the bundled dictionary, compresses with trace preservation, audits objectively, hashes artifacts, reports benchmarks, and verifies releases. It never chooses aesthetics, story beats, or shots for you.

## Scenarios

| Task | Model | Dialect |
|---|---|---|
| anima | Anima still image | [dialects/anima/dialect.md](references/dialects/anima/dialect.md) |
| h3_t2va | MiniMax-H3 text-to-video-with-audio | [dialects/minimax-h3/dialect.md](references/dialects/minimax-h3/dialect.md) |
| h3_ref2va | MiniMax-H3 reference-to-video-with-audio | [dialects/minimax-h3/dialect.md](references/dialects/minimax-h3/dialect.md) |

## Method

5-step authoring process: [shared/method.md](references/shared/method.md).
Aesthetic coverage (mandatory retrieval): [shared/aesthetic-coverage.md](references/shared/aesthetic-coverage.md).
Pre-compile gate: [shared/self-check.md](references/shared/self-check.md).

## References index

### Shared (cross-model)
- authoring-contract · method · aesthetic-coverage · decision-tree · self-check · output-protocol · natural-language

### Quality (gates)
- conflict-table · tag-count-ruler · style-consistency · budget-ruler · audit-and-recovery · dictionary-preflight

### Dialects (per model)
- anima/dialect · anima/vocabulary · anima/recipes
- minimax-h3/dialect · minimax-h3/budget-policy

## Tool

`compile_prompt_artifact(task, request)` → `{ref_id, prompt, metadata}`.
Audit via `get_build_audit(ref_id)` if status is `quality_rejected` or `budget_conflict`.

## Scripts

- [preflight.py](scripts/preflight.py) — pre-compile quality gates
- [tag-validate.py](scripts/tag-validate.py) — tag dictionary lookup
