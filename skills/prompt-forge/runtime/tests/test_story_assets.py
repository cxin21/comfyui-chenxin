import pytest

from runtime.contracts import ContractError, content_hash
from runtime.story_assets import (
    art_bible_hash,
    asset_card_hash,
    story_breakdown_hash,
    validate_art_bible,
    validate_asset_card,
    validate_story_breakdown,
)


def _provenance(*facts):
    return {
        "explicit_evidence": list(facts),
        "reasonable_inference": [],
        "prohibited_expansion": [],
    }


def _character_card():
    facts = (
        "young woman with a heart-shaped face",
        "deep brown almond eyes",
        "short black bob with blunt fringe",
        "indigo linen coat with brass buttons",
    )
    return {
        "schema_version": "1.0",
        "asset_type": "character",
        "asset_id": "character-lee",
        "source_story_hash": "a" * 64,
        "visual_fingerprint": [
            "heart-shaped silhouette",
            "slender proportions",
            "indigo and brass palette",
            "linen and brass materials",
            "matte fabric surface",
            "cool window lighting",
        ],
        "identity_lock": [facts[0], facts[2], facts[3]],
        "face_lock": [facts[1]],
        "provenance": _provenance(*facts),
    }


def _environment_card():
    facts = (
        "weathered stone arch at the entrance",
        "red lacquer seal above the doorway",
        "narrow cedar counter along the east wall",
    )
    return {
        "schema_version": "1.0",
        "asset_type": "environment",
        "asset_id": "environment-workshop",
        "source_story_hash": "b" * 64,
        "visual_fingerprint": [
            "low stone silhouette",
            "compressed interior proportions",
            "cedar red and slate palette",
            "stone and cedar materials",
            "weathered surfaces",
            "soft north-window lighting",
        ],
        "environment_anchors": list(facts),
        "provenance": _provenance(*facts),
    }


def _prop_card():
    facts = ("hand-sized bronze key", "opens the workshop archive")
    return {
        "schema_version": "1.0",
        "asset_type": "prop",
        "asset_id": "prop-archive-key",
        "source_story_hash": "c" * 64,
        "visual_fingerprint": [
            "long-tooth silhouette",
            "palm-sized proportions",
            "aged bronze palette",
            "cast bronze material",
            "oxidized surface detail",
            "warm sidelight",
        ],
        "scale": facts[0],
        "function": facts[1],
        "provenance": _provenance(*facts),
    }


def _story_breakdown():
    return {
        "schema_version": "1.0",
        "visual_system": {"primary_style": "ink wash"},
        "characters": [{"asset_id": "character-lee"}],
        "scenes": [{"asset_id": "environment-workshop"}],
        "story_logic": ["the key opens the archive"],
        "uncertainty": ["archive contents are uncertain"],
        "source_hash": "d" * 64,
    }


def _art_bible():
    return {
        "style": "restrained ink wash",
        "medium": "digital watercolor",
        "visual_grammar": "negative space foregrounds the key",
        "palette": ["indigo", "cedar red"],
        "materials": ["linen", "cedar", "bronze"],
        "lighting": "cool window light with warm sidelight",
        "motifs": ["sealed thresholds"],
        "world_taboos": ["no modern electronics"],
        "continuity_strategy": "reuse fixed anchors and palette",
        "style_prompt": "restrained ink wash, digital watercolor",
    }


def test_asset_card_requires_evidence_tiers_and_visual_fingerprint():
    with pytest.raises(ContractError, match="visual_fingerprint"):
        validate_asset_card({"schema_version": "1.0", "asset_type": "character"})


def test_prohibited_expansion_cannot_become_a_locked_fact():
    card = _character_card()
    card["identity_lock"] = ["modern LED glasses"]
    card["provenance"]["prohibited_expansion"] = ["modern LED glasses"]

    with pytest.raises(ContractError, match="prohibited"):
        validate_asset_card(card)


def test_asset_cards_validate_role_specific_fields_and_are_deep_copied():
    character = _character_card()
    environment = _environment_card()
    prop = _prop_card()

    character_copy = validate_asset_card(character, expected_type="character")
    environment_copy = validate_asset_card(environment, expected_type="environment")
    prop_copy = validate_asset_card(prop, expected_type="prop")

    character_copy["identity_lock"].append("new fact")
    environment_copy["environment_anchors"].append("new anchor")
    prop_copy["scale"] = "oversized"
    assert len(character["identity_lock"]) == 3
    assert len(environment["environment_anchors"]) == 3
    assert prop["scale"] == "hand-sized bronze key"


def test_asset_card_rejects_an_unreferenced_downstream_fact():
    card = _prop_card()
    card["function"] = "opens a hidden modern elevator"

    with pytest.raises(ContractError, match="referenced"):
        validate_asset_card(card)


def test_story_and_art_bible_contracts_are_copied_and_hash_validated_content():
    story = _story_breakdown()
    bible = _art_bible()

    story_copy = validate_story_breakdown(story)
    bible_copy = validate_art_bible(bible)
    story_copy["uncertainty"].append("camera height is uncertain")
    bible_copy["palette"].append("bronze")

    assert story["uncertainty"] == ["archive contents are uncertain"]
    assert bible["palette"] == ["indigo", "cedar red"]
    assert story_breakdown_hash(story) == content_hash(story)
    assert art_bible_hash(bible) == content_hash(bible)
    assert asset_card_hash(_character_card()) == content_hash(_character_card())
