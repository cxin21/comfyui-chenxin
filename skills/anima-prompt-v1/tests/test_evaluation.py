from pathlib import Path

from anima_prompt_v1.catalog.builder import verify_manifest


def test_manifest_declares_unfiltered_source_and_output():
    assert verify_manifest(Path(__file__).parents[1] / "knowledge" / "manifest.json")
