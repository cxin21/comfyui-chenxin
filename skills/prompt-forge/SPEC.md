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

1. `explicit > recipe > inferred`; explicit facts are locked.
2. PromptIntent and PromptBuild are separate contracts.
3. Compilation is side-effect free. Generation is never implied by prompt work.
4. Open vocabulary belongs to the LLM; Python owns deterministic validation.
5. Semantic tags require exact/alias validation. Recipe control tokens are a
   separate channel.
6. Model modality, dialect and negative policy come from the matched recipe.
7. Video requires temporal semantics: action, motion, camera and continuity.
8. Unknown Chinese is preserved as evidence, never guessed character by character.

## Contracts

PromptIntent 6.1 requires target, mode, generation mode, model/dialect, negative
and output constraints, references, locked facts, and all fourteen dimensions.
See `references/prompt-contracts.md` for the canonical shape.

PromptBuild 1.0 contains the final prompt, model policy decisions, validated and
rejected tags, provenance, warnings/errors, readiness and a non-mutating execution
request. `ready_to_execute=false` is a hard stop.

## Deterministic components

- `recipe_lookup.py`: canonical model recipe and alias resolution.
- `intent_normalize.py`: schema validation, provenance merge, bilingual concept
  cross-check and lookup channel derivation.
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
- At least 0.90 deterministic corpus pass rate, with image, editing and video
  model coverage.
- Trigger corpus contains balanced positive and negative boundary cases.
- Full unit suite, syntax compilation, recipe schema check and Skill validator pass.

## Known evaluation boundary

The deterministic corpus verifies contracts and representative golden drafts. It
does not replace a real-model visual preference benchmark. Promotion claims about
aesthetic superiority require rendered outputs, blinded human comparison and
model/version-specific baselines.
