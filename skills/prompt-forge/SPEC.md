# Prompt Forge v6.1 Specification

## Purpose

Prompt Forge is a semantic compiler for image and video generation prompts. It
turns source-language intent into a model-specific dialect while preserving
explicit facts, model constraints and execution authority.

```text
source request
  -> PromptIntent 6.1
  -> recipe + optional scene enrichment
  -> target-dialect draft
  -> deterministic compiler/auditor
  -> PromptBuild 1.0
  -> optional, explicitly authorized execution
```

## Invariants

1. `explicit_evidence > recipe-controlled reasonable_inference > model
   invention`; explicit facts and accepted asset locks are locked. Inference
   never silently becomes identity truth.
2. PromptIntent and PromptBuild are separate contracts.
3. Compilation is side-effect free. Generation is never implied by prompt work.
4. Open vocabulary belongs to the LLM; Python owns deterministic validation.
5. Semantic tags require exact/alias validation. Recipe control tokens are a
   separate channel.
6. Model modality, dialect and negative policy come from the matched recipe.
7. Video requires temporal semantics: action, motion, camera and continuity.
8. Unknown Chinese is preserved as evidence, never guessed character by character.
9. `prohibited_expansion` is a hard negative and is hash-bound to downstream
   builds.
10. LTX uses one selected global prompt and the workflow-owned negative system;
    video `negative_prompt` is always the empty string.

## Contracts

PromptIntent 6.1 requires target, mode, generation mode, model/dialect, negative
and output constraints, references, locked facts, and all fourteen dimensions.
It may carry the compatible evidence extension: story/art-bible hashes, typed
asset references, three evidence tiers, continuity locks, and uncertainty.
See `references/prompt-contracts.md` for the canonical shape.

PromptBuild 1.0 contains the final prompt, model policy decisions, validated and
rejected tags, provenance, warnings/errors, readiness and a non-mutating execution
request. Its image and LTX evidence fields are compatible extensions: legacy
callers retain `prompt` and `negative_prompt`, while evidence-bound builds add
typed locks, source hashes, bilingual positives, timeline/dialogue metadata, and
split decisions. `ready_to_execute=false` is a hard stop.

## Deterministic components

- `recipe_lookup.py`: canonical model recipe and alias resolution.
- `intent_normalize.py`: schema validation, provenance merge, bilingual concept
  cross-check and lookup channel derivation.
- `runtime/prompt_quality.py`: non-mutating image-lock and bilingual LTX quality
  gates, strict second-based timeline parsing, global-prompt selection, and
  complexity split decisions. It never submits a render.
- `scene_match.py`: specificity-weighted scene recipe suggestions; misses return
  explicit choices rather than selecting a default.
- `tag_lookup.py`: exact/alias canonical tag validation.
- `prompt_compile.py`: model/dialect resolution, final rendering audit and
  PromptBuild emission. It never invokes an MCP or generator.
- `evaluate.py`: offline PromptBuild regression corpus.

## Quality gates

- All explicit facts represented in the final dialect.
- No recipe modality mismatch or unsupported negative field.
- No rejected semantic tags or internal placeholders.
- Video contract complete for the requested generation mode.
- English LTX text preserves declared Chinese dialogue code points exactly while
  translating the surrounding scene, action, and camera text.
- LTX intervals use only positive-duration `〖start-end s〗` markers, start at
  zero, and form one monotonic gap-free execution timeline. Adjacent floating
  boundaries use a small numeric tolerance; hidden or placeholder timelines
  fail closed.
- Dialogue is established by `dialogue_attribution` or an explicit dialogue
  marker, not by quotation marks alone. Attributed speaker names and exact text
  occur in both language prompts; quoted signage, titles, and UI labels remain
  legal non-dialogue text.
- At least 0.90 deterministic corpus pass rate, with image, editing and video
  model coverage.
- Trigger corpus contains balanced positive and negative boundary cases.
- Full unit suite, syntax compilation, recipe schema check and Skill validator pass.

## Known evaluation boundary

The deterministic corpus verifies contracts and representative golden drafts. It
does not replace a real-model visual preference benchmark. Promotion claims about
aesthetic superiority require rendered outputs, blinded human comparison and
model/version-specific baselines.
