---
name: prompt-forge
description: Author and audit high-quality model-native prompts for exactly Anima still images, MiniMax-H3 text-to-video-with-audio, and MiniMax-H3 reference-to-video-with-audio. Use whenever Codex must turn creative intent into an Anima or MiniMax-H3 production prompt, calculate its exact token budget, preserve subject/reference ownership, or return a verified PromptArtifact for camera-image or camera-video.
---

# Prompt Forge

Author creative content with the LLM. Use deterministic code only for exact counting, bounded Anima tag retrieval, trace-preserving compression, objective audit, artifact hashing, benchmark reporting, and release verification.

## Select one path

- Use `author_anima_prompt` for Anima T2I or I2I still images. Read [references/anima.md](references/anima.md) before authoring.
- Use `author_h3_t2va_prompt` for MiniMax-H3 text-to-video-with-audio. Read [references/minimax-h3.md](references/minimax-h3.md) before authoring.
- Use `author_h3_ref2va_prompt` for MiniMax-H3 reference-to-video-with-audio with one or three ordered input images. Read [references/minimax-h3.md](references/minimax-h3.md) before authoring.

Do not choose a path from a model selector, infer a fourth path, or build a generic grammar. Stop if the requested production model is not one of these paths.

## Authoring method

1. Extract every explicit requirement into an immutable fact ledger. Give each fact a stable ID, owner, dimension, origin, and lock state. Treat user facts as protected even when they are not locked.
2. Resolve conflicts before writing. Never silently merge two owners, weaken a negation, alter exact dialogue or visible text, or invent a reference.
3. Calculate the path-specific target, soft, quality, and physical limits with the exact offline tokenizer. Read [references/artifact-and-budgets.md](references/artifact-and-budgets.md).
4. Author directly in the selected model's native fields. Write visible and audible facts before aesthetic polish. Express identity, count, ownership, spatial relations, actions, state changes, camera behavior, sound, and landing states concretely.
5. Link every authored segment to the facts it renders. Do not emit opaque prose with no fact provenance.
6. If above the soft limit, apply the ordered A+B compression method: exact dedupe, equal-fact semantic dedupe, model-native structure extraction, protected lexical compression, then removal of lowest-utility agent embellishment.
7. Never truncate a prompt or remove a protected fact. If protected content remains above the quality limit, return `budget_conflict` with causes and user choices.
8. Run the model-specific hard audit after authoring. A script may reject syntax, references, ownership, timing, dialogue, sound separation, context, token limits, or artifact integrity; scripts do not infer intent or rewrite creative content.
9. Return the immutable `prompt_artifact`. Only `production_ready` artifacts expose executable prompt text. Camera skills reject every other status and every artifact whose hash or exact-token verification is invalid.

## Quality hierarchy

Prioritize in this order:

1. user-locked facts, exact dialogue, visible text, negation, count, ownership, reference identity, and action results;
2. model adherence and executable temporal/reference structure;
3. subject and scene coherence;
4. composition, camera, lighting, motion, sound, and style;
5. optional embellishment.

Additional tokens must add non-redundant information. Never pad toward a target.

## Script boundary

Use scripts to build and verify knowledge assets, count exact tokens, query the Anima dictionary, benchmark deterministic artifacts, prepare generation-pair manifests, and verify a release. The scripts do not select aesthetic concepts, decide story beats, invent shots, resolve ambiguous intent, or write final prompt prose.

Production authoring is offline and side-effect free. Maintainer acquisition scripts are the only network boundary. Do not run ComfyUI, discover workflows, choose checkpoints, or apply local checkpoint/LoRA knowledge from this skill.

## Output boundary

Read [references/artifact-and-budgets.md](references/artifact-and-budgets.md) for formulas and exact artifact fields. Pass the complete serialized artifact under `envelope.prompt_artifact`; never copy only its prompt text into a camera request.
