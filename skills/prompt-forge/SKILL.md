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
4. **Polish.** Apply the **Aesthetic coverage (mandatory retrieval)** flow
   below. A prompt with only subject / action / environment is *correct but
   flat*. A prompt that ignores the bundled aesthetics knowledge is *correct
   but slop*. Every aesthetic term must come from `knowledge/aesthetics/` —
   never from memory, never from generic prose.
5. **Preflight and compile.** Check tags against the dictionary
   ([references/dictionary-preflight.md](references/dictionary-preflight.md)), compile, then
   fix every code the audit reports in one pass
   ([references/audit-and-recovery.md](references/audit-and-recovery.md)).

Never truncate a prompt or remove a protected fact. If protected content stays above the
quality limit, resolve the conflict through its `user_choices` — never weaken a protected fact
automatically.

## Aesthetic coverage (mandatory retrieval)

The five aesthetic layers are not a checklist of "questions to ask" the model.
They are a mandatory retrieval from `knowledge/aesthetics/` that the author must
do before writing a single tag.

### The five required sources

For every Anima prompt, the author must read and apply terms from:

1. [`knowledge/aesthetics/composition.md`](knowledge/aesthetics/composition.md) — framing, angle, layout
2. [`knowledge/aesthetics/lighting.md`](knowledge/aesthetics/lighting.md) — quality, direction, source
3. [`knowledge/aesthetics/palette.md`](knowledge/aesthetics/palette.md) — named grades and palettes
4. [`knowledge/aesthetics/camera.md`](knowledge/aesthetics/camera.md) — render medium and optical style
5. [`knowledge/aesthetics/mood-texture.md`](knowledge/aesthetics/mood-texture.md) — mood, atmosphere, particles

### How to apply

1. **Read once per authoring session.** Open all five files; do not author from memory.
2. **Pick at least one term per layer** from the bundled knowledge; bind it to a
   fact in the ledger as `agent_embellishment`. The five facts together give
   the prompt design intent.
3. **Use a recipe when the genre is named.** When the user's request maps to a
   genre in `knowledge/aesthetics/recipes/` (film-noir, cyberpunk-neon,
   wes-anderson-pastel, helmut-newton-bw, ghibli-aesthetic, wuxia-ink), pull
   the recipe's pre-composed five-layer composition instead of assembling
   from scratch.
4. **Cite the source.** Each aesthetic fact carries a `source_ref` of the
   form `<file>.md#<cluster>:<term>` — e.g.
   `composition.md#framing:close-up` or
   `recipes/film-noir.md`. The audit treats uncited aesthetic terms as
   unverified noise.
5. **Run `anti-patterns.md` as an override.** Any pattern in sections A–G of
   [`knowledge/aesthetics/anti-patterns.md`](knowledge/aesthetics/anti-patterns.md)
   must be removed before compiling, regardless of what the five layers
   suggest. Empty intensifiers are worse than absent content.
6. **Preflight before compile.** Verify every aesthetic tag against the
   bundled Anima dictionary using the command in
   [`references/dictionary-preflight.md`](references/dictionary-preflight.md);
   `unverified` aesthetic tags from memory (i.e. not in `knowledge/aesthetics/`)
   must be dropped, not shipped.

### Coverage check

Before compiling, the ledger must contain at least one fact bound to each
of `composition.md`, `lighting.md`, `palette.md`, `camera.md`, and
`mood-texture.md`. A prompt that compiles but lacks any one layer ships
flat — the audit will not catch this; the author must.

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
