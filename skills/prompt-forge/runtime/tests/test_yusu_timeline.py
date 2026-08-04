from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.adapters.yusu_timeline import (
    YusuTimelineError,
    patch_yusu_timeline,
    validate_yusu_immutable_inputs,
    validate_yusu_sync,
)
from runtime.prompt_quality import recommend_ltx_split
from runtime.stages import StageError, build_video_plan, ltx_output_frame_count


FIXTURE = Path(__file__).parent / "fixtures" / "yusu-api-minimal.json"
PROFILE = {"director_node_id": 174, "negative_node_id": 195}
PROFILE_FILE = Path(__file__).parents[1] / "profiles" / "ltx-yusu-director.json"


def _graph():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _contract_profile():
    return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))


def _contract_graph():
    graph = _graph()
    profile = _contract_profile()
    for node_id, node in profile["immutable_node_inputs"].items():
        graph[node_id] = copy.deepcopy(node)
    graph["174"]["inputs"].update(profile["director_immutable_inputs"])
    return graph


def test_one_segment_is_patched_and_derived_fields_match():
    graph = _graph()
    patched = patch_yusu_timeline(
        graph,
        {
            "imageFile": "runs/lineage/shot.png",
            "imageB64": "/api/view?filename=shot.png&type=input&subfolder=runs/lineage",
        },
        "The swordswoman lunges as the camera slowly dollies in.",
        24,
        24,
        PROFILE,
    )
    node = patched["174"]["inputs"]
    timeline = json.loads(node["timeline_data"])
    assert timeline["segments"][0]["imageFile"] == "runs/lineage/shot.png"
    assert timeline["segments"][0]["prompt"].startswith("The swordswoman")
    assert node["local_prompts"] == timeline["segments"][0]["prompt"]
    assert node["segment_lengths"] == "24"
    assert node["duration_frames"] == 24
    assert node["frame_rate"] == 24
    validate_yusu_sync(patched, PROFILE)


def test_malformed_timeline_is_rejected():
    graph = _graph()
    graph["174"]["inputs"]["timeline_data"] = "{broken"
    with pytest.raises(YusuTimelineError, match="timeline_data"):
        patch_yusu_timeline(graph, {"imageFile": "a.png", "imageB64": "/api/view?a"}, "move", 24, 24, PROFILE)


def test_fixed_negative_node_is_unchanged():
    graph = _graph()
    original_negative = copy.deepcopy(graph["195"])
    patched = patch_yusu_timeline(
        graph,
        {"imageFile": "a.png", "imageB64": "/api/view?a"},
        "The subject moves while the camera pans.",
        24,
        24,
        PROFILE,
    )
    assert patched["195"] == original_negative


def test_source_graph_is_not_mutated():
    graph = _graph()
    original = copy.deepcopy(graph)
    patch_yusu_timeline(graph, {"imageFile": "a.png", "imageB64": "/api/view?a"}, "move", 24, 24, PROFILE)
    assert graph == original


def test_unsafe_image_reference_is_rejected():
    with pytest.raises(YusuTimelineError, match="imageFile"):
        patch_yusu_timeline(_graph(), {"imageFile": "../shot.png", "imageB64": "/api/view?a"}, "move", 24, 24, PROFILE)


def test_immutable_ltx_inputs_are_pinned_and_drift_is_rejected():
    profile = _contract_profile()
    graph = _contract_graph()
    validate_yusu_immutable_inputs(graph, profile)

    graph["196"]["inputs"]["unet_name"] = "drifted-model.gguf"
    with pytest.raises(YusuTimelineError, match="immutable node 196"):
        validate_yusu_immutable_inputs(graph, profile)


def test_director_output_inputs_are_pinned_and_drift_is_rejected():
    profile = _contract_profile()
    graph = _contract_graph()
    validate_yusu_immutable_inputs(graph, profile)

    graph["174"]["inputs"]["resize_method"] = "crop"
    with pytest.raises(YusuTimelineError, match="director immutable input resize_method"):
        validate_yusu_immutable_inputs(graph, profile)


def test_immutable_numeric_inputs_accept_json_int_float_round_trip():
    profile = _contract_profile()
    graph = _contract_graph()
    graph["135"] = {
        "class_type": "BasicScheduler",
        "inputs": {"denoise": 1.0},
    }
    profile["immutable_node_inputs"]["135"] = {
        "class_type": "BasicScheduler",
        "inputs": {"denoise": 1},
    }
    validate_yusu_immutable_inputs(graph, profile)


