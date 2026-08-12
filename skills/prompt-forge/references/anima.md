# Anima authoring dialect

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

## Built-in dictionary

Use the bundled read-only `knowledge/anima/tags.sqlite`. It contains the full locked Gelbooru canonical snapshot plus Danbooru compatibility aliases under deterministic precedence. Runtime retrieval is offline and bounded. The manifest records immutable revisions, source hashes, row counts, database hash, builder hash, licenses, and redistribution decisions.

Do not scrape at runtime, add a user tag overlay, or use a local checkpoint/LoRA vocabulary layer. Maintainers update the dictionary only by acquiring pinned source snapshots, passing the redistribution gate, rebuilding twice byte-identically, updating the manifest, and rerunning the release verifier.

The image model's physical tokenizer limit is 32,768 tokens. Prompt Forge uses much smaller calibrated quality limits; physical capacity is not a recommendation to fill the context.
