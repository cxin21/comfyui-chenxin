# Inspection and Output

## Immutable inspection

`inspect_draft()` reads a frozen `PromptDraft` and returns an
`InspectionReport`. It may report syntax, weight, trigger, wildcard, conflict,
graph, lock, repetition, token, and provenance issues.

For Anima it must additionally verify:

- the selected variant's mandatory positive quality terms are present;
- mandatory negative quality terms are present;
- Base retains `score_7`;
- Aesthetic has no unrequested `score_*` terms;
- official quality provenance is retained;
- quality terms are not duplicated or placed in the wrong channel.

Inspection never mutates, rewrites, invents, blocks, or certifies a draft. Token
estimates are diagnostics, never quality gates. Every issue remains an advisory.

## PromptOutput

`output_from_draft()` returns exactly:

```json
{
  "positive": "...",
  "negative": "...",
  "notes": [],
  "assumptions": [],
  "advisories": []
}
```

The prompt fields contain only copyable text. Use `notes` for Catalog and official
quality provenance plus accepted relations; `assumptions` for variant defaults,
inferred additions, unknowns, fuzzy candidates, and unaccepted relations; and
`advisories` for inspection, missing provenance, conflicts, and relation failures.

`attach_relation_submission()` may add metadata and issues after initial output;
it must not change either prompt channel.

Human serialization is exactly:

```text
POSITIVE:
...

NEGATIVE:
...
```

Do not append explanations, IDs, diagnostics, or status text to human output.
