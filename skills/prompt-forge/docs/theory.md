# Theory: the three invariants of a renderable prompt

A prompt is a specification of a target world (image) or world-sequence
(video). For the model to render it, the prompt must satisfy three
invariants. These are derived from first principles, not enumerated.

## Invariant A ¡ª Visibility

Every sentence describes something a storyboard artist can draw.

What counts as drawable: subjects, props, places, lights, motions,
textures, sounds, camera viewpoints.

What does not count: pure emotions, intentions, moral judgments,
metaphors. ("She felt sad", "He wanted to leave", "Time flows like
water".)

A sentence is tested structurally: it must contain at least one
concrete noun and at least one physical verb. If a sentence has many
emotion/intention markers but no physical verb, it fails. The check is
intentionally permissive about new words (we want this list to stay
small) and strict about structure.

## Invariant B ¡ª Causality

Every change has a trigger, an action, and a result.

A change "she turns around" alone is incomplete. What triggered the
turn? A sound? A name? A memory? Without a trigger, the model will
fill the gap with random motion. Without an action, there is no
visible behavior. Without a result, there is no terminal state.

This is encoded as the `Transition` dataclass: every transition has
`trigger`, `action`, and `result` fields. Empty values fail at
validation time (P2).

## Invariant C ¡ª Continuity

Every declared invariant must hold in every visible state.

If the user says "the swordswoman wears a red robe throughout", that
fact must appear in the initial state and in every transition's
result state. The model cannot be trusted to remember continuity on
its own; the validator enforces it.

This is encoded as the `Constraint` dataclass and validated by P3.

## Why these three

- Visibility fails first: the model can't draw what isn't described.
- Causality fails next: the model will invent motion to fill gaps.
- Continuity fails last: the model drifts between frames without help.

Together they ensure the prompt is renderable, faithful, and continuous.
