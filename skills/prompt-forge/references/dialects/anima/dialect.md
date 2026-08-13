# Anima authoring dialect

> The model-native form and ordering for Anima still images. The tool-enforced contract —
> one tag per segment (both streams), reserved namespaces, attribution, fields, weights — is
> [../../shared/authoring-contract.md](../../shared/authoring-contract.md). Preflight your tags
> against the dictionary before compiling: [../../quality/dictionary-preflight.md](../../quality/dictionary-preflight.md).
> Anima's complete tag vocabulary lives in [vocabulary/](vocabulary/).

## Native form

Positive prompt, in this exact order (front-weighted):

1. `protocol_prefix` — quality/meta/year/safety baseline
2. `count` — subject count
3. `character` — subject identity
4. `series` — source work
5. `artist` — `@artist`, weighted, mixable
6. `appearance` — hair/eyes/body/clothing
7. `general` — action/expression, then composition → lighting → palette → camera → mood/texture
8. `environment` — location/props/weather
9. `scene_description` — ≤1 natural-language bridge, after a period

Separate tags with `, ` (comma-space). Lowercase + spaces for ordinary tags; underscores only in `score_N`. Artist tags require `@`. A weighted tag renders `(text:weight)`.

## Quality prefix (enforced baseline)

| Tier | Trigger | Prefix |
|---|---|---|
| Standard | default (Base / Turbo) | `masterpiece, best quality, score_7, safe` |
| Artist-led | `@artist` present, style should dominate | `best quality, safe` |
| Aesthetic | variant = Aesthetic | `best quality, safe` |

Use `score_7`, not `score_8/9` (they stiffen composition). The two quality systems (human + score) may be used alone, together, or neither.

The official 4-tag prefix is authored as **four separate `protocol_prefix` segments** — one tag per segment is the contract. Never write the prefix as a single comma-list segment: `masterpiece, best quality, score_7, safe` in one segment trips the underscore-form check (the string contains the underscore in `score_7` but does not itself start with `score_`, so the audit rejects it as `wrong_underscore_form`).

## Negative baseline

`worst quality, low quality, score_1, score_2, score_3` + `blurry, jpeg artifacts, chromatic aberration` + anatomy/count defects as needed + user exclusions. Keep it lean — Anima's negative is temperamental.

## Weight calibration

| Target | Range |
|---|---|
| ordinary tag | 1.0 – 2.0 |
| artist tag | 2.0 – 4.0 (whole block `(:2.0)` allowed) |
| window | 0.0 – 4.0 |

## Artist mixing

1. comma list: `@a, @b`
2. natural language: `using artist @A and @B to draw a picture`
3. weighted block: `Mixed style of following artists: (@artist1, @artist2:2.0)`
4. inline weights: `(@a:2.0), (@b:0.8)`

Warning: anime character names carry style bias — raise artist weight or bind to distinguishing features.

## Variants

- `base` (default, what camera-image pins): full quality stack.
- `aesthetic`: drop `score_*`; keep `best quality, safe`.
- `turbo`: full quality stack; CFG 1, 8–12 steps.

## Sparse input

When the user gives little detail, complete it by coherent inference (see `../../shared/aesthetic-coverage.md`) — five coherence layers, all as removable `agent_embellishment`.

## Vocabulary

For complete tag selection, consult the [vocabulary](vocabulary/) cluster:

- [vocabulary/README.md](vocabulary/README.md) — positioning, field mapping, 9-slot structure
- [vocabulary/count-identity.md](vocabulary/count-identity.md) — count, IP, body type, age difference
- [vocabulary/appearance.md](vocabulary/appearance.md) — hair, eyes, body, non-human, marks
- [vocabulary/clothing.md](vocabulary/clothing.md) — garments + 7-dim modifications + contrast
- [vocabulary/pose-action.md](vocabulary/pose-action.md) — single / dual / multi / storyboard
- [vocabulary/expression.md](vocabulary/expression.md) — emotions + intensity Lv1-4 + reactions
- [vocabulary/camera-shot.md](vocabulary/camera-shot.md) — framing, angle, POV, composition
- [vocabulary/scene-environment.md](vocabulary/scene-environment.md) — locations + risk matrix + weather
- [vocabulary/detail-mood.md](vocabulary/detail-mood.md) — texture + mood + tag blacklist
- [vocabulary/special-themes.md](vocabulary/special-themes.md) — cross-slot theme recipes

## Built-in dictionary

Use the bundled read-only `knowledge/anima/tags.sqlite`. It contains the full locked Gelbooru canonical snapshot plus Danbooru compatibility aliases under deterministic precedence. Runtime retrieval is offline and bounded. The manifest records immutable revisions, source hashes, row counts, database hash, builder hash, licenses, and redistribution decisions.

Do not scrape at runtime, add a user tag overlay, or use a local checkpoint/LoRA vocabulary layer. Maintainers update the dictionary only by acquiring pinned source snapshots, passing the redistribution gate, rebuilding twice byte-identically, updating the manifest, and rerunning the release verifier.

## Token limit

The image model's physical tokenizer limit is 32,768 tokens. Prompt Forge uses much smaller calibrated quality limits; physical capacity is not a recommendation to fill the context.
