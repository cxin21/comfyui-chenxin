# Prompt Forge v6.1 — Production Intent Compiler

**Date:** 2026-08-02
**Status:** implementation complete; deterministic verification pending final run

## First-principles decision

The user does not need “a longer prompt.” They need a reliable translation from a
human goal into the control language of one specific generative model. Therefore
the system is a compiler with a semantic IR, target dialects, validation and a
separate execution boundary:

```text
source request
  -> PromptIntent 6.1 (meaning + authority)
  -> recipes and controlled enrichment
  -> model-specific draft
  -> PromptBuild 1.0 (audited artifact)
  -> optional explicit execution
```

## Why two contracts are necessary

`PromptIntent` answers “what must be true?” It holds target, generation mode,
explicit/recipe/inferred facts, locked facts, output constraints and references.

`PromptBuild` answers “what will this model receive?” It holds the final dialect,
negative-policy decision, validated tags, recipe tokens, parameters, warnings,
errors and readiness.

Without this separation, final prose leaks back into the semantic source, tag
validation cannot be audited, and asking for a prompt can accidentally become an
external generation action.

## Authority model

- `explicit > recipe > inferred`
- Explicit facts are locked and cannot be overwritten.
- Default mode is `compile`.
- `execute` is legal only when the current user request explicitly asks to
  generate/run. The compiler never executes and always emits
  `execution.performed=false`.
- A generator is called only after `ready_to_execute=true`.

## Dialects

### Tag image models

The LLM proposes semantic tags. The compiler exact/alias-validates each candidate,
separates recipe-owned control tokens, orders validated tags and fails if an
explicit fact has no canonical representation.

### Natural-language image models

The LLM renders visible facts as coherent prose using the recipe's order and
negative policy. Locked facts are checked against the final draft. References and
technical output constraints stay structured.

### Video models

Video is temporal direction, not animated image description. The IR adds camera,
motion, timeline and audio dimensions. Text-to-video requires subject, action,
motion and camera; multiple events require an ordered timeline. Model-specific
reference and camera syntax remains recipe-owned.

## Deterministic boundaries

- Concept map: curated cross-check only; longest phrase wins; ambiguous one-CJK
  character matches require an exact whole query.
- Scene matcher: phrase/specificity evidence; a miss returns explicit choices and
  never silently picks the first aesthetic preset.
- Recipe matcher: one public library/CLI contract.
- Prompt compiler: side-effect-free model/dialect/negative/tag/locked-fact/video
  validation.

## Production evaluation

The repository contains:

- 24 balanced trigger-boundary cases, including ComfyUI troubleshooting and news
  queries that must not trigger the Skill;
- 12 deterministic PromptBuild cases across tag images, prose images, edits,
  references and five video families;
- frozen Anima, Flux and Wan fixtures;
- unit/integration checks for both valid and hard-stop builds.

The deterministic gate is pass rate >= 0.90. It proves contracts, not aesthetic
superiority. A claim of “better-looking outputs” still requires rendered A/B
samples, fixed model/version/settings and blinded preference scoring.

## Deliberate non-goals

- General Chinese-to-English translation.
- Automatic model installation, ComfyUI repair or workflow construction.
- Silent recipe fallback between vendors.
- Automatic generation merely because a user mentions a model or ComfyUI.
