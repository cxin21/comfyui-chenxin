# Authoring contract

## Request shape

```json
{
  "facts": [{"fact_id": "...", "value": "...", "origin": "...", "locked": bool, "owner": "...", "dimension": "..."}],
  "positive_segments": [{"segment_id": "...", "field": "...", "text": "...", "fact_ids": ["..."], "render_weight": float | null}],
  "complexity": {"subjects": int, "explicit_relations": int, "complex_actions": int, "environment_clusters": int, "scene_descriptions": int},
  "negative_segments": [{"segment_id": "...", "field": "...", "text": "...", "fact_ids": ["..."], "render_weight": float | null}],
  "exclusion_groups": int,
  "variant": "base"
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
| 1 | `protocol_prefix` | highest (enforced baseline) | quality + meta + year + safety tags |
| 2 | `count` | high | subject count |
| 3 | `character` | high | subject identity / IP character |
| 4 | `series` | high | source work / franchise |
| 5 | `artist` | medium-high | `@artist`, weighted, mixable |
| 6 | `appearance` | medium | hair, eyes, body, clothing |
| 7 | `general` | medium | action/expression + five aesthetic layers, ordered (below) |
| 8 | `environment` | medium | location, props, weather |
| 9 | `scene_description` | lowest | ≤1 natural-language bridge, after a period |

`general` internal order: action/expression → composition → lighting → palette → camera → mood.

## One tag per segment

Every `positive_segments[].text` and every `negative_segments[].text` is **exactly one tag**. Comma-separated lists are rejected.

## Reserved namespaces

- `score_N` — exactly `score_1` through `score_9`, underscore kept
- `year YYYY` — four digits
- `@artist` — `@` prefix, must resolve
- Ordinary tags — spaces, never underscores

## Positive slots (anima)

`protocol_prefix`, `count`, `character`, `series`, `artist`, `appearance`, `general`, `environment`, `scene_description`

Ordered front-weighted; `general` internally orders action/expression → composition → lighting → palette → camera → mood.

## Negative slots (anima)

`quality_baseline`, `anatomy_and_structure`, `technical_defects`, `user_exclusions`

## Weighted segment

A segment may set `render_weight: float | None`. When set, it renders `(text:weight)`. Dedup/audit/compression operate on the de-weighted text.

## Compressibility

- **Mandatory**: segments linked to any protected fact
- **Compressible**: segments linked only to `agent_embellishment` facts
- Agent-authored segments MUST link only to agent facts

## Bridge

- Count ≤ 1
- Position = end of positive stream
- Dimensions allowed: `ownership | spatial_relation | causal_action | action_result | relation`
- No overlap with tag segments' fact_ids
