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

## Out-of-scope: no binding to camera skills

Prompt Forge is a **standalone prompt-authoring skill**. It has **no runtime
binding** to `camera-image`, `camera-video`, or `camera-multiview`:

- The three camera skills **recommend** Prompt Forge for prompt generation,
  but **do not require it**. They accept any `prompt` dict that contains
  model-native `positive` and `negative` strings.
- Prompt Forge does **not** verify, sign, hash, or seal its outputs in any
  way that the camera skills would refuse to bypass. There is no
  `checksum_lock`, no `production_ready` gate at the camera side, no
  "you must call compile_prompt_artifact first" check.
- If you call `compile_prompt_artifact`, you may then pass the resulting
  `prompt` dict into a camera skill — or modify it first, or skip
  Prompt Forge entirely and write the `prompt` dict yourself. The camera
  skills accept all three paths identically.
- If you only have a `prompt_ref` and want the camera skill to fetch it
  server-side, that is also optional; the camera skill only resolves a
  ref when one is explicitly provided in `envelope.prompt_ref`.
