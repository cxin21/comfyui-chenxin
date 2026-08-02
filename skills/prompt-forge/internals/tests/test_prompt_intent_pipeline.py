import json
from pathlib import Path

from internals.intent_normalize import load_concept_map, normalize_intent
from internals.prompt_compile import compile_prompt
from internals.scene_match import load_index as load_scene_index, match as match_scene
from internals.tag_lookup import load_index as load_tag_index, lookup_many


WORKSPACE = Path(__file__).resolve().parents[4]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCENE_INDEX = WORKSPACE / "skills/prompt-forge/aesthetics/INDEX.md"
TAG_INDEX = WORKSPACE / "skills/prompt-forge/dictionary/tag-index.json"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_anima_fixture_preserves_explicit_facts_and_validates_tags():
    result = normalize_intent(_load_fixture("anima-intent.json"), load_concept_map())
    assert result["intent"]["dialect"] == "danbooru"
    assert "blonde hair" in result["english_terms"]
    assert "blonde_hair" in result["tag_candidates"]
    assert "long_hair" not in result["tag_candidates"]

    validation = lookup_many(load_tag_index(TAG_INDEX), result["tag_candidates"], exact=True)
    assert validation
    assert all(item["results"] for item in validation)


def test_flux_fixture_uses_natural_language_channel_and_scene_terms():
    result = normalize_intent(_load_fixture("flux-intent.json"), load_concept_map())
    assert result["intent"]["dialect"] == "natural-language"
    assert "a female mage" in result["english_terms"]
    assert "a neon night street" in result["scene_terms"]

    scenes = match_scene(load_scene_index(SCENE_INDEX), " ".join(result["scene_terms"]), top=1)
    assert scenes[0]["scene"] == "night_street"


def test_video_fixture_compiles_to_auditable_build_without_execution():
    build = compile_prompt(_load_fixture("wan-video-intent.json"))
    assert build["target"] == "video"
    assert build["ready_to_execute"] is True
    assert build["execution"]["performed"] is False
