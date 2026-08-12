# Anima authoring dialect

> The model-native form and ordering for Anima still images. The tool-enforced contract —
> one tag per segment (both streams), reserved namespaces, attribution, fields, weights — is
> [../../shared/authoring-contract.md](../../shared/authoring-contract.md). Preflight your tags
> against the dictionary before compiling: [../../quality/dictionary-preflight.md](../../quality/dictionary-preflight.md).
> Anima's complete tag vocabulary lives in [vocabulary/](vocabulary/).

## Native form

Build the positive prompt in this order:

1. quality, meta, year, and safety;
2. subject count;
3. character;
4. copyright;
5. artist;
6. general visual semantics;
7. at most one necessary natural-language bridge.

Separate tags with comma-space. Use lowercase spaces for ordinary tags, retain underscores only in reserved score tags such as `score_9`, and prefix artist tags with `@`. Treat malformed reserved syntax as blocking. Treat an unknown ordinary semantic as advisory when it is well formed and linked to a fact.

Use tags when they express the semantic unambiguously. Add one concise natural-language bridge only for ownership, spatial relations, causal action, action result, or another relation that independent tags cannot bind. Do not render the same fact as both a tag and prose.

Example fact ledger:

```text
f_count | subject_group | count | 2girls
f_relation | subject_1 -> subject_2 | ownership | Subject 1 holds Subject 2's umbrella.
```

Example authored fields:

```text
count [f_count]: 2girls
natural_language_bridge [f_relation]: Subject 1 holds Subject 2's umbrella.
```

The negative prompt has its own facts and budget. Use explicit exclusions; reject a semantic present in both positive and negative streams.

## Vocabulary

For complete tag selection, consult the [vocabulary](vocabulary/) cluster:

- [vocabulary/README.md](vocabulary/README.md) — positioning, field mapping, 5-segment structure
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
