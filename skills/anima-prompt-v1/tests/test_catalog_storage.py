from pathlib import Path

from anima_prompt_v1.catalog.builder import verify_manifest
from anima_prompt_v1.catalog.storage import CatalogStore


def test_catalog_artifact_and_manifest_share_the_supported_schema():
    root = Path(__file__).parents[1]
    assert CatalogStore.schema_errors(root / "knowledge" / "tag-catalog.sqlite") == ()
    assert verify_manifest(root / "knowledge" / "manifest.json")
