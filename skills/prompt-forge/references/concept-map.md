# Chinese concept map

`dictionary/zh-en.json` is a deterministic cross-check map, not a general
translator. `intent_normalize.py` uses it to preserve known Chinese source
phrases, derive English semantic phrases and propose real canonical tags.

Entry shape:

```json
{
  "金发": {
    "english": "blonde hair",
    "canonical_tags": ["blonde_hair"],
    "dimension": "subject"
  }
}
```

- Compounds may expand to several real tags; never invent a compound canonical.
- Matching is longest-first. Single-character Chinese surfaces match only when
  the entire query is that concept, avoiding accidental substring semantics.
- Unknown Chinese spans remain in `lexicon_unresolved`; the LLM must understand
  them from context, and must not translate character by character.
- Every canonical tag must exist in `dictionary/tag-index.json`.

When adding an entry, add a realistic regression case and run
`test_intent_normalize.py` plus the canonical-integrity test.
