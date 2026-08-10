# Specification: the data shapes

A `Specification` is what the LLM authors; the projector consumes it.
Every field exists because one of the three invariants (visibility,
causality, continuity) demands it.

v3 introduces typed concept objects in place of v2's flat string
fields. Each concept is a frozen dataclass with named axes; the
projector expands each axis into dialect-appropriate prose.

## Subject

Who is rendered.

| Field | Type | Notes |
|---|---|---|
| identity | str | P1 requires non-empty. Drawable person / creature / entity. |
| appearance | str | Optional: surface details (scars, age cues, hair). |
| age | str | Optional: "in her late thirties", "elderly". |
| pose | str | Optional: static body posture. |
| gesture | str | Optional: deliberate body movement ("hand on hilt"). |
| expression | str | Optional: facial expression. |
| gaze | str | Optional: where the subject is looking. |
| micro_action | str | Optional: mid-motion cue ("mid-breath, chest barely rising"). |
| costume | tuple[Costume, ...] | Optional: one or more garments. |
| props | tuple[Prop, ...] | Optional: one or more carried objects. |

## Costume

One garment.

| Field | Type | Notes |
|---|---|---|
| garment | str | P1 requires non-empty for the costume to render. |
| material | str | Optional: "hand-spun silk", "leather". |
| color | str | Optional: "iron-oxide vermilion". |
| condition | str | Optional: "worn, frayed at the hem". |
| fit | str | Optional: "loose, layered, ankle-length". |
| details | str | Optional: "embroidered phoenix at the collar". |

## Prop

One carried or staged object.

| Field | Type | Notes |
|---|---|---|
| item | str | P1 requires non-empty. |
| material | str | Optional. |
| condition | str | Optional. |
| details | str | Optional. |

## Environment

Where the scene takes place.

| Field | Type | Notes |
|---|---|---|
| place | str | P1 requires non-empty for the environment to render. |
| spatial | str | Optional: spatial layout ("subject 6m from stone lantern"). |
| immediate_surroundings | tuple[str, ...] | Optional: nearby objects / features. |
| ambient | str | Optional: tactile / olfactory / sonic environment. |
| atmosphere | Atmosphere | Optional: depth-layered air. |

## Atmosphere

What the air is doing.

| Field | Type | Notes |
|---|---|---|
| haze | str | Optional: volume cue ("thin ground fog 0.3m tall"). |
| particles_foreground | tuple[str, ...] | Optional: close particles. |
| particles_midground | tuple[str, ...] | Optional: mid-depth particles. |
| particles_background | tuple[str, ...] | Optional: distant particles. |
| wind | str | Optional: motion cue. |
| sky | str | Optional: sky / ceiling. |

## Lighting

How the scene is lit. v3 decomposes lighting into named roles; the
projector emits each non-empty role as its own sentence.

| Field | Type | Notes |
|---|---|---|
| key | str | Optional: main light (direction, temperature, quality). |
| fill | str | Optional: shadow-side softening. |
| rim | str | Optional: back / separation light. |
| practical | tuple[str, ...] | Optional: on-set light sources (lanterns, candles). |
| quality | str | Optional: hard / soft, specular / diffused. |
| shadow_density | str | Optional: "deep shadows, crushed blacks". |
| contrast | str | Optional: "high contrast, low-key". |

## Frame

How we capture the scene.

| Field | Type | Notes |
|---|---|---|
| shot | str | Optional but commonly required by dialects. |
| camera_height | str | Optional: "eye-level, slight low". |
| camera_angle | str | Optional: "three-quarter from the right". |
| lens | str | Optional: "85mm portrait, f/1.4". |
| depth_of_field | str | Optional: "shallow, focus locked on eyes". |
| composition | str | Optional: "subject on left third". |
| foreground | tuple[str, ...] | Optional: foreground-layer elements. |
| midground | tuple[str, ...] | Optional: midground-layer elements. |
| background | tuple[str, ...] | Optional: background-layer elements. |
| aspect_ratio | str | Optional: "3:2", "16:9". |
| quality | tuple[str, ...] | Optional: quality keywords. |

## State

A snapshot of what is visible at one moment.

| Field | Type | Notes |
|---|---|---|
| subjects | tuple[Subject, ...] | WHO. Empty State is render-time error. |
| environment | Environment | WHERE. |
| lighting | Lighting | LIGHT. |
| frame | Frame | FRAME. |

## Transition

A directed change from one State to another.

| Field | Type | Notes |
|---|---|---|
| start | float (seconds) | `>= 0`. First transition must be 0. |
| end | float (seconds) | `> start`. Contiguous with next. |
| trigger | str | The cause of the change. |
| action | str | What the subject did. |
| result | State | The visible state after the change. |
| camera_motion | str | Camera move (distinct from body motion). |
| sound | str | Ambient sound for this segment. |
| dialogue | tuple | (speaker, line) pairs. |

`duration()` returns `end - start`.

## Constraint

An invariant that must hold across transitions. v3 reads
`must_contain` directly; every token must appear in the result
state for the constraint to hold.

| Field | Type | Notes |
|---|---|---|
| must_contain | tuple[str, ...] | P3: tokens, all of which must appear in every result state. |
| kind | Literal | identity / direction / lighting / exclusion / other. |
| description | str | Human-readable rendering; auto-generated from must_contain when not provided. |
| anchor_role | Optional[str] | v3: when set, tokens are checked only inside that concept's rendered text. One of: subject, costume, prop, lighting, place, environment, atmosphere. |

## Style

Visual-language envelope. Advisory only.

| Field | Type | Notes |
|---|---|---|
| medium | str | FORM |
| rendering | str | FORM |
| art_movement | str | FORM |
| texture | str | FORM |
| palette | str | PALETTE |
| mood | str | PALETTE |
| camera_feel | str | PALETTE |
| motion_quality | str | PALETTE |
| directives | tuple[str, ...] | v3: free-form render cue stack ("matte stock", "low-key tungsten key", "shallow DOF"). |

## Reference

| Field | Type | Notes |
|---|---|---|
| index | int | 1-based. |
| role | str | "identity" / "palette" / "nine-grid" / etc. |

## Specification

The root object.

| Field | Type | Required | Notes |
|---|---|---|---|
| modality | `"image"` or `"video"` | yes | |
| initial_state | State | yes | The t=0 visible state. |
| transitions | tuple[Transition, ...] | video only | Empty for image. |
| constraints | tuple[Constraint, ...] | (advisory) | Continuity locks. |
| style | Style or None | (advisory) | Visual language. |
| duration | float or None | video only | Total seconds. |
| references | tuple[Reference, ...] | (advisory) | For dialects with ref conventions. |
| literal_text | tuple[str, ...] | (advisory) | Visible-text rendering (ideogram / qwen_image / krea_2). |
| h3_flow | `"drama"` / `"action"` / `"storyboard"` or None | minimax_h3 only | |
| extras | tuple[(key, value), ...] | (advisory) | Dialect-specific overrides. |
| negative | tuple[str, ...] | (advisory) | Tag-form image dialects only. v3 fix. |

A Specification is immutable. To change a field, construct a new one
with `dataclasses.replace`.

## Evidence integration

When `compile(spec, dialect_id, evidence)` is called with non-empty
`evidence.locked_facts`, the compile entry point synthesises
`Constraint(must_contain=_tokens_of(fact), kind="identity",
description=fact)` for each fact and appends them to
`spec.constraints`. This means locked facts participate in P3
enforcement exactly like user-declared constraints.