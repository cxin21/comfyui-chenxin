from pathlib import Path
from tempfile import TemporaryDirectory

from anima_prompt_v1.catalog import Catalog, RelationOverlay, RelationProposal


def test_search_protocol_keeps_fuzzy_as_candidate_and_related_is_evidence_backed():
    catalog = Catalog()
    assert catalog.search("watercolour", mode="fuzzy", limit=1)[0].match_type == "fuzzy"
    assert catalog.search("long_hair", mode="related", limit=1) == []


def test_accepted_overlay_is_the_only_runtime_related_source():
    catalog = Catalog()
    source = catalog.search("long_hair", mode="exact", limit=1)[0]
    target = catalog.search("blue_eyes", mode="exact", limit=1)[0]
    with TemporaryDirectory() as directory:
        overlay = RelationOverlay(Path(directory) / "relation-overlay.sqlite", record_exists=catalog.has_record)
        overlay.save(RelationProposal(
            "rel:test", source.record_id, target.record_id, "related", "candidate", 0.9,
            "llm", "same user context", evidence=("explicit test evidence",),
        ))
        assert Catalog(relation_overlay=overlay).search("long_hair", mode="related", limit=1) == []
        overlay.accept("rel:test")
        hits = Catalog(relation_overlay=overlay).search("long_hair", mode="related", limit=1)
        assert hits[0].record_id == target.record_id
        assert "accepted_relation:rel:test" in hits[0].provenance
