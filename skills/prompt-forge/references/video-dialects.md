# Video dialects

Video prompting is temporal direction, not an image prompt with the word
"moving" appended.

## Required semantic layers

1. Shot/framing: what the camera sees at the start.
2. Subject and primary action: one dominant action per shot.
3. Motion: direction, speed/amplitude, endpoint, and physically visible response.
4. Camera: one compatible move unless the recipe explicitly supports a sequence.
5. Timeline: ordered beats or persistent continuity constraints.
6. Scene, lighting, color, style and optional audio.

For text-to-video, subject, action, motion and camera are required. For
image-to-video, the image anchors appearance and composition; prompt the change,
motion and camera rather than redundantly rebuilding the first frame.

## Temporal rules

- Use present-tense visible verbs.
- Give each motion an endpoint: "turns toward camera and stops" is more stable
  than "turning".
- State persistent conditions explicitly: rain continues, wardrobe stays the
  same, background geometry remains fixed.
- For multiple events, use `timeline` beats such as `0-2s`, `2-5s`, or
  `first... then...`; use model-specific multi-shot syntax only when its recipe
  supports it.
- Avoid competing camera moves, simultaneous unrelated actions, and unbounded
  motion that invites looping.

## Audio

Only add audio when the model supports it. Separate dialogue, sound effects,
ambience and music. Quote spoken lines; describe who speaks and when. Audio is a
temporal constraint, not decorative prose.

## References

- `image-to-video`: reference purpose is normally `first-frame` or `identity`.
- `first-last-frame-to-video`: describe only the bridge motion and continuity.
- `reference-to-video`: identify reference indices exactly in the syntax owned by
  that recipe; do not transfer `@ImageN` syntax between vendors.
- `video-to-video`: name the edit and locked invariants; do not regenerate the
  source identity by prose alone.

## Model-specific authority

The recipe's `dialect_block` overrides generic ordering, negative policy, prompt
length, camera syntax and reference syntax. When the recipe is ambiguous, surface
the uncertainty instead of borrowing rules from a similar vendor.
