import copy
import json
from pathlib import Path

import pytest

from runtime.adapters.flux_multiview import (
    FluxAdapterError,
    assert_dual_input_sync,
    patch_base_images,
)


FIXTURE = Path(__file__).parent / "fixtures" / "flux-api-minimal.json"
PROFILE = Path(__file__).parents[1] / "profiles" / "flux2-klein-multiview.json"
SLOTS = {"base_image_primary": 111, "base_image_secondary": 667}


def load_graph():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_both_flux_inputs_receive_the_same_image():
    graph = load_graph()
    patched = patch_base_images(graph, "runs/abc/base-deadbeef.png", SLOTS)

    assert patched["111"]["inputs"]["image"] == "runs/abc/base-deadbeef.png"
    assert patched["667"]["inputs"]["image"] == "runs/abc/base-deadbeef.png"
    assert_dual_input_sync(patched, SLOTS)


def test_one_sided_patch_is_rejected():
    graph = load_graph()
    graph["111"]["inputs"]["image"] = "a.png"
    graph["667"]["inputs"]["image"] = "b.png"

    with pytest.raises(FluxAdapterError, match="same image"):
        assert_dual_input_sync(graph, SLOTS)


def test_pose_images_are_not_changed():
    graph = load_graph()
    patched = patch_base_images(graph, "base.png", SLOTS)

    for node_id in (368, 151, 152, 154, 360, 364, 148, 149, 147, 373, 150, 367):
        assert patched[str(node_id)] == graph[str(node_id)]


def test_patch_is_a_deep_copy_with_exactly_two_allowed_image_changes():
    graph = load_graph()
    original = copy.deepcopy(graph)

    patched = patch_base_images(graph, "runs/abc/base.png", SLOTS)

    assert graph == original
    changed = {
        (node_id, input_name)
        for node_id in graph
        for input_name in set(graph[node_id].get("inputs", {}))
        | set(patched[node_id].get("inputs", {}))
        if graph[node_id].get("inputs", {}).get(input_name)
        != patched[node_id].get("inputs", {}).get(input_name)
    }
    assert changed == {("111", "image"), ("667", "image")}


@pytest.mark.parametrize("image_name", ["", "   ", "/tmp/base.png", "C:/tmp/base.png", "../base.png", "runs/../base.png", "runs\\base.png"])
def test_unsafe_base_image_name_is_rejected(image_name):
    with pytest.raises(FluxAdapterError, match="image_name"):
        patch_base_images(load_graph(), image_name, SLOTS)


def test_invalid_or_same_slots_fail_closed():
    graph = load_graph()
    with pytest.raises(FluxAdapterError, match="different"):
        patch_base_images(graph, "base.png", {"base_image_primary": 111, "base_image_secondary": 111})
    with pytest.raises(FluxAdapterError, match="LoadImage"):
        patch_base_images(graph, "base.png", {"base_image_primary": 524, "base_image_secondary": 667})


def test_profile_has_verified_slots_fingerprint_and_immutable_pose_roles():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    assert profile["runtime_classification"] == "local"
    assert profile["workflow_fingerprint"] == (
        "fff6236efa6727ac6584d61f640a63f9602b2d07a545d216b96a870a681e6faf"
    )
    assert profile["slots"] == {
        "base_image_primary": {"id": 111, "type": "LoadImage"},
        "base_image_secondary": {"id": 667, "type": "LoadImage"},
    }
    assert profile["immutable_roles"]["pose_references"] == [
        368, 151, 152, 154, 360, 364, 148, 149, 147, 373, 150, 367,
    ]
