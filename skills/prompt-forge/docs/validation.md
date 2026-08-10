# Validation rules

Each rule is a proposition the prompt must satisfy. Codes (P1-1,
P2-3, ...) are stable so docs and tests can reference them.

v3 changes from v2:
- Validator operates on concept objects (Subject, Costume, Prop,
  Environment, Atmosphere, Lighting, Frame), not flat string fields.
- `Constraint.anchor_role` (v3) lets a continuity token be checked
  only inside that concept's rendered text. Without anchor_role,
  tokens are checked anywhere in the spec.

## P1 - Visibility

> Every Subject has an identity; every concept field is drawable.

**Check**: `initial_state.subjects` must contain at least one
Subject with non-empty `identity`. Each Transition's trigger and
action must contain at least one physical verb; sentences with only
abstract markers fail. Each Transition's `result` must declare at
least one Subject.

Abstract markers include English emotion/inner-state words ("feel",
"want"), metaphor/decorative words ("seems", "as if"), and moral
adjectives ("epic", "magical"). The Chinese equivalents are
included in the lexicon.

**Violations**: `P1-1` (no subjects), `P1-2` (subject identity
empty), `P1-3` (trigger abstract), `P1-4` (action abstract),
`P1-5` (result has no subjects).

## P2 - Causality

> Every Transition has trigger + action + result.

**Check**: All three fields are non-empty. Video specs must declare
at least one transition.

**Violations**: `P2-0` (no transitions for video), `P2-1` (empty
trigger), `P2-2` (empty action), `P2-3` (empty result state).

## P3 - Continuity

> Every declared Constraint holds in every result State.

**Check**: For each transition, every token in
`Constraint.must_contain` must appear in some text field of the
result state.

When `Constraint.anchor_role` is set, tokens are checked only
inside that concept's rendered text:
- `subject` - Subject.identity / appearance / pose / gesture /
  expression / gaze
- `costume` - Subject.costume[].color / material / garment / condition
  / fit / details
- `prop` - Subject.props[].material / item / condition / details
- `lighting` - Lighting.key / fill / rim / quality / shadow_density
  / contrast / practical
- `environment` / `place` - Environment.place / spatial /
  immediate_surroundings
- `atmosphere` - Environment.atmosphere.haze / particles_* / wind /
  sky

Timeline must be contiguous from 0 to duration.

**Violations**: `P3-1` (first transition not at 0), `P3-2` (gap in
timeline), `P3-3` (duration mismatch), `P3-4` (anchored token
missing from role), `P3-5` (token missing from result state).

## P4 - Completeness

> The spec satisfies the dialect's required dimensions.

**Check**: For each dimension in `dialect.required`, the
corresponding concept field must be non-empty.

**Violations**: `P4-1` (no subjects), `P4-2` (no place), `P4-3` (no
lighting), `P4-4` (no shot), `P4-5` (video without transitions),
`P4-6` (video without positive duration).

## P5 - Density

> Each field carries enough information to be actionable.

**Check**: trigger and action must contain at least 2 word-tokens
each. Video transitions must be >= 0.5 seconds.

**Violations**: `P5-1` (trigger too short), `P5-2` (action too
short), `P5-3` (transition too short).

## How to fix violations

| Code | Typical cause | Fix |
|---|---|---|
| P1-1 | forgot Subject | add a `Subject(identity="...")` to `initial_state.subjects` |
| P1-2 | Subject identity empty | fill in `identity` |
| P1-3 / P1-4 | used abstract verbs | replace "feels" with concrete motion |
| P2-1 / P2-2 / P2-3 | forgot a field | fill in trigger / action / result |
| P3-1 / P3-2 / P3-3 | timeline math error | check start = previous end, end <= duration |
| P3-4 | anchored token missing from role | add the token to a field of the anchored concept |
| P3-5 | token missing from result state | add the token to a result-state field |
| P4-1..P4-4 | missing required concept | fill in the corresponding concept field |
| P4-5 / P4-6 | missing transitions / duration | add them |
| P5-1 / P5-2 | prompt too thin | elaborate each field |
| P5-3 | too many segments | reduce or extend duration |