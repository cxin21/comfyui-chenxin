import copy
import json
from pathlib import Path

import pytest

from runtime.adapters.flux_multiview import (
    FluxAdapterError,
    assert_dual_input_sync,
    patch_base_images,
    patch_view_plan,
)


FIXTURE = Path(__file__).parent / "fixtures" / "flux-api-minimal.json"
PROFILE = Path(__file__).parents[1] / "profiles" / "flux2-klein-multiview.json"
VIEW_PROFILE = Path(__file__).parents[1] / "profiles" / "flux2-klein-view-selection.json"
SLOTS = {"base_image_primary": 111, "base_image_secondary": 667}
POSE_IDS = (368, 151, 152, 154, 360, 364, 148, 149, 147, 373, 150, 367)


def load_graph():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _flat_v2_graph():
    graph = load_graph()
    graph.update(
        {
            "731": {"class_type": "ImpactBoolean", "inputs": {"boolean": False}},
            "756": {"class_type": "ImpactBoolean", "inputs": {"boolean": False}},
            "700": {"class_type": "Text Multiline", "inputs": {"text": "original"}},
            "701": {"class_type": "RandomNoise", "inputs": {"noise_seed": 1}},
            "702": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 512, "height": 512},
            },
            "663": {"class_type": "SaveImage", "inputs": {"filename_prefix": "views/front"}},
            "761": {"class_type": "SaveImage", "inputs": {"filename_prefix": "views/rear45"}},
            "565": {"class_type": "SaveImage", "inputs": {"filename_prefix": "views/side"}},
            "609": {"class_type": "SaveImage", "inputs": {"filename_prefix": "views/rear"}},
        }
    )
    return graph


def _view_profile():
    return {
        "schema_version": "1.0",
        "profile_id": "flux2-klein-view-selection-v1",
        "base_profile_id": "flux2-klein-multiview-flat-v2",
        "workflow_id": "prompt-forge-flat-v2",
        "workflow_name": "PromptForge-Flux2-Klein-multiview-flat-v2.json",
        "workflow_fingerprint": "9dc2b01e2aea0b051113b187b134d007f452df6c83cfcbbd8d325eaa4c29e4da",
        "source_api_graph_hash": "450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36",
        "slots": {
            "base_image_primary": {"id": 111, "type": "LoadImage"},
            "base_image_secondary": {"id": 667, "type": "LoadImage"},
        },
        "view_plan": {
            "switches": {
                "731": {"input": "boolean", "type": "ImpactBoolean"},
                "756": {"input": "boolean", "type": "ImpactBoolean"},
            },
            "prompt_slots": {"700": {"input": "text", "type": "Text Multiline"}},
            "seed_slots": {"701": {"input": "noise_seed", "type": "RandomNoise"}},
            "dimension_slots": {
                "702": {
                    "inputs": ["width", "height"],
                    "type": "EmptyLatentImage",
                }
            },
        },
        "immutable_roles": {"pose_references": list(POSE_IDS)},
        "output_nodes": {
            "524": {"artifact_type": "CharacterAngleView", "view_label": "front_closeup"},
            "663": {"artifact_type": "CharacterAngleView", "view_label": "front"},
            "761": {"artifact_type": "CharacterAngleView", "view_label": "rear_45"},
            "565": {"artifact_type": "CharacterAngleView", "view_label": "side_unknown"},
            "609": {"artifact_type": "CharacterAngleView", "view_label": "rear"},
        },
    }


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


def test_view_plan_changes_only_allowlisted_paths_and_keeps_pose_inputs_immutable():
    graph = _flat_v2_graph()
    original = copy.deepcopy(graph)
    plan = {
        "views": ["front", "rear"],
        "switches": {"731": True},
        "prompts": {"700": "front and rear identity sheet"},
        "seeds": {"701": 42},
        "dimensions": {"702": {"width": 768, "height": 1024}},
        "base_image": "runs/abc/base.png",
        "orientation_evidence": {
            "front": {"source": "profile-output-map", "verified": True},
            "rear": {"source": "profile-output-map", "verified": True},
        },
    }
    patched = patch_view_plan(graph, plan, _view_profile())
    assert graph == original
    assert patched["731"]["inputs"]["boolean"] is True
    assert patched["700"]["inputs"]["text"] == "front and rear identity sheet"
    assert patched["701"]["inputs"]["noise_seed"] == 42
    assert patched["702"]["inputs"] == {"width": 768, "height": 1024}
    assert patched["111"]["inputs"]["image"] == "runs/abc/base.png"
    assert patched["667"]["inputs"]["image"] == "runs/abc/base.png"
    assert {node_id: patched[str(node_id)] for node_id in POSE_IDS} == {
        node_id: graph[str(node_id)] for node_id in POSE_IDS
    }


def test_view_plan_rejects_unknown_switch_and_unmapped_output_label():
    with pytest.raises(FluxAdapterError, match="allowlisted"):
        patch_view_plan(_flat_v2_graph(), {"views": ["front"], "switches": {"999": True}}, _view_profile())
    with pytest.raises(FluxAdapterError, match="output label"):
        patch_view_plan(_flat_v2_graph(), {"views": ["right"], "switches": {}}, _view_profile())


def test_grouped_flux_profile_is_rejected_for_view_plan_patching():
    grouped = _view_profile()
    grouped["base_profile_id"] = "flux2-klein-multiview-v1"
    grouped["workflow_id"] = "grouped-reference-only"
    grouped["workflow_name"] = "Flux2-Klein人物一键多视图工作流.json"
    with pytest.raises(FluxAdapterError, match="flat-v2|flat v2"):
        patch_view_plan(_flat_v2_graph(), {"views": ["front"]}, grouped)


def test_view_selection_profile_pins_flat_v2_switches_and_output_map():
    profile = json.loads(VIEW_PROFILE.read_text(encoding="utf-8"))
    assert profile["base_profile_id"] == "flux2-klein-multiview-flat-v2"
    assert profile["workflow_name"] == "PromptForge-Flux2-Klein-multiview-flat-v2.json"
    assert profile["workflow_fingerprint"] == "9dc2b01e2aea0b051113b187b134d007f452df6c83cfcbbd8d325eaa4c29e4da"
    assert profile["source_api_graph_hash"] == "450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36"
    assert len(profile["view_plan"]["switches"]) == 17
    assert {node["view_label"] for node in profile["output_nodes"].values()} == {
        "front_closeup", "front", "rear_45", "side_unknown", "rear",
    }


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
