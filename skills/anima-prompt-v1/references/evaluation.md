# Evaluation

Evaluate Anima invariants and interface behavior, not arbitrary prompt length.

## Mandatory quality invariants

- Every positive prompt contains the selected variant's required quality terms.
- Anima-Base contains `masterpiece`, `best quality`, and `score_7` unless the
  user explicitly locked a conflicting segment; any conflict is an advisory.
- Anima-Aesthetic contains `masterpiece` and `best quality` and does not receive
  unrequested `score_*` tags.
- Anima-Turbo contains `masterpiece` and `best quality` while remaining concise.
- Every negative prompt contains the selected variant's required quality terms.
- `safe` is treated as a safety tag, not counted as a quality term.
- Quality terms retain official Catalog provenance and are not fuzzy candidates.
- Quality terms are not duplicated or placed in both channels incorrectly.

## Other invariants

### Brief and authoring

- Explicit facts/exclusions are preserved.
- Official model facts, user facts, inferred additions, and unknowns are distinct.
- Locked segments, triggers, wildcards, and weights remain byte-faithful.
- Positive and negative channels remain independent and non-conflicting.
- Routes change representation, not facts or quality policy.
- Actions retain performers and explicit relation endpoints.

### Catalog and relations

- TagHit retains ID, canonical/prompt names, category, score, matched name,
  match type, aliases, source/version, facets, and provenance.
- Exact/alias/prefix/related/fuzzy remain distinguishable.
- Fuzzy cannot satisfy mandatory quality terms.
- Base Catalog is read-only.
- Candidate relations never enter default auto/related retrieval.
- LLM reasoning never creates cooccurrence.
- Invalid relation submissions produce issues without blocking prompt output.

### Inspection and output

- Inspector is read-only and non-blocking.
- Diagnostics never enter prompt text.
- Human output is exactly two blocks.
- Machine output has exactly five fields.
- Relation attachment never changes positive or negative text.

## Regression matrix

Cover: Anima with no variant (Base default); Base/Aesthetic/Turbo quality policy;
user quality overrides; Catalog exact/alias/fuzzy quality hits; Catalog outage;
locked quality text; trigger/wildcard/weight preservation; route changes;
multi-subject graph advisories; negative exclusions; accepted/candidate relations;
empty/invalid/duplicate/conflicting/cooccurrence submissions; human and JSON
serialization; and inspection warnings that must not block output.
