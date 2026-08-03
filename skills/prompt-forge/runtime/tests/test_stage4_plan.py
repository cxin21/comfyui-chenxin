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
    return {"artifact_type": "ShotImage", "accepted": accepted, "content_hash": "shot"}


def _build():
    return {
        "ready_to_execute": True,
        "target": "video",
        "dialect": "video-timeline",
        "prompt": "The subject moves as the camera dollies in.",
        "negative_prompt": "",
    }


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
    assert plan["source_shot_hash"] == "shot"


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
