# Authoring contract

## Request shape

```json
{
  "facts": [{"fact_id": "...", "value": "...", "origin": "...", "locked": bool, "owner": "...", "dimension": "..."}],
  "positive_segments": [{"segment_id": "...", "field": "...", "text": "...", "fact_ids": ["..."]}],
  "complexity": {"subjects": int, "explicit_relations": int, "complex_actions": int, "environment_clusters": int, "natural_language_bridges": int},
  "negative_segments": [{"segment_id": "...", "field": "...", "text": "...", "fact_ids": ["..."]}],
  "exclusion_groups": int
}
```

## Fact ledger

- `origin` ∈ `user_locked | user_explicit | necessary_inference | agent_embellishment`
- `locked: true` ⟺ `origin == "user_locked"`
- User facts (`user_locked`, `user_explicit`, `necessary_inference`) are protected even when `locked: false`

## Slot weight (前重后轻 — front-weighted)

Positive segments are rendered in this order; **earlier fields carry higher implicit weight**.

| Position | Field | Weight | Purpose |
|---|---|---|---|
| 1 | `quality_meta_year_safety` | highest | quality tags, year, safety |
| 2 | `count` | high | subject count |
| 3 | `character` | high | subject identity |
| 4 | `copyright` | high | IP |
| 5 | `artist` | medium | @artist |
| 6 | `general` | medium | free visual semantics |
| 7 | `composition_and_camera` | medium | framing, lens |
| 8 | `environment_and_props` | medium | scene, props |
| 9 | `lighting_and_visual_style` | medium | light, color, mood |
| 10 | `natural_language_bridge` | lowest | bridge at end |

## One tag per segment

Every `positive_segments[].text` and every `negative_segments[].text` is **exactly one tag**. Comma-separated lists are rejected.

## Reserved namespaces

- `score_N` — exactly `score_1` through `score_9`, underscore kept
- `year YYYY` — four digits
- `@artist` — `@` prefix, must resolve
- Ordinary tags — spaces, never underscores

## Positive field enums

`quality_meta_year_safety`, `count`, `subject_anchor`, `character`, `copyright`, `artist`, `general`, `tag`, `attribute_binding`, `action_and_relation`, `composition_and_camera`, `environment_and_props`, `lighting_and_visual_style`, `natural_language_bridge`

## Negative field enums

`official_quality_baseline`, `anatomy_count_structure_errors`, `image_technical_defects`, `user_exclusions`, `general`

## Compressibility

- **Mandatory**: segments linked to any protected fact
- **Compressible**: segments linked only to `agent_embellishment` facts
- Agent-authored segments MUST link only to agent facts

## Bridge

- Count ≤ 1
- Position = end of positive stream
- Dimensions allowed: `ownership | spatial_relation | causal_action | action_result | relation`
- No overlap with tag segments' fact_ids
