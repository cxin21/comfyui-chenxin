from __future__ import annotations

import pytest

from runtime.stages import StageError, build_video_plan


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
    assert plan["parameters"]["fps"] == 24
    assert plan["source_shot_hash"] == "shot"


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
