---
name: prompt-forge
description: Author and audit high-quality model-native prompts for exactly Anima still images, MiniMax-H3 text-to-video-with-audio, and MiniMax-H3 reference-to-video-with-audio. Use whenever Codex must turn creative intent into an Anima or MiniMax-H3 production prompt, calculate its exact token budget, preserve subject/reference ownership, or return a verified prompt for camera-image or camera-video. The verified prompt is consumed only by camera-image (anima) and camera-video (h3_t2va / h3_ref2va); camera-multiview uses a fixed-prompt Flux2-Klein workflow and does NOT take a prompt.
---

# Prompt Forge

Author creative content with the LLM. Use deterministic code only for exact counting, bounded Anima tag retrieval, trace-preserving compression, objective audit, artifact hashing, benchmark reporting, and release verification.

## Call the authoring tool

Authoring runs through the MCP tool `compile_prompt_artifact(task, request)` — **not** the underlying library functions. The tool returns `{ref_id, prompt, metadata}`; carry the `prompt` dict (and optionally `prompt_ref`) into `run_skill`.

This skill documents the exact `request` schema so you can author without reading source. One task per call: `anima` (still image), `h3_t2va` (text-to-video), `h3_ref2va` (reference-to-video). Read [references/anima.md](references/anima.md) for the Anima dialect or [references/minimax-h3.md](references/minimax-h3.md) for the H3 dialect before authoring.

Do not choose a task from a model selector, infer a fourth task, or build a generic grammar. Stop if the requested production model is not one of the three.

## Authoring method

1. Extract every explicit requirement into an immutable fact ledger. Give each fact a stable ID, owner, dimension, origin, and lock state. Treat user facts as protected even when they are not locked.
2. Resolve conflicts before writing. Never silently merge two owners, weaken a negation, alter exact dialogue or visible text, or invent a reference.
3. Calculate the path-specific target, soft, quality, and physical limits with the exact offline tokenizer. Read [references/artifact-and-budgets.md](references/artifact-and-budgets.md).
4. Author directly in the model's native fields. For Anima this means **comma-separated tags in the model's order, not English prose sentences** (see the Anima dialect below). Write visible and audible facts before aesthetic polish.
5. Link every authored segment to the facts it renders. Do not emit opaque prose with no fact provenance.
6. If above the soft limit, apply the ordered A+B compression method: exact dedupe, equal-fact semantic dedupe, model-native structure extraction, protected lexical compression, then removal of lowest-utility agent embellishment.
7. Never truncate a prompt or remove a protected fact. If protected content remains above the quality limit, return `budget_conflict` with causes and user choices.
8. Run the model-specific hard audit after authoring (the tool does this). A rejected build (`quality_rejected`) carries no executable prompt — **call `get_build_audit(ref_id)` to read `hard_gate_codes`**, fix the exact gate, and retry.
9. Only `production_ready` builds expose executable prompt text. Camera skills reject every other status and every build whose hash or exact-token verification is invalid.

## Anima authoring request (`task="anima"`)

Pass a single `request` object with exactly these fields:

```json
{
  "facts": [{"fact_id": "…", "value": "…", "origin": "…", "locked": true, "owner": "…", "dimension": "…"}],
  "positive_segments": [{"segment_id": "…", "field": "…", "text": "…", "fact_ids": ["…"]}],
  "complexity": {"subjects": 1, "explicit_relations": 0, "complex_actions": 0, "environment_clusters": 0, "natural_language_bridges": 0},
  "negative_segments": [{"segment_id": "…", "field": "general", "text": "…", "fact_ids": ["…"]}],
  "exclusion_groups": 0
}
```

### Hard rules (the tool rejects violations with `FactLedgerError` / `quality_rejected`)

- **`facts[].origin` / `locked`**: `origin` is one of `user_locked | user_explicit | necessary_inference | agent_embellishment`. A fact is `locked: true` **if and only if** `origin == "user_locked"`; every other origin must be `locked: false`. `fact_id` must be unique and non-empty.
- **`positive_segments[].field`** must be one of:
  `quality_meta_year_safety`, `count`, `subject_anchor`, `character`, `copyright`, `artist`, `general`, `tag`, `attribute_binding`, `action_and_relation`, `composition_and_camera`, `environment_and_props`, `lighting_and_visual_style`, `natural_language_bridge`.
  Anything else → `unsupported_positive_field`.
- **`negative_segments[].field`** must be one of:
  `official_quality_baseline`, `anatomy_count_structure_errors`, `image_technical_defects`, `user_exclusions`, `general`.
- **`complexity.natural_language_bridges`** must equal the number of `positive_segments` whose `field == "natural_language_bridge"`, and that count is at most 1. Set it to `0` unless you include exactly one bridge segment.
- **bridge fact dimension**: a `natural_language_bridge` segment's `fact_ids` must resolve to facts whose `dimension` is one of `ownership | spatial_relation | causal_action | action_result | relation`, and its fact_ids must not overlap the tag segments' fact_ids.
- **segment weights** (optional, defaults shown): `priority` default 1.0 (positive, finite), `adherence_risk` default 0.5, `source_confidence` default 0.9. `fact_ids` must be non-empty.

### Anima dialect (the single most common failure)

**Each `positive_segment.text` is exactly one tag** — a single semantic token, not a comma-separated list. The tool joins every segment's text with `", "`, so a segment holding `"score_9, masterpiece"` is treated as one malformed tag and rejected (`invalid_protocol_tag`). Write one segment per tag.

Order the segments (and thus the rendered tags) in the model's native order:

1. quality / meta / year / safety (`field: quality_meta_year_safety`) — `score_9`, `masterpiece`, `best quality`, `highres`, `absurdres`, `safe`, `year 2026`
2. subject count (`field: count`) — `1girl`, `2boys`
3. character (`field: character`) — appearance tags
4. copyright / artist
5. general visual semantics — action, environment, lighting, style tags
6. at most one `natural_language_bridge` segment for a relation tags cannot bind

### Aesthetic quality gate (the difference between "content" and "art")

A build with only subject/action/environment is *correct but flat* — the gap between a competent image and a beautiful one lives almost entirely in four missing layers. Before authoring, ask all five questions and add tags for each (as `environment_and_props`, `lighting_and_visual_style`, or `composition_and_camera` segments). Skipping one is the single most common cause of "no beauty / no design sense":

1. **Composition** — where is the eye drawn? Add one: `rule of thirds`, `golden ratio`, `low angle shot`, `high angle shot`, `leading lines`, `foreground framing`, `negative space`, `centered composition`, `diagonal composition`, `frame within frame`.
2. **Color grade** — is there a unified palette, not scattered color words? Add one coherent scheme: `teal and orange color grade`, `warm golden color grade`, `cold blue tonal palette`, `desaturated muted palette`, `high contrast`, `complementary colors`.
3. **Camera / lens** — how is it shot? Add one: `wide cinematic shot`, `close-up`, `medium shot`, `full body shot`, `shallow depth of field`, `background blur`, `35mm film look`, `anamorphic lens`, `bird's eye view`.
4. **Lighting direction + atmosphere** — not just "warm", but directional and layered: `golden hour`, `backlit`, `rim light`, `volumetric light`, `dramatic backlighting`, `chiaroscuro`, `soft ambient light`, `lens flare`, `god rays`.
5. **Mood / texture** — the "feeling": `film grain`, `dusty haze`, `fog`, `floating ash`, `rain-soaked reflections`, `smoke`, `wet reflections`, `melancholic`, `epic`, `serene`, `grim`.

Rule: at least one tag from each of the five layers, each a separate segment, each linked to a fact. A request with zero composition, zero color-grade, and zero camera tags reads as amateur even when every tag is real.

Example `request` (verified `production_ready`) — one tag per segment:

