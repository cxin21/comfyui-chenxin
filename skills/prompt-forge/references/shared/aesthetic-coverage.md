# Aesthetic coverage (mandatory retrieval)

The five aesthetic layers are **not** a checklist of questions to ask the model. They are a **mandatory retrieval** from `knowledge/aesthetics/` that the author must do before writing a single tag.

## The five required sources

For every Anima prompt, the author must read and apply terms from:

1. [composition.md](../../knowledge/aesthetics/composition.md) — framing, angle, layout
2. [lighting.md](../../knowledge/aesthetics/lighting.md) — quality, direction, source
3. [palette.md](../../knowledge/aesthetics/palette.md) — named grades and palettes
4. [camera.md](../../knowledge/aesthetics/camera.md) — render medium and optical style
5. [mood-texture.md](../../knowledge/aesthetics/mood-texture.md) — mood, atmosphere, particles

Plus the override layer: [anti-patterns.md](../../knowledge/aesthetics/anti-patterns.md).

## How to apply

1. **Read once per authoring session.** Open all six files; do not author from memory.
2. **Pick ≥ 1 term per layer** from the bundled knowledge; bind to a fact in the ledger as `agent_embellishment`. Five facts together give the prompt design intent.
3. **Use a recipe when the genre is named.** When the user's request maps to a recipe under `references/dialects/anima/recipes/` (film-noir, cyberpunk-neon, wes-anderson-pastel, helmut-newton-bw, ghibli-aesthetic, wuxia-ink), pull its pre-composed 5-layer composition.
4. **Cite the source.** Each aesthetic fact carries `source_ref` of form `<file>.md#<cluster>:<term>` — e.g., `composition.md#framing:wide-shot`.
5. **Run anti-patterns as override.** Patterns in §2 of `anti-patterns.md` must be removed before compiling, regardless of what the five layers suggest.
6. **Preflight before compile.** Verify every aesthetic tag against the bundled Anima dictionary via `scripts/tag-validate.py`; unverified tags from memory must be dropped.

## Coverage check

Before compiling, the ledger must contain ≥ 1 fact bound to each of `composition.md`, `lighting.md`, `palette.md`, `camera.md`, `mood-texture.md`. A prompt that compiles but lacks any one layer ships flat — the audit will not catch this; the author must.

## When to ignore

Skip aesthetic retrieval when:
- prompt is text-only (no visual)
- prompt is a sticker / icon / emoji style
- prompt is a schematic / diagram / chart
