import json
from pathlib import Path
import subprocess

import pytest

from internals.intent_normalize import (
    DIMENSIONS,
    load_concept_map,
    match_concepts,
    normalize_intent,
    normalize_query,
    validate_canonical_tags,
)


WORKSPACE = Path(__file__).resolve().parents[4]
SCRIPT = WORKSPACE / "skills/prompt-forge/internals/intent_normalize.py"


def _intent() -> dict:
    dimensions = {dimension: [] for dimension in DIMENSIONS}
    dimensions["subject"] = [
        {"value": "female elf mage", "origin": "explicit", "tag_candidates": ["1girl", "elf"]},
        {"value": "blonde hair", "origin": "explicit", "tag_candidates": ["blonde_hair"]},
    ]
    dimensions["action"] = [
        {"value": "casting magic", "origin": "explicit", "tag_candidates": ["casting_spell", "magic"]}
    ]
    dimensions["scene"] = [
        {"value": "under cherry blossoms", "origin": "explicit", "tag_candidates": ["cherry_blossoms"]}
    ]
    dimensions["lighting"] = [
        {"value": "soft afternoon light", "origin": "recipe"}
    ]
    return {
        "schema_version": "6.1",
        "original_query": "金发精灵女法师在樱花树下释放魔法",
        "target": "image",
        "mode": "compile",
        "generation_mode": "text-to-image",
        "model_id": "anima",
        "dialect": "danbooru",
        "negative_constraints": [],
        "output_constraints": {},
        "references": [],
        "locked_facts": ["female elf mage", "blonde hair", "casting magic"],
        "dimensions": dimensions,
    }


def test_concept_map_preserves_blonde_semantics():
    entries = load_concept_map()
    assert entries["金发"]["english"] == "blonde hair"
    assert entries["金发"]["canonical_tags"] == ["blonde_hair"]
    assert "long_hair" not in entries["金发"]["canonical_tags"]


def test_all_canonical_tags_exist_in_index():
    assert validate_canonical_tags(load_concept_map()) == []


def test_longest_phrase_wins_without_fabricated_compound():
    matches = match_concepts("金发精灵", load_concept_map())
    assert [match["source_text"] for match in matches] == ["金发精灵"]
    assert matches[0]["canonical_tags"] == ["blonde_hair", "elf"]


def test_single_character_concepts_require_exact_query():
    entries = load_concept_map()
    assert match_concepts("雨", entries)[0]["source_text"] == "雨"
    assert not any(match["source_text"] == "雨" for match in match_concepts("雨伞", entries))


def test_user_example_extracts_ordered_terms_and_no_unknown_cjk():
    result = normalize_query("金发精灵女法师在樱花树下释放魔法", load_concept_map())
    assert result["english_terms"] == [
        "blonde-haired elf",
        "female mage",
        "under cherry blossoms",
        "casting magic",
    ]
    assert "blonde_hair" in result["tag_candidates"]
    assert "long_hair" not in result["tag_candidates"]
    assert result["lexicon_unresolved"] == []


def test_unknown_cjk_is_preserved_as_a_span():
    result = normalize_query("未知机械生命体", load_concept_map())
    assert result["english_terms"] == []
    assert result["lexicon_unresolved"] == ["未知机械生命体"]
    assert result["has_unresolved"] is True


def test_normalize_intent_preserves_provenance_and_derives_channels():
    intent = _intent()
    result = normalize_intent(intent, load_concept_map())
    assert result["intent"] == intent
    assert "under cherry blossoms" in result["scene_terms"]
    assert "soft afternoon light" in result["scene_terms"]
    assert "blonde_hair" in result["tag_candidates"]
    assert result["intent"]["dimensions"]["subject"][0]["origin"] == "explicit"
    assert "female elf mage" in result["locked_facts"]
    assert result["provenance"]["explicit"] == 4


def test_duplicate_values_keep_highest_priority_origin():
    intent = _intent()
    intent["dimensions"]["lighting"].append(
        {"value": "soft afternoon light", "origin": "explicit", "locked": True}
    )
    result = normalize_intent(intent, load_concept_map())
    assert result["intent"]["dimensions"]["lighting"] == [
        {"value": "soft afternoon light", "origin": "explicit", "locked": True}
    ]


def test_normalize_intent_merges_evidence_locks_and_prohibited_expansion_without_aliasing():
    intent = _intent()
    intent.update(
        {
            "story_breakdown_hash": "a" * 64,
            "art_bible_hash": "b" * 64,
            "asset_refs": [
                {"asset_id": "character-lee", "asset_type": "character", "content_hash": "c" * 64}
            ],
            "explicit_evidence": ["indigo linen coat"],
            "reasonable_inference": ["the coat is weathered"],
            "prohibited_expansion": ["modern LED glasses"],
            "continuity_locks": {
                "identity": ["indigo linen coat"],
                "style": ["restrained ink wash"],
                "scene": [],
                "prop": [],
            },
            "uncertainty": ["exact coat age"],
        }
    )

    result = normalize_intent(intent, load_concept_map())

    assert result["story_breakdown_hash"] == "a" * 64
    assert result["art_bible_hash"] == "b" * 64
    assert result["asset_refs"] == intent["asset_refs"]
    assert result["explicit_evidence"] == ["indigo linen coat"]
    assert result["reasonable_inference"] == ["the coat is weathered"]
    assert result["prohibited_expansion"] == ["modern LED glasses"]
    assert "indigo linen coat" in result["locked_facts"]
    assert "restrained ink wash" in result["locked_facts"]
    assert "the coat is weathered" not in result["locked_facts"]
    assert "modern LED glasses" in result["intent"]["negative_constraints"]
    assert "exact coat age" in result["uncertainty"]

    result["asset_refs"][0]["asset_id"] = "mutated"
    result["continuity_locks"]["identity"].append("mutated")
    assert intent["asset_refs"][0]["asset_id"] == "character-lee"
    assert intent["continuity_locks"]["identity"] == ["indigo linen coat"]


def test_normalize_intent_rejects_prohibited_facts_in_evidence_or_locks():
    intent = _intent()
    intent["explicit_evidence"] = ["modern LED glasses"]
    intent["prohibited_expansion"] = ["modern LED glasses"]

    with pytest.raises(ValueError, match="prohibited"):
        normalize_intent(intent, load_concept_map())


def test_generation_mode_must_match_target():
    intent = _intent()
    intent["target"] = "video"
    with pytest.raises(ValueError, match="does not match target"):
        normalize_intent(intent, load_concept_map())


def test_intent_requires_all_dimensions():
    intent = _intent()
    del intent["dimensions"]["quality"]
    with pytest.raises(ValueError, match="missing dimensions"):
        normalize_intent(intent, load_concept_map())


def test_cli_query_json_contract():
    result = subprocess.run(
        ["python", str(SCRIPT), "--query", "金发精灵女法师"],
        capture_output=True,
        text=True,
        cwd=str(WORKSPACE),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["english_terms"] == ["blonde-haired elf", "female mage"]


def test_cli_stats_uses_actual_entry_count():
    result = subprocess.run(
        ["python", str(SCRIPT), "--stats"],
        capture_output=True,
        text=True,
        cwd=str(WORKSPACE),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["entries"] == len(load_concept_map())
    assert payload["missing_canonical_tags"] == []
