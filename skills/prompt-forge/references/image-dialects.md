# Image dialects

## Tag dialect

Use for recipes whose dialect explicitly requires Danbooru or comma-separated
tags.

1. Preserve the recipe's required quality/control tokens verbatim and mark them
   as recipe-origin quality values.
2. Order semantic tags by subject, defining traits, action, scene,
   composition/camera, lighting/color, style/medium, mood.
3. Give each semantic concept its own candidate. Never concatenate multiple
   concepts into a fabricated compound.
4. Validate candidates with `tag_lookup.py --queries ... --exact` or let
   `prompt_compile.py` perform the same check.
5. If an explicit fact has no validated representation, find a real semantic
   equivalent or stop for clarification. Do not silently drop it.

## Natural-language dialect

Use for Flux, Qwen, GPT Image and other prose-first recipes.

- Lead with subject and concrete action, then scene and composition.
- Add camera/lens, lighting/color and style only when supported by intent or
  recipe. Prefer concrete visible properties over praise such as "stunning".
- One coherent style is better than a list of unrelated style names.
- Quote literal on-image text exactly and preserve case/punctuation when the
  model recipe supports text rendering.
- Phrase exclusions positively when negative prompts are unsupported, for
  example "an uncluttered background" rather than a hidden negative field.

## Editing and references

- Separate what must change from what must remain invariant.
- Bind each reference to one purpose. Identity, style and composition references
  are not interchangeable.
- For image editing, use an imperative edit instruction and state invariants:
  identity, pose, framing, background geometry, colors, or text as applicable.
- Do not re-describe reference facts as new guesses when the source image is the
  authority.
