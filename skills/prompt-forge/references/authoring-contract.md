# Anima authoring contract

The hard, tool-enforced rules for `task="anima"` (via `compile_prompt_artifact`).
Everything here is what the tool checks. Author to satisfy it in one pass — read this
file before writing any segment. For H3 requests see [minimax-h3.md](minimax-h3.md).

## Request shape

```json
{
  "facts": [{"fact_id": "…", "value": "…", "origin": "…", "locked": true, "owner": "…", "dimension": "…"}],
  "positive_segments": [{"segment_id": "…", "field": "…", "text": "…", "fact_ids": ["…"]}],
  "complexity": {"subjects": 1, "explicit_relations": 0, "complex_actions": 0, "environment_clusters": 0, "natural_language_bridges": 0},
  "negative_segments": [{"segment_id": "…", "field": "…", "text": "…", "fact_ids": ["…"]}],
  "exclusion_groups": 0
}
```

## Fact ledger rules

- `origin` is one of `user_locked | user_explicit | necessary_inference | agent_embellishment`.
- `locked: true` **if and only if** `origin == "user_locked"`; every other origin is `locked: false`.
- `fact_id` must be unique and non-empty.
- Treat user facts (`user_locked`, `user_explicit`, `necessary_inference`) as protected even when unlocked.

## One tag per segment — both streams (the #1 failure)

**Every `positive_segment.text` and every `negative_segment.text` is exactly one tag.**
The tool joins segment texts with `", "`, so a segment holding a comma-separated list is
treated as one malformed tag and rejected (`invalid_protocol_tag`). This applies to the
**negative stream too**: do not write `"lowres, worst quality, low quality"` in one segment —
write three segments. Reserved score tags in the negative follow the same rule: a segment
`"score_4, score_5, score_6"` is rejected; write `score_4`, `score_5`, `score_6` as separate
segments.

## Reserved namespaces

- `score_N` — exactly `score_1` through `score_9`, underscore kept. Any other `score_` string
  (e.g. `score_10`, or a comma list starting with `score_`) → `invalid_protocol_tag`.
- `year YYYY` — exactly four digits (`year 2026`).
- `@artist` — artist tags require the `@` prefix and must resolve to a known artist tag.
- Ordinary tags use spaces, never underscores: `blue_hair` → `wrong_underscore_form`.

## Field enums

`positive_segments[].field` must be one of:
`quality_meta_year_safety`, `count`, `subject_anchor`, `character`, `copyright`, `artist`,
`general`, `tag`, `attribute_binding`, `action_and_relation`, `composition_and_camera`,
`environment_and_props`, `lighting_and_visual_style`, `natural_language_bridge`.
Anything else → `unsupported_positive_field`.

`negative_segments[].field` must be one of:
`official_quality_baseline`, `anatomy_count_structure_errors`, `image_technical_defects`,
`user_exclusions`, `general`. Anything else → `unsupported_negative_field`.

## Segment ordering (rendered tag order)

quality / meta / year / safety → count → character → copyright → artist → general → bridge.
The tool re-orders by field; keep your segments in this order anyway so the audit is readable.

## Complexity and bridges

- `complexity.natural_language_bridges` must equal the number of `natural_language_bridge`
  segments, and that count is at most 1.
- A bridge segment's `fact_ids` resolve to facts whose `dimension` is one of
  `ownership | spatial_relation | causal_action | action_result | relation`, and its `fact_ids`
  must not overlap the tag segments' `fact_ids`.
- `subjects`, `explicit_relations`, `complex_actions`, `environment_clusters` must match what
  you actually render — understating them starves the budget, overstating them is a lie.

## Attribution — the compressible pool

Compressibility is a property of a segment's facts:

- **Compressible**: every fact the segment links is `agent_embellishment`.
- **Mandatory**: any fact the segment links is protected (`user_locked`, `user_explicit`,
  `necessary_inference`).

Authoring rules that follow (these keep budget conflicts solvable):

1. Link every segment to the facts it renders. Provenance is not optional.
2. **Agent-authored segments link agent facts only.** Never link an agent-authored segment —
   including any agent-added negative segment — to a protected fact. Doing so freezes the
   segment into the mandatory pool; a budget conflict then has no escape hatch except touching
   protected facts, which the tool will not do automatically.
3. If a tag renders a user fact plus an agent flourish, **split it**: one segment for the user
   fact, one agent-only segment for the flourish. Only the flourish is compressible.
4. In the negative stream, the three standard baselines (quality / anatomy / technical defects)
   may link protected facts — they are the mandatory floor. Anything agent-added beyond that
   links agent facts only.

## Segment weights

`priority` default 1.0 (positive, finite), `adherence_risk` default 0.5,
`source_confidence` default 0.9. `fact_ids` must be non-empty.

## Minimal contract-correct example

Three protected user facts and one agent flourish; the flourish is its own segment so it stays
compressible; the negative is split into single-tag segments.

```json
{
  "facts": [
    {"fact_id": "f_count", "value": "1boy", "origin": "user_locked", "locked": true, "owner": "user", "dimension": "count"},
    {"fact_id": "f_subject", "value": "solo male wanderer", "origin": "user_explicit", "locked": false, "owner": "user", "dimension": "subject"},
    {"fact_id": "f_style", "value": "cinematic lighting", "origin": "user_locked", "locked": true, "owner": "user", "dimension": "style"},
    {"fact_id": "f_flourish", "value": "scarred tattered clothing", "origin": "agent_embellishment", "locked": false, "owner": "agent", "dimension": "appearance"}
  ],
  "positive_segments": [
    {"segment_id": "s_score9", "field": "quality_meta_year_safety", "text": "score_9", "fact_ids": ["f_style"]},
    {"segment_id": "s_count", "field": "count", "text": "1boy", "fact_ids": ["f_count"]},
    {"segment_id": "s_solo", "field": "character", "text": "solo", "fact_ids": ["f_subject"]},
    {"segment_id": "s_male", "field": "character", "text": "male", "fact_ids": ["f_subject"]},
    {"segment_id": "s_cinematic", "field": "lighting_and_visual_style", "text": "cinematic lighting", "fact_ids": ["f_style"]},
    {"segment_id": "s_flourish", "field": "character", "text": "scar", "fact_ids": ["f_flourish"]}
  ],
  "complexity": {"subjects": 1, "explicit_relations": 0, "complex_actions": 0, "environment_clusters": 0, "natural_language_bridges": 0},
  "negative_segments": [
    {"segment_id": "neg_s4", "field": "official_quality_baseline", "text": "score_4", "fact_ids": ["f_style"]},
    {"segment_id": "neg_lowres", "field": "official_quality_baseline", "text": "lowres", "fact_ids": ["f_style"]},
    {"segment_id": "neg_worst", "field": "official_quality_baseline", "text": "worst quality", "fact_ids": ["f_style"]},
    {"segment_id": "neg_anat", "field": "anatomy_count_structure_errors", "text": "bad anatomy", "fact_ids": ["f_subject"]},
    {"segment_id": "neg_tech", "field": "image_technical_defects", "text": "blurry", "fact_ids": ["f_subject"]}
  ],
  "exclusion_groups": 0
}
```
