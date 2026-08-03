from __future__ import annotations

import pytest

from runtime.stages import StageError, build_shot_plan


def _reference():
    return {
        "artifact_type": "CharacterAngleView",
        "view_label": "left_45",
        "accepted": True,
        "content_hash": "ref",
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


def test_shot_plan_rejects_unaccepted_reference():
    reference = _reference()
    reference["accepted"] = False
    with pytest.raises(StageError, match="accepted reference"):
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
