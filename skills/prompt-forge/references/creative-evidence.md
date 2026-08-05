# Creative evidence mapping

This guide is a field-level synthesis of possible source-to-field relationships. The three named files are source identifiers only. Their contents were not supplied in this checkout, so this guide does not claim what any file contains.

## Availability boundary

Each named source may populate the listed fields only when provided as a readable excerpt or approved structured input. No content is inferred or attributed without a supplied excerpt. A filename, title, or expected document genre is never evidence by itself.

## Conditional source mapping

| Source identifier | Potential destination fields | Condition |
|---|---|---|
| `前期剧情拆解模板.md` | `identity`, `plot_facts`, `shot_plan`, `dialogue`, `continuity_locks`, `uncertainty` | May populate only fields directly supported by provided source text. |
| `提示词公开版本.txt` | `art_direction`, `style_evidence`, `composition`, `lighting`, `motion_quality`, `uncertainty` | May populate only explicitly stated visual-language guidance when provided. |
| `影视资产.md` | `character_assets`, `environment_assets`, `prop_assets`, `props`, `identity`, `continuity_locks`, `uncertainty` | May populate only asset facts and roles present in provided source text. |

The table is a routing allowance, not a statement that a source contains every listed field.

## Provenance for supplied excerpts

Every populated item records:

- `source_id`: the supplied file or source identifier
- `source_section`: the supplied heading, scene, shot, or entry label
- `source_text`: the minimal supplied excerpt that supports the value
- `origin`: explicit or advisory
- `confidence`: known or uncertain

If the excerpt is missing, unreadable, ambiguous, or silent about a field, leave that field empty and add a precise item to `uncertainty`. Do not reconstruct likely template sections or likely asset details.

## Evidence routing

- `shared_known`: explicit facts supported by the request or a supplied excerpt.
- `user_known_agent_unknown`: facts the user says exist but has not supplied.
- `assistant_known_user_unknown`: visual-language options clearly labeled as advisory.
- `joint_unknown`: unresolved facts that require clarification.
- `locked_facts`: supplied identity, plot, prop, dialogue, or spatial facts that must survive every variant.
- `style_evidence`: supplied or explicitly requested visual attributes.
- `asset_refs`: supplied character, environment, or prop references with declared roles.
- `uncertainty`: missing timing, ownership, appearance, role, or causality.

## Style-invariance policy

protected_fields: identity, plot_facts, props, continuity_locks
style_fields: medium, palette, lighting, texture, camera_feel, motion_quality

For two variants built from the same supplied evidence, every protected field is copied unchanged. Only listed style fields may differ. Art direction cannot supply a missing character trait, event, prop, line of dialogue, location, or continuity condition.