def test_pinned_ltx_profile_contains_live_workflow_identity():
    profile = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    assert profile["profile_id"] == "ltx-yusu-director-v1"
    assert profile["workflow_name"] == "LTX全新导演台工作流.json"
    assert profile["workflow_fingerprint"] == "8f777f6315bab2c14fb4d99d83a44d73cf8dfd7362011fc3a931fffa9a081074"
    assert profile["director_node_id"] == 174
    assert profile["negative_node_id"] == 195
    assert profile["expected_outputs"] == ["video"]


def test_timeline_accepts_contiguous_segments_and_preserves_same_image_and_dialogue():
    graph = _contract_graph()
    profile = _contract_profile()
    profile.update({"profile_id": "ltx-yusu-long-v1", "duration_seconds": 4.0, "baseline_frames": 96, "baseline_fps": 24})
    patched = patch_yusu_timeline(
        graph,
        {"imageFile": "runs/shot.png", "imageB64": "/api/view?filename=shot.png"},
        "她抬头。她说：'快走。'",
        96,
        24,
        profile,
        timeline_segments=[
            {"start_second": 0.0, "end_second": 1.5, "prompt": "她抬头。"},
            {"start_second": 1.5, "end_second": 4.0, "prompt": "她说：'快走。'"},
        ],
    )
    timeline = json.loads(patched["174"]["inputs"]["timeline_data"])
    assert len(timeline["segments"]) == 2
    assert {segment["imageFile"] for segment in timeline["segments"]} == {"runs/shot.png"}
    assert "快走" in patched["174"]["inputs"]["local_prompts"]
    assert patched["195"] == graph["195"]


def test_timeline_rejects_gapped_segment_ranges():
    profile = _contract_profile()
    profile.update({"duration_seconds": 1.0})
    with pytest.raises(YusuTimelineError, match="contiguous"):
        patch_yusu_timeline(
            _contract_graph(),
            {"imageFile": "shot.png", "imageB64": "/api/view?filename=shot.png"},
            "move",
            24,
            24,
            profile,
            timeline_segments=[
                {"start_second": 0.0, "end_second": 1.0, "prompt": "move"},
            {"start_second": 0.6, "end_second": 1.0, "prompt": "talk"},
            ],
        )


def test_timeline_rejects_segments_that_do_not_cover_profile_duration():
    profile = _contract_profile()
    profile.update({"duration_seconds": 1.0})
    with pytest.raises(YusuTimelineError, match="cover"):
        patch_yusu_timeline(
            _contract_graph(),
            {"imageFile": "shot.png", "imageB64": "/api/view?filename=shot.png"},
            "move",
            24,
            24,
            profile,
            timeline_segments=[{"start_second": 0.0, "end_second": 0.5, "prompt": "move"}],
        )


def test_short_and_long_profiles_declare_distinct_temporal_budgets():
    short = json.loads((PROFILE_FILE.parent / "ltx-yusu-short.json").read_text(encoding="utf-8"))
    long = json.loads((PROFILE_FILE.parent / "ltx-yusu-long.json").read_text(encoding="utf-8"))
    assert (short["baseline_frames"], short["duration_seconds"], short["baseline_output_frames"]) == (24, 1.0, 25)
    assert (long["baseline_frames"], long["duration_seconds"], long["baseline_output_frames"]) == (96, 4.0, 97)
    assert short["workflow_fingerprint"] == long["workflow_fingerprint"]
    assert short["negative_node_id"] == long["negative_node_id"] == 195


def test_profile_duration_must_match_integer_frame_budget_on_patch_and_sync():
    profile = _contract_profile()
    profile.update({"duration_seconds": 4.3, "baseline_frames": 24, "baseline_fps": 24})
    with pytest.raises(YusuTimelineError, match="duration_seconds"):
        patch_yusu_timeline(
            _contract_graph(),
            {"imageFile": "shot.png", "imageB64": "/api/view?filename=shot.png"},
            "move",
            24,
            24,
            profile,
        )
    with pytest.raises(YusuTimelineError, match="duration_seconds"):
        validate_yusu_sync(_contract_graph(), profile)


def test_timeline_segments_must_cover_frame_budget_after_rounding():
    profile = _contract_profile()
    profile.update({"duration_seconds": 1.0, "baseline_frames": 24, "baseline_fps": 24})
    with pytest.raises(YusuTimelineError, match="frame lengths"):
        patch_yusu_timeline(
            _contract_graph(),
            {"imageFile": "shot.png", "imageB64": "/api/view?filename=shot.png"},
            "move",
            24,
            24,
            profile,
            timeline_segments=[
                {"start_second": 0.0, "end_second": 0.1, "prompt": "one"},
                {"start_second": 0.1, "end_second": 0.2, "prompt": "two"},
                {"start_second": 0.2, "end_second": 1.0, "prompt": "three"},
            ],
        )