```json
{
  "facts": [
    {"fact_id": "f_style", "value": "post-apocalyptic wasteland cinematic aesthetic", "origin": "user_locked", "locked": true, "owner": "user", "dimension": "style"},
    {"fact_id": "f_count", "value": "1boy", "origin": "necessary_inference", "locked": false, "owner": "user", "dimension": "count"},
    {"fact_id": "f_subject", "value": "solo male wanderer survivor", "origin": "necessary_inference", "locked": false, "owner": "user", "dimension": "subject"},
    {"fact_id": "f_appearance", "value": "scarred tattered survivor clothing torn coat scarf", "origin": "agent_embellishment", "locked": false, "owner": "agent", "dimension": "appearance"},
    {"fact_id": "f_weapon", "value": "katana", "origin": "necessary_inference", "locked": false, "owner": "user", "dimension": "equipment"},
    {"fact_id": "f_combat", "value": "melee battle fighting stance", "origin": "user_locked", "locked": true, "owner": "user", "dimension": "action"},
    {"fact_id": "f_env_ruins", "value": "collapsed city ruins rubble broken building", "origin": "user_locked", "locked": true, "owner": "user", "dimension": "environment"},
    {"fact_id": "f_light", "value": "dusk amber warm cinematic lighting", "origin": "user_locked", "locked": true, "owner": "user", "dimension": "lighting"}
  ],
  "positive_segments": [
    {"segment_id": "s_score9", "field": "quality_meta_year_safety", "text": "score_9", "fact_ids": ["f_style"]},
    {"segment_id": "s_masterpiece", "field": "quality_meta_year_safety", "text": "masterpiece", "fact_ids": ["f_style"]},
    {"segment_id": "s_best", "field": "quality_meta_year_safety", "text": "best quality", "fact_ids": ["f_style"]},
    {"segment_id": "s_highres", "field": "quality_meta_year_safety", "text": "highres", "fact_ids": ["f_style"]},
    {"segment_id": "s_safe", "field": "quality_meta_year_safety", "text": "safe", "fact_ids": ["f_style"]},
    {"segment_id": "s_count", "field": "count", "text": "1boy", "fact_ids": ["f_count"]},
    {"segment_id": "s_solo", "field": "character", "text": "solo", "fact_ids": ["f_subject"]},
    {"segment_id": "s_male", "field": "character", "text": "male", "fact_ids": ["f_subject"]},
    {"segment_id": "s_adult", "field": "character", "text": "adult", "fact_ids": ["f_subject"]},
    {"segment_id": "s_hair", "field": "character", "text": "short hair", "fact_ids": ["f_appearance"]},
    {"segment_id": "s_scar", "field": "character", "text": "scar", "fact_ids": ["f_appearance"]},
    {"segment_id": "s_tattered", "field": "character", "text": "tattered clothes", "fact_ids": ["f_appearance"]},
    {"segment_id": "s_scarf", "field": "character", "text": "scarf", "fact_ids": ["f_appearance"]},
    {"segment_id": "s_katana", "field": "action_and_relation", "text": "holding katana", "fact_ids": ["f_weapon"]},
    {"segment_id": "s_fighting", "field": "action_and_relation", "text": "fighting", "fact_ids": ["f_combat"]},
    {"segment_id": "s_dpose", "field": "action_and_relation", "text": "dynamic pose", "fact_ids": ["f_combat"]},
    {"segment_id": "s_ruined_city", "field": "environment_and_props", "text": "ruined city", "fact_ids": ["f_env_ruins"]},
    {"segment_id": "s_collapsed", "field": "environment_and_props", "text": "collapsed building", "fact_ids": ["f_env_ruins"]},
    {"segment_id": "s_rubble", "field": "environment_and_props", "text": "rubble", "fact_ids": ["f_env_ruins"]},
    {"segment_id": "s_dust", "field": "environment_and_props", "text": "dust", "fact_ids": ["f_light"]},
    {"segment_id": "s_dusk", "field": "lighting_and_visual_style", "text": "dusk", "fact_ids": ["f_light"]},
    {"segment_id": "s_amber", "field": "lighting_and_visual_style", "text": "amber", "fact_ids": ["f_light"]},
    {"segment_id": "s_warm", "field": "lighting_and_visual_style", "text": "warm lighting", "fact_ids": ["f_light"]},
    {"segment_id": "s_cinematic", "field": "lighting_and_visual_style", "text": "cinematic lighting", "fact_ids": ["f_style"]},
    {"segment_id": "s_composition", "field": "composition_and_camera", "text": "low angle shot", "fact_ids": ["f_combat"]},
    {"segment_id": "s_leading", "field": "composition_and_camera", "text": "leading lines", "fact_ids": ["f_env_ruins"]},
    {"segment_id": "s_foreground", "field": "composition_and_camera", "text": "foreground framing", "fact_ids": ["f_env_ruins"]},
    {"segment_id": "s_colorgrade", "field": "composition_and_camera", "text": "teal and orange color grade", "fact_ids": ["f_light"]},
    {"segment_id": "s_rimlight", "field": "lighting_and_visual_style", "text": "rim light", "fact_ids": ["f_light"]},
    {"segment_id": "s_volumetric", "field": "lighting_and_visual_style", "text": "volumetric light", "fact_ids": ["f_light"]},
    {"segment_id": "s_filmgrain", "field": "lighting_and_visual_style", "text": "film grain", "fact_ids": ["f_style"]},
    {"segment_id": "s_haze", "field": "environment_and_props", "text": "dusty haze", "fact_ids": ["f_light"]}
  ],
  "complexity": {"subjects": 1, "explicit_relations": 0, "complex_actions": 1, "environment_clusters": 3, "natural_language_bridges": 0},
  "negative_segments": [
    {"segment_id": "neg", "field": "general", "text": "lowres, worst quality, low quality, normal quality, bad anatomy, bad hands, missing fingers, extra fingers, fused fingers, deformed, blurry, out of focus, jpeg artifacts, watermark, text, signature", "fact_ids": ["f_subject"]}
  ]
}
```

## H3 request shapes

- `h3_t2va`: `facts`, `duration_seconds`, `shot_count`, `integrated_multimodal_description` (segments with `[Shot 1]…[Shot N]` markers and `At MM:SS.mmm` cut timestamps), optional `overall_soundscape` / `non_diegetic_music`. Read [references/minimax-h3.md](references/minimax-h3.md) for the shot/sound dialect.
- `h3_ref2va`: adds `references` (list of `{reference_id: "Picture N", owner, resized_width, resized_height}`), `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`. All `Picture N` labels in text must resolve to ordered references. `reference_count` must match the execution stage.

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

Read [references/artifact-and-budgets.md](references/artifact-and-budgets.md) for formulas and exact artifact fields. Pass the production-ready `prompt` dict (from `compile_prompt_artifact`) under `envelope.prompt`, optionally with its `prompt_ref`; never copy only its prompt text into a camera request.
