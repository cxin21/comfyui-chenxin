# Image prompt dialects

Image prompts express the same evidence through different linguistic forms. Dialect changes wording, not facts.

## Tag form

- Use exact validated semantic tags and approved aliases only.
- Keep recipe control tokens separate from semantic tags.
- Order concepts coherently: subject, defining traits, action, setting, composition, lighting, medium, and mood.
- If an explicit fact lacks a validated tag, retain the unresolved fact for clarification; do not invent a near match.

## Natural-language form

- State the subject, defining identity cues, and visible action in clear sentences.
- Describe setting and composition from evidence before optional visual language.
- Use concrete medium, palette, lighting, and texture terms supported by `style_evidence`.
- Quote visible text exactly when it is evidence.
- Express exclusions only in the dialect-supported field.

## Reference-led edits

State the requested change and the invariants separately. Bind each reference to a declared role such as identity, composition, palette, or edit source. Identity, pose, framing, scene geometry, props, and visible text remain unchanged unless the request explicitly changes them.