def test_cli_patch_yusu_rejects_profile_duration_frame_mismatch():
    profile = _contract_profile()
    profile.update({"duration_seconds": 4.3, "baseline_frames": 24, "baseline_fps": 24})
    payload = {
        "graph": _contract_graph(),
        "image_ref": {"imageFile": "shot.png", "imageB64": "/api/view?filename=shot.png"},
        "prompt": "move",
        "frames": 24,
        "fps": 24,
        "profile": profile,
    }
    script = Path(__file__).resolve().parents[2] / "runtime" / "runtime_cli.py"
    result = subprocess.run(
        [sys.executable, str(script), "patch-yusu", "--from-stdin"],
        cwd=Path(__file__).resolve().parents[4],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "duration_seconds" in (result.stdout + result.stderr)


def _experiment_video_build_and_intent():
    positive_zh = "〖0-1 s〗主体移动。"
    positive_en = "〖0-1 s〗The subject moves with a slow dolly in."
    build = {
        "ready_to_execute": True,
        "target": "video",
        "dialect": "video-timeline",
        "prompt": positive_en,
        "positive_zh": positive_zh,
        "positive_en": positive_en,
        "negative_prompt": "",
        "global_prompt": "Preserve identity continuity.",
        "timeline_segments": [{
            "start": 0.0,
            "end": 1.0,
            "text_zh": "主体移动。",
            "text_en": "The subject moves with a slow dolly in.",
        }],
        "dialogue_attribution": [],
        "continuity_requirements": ["subject"],
        "split_recommendation": {"required": False, "reason": "single shot"},
        "source_shot_plan_hash": "a" * 64,
    }
    dimensions = {
        name: []
        for name in (
            "subject", "action", "scene", "lighting", "composition", "camera",
            "motion", "timeline", "audio", "color", "style", "mood", "medium", "quality",
        )
    }
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


def _experiment_shot():
    return {
        "artifact_type": "ShotImage",
        "accepted": True,
        "content_hash": "a" * 64,
        "task_context_hash": "b" * 64,
        "source_story_hash": "c" * 64,
        "art_bible_hash": "d" * 64,
        "lineage_id": "lineage-1",
    }


def test_experiment_d_simple_ltx_timeline_has_25_frames_and_preserves_negative_node():
    graph = _contract_graph()
    original_negative = copy.deepcopy(graph["195"])
    profile = json.loads((PROFILE_FILE.parent / "ltx-yusu-short.json").read_text(encoding="utf-8"))
    patched = patch_yusu_timeline(
        graph,
        {"imageFile": "runs/shot.png", "imageB64": "/api/view?filename=shot.png"},
        "The subject moves with a slow dolly in.",
        24,
        24,
        profile,
        timeline_segments=[{"start_second": 0.0, "end_second": 1.0, "prompt": "The subject moves."}],
    )
    plan_build, intent = _experiment_video_build_and_intent()
    plan = build_video_plan(
        _experiment_shot(),
        plan_build,
        "workflow-hash",
        "profile-hash",
        True,
        duration_profile_id="ltx-yusu-short-v1",
        motion_delta="slow dolly in",
        split_decision={"required": False, "approved": True},
        intent=intent,
    )
    assert plan["parameters"] == {
        "frames": 24,
        "output_frames": 25,
        "fps": 24,
        "duration_seconds": 1.0,
        "output_width": 1024,
        "output_height": 704,
        "start_frame": 0,
        "end_frame": 23,
    }
    assert ltx_output_frame_count(24) == 25
    assert patched["174"]["inputs"]["frame_rate"] == 24
    assert patched["174"]["inputs"]["duration_frames"] == 24
    assert patched["195"] == original_negative


def test_experiment_d_over_complex_event_is_blocked_by_stage4_split_gate():
    build, intent = _experiment_video_build_and_intent()
    intent["complexity"] = {"scene_change": True}
    build["split_recommendation"] = {"required": True, "reason": "scene/time change"}
    assert recommend_ltx_split(intent) == {"required": True, "reason": "scene/time change"}
    with pytest.raises(StageError, match="split"):
        build_video_plan(
            _experiment_shot(),
            build,
            "workflow-hash",
            "profile-hash",
            True,
            duration_profile_id="ltx-yusu-short-v1",
            motion_delta="slow dolly in",
            split_decision={"required": True, "approved": False},
            intent=intent,
        )
