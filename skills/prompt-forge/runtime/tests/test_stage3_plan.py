from __future__ import annotations

import pytest

from runtime.contracts import content_hash
from runtime.stages import StageError, build_shot_intent, build_shot_plan


def _reference():
    return {
        "artifact_type": "CharacterAngleView",
        "view_label": "left_45",
        "accepted": True,
        "content_hash": "ref",
    }


def _story():
    return {
        "schema_version": "1.0",
        "visual_system": {"primary_style": "ink wash"},
        "characters": [{"asset_id": "character-lee"}],
        "scenes": [
            {
                "scene_id": "workshop",
                "environment_id": "environment-workshop",
                "timeline_nodes": [
                    {
                        "timeline_node_id": "beat-1",
                        "action": "Lee unlocks the archive",
                        "dialogue": [{"speaker": "character-lee", "text": "开门。"}],
                        "emotion": "controlled resolve",
                        "shot_deltas": {"framing": "medium"},
                    }
                ],
            }
        ],
        "props": [{"asset_id": "prop-archive-key"}],
        "story_logic": ["the key opens the archive"],
        "uncertainty": ["archive contents remain unknown"],
        "source_hash": "d" * 64,
        "task_context_hash": "1" * 64,
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


def _shot_intent():
    return build_shot_intent(
        _story(),
        _art_bible(),
        scene_id="workshop",
        timeline_node_id="beat-1",
        character_ids=["character-lee"],
        environment_id="environment-workshop",
        prop_ids=["prop-archive-key"],
        desired_view="right",
        camera={"direction": "right", "distance": "medium"},
    )


def _bound_reference(intent):
    artifact = {
        "artifact_type": "CharacterAngleView",
        "view_label": "right_45",
        "accepted": True,
        "reference_eligible": True,
        "semantic_conflict": False,
        "hash_verified": True,
        "content_hash": "a" * 64,
        "lineage_id": "lineage-1",
        "source_story_hash": intent["source_story_hash"],
        "art_bible_hash": intent["art_bible_hash"],
        "task_context_hash": intent["task_context_hash"],
        "character_board_hash": "b" * 64,
        "source_artifact_hash": "c" * 64,
        "orientation_proof": {
            "schema_version": "1.0",
            "expected_view": "right_45",
            "observed_view": "right_45",
            "source": "manual-review",
            "verified": True,
        },
    }
    acceptance = {
        "schema_version": "1.0",
        "artifact_hash": artifact["content_hash"],
        "actor": "user:test",
        "accepted_at": "2026-08-04T08:00:00Z",
    }
    acceptance["acceptance_id"] = content_hash(acceptance)
    artifact["acceptance"] = acceptance
    artifact["acceptance_id"] = acceptance["acceptance_id"]
    return artifact


def _board(artifact_type, asset_id, digest, intent):
    return {
        "artifact_type": artifact_type,
        "asset_id": asset_id,
        "accepted": True,
        "content_hash": digest,
        "lineage_id": "lineage-1",
        "source_story_hash": intent["source_story_hash"],
        "art_bible_hash": intent["art_bible_hash"],
        "task_context_hash": intent["task_context_hash"],
    }


def test_stage1_prompt_build_cannot_be_reused_for_shot():
    with pytest.raises(StageError, match="new PromptBuild"):
        build_shot_plan(
            base_prompt_build_hash="same",
            shot_prompt_build_hash="same",
            reference=_reference(),
            desired_view="left_45",
            execution_approved=True,
        )


def test_shot_plan_records_reference_and_camera():
    result = build_shot_plan(
        base_prompt_build_hash="base",
        shot_prompt_build_hash="shot",
        reference=_reference(),
        desired_view="left_45",
        execution_approved=True,
    )
    assert result["stage"] == "shot-image"
    assert result["reference_hash"] == "ref"
    assert result["desired_view"] == "left_45"
    assert result["execution_approved"] is True
    assert result["production_eligible"] is False
    assert result["plan_mode"] == "legacy-dry-run"


def test_shot_plan_rejects_unaccepted_reference():
    reference = _reference()
    reference["accepted"] = False
    with pytest.raises(StageError, match="accepted reference"):
        build_shot_plan("base", "shot", reference, "front", True)


def test_shot_plan_rejects_stage1_base_fallback_without_multiview_angle():
    reference = _reference()
    reference["artifact_type"] = "CharacterBaseImage"
    with pytest.raises(StageError, match="CharacterAngleView"):
        build_shot_plan("base", "shot", reference, "front", True)


def test_ready_shot_build_requires_locked_identity_and_g1_proof():
    build = {
        "target": "image",
        "dialect": "tag",
        "prompt": "score_9, the_swordswoman, sword",
        "negative_prompt": "lowres",
        "recipe_control_tokens": ["score_9"],
        "validated_tags": ["the_swordswoman", "sword"],
        "rejected_tags": [],
        "locked_facts": ["the_swordswoman"],
        "ready_to_execute": True,
        "execution": {"requested": True, "performed": False},
    }
    with pytest.raises(StageError, match="G1 path proof"):
        build_shot_plan(
            "base",
            "shot",
            _reference(),
            "left_45",
            True,
            shot_prompt_build=build,
            identity_facts=["the_swordswoman"],
        )


def test_ready_shot_build_emits_allowlisted_patches_and_proof():
    build = {
        "target": "image",
        "dialect": "tag",
        "prompt": "score_9, the_swordswoman, sword",
        "negative_prompt": "lowres",
        "recipe_control_tokens": ["score_9"],
        "validated_tags": ["the_swordswoman", "sword"],
        "rejected_tags": [],
        "locked_facts": ["the_swordswoman"],
        "ready_to_execute": True,
        "execution": {"requested": True, "performed": False},
    }
    proof = {"vae_encode_node_id": 59, "sampler_node_id": 27, "traversed_node_ids": [27, 75, 59]}
    result = build_shot_plan(
        "base",
        "shot",
        _reference(),
        "left_45",
        True,
        shot_prompt_build=build,
        identity_facts=["the_swordswoman"],
        g1_proof=proof,
        workflow_fingerprint="wf",
        profile_hash="profile",
    )
    assert result["g1_path_proof"] == proof
    assert {patch["slot"] for patch in result["patches"]} == {
        "positive_prompt",
        "negative_prompt",
        "camera",
        "reference_image",
        "g1_mode",
    }
    assert result["patches"][-1]["node_ids"] == [21, 58, 57, 59]
    assert result["plan_hash"]


def test_shot_intent_binds_story_art_bible_timeline_and_declared_deltas():
    intent = _shot_intent()

    assert intent["artifact_type"] == "ShotIntent"
    assert intent["action"] == "Lee unlocks the archive"
    assert intent["dialogue"] == [{"speaker": "character-lee", "text": "开门。"}]
    assert intent["emotion"] == "controlled resolve"
    assert intent["shot_deltas"] == {"framing": "medium"}
    assert intent["source_story_hash"] == content_hash(_story())
    assert intent["art_bible_hash"] == content_hash(_art_bible())
    assert intent["shot_intent_hash"] == content_hash(
        {key: value for key, value in intent.items() if key != "shot_intent_hash"}
    )


def test_scene_aware_shot_plan_binds_boards_and_nearest_orientation_reason():
    intent = _shot_intent()
    character = _board("CharacterBoard", "character-lee", "b" * 64, intent)
    environment = _board(
        "EnvironmentBoard", "environment-workshop", "e" * 64, intent
    )
    prop = _board("PropBoard", "prop-archive-key", "f" * 64, intent)

    plan = build_shot_plan(
        "base",
        "shot",
        _bound_reference(intent),
        "right",
        True,
        shot_intent=intent,
        character_board=character,
        environment=environment,
        props=[prop],
    )

    assert plan["shot_intent_hash"] == intent["shot_intent_hash"]
    assert plan["character_board_hash"] == "b" * 64
    assert plan["environment_board_hash"] == "e" * 64
    assert plan["prop_board_hashes"] == {"prop-archive-key": "f" * 64}
    assert plan["production_eligible"] is True
    assert plan["plan_mode"] == "scene-aware-production"
    assert plan["reference_selection"] == {
        "selection_reason": "nearest-angle",
        "distance_degrees": 45,
        "desired_view": "right",
        "selected_view": "right_45",
        "content_hash": "a" * 64,
        "source_artifact_hash": "c" * 64,
        "character_board_hash": "b" * 64,
    }


def test_shot_plan_rejects_environment_board_from_a_different_art_bible():
    intent = _shot_intent()
    character = _board("CharacterBoard", "character-lee", "b" * 64, intent)
    environment = _board(
        "EnvironmentBoard", "environment-workshop", "e" * 64, intent
    )
    environment["art_bible_hash"] = "9" * 64

    with pytest.raises(StageError, match="art_bible_hash"):
        build_shot_plan(
            "base",
            "shot",
            _bound_reference(intent),
            "right",
            True,
            shot_intent=intent,
            character_board=character,
            environment=environment,
            props=[_board("PropBoard", "prop-archive-key", "f" * 64, intent)],
        )


def test_shot_plan_rejects_missing_referenced_environment_or_prop_board():
    intent = _shot_intent()
    character = _board("CharacterBoard", "character-lee", "b" * 64, intent)
    kwargs = {
        "shot_intent": intent,
        "character_board": character,
        "environment": _board(
            "EnvironmentBoard", "environment-workshop", "e" * 64, intent
        ),
        "props": [_board("PropBoard", "prop-archive-key", "f" * 64, intent)],
    }

    with pytest.raises(StageError, match="environment board"):
        build_shot_plan(
            "base", "shot", _bound_reference(intent), "right", True, **{**kwargs, "environment": None}
        )
    with pytest.raises(StageError, match="prop board"):
        build_shot_plan(
            "base", "shot", _bound_reference(intent), "right", True, **{**kwargs, "props": []}
        )


def test_shot_plan_rejects_unproven_orientation_source():
    intent = _shot_intent()
    reference = _bound_reference(intent)
    reference.pop("orientation_proof")

    with pytest.raises(StageError, match="orientation"):
        build_shot_plan(
            "base",
            "shot",
            reference,
            "right",
            True,
            shot_intent=intent,
            character_board=_board("CharacterBoard", "character-lee", "b" * 64, intent),
            environment=_board(
                "EnvironmentBoard", "environment-workshop", "e" * 64, intent
            ),
            props=[_board("PropBoard", "prop-archive-key", "f" * 64, intent)],
        )


def test_scene_aware_shot_plan_rejects_forged_reference_content_hash():
    intent = _shot_intent()
    reference = _bound_reference(intent)
    reference["content_hash"] = "forged"

    with pytest.raises(StageError, match="content_hash"):
        build_shot_plan(
            "base",
            "shot",
            reference,
            "right",
            True,
            shot_intent=intent,
            character_board=_board("CharacterBoard", "character-lee", "b" * 64, intent),
            environment=_board(
                "EnvironmentBoard", "environment-workshop", "e" * 64, intent
            ),
            props=[_board("PropBoard", "prop-archive-key", "f" * 64, intent)],
        )


def test_scene_aware_shot_plan_rejects_forged_reference_acceptance_hash():
    intent = _shot_intent()
    reference = _bound_reference(intent)
    reference["acceptance"]["artifact_hash"] = "9" * 64

    with pytest.raises(StageError, match="acceptance"):
        build_shot_plan(
            "base",
            "shot",
            reference,
            "right",
            True,
            shot_intent=intent,
            character_board=_board("CharacterBoard", "character-lee", "b" * 64, intent),
            environment=_board(
                "EnvironmentBoard", "environment-workshop", "e" * 64, intent
            ),
            props=[_board("PropBoard", "prop-archive-key", "f" * 64, intent)],
        )
