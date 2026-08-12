---
name: prompt-forge
description: Author and audit high-quality model-native prompts for exactly Anima still images, MiniMax-H3 text-to-video-with-audio, and MiniMax-H3 reference-to-video-with-audio. Use whenever creative intent must become an Anima or MiniMax-H3 production prompt with an exact token budget, preserved subject/reference ownership, and a verified prompt for camera-image or camera-video. The verified prompt is consumed only by camera-image (anima) and camera-video (h3_t2va / h3_ref2va); camera-multiview uses a fixed-prompt Flux2-Klein workflow and does NOT take a prompt.
---

# Prompt Forge

Author creative content with the LLM. Deterministic code only counts tokens exactly, looks up
the bundled dictionary, compresses with trace preservation, audits objectively, hashes
artifacts, reports benchmarks, and verifies releases. It never chooses aesthetics, story beats,
or shots for you.

## Method first, code second

This is a methodology. `compile_prompt_artifact(task, request)` *verifies* what you author; it
cannot author for you. Everything you need to author correctly is in this file and its
references — do not read source.

## When to use

One production model per call, exactly three tasks:

- `anima` — Anima still image (contract: [references/authoring-contract.md](references/authoring-contract.md)).
- `h3_t2va` — MiniMax-H3 text-to-video-with-audio, no references (dialect: [references/minimax-h3.md](references/minimax-h3.md)).
- `h3_ref2va` — MiniMax-H3 reference-to-video-with-audio, one or three ordered images (dialect: [references/minimax-h3.md](references/minimax-h3.md)).

Do not infer a fourth task, choose a task from a model selector, or build a generic grammar.
Stop if the requested production model is not one of the three.

## The authoring method

1. **Ledger.** Extract every explicit requirement into immutable facts — stable ID, owner,
   dimension, origin, lock state. Treat user facts as protected even when unlocked. Resolve
   conflicts before writing; never silently merge owners, weaken a negation, alter exact
   dialogue or visible text, or invent a reference.
2. **Budget.** Size the streams with the `exact offline tokenizer` before writing.
   [references/budget-ruler.md](references/budget-ruler.md) is the ruler.
3. **Write.** Author directly in model-native fields — one tag per segment, in the model's
   order, visible and audible facts before aesthetic polish. Link every segment to the facts it
   renders; no opaque prose. The hard contract — including the negative stream, reserved
   namespaces, and attribution — is in
   [references/authoring-contract.md](references/authoring-contract.md).
4. **Polish.** Cover the five aesthetic layers below. A prompt with only
   subject/action/environment is *correct but flat*.
5. **Preflight and compile.** Check tags against the dictionary
   ([references/dictionary-preflight.md](references/dictionary-preflight.md)), compile, then
   fix every code the audit reports in one pass
   ([references/audit-and-recovery.md](references/audit-and-recovery.md)).

Never truncate a prompt or remove a protected fact. If protected content stays above the
quality limit, resolve the conflict through its `user_choices` — never weaken a protected fact
automatically.

## The five aesthetic layers (content vs art)

The gap between a competent image and a beautiful one lives almost entirely in the missing
layers. Before authoring, ask all five questions and add at least one tag for each, each as its
own segment, each linked to a fact:

1. **Composition** — where is the eye drawn? `rule of thirds`, `golden ratio`,
   `low angle shot`, `leading lines`, `foreground framing`, `negative space`,
   `diagonal composition`.
2. **Color grade** — one coherent palette, not scattered color words. `teal and orange color
   grade`, `warm golden color grade`, `cold blue tonal palette`, `high contrast`,
   `complementary colors`.
3. **Camera / lens** — how is it shot? `wide cinematic shot`, `close-up`, `medium shot`,
   `shallow depth of field`, `background blur`, `35mm film look`, `anamorphic lens`.
4. **Lighting direction + atmosphere** — directional and layered, not just "warm".
   `golden hour`, `backlit`, `rim light`, `volumetric light`, `dramatic backlighting`,
   `god rays`, `chiaroscuro`.
5. **Mood / texture** — the feeling. `film grain`, `dusty haze`, `fog`, `floating ash`,
   `rain-soaked reflections`, `smoke`, `melancholic`, `epic`, `grim`.

A request with zero composition, zero color grade, and zero camera tags reads as amateur even
when every tag is real.

## Quality hierarchy

Prioritize in this order:

1. user-locked facts, exact dialogue, visible text, negation, count, ownership, reference
   identity, and action results;
2. model adherence and executable temporal/reference structure;
3. subject and scene coherence;
4. composition, camera, lighting, motion, sound, and style;
5. optional embellishment.

Additional tokens must add non-redundant information. Never pad toward a target.

## Call the tool

`compile_prompt_artifact(task, request)` returns `{ref_id, prompt, metadata}`. Carry the
`prompt` dict (and optionally `prompt_ref`) into `run_skill` under `envelope.prompt`; never
copy only its prompt text into a camera request. A rejected build carries no executable prompt
— call `get_build_audit(ref_id)` and read `hard_gate_codes`.

## Script boundary

Use scripts to build and verify knowledge assets, count exact tokens, query the dictionary,
benchmark deterministic artifacts, prepare generation-pair manifests, and verify a release.
The `scripts do not` select aesthetic concepts, decide story beats, invent shots, resolve
ambiguous intent, or write final prompt prose. Production authoring is offline and side-effect
free; maintainer acquisition scripts are the only network boundary. Do not run ComfyUI,
discover workflows, choose checkpoints, or apply local checkpoint/LoRA knowledge from this
skill.

## Output boundary

Pass the production-ready `prompt` dict from `compile_prompt_artifact` under
`envelope.prompt`, optionally with its `prompt_ref`. Camera skills accept only
`production_ready` builds with valid content hash and exact-token verification.
`camera-multiview` uses a fixed-prompt Flux2-Klein workflow and takes no prompt.
