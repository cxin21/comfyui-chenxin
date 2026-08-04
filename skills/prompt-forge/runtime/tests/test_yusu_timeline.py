from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime.adapters.yusu_timeline import (
    YusuTimelineError,
    patch_yusu_timeline,
    validate_yusu_immutable_inputs,
    validate_yusu_sync,
)


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
