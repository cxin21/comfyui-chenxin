# Catalog Architecture

The Catalog is a read-only runtime knowledge source plus a separate writable
relation overlay. It is not a generic model registry.

## Storage layers

```text
source tags.sqlite
    → Source Layer
    → Concept/Record Layer
    → Search Projections
    → Catalog.search() / Catalog.related() / CLI
```

The source layer preserves original fields, snapshot version, checksum, and
fetch provenance. The record layer retains canonical name, prompt form, category,
description, language names, confidence, source IDs, and provenance. Names are
separate canonical, alias, translation, and historical rows.

The Catalog includes an official Anima protocol source for mandatory quality and
safety terms. The required records include `masterpiece`, `best quality`,
`score_7`, `safe`, `worst quality`, `low quality`, and relevant `score_*` terms.
These must be exact or alias hits; fuzzy results cannot satisfy a mandatory
quality policy.

Base relations contain only provenance-backed accepted `parent`, `child`,
`related`, or real-statistics `cooccurrence`. Alias rows are names, never
semantic self-relations.

Runtime proposals use independent `relation-overlay.sqlite` with
`parent|child|related` and `candidate|accepted|rejected` states. Candidate
relations never enter default `auto` or `related` search; only accepted overlay
relations do.

## Search interface

```text
search(query, mode="auto | exact | prefix | alias | fuzzy | related",
       categories=[], facets=[], sources=[], limit=50)
```

Default order:

```text
exact canonical → exact alias → prefix → category/facet constrained
→ accepted related → fuzzy candidate
```

Categories and facets constrain search; they are not a new semantic match type.
Related follows only accepted evidence-backed edges and never replaces lexical
resolution. Empty search is a miss. `browse()` is the explicit read-only export
seam.

## TagHit

Every hit retains:

```text
record_id, canonical_name, prompt_form, category, score,
matched_name, match_type, aliases, source, source_version, facets, provenance
```

Quality hits additionally retain the official protocol source in provenance.
Exact canonical, exact alias, prefix, related, and fuzzy types remain distinct.
Unknown Catalog or manifest access preserves user text and emits an advisory.
