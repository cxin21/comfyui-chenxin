# MiniMax-H3 authoring dialect

## Shared temporal method

Use 2–15 seconds. Calculate maximum shot count as `1 + floor((duration - 1) / 3)`. Use `[Shot 1]` without a timestamp. Start every later shot with `[Shot N] At MM:SS.mmm,` followed by a model-native cut/transition and a genuinely new view, state, space, or time.

For every shot define an opening state, executable action or state transition, feasible camera behavior, synchronous sound/dialogue, and a visible landing state. Reject repeated cuts, contradictory static/moving camera instructions, missing action results, or a timestamp outside the duration.

Preserve user dialogue byte-for-byte inside `<d>[Language] exact words</d>`. Preserve visible text byte-for-byte inside double quotes. Keep dialogue in the detailed visual timeline, diegetic ambience in `overall_soundscape`, and only non-diegetic score in `non_diegetic_music`.

## T2VA fields

Use exactly this order:

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: N/A
```

The integrated description owns appearance, environment, composition, action, camera, synchronous dialogue, transitions, and landing states. Global ambience and score must not duplicate it unnecessarily.

## Ref2VA fields

Use exactly this order:

```text
subject_definitions: <Subject 1> is ... from <Picture 1>.

summary: [reference generation] ...

retention_analysis: <Subject 1> from <Picture 1> remains fully_preserved ...

detailed_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: N/A
```

Use ordered labels `Picture 1..N` and give every picture an owner present in the fact ledger. Define stable appearance once in `subject_definitions`; do not restate it in the detailed timeline. Use `retention_analysis` to name what remains tied to every picture. Put only visible changes, actions, camera behavior, dialogue, and landing states in `detailed_description`.

Record verified processor-resized width and height for every reference. Visual token cost is `ceil(width / 32) * ceil(height / 32)` after enforcing 65,536–16,777,216 pixels. Compute available context as:

```text
262144 - visual_tokens - exact_chat_template_tokens - special_tokens - runtime_safety_margin
```

Available physical context can reduce the text quality limit; it can never raise it. Missing dimensions, reference collisions, owner mismatch, wrong order, or changed reference metadata are blocking.

---

## Budget policy

See [budget-policy.json](budget-policy.json) for H3-specific token budgets (t2va + ref2va).
