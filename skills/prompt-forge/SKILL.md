# Prompt Forge

Prompt Forge is an LLM-first authoring and audit skill for high-quality image and video prompts. It produces a model-specific `PromptArtifact`; it does not invent a generic prompt language and it does not rewrite authored prompts through a deterministic projector.

## Operating contract

1. Identify the exact production profile before writing: checkpoint family, task type, reference count, duration, and workflow identity.
2. Author the prompt directly in the target model's dialect. Preserve creative intent, shot logic, subject identity, spatial relations, lighting, sound, and temporal causality.
3. Use the profile's native structure. Anima uses weighted tags and concise natural language; MiniMax-H3 uses its official section grammar and timestamped shot logic.
4. Run objective lint only after authoring. Lint may reject malformed syntax, unsupported fields, impossible references, or invalid timing. It must never add creative content.
5. Return a `PromptArtifact` containing the exact authored prompt, profile identity, runtime bindings, lint result, assumptions, and provenance.

## Supported production profiles

- `anima.miaomiao-harem.anima-1.5`: Anima 1.5 checkpoint used by the fixed camera-image workflow; supports T2I and I2I.
- `minimax-h3.base.t2va`: MiniMax-H3 T2VA text-to-video; no reference images and no negative prompt.
- `minimax-h3.base.ref2va`: MiniMax-H3 Ref2VA image/reference-to-video; 1–3 reference images and no negative prompt.

Do not substitute a generic profile, silently coerce a profile id, or infer a video dialect from free-form prose. If the exact production profile is unknown, stop and request it.

## Prompt quality rules

- Write concrete visible or audible facts before style adjectives.
- Resolve subject identity, count, pose, location, camera, action, and result before adding polish.
- For video, define what changes over time, when it changes, how the camera moves, and what remains stable.
- Keep one coherent visual language. Avoid contradictory camera, lighting, lens, motion, or style instructions.
- Treat dialogue as timed audio with a speaker, language, exact words, delivery, and audible environment.
- Do not add unsupported negative prompts, parameter syntax, LoRAs, or node names to the prompt text.

## Files

- `prompt_forge/`: contract, profile loading, lint, and artifact creation.
- `profiles/`: exact model/workflow profiles; each profile is explicit and versioned.
- `scripts/`: narrow objective checks for CI or release validation; scripts do not author or rewrite prompts.
- `tests/`: contract and dialect regression tests.

The execution skills consume the artifact's `prompt` and `asset_bindings`. They do not consume legacy `draft`, `dialect_id`, or `PromptPackage` fields.
