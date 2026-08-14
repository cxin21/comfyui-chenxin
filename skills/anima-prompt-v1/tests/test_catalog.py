from pathlib import Path

from anima_prompt_v1.catalog import Catalog
from anima_prompt_v1.catalog.storage import CatalogStore


def test_catalog_stats_and_search_modes():
    catalog = Catalog(Path(__file__).parents[1] / "knowledge" / "tag-catalog.sqlite")
    stats = catalog.stats()
    assert stats["records"] >= 1_000_000
    assert stats["relations"] == 0
    assert stats["fts_rows"] == stats["names"]
    exact = catalog.search("long_hair", mode="exact", limit=1)[0]
    assert exact.canonical_name == "long_hair"
    assert exact.aliases
    record = catalog.get_record(exact.record_id)
    assert record.canonical_name == "long_hair"
    assert record.source_ids and record.provenance
    assert catalog.search("miku", mode="prefix", categories=("character",), limit=1)[0].category == "character"
    assert catalog.search("longhair", mode="alias", limit=1)[0].match_type == "alias"
    assert catalog.search("long_hair", mode="related", limit=1) == []
    assert CatalogStore.schema_errors(Path(__file__).parents[1] / "knowledge" / "tag-catalog.sqlite") == ()


def test_catalog_keeps_nsww_and_style_facets_searchable():
    catalog = Catalog(Path(__file__).parents[1] / "knowledge" / "tag-catalog.sqlite")
    assert catalog.search("watercolor", facets=("style",), mode="fuzzy", limit=1)
    assert catalog.search("nude", facets=("nsfw",), mode="prefix", limit=1)
