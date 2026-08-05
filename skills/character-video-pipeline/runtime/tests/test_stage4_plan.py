from __future__ import annotations

import pytest

from runtime.stages import (
    LTX_BASELINE_OUTPUT_HEIGHT,
    LTX_BASELINE_OUTPUT_WIDTH,
    StageError,
    build_video_plan,
    ltx_output_frame_count,
)


def _shot(accepted=True):
    return {
        "artifact_type": "ShotImage",
        "accepted": accepted,
        "content_hash": "a" * 64,
        "task_context_hash": "b" * 64,
        "source_story_hash": "c" * 64,
        "art_bible_hash": "d" * 64,
        "lineage_id": "lineage-1",
    }


def _build():
    return {
        "ready_to_execute": True,
        "target": "video",
        "dialect": "video-timeline",
        "prompt": "The subject moves as the camera dollies in.",
        "negative_prompt": "",
    }


def _strict_build_and_intent():
    positive_zh = "\u30160-1 s\u3017\u4e3b\u4f53\u79fb\u52a8\u3002"
    positive_en = "\u30160-1 s\u3017The subject moves with a slow dolly in."
    build = {
        "ready_to_execute": True,
        "target": "video",
        "dialect": "video-timeline",
        "prompt": positive_en,
        "positive_zh": positive_zh,
        "positive_en": positive_en,
        "negative_prompt": "",
        "global_prompt": "Preserve identity continuity.",
        "timeline_segments": [
            {"start": 0.0, "end": 1.0, "text_zh": "\u4e3b\u4f53\u79fb\u52a8\u3002", "text_en": "The subject moves with a slow dolly in."}
        ],
        "dialogue_attribution": [],
        "continuity_requirements": ["subject"],
        "split_recommendation": {"required": False, "reason": "single shot"},
        "source_shot_plan_hash": "a" * 64,
    }
    dimensions = {name: [] for name in ("subject", "action", "scene", "lighting", "composition", "camera", "motion", "timeline", "audio", "color", "style", "mood", "medium", "quality")}
    dimensions["subject"] = [{"value": "subject", "origin": "explicit"}]
    dimensions["action"] = [{"value": "moves", "origin": "explicit"}]
    dimensions["motion"] = [{"value": "slow dolly in", "origin": "explicit"}]
    dimensions["camera"] = [{"value": "slow dolly in", "origin": "explicit"}]
    intent = {
        "target": "video",
        "dimensions": dimensions,
        "locked_facts": ["subject"],
        "input_type": "reference",
        "global_prompts": {"reference": "Preserve identity continuity."},
        "continuity_locks": {"identity": ["subject"]},
    }
    return build, intent


def test_video_plan_requires_accepted_shot():
    with pytest.raises(StageError, match="accepted ShotImage"):
        build_video_plan(_shot(False), _build(), "wfhash", "profilehash", True)


def test_video_plan_locks_one_second_baseline():
    plan = build_video_plan(_shot(), _build(), "wfhash", "profilehash", True)
    assert plan["stage"] == "video"
    assert plan["parameters"]["frames"] == 24
    assert plan["parameters"]["output_frames"] == 25
    assert plan["parameters"]["fps"] == 24
    assert plan["parameters"]["output_width"] == LTX_BASELINE_OUTPUT_WIDTH == 1024
    assert plan["parameters"]["output_height"] == LTX_BASELINE_OUTPUT_HEIGHT == 704
    assert plan["source_shot_hash"] == "a" * 64


def test_video_plan_rejects_unprofiled_output_canvas():
    with pytest.raises(StageError, match="1024x704"):
        build_video_plan(
            _shot(), _build(), "wfhash", "profilehash", True,
            output_width=1280,
            output_height=720,
        )


def test_ltx_output_frame_count_uses_the_8n_plus_1_lattice():
    assert ltx_output_frame_count(1) == 9
    assert ltx_output_frame_count(24) == 25
    assert ltx_output_frame_count(25) == 25


def test_video_plan_rejects_second_negative_system():
    build = _build()
    build["negative_prompt"] = "watermark"
    with pytest.raises(StageError, match="workflow-owned negative"):
        build_video_plan(_shot(), build, "wfhash", "profilehash", True)


def test_video_plan_can_apply_full_intent_quality_gate():
    dimensions = {name: [] for name in ("subject", "action", "scene", "lighting", "composition", "camera", "motion", "timeline", "audio", "color", "style", "mood", "medium", "quality")}
    dimensions["subject"] = [{"value": "the subject", "origin": "explicit"}]
    dimensions["action"] = [{"value": "moves", "origin": "explicit"}]
    dimensions["motion"] = [{"value": "moves", "origin": "explicit"}]
    dimensions["camera"] = [{"value": "dolly in", "origin": "explicit"}]
    intent = {"target": "video", "dimensions": dimensions, "locked_facts": ["the subject"]}
    plan = build_video_plan(_shot(), _build(), "wfhash", "profilehash", True, intent=intent)
    assert plan["prompt_build_hash"]


def test_video_plan_rejects_over_complex_single_clip():
    build = _build()
    build["positive_zh"] = "她移动。"
    build["positive_en"] = "She moves."
    build["prompt"] = build["positive_en"]
    build["split_recommendation"] = {"required": True, "reason": "scene change"}
    with pytest.raises(StageError, match="split"):
        build_video_plan(
            _shot(), build, "wfhash", "profilehash", True,
            duration_profile_id="ltx-yusu-short-v1",
            split_decision={"required": True, "approved": False},
            motion_delta="slow dolly",
        )


def test_video_plan_requires_duration_profile_for_production_video():
    build = _build()
    build["split_recommendation"] = {"required": False, "reason": ""}
    with pytest.raises(StageError, match="duration profile"):
        build_video_plan(
            _shot(), build, "wfhash", "profilehash", True,
            motion_delta="slow dolly",
            split_decision={"required": False, "approved": True},
        )


def test_legacy_compact_video_plan_is_explicitly_nonproduction():
    plan = build_video_plan(_shot(), _build(), "wfhash", "profilehash", True)
    assert plan["production_eligible"] is False
    assert plan["plan_mode"] == "legacy-dry-run"
    assert plan["submission_blocked"] is True


def test_video_plan_rejects_timeline_that_ends_before_profile_duration():
    build, intent = _strict_build_and_intent()
    with pytest.raises(StageError, match="cover profile duration"):
        build_video_plan(
            _shot(),
            build,
            "wfhash",
            "profilehash",
            True,
            duration_profile_id="ltx-yusu-short-v1",
            motion_delta="slow dolly",
            split_decision={"required": False, "approved": True},
            timeline_segments=[{"start_second": 0.0, "end_second": 0.5, "prompt": "She moves."}],
            intent=intent,
        )


def test_production_video_requires_intent_quality_contract():
    build = _build()
    build.update(
        {
            "positive_zh": "她移动。",
            "positive_en": "She moves.",
            "prompt": "She moves.",
            "split_recommendation": {"required": False, "reason": "single shot"},
        }
    )
    with pytest.raises(StageError, match="PromptIntent"):
        build_video_plan(
            _shot(),
            build,
            "wfhash",
            "profilehash",
            True,
            duration_profile_id="ltx-yusu-short-v1",
            motion_delta="slow dolly",
            split_decision={"required": False, "approved": True},
        )
