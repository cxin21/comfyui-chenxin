# Catalog source snapshot

`tags.sqlite` is the immutable source snapshot used to build the checked-in
`tag-catalog.sqlite`. The builder copies source rows into the source,
concept, and search layers without destructive cross-source merging.

The snapshot contains canonical names and aliases but no provenance-backed
semantic relations. The builder therefore leaves the base relation table
empty; aliases remain name records and are never converted into relation
self-edges. Runtime LLM proposals belong only in the separate relation
overlay.

The runtime catalog is read-only. Rebuild it with `scripts/build_catalog.py`
and verify the resulting manifest before replacing a checked-in artifact.
