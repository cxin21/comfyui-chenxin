# Intent and Relation Graph

This reference defines the typed input seam for the Anima-specific skill.

## PromptBrief

`IntentParser` produces a `PromptBrief` containing:

```text
facts[], exclusions[], locked_segments[], subjects[], relations[],
scene, style, lighting, camera, inferred[], unknowns[], notes, source_priority
```

The implementation may derive scene/style/lighting/camera/inferred/unknowns/notes
from the single fact ledger. Do not duplicate facts to populate those views.

Each fact retains `value`, `kind`, `source`, `locked`, `confidence`, `user_text`,
`subject_id`, `representation_hint`, and `notes`:

```text
kind: explicit | inferred | unknown
source: user | local_model | official | community | default
representation_hint: auto | tag | prose
```

The Anima variant's mandatory quality terms enter the Brief as official model
facts with a reason such as `required_by_anima_variant`. User-requested quality
terms remain user facts. This distinction must survive into segment provenance.

Preserve triggers, wildcards, weights, and locked segments as opaque source text.
Classify them, but never expand, normalize, or remove them.

## Typed relations

Relations come from explicit `RelationClaim` values or structured subject/fact
IDs. Never parse a free-form notes string to recover a relation.

Supported relation types include:

```text
has_attribute, performs, located_at, interacts_with, occludes, faces,
contains, uses_style, uses_lighting, uses_camera,
receives_or_is_target_of, left_of, right_of, in_front_of, behind,
near, far, not_interacting
```

Actions preserve ownership and targets:

```text
subject A --performs--> action X
subject B --receives_or_is_target_of--> action X
```

## VisualRelationGraph

The graph is internal reasoning and inspection data, never the Anima prompt. Its
nodes are `subject`, `attribute`, `action`, `scene`, `style`, `lighting`,
`camera`, and `region`.

Build scene `contains` and `uses_*` edges only from typed facts. Do not add a
location, target, interaction, occlusion, or causal edge because it seems likely.

For two or more subjects, attempt relative position, action ownership,
interaction or explicit non-interaction, and any user-mentioned foreground,
background, or occlusion. Missing relations produce advisories, not guesses.
