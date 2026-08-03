from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime.adapters.camera import (
    CameraAdapterError,
    activate_g1,
    patch_img2img_graph,
    verify_img2img_path,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _ui_workflow():
    return json.loads((FIXTURES / "camera-img2img-ui-minimal.json").read_text(encoding="utf-8"))


def _profile():
    return {
        "img2img": {
            "group_id": 3,
            "node_ids": [21, 58, 57, 59],
            "load_image_node_id": 21,
            "vae_encode_node_id": 59,
            "sampler_node_id": 27,
        }
    }


def test_complete_g1_group_is_activated():
    workflow = _ui_workflow()
    patched = activate_g1(workflow, "runs/lineage/ref.png", _profile())
    nodes = {node["id"]: node for node in patched["nodes"]}
    assert {nodes[node_id]["mode"] for node_id in (21, 58, 57, 59)} == {0}
    assert nodes[21]["widgets_values"][0] == "runs/lineage/ref.png"
    assert nodes[90]["mode"] == 4
    assert nodes[90]["widgets_values"] == ["unchanged"]


def test_partial_g1_profile_is_rejected():
    with pytest.raises(CameraAdapterError, match="complete G1"):
        activate_g1(
            _ui_workflow(),
            "ref.png",
            {"img2img": {"group_id": 3, "node_ids": [21, 57, 59], "load_image_node_id": 21}},
        )


def test_activation_does_not_mutate_source():
    workflow = _ui_workflow()
    original = copy.deepcopy(workflow)
    activate_g1(workflow, "ref.png", _profile())
    assert workflow == original


def test_extra_group_member_is_rejected():
    workflow = _ui_workflow()
    workflow["nodes"].append(
        {"id": 60, "type": "Anything", "mode": 4, "group_id": 3, "widgets_values": []}
    )
    with pytest.raises(CameraAdapterError, match="complete G1"):
        activate_g1(workflow, "ref.png", _profile())


def test_converted_graph_must_reach_sampler_latent():
    graph = json.loads((FIXTURES / "camera-img2img-api-minimal.json").read_text(encoding="utf-8"))
    proof = verify_img2img_path(graph, {"img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27}})
    assert proof["vae_encode_node_id"] == 59
    assert proof["sampler_node_id"] == 27
    assert proof["traversed_node_ids"] == [27, 59]


def test_path_proof_can_bind_the_vae_back_to_the_selected_load_image():
    graph = json.loads((FIXTURES / "camera-img2img-api-minimal.json").read_text(encoding="utf-8"))
    proof = verify_img2img_path(
        graph,
        {"img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27, "load_image_node_id": 21, "expected_path_node_ids": [27, 59]}},
    )
    assert proof["image_path_node_ids"] == [59, 57, 21]


def test_converted_graph_must_follow_the_selected_latent_switch_branch():
    graph = {
        "27": {"class_type": "KSampler", "inputs": {"latent_image": [75, 0]}},
        "75": {
            "class_type": "ImpactSwitch",
            "inputs": {"input1": [100, 0], "input2": [59, 0], "select": [58, 0]},
        },
        "100": {"class_type": "EmptyLatentImage", "inputs": {"width": 512}},
        "58": {"class_type": "PrimitiveInt", "inputs": {"value": 2}},
        "59": {"class_type": "VAEEncode", "inputs": {"pixels": [57, 0]}},
        "57": {"class_type": "ImageResizeKJv2", "inputs": {"image": [21, 0]}},
        "21": {"class_type": "LoadImage", "inputs": {"image": "ref.png"}},
    }
    proof = verify_img2img_path(
        graph,
        {"img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27}},
    )
    assert proof["traversed_node_ids"] == [27, 75, 59]


def test_path_rejects_cycle():
    graph = {
        "27": {"class_type": "KSampler", "inputs": {"latent_image": [57, 0]}},
        "57": {"class_type": "ImageResizeKJv2", "inputs": {"image": [57, 0]}},
        "59": {"class_type": "VAEEncode", "inputs": {}},
    }
    with pytest.raises(CameraAdapterError, match="cycle"):
        verify_img2img_path(graph, {"img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27}})


def test_path_rejects_wrong_vae_class():
    graph = {"27": {"class_type": "KSampler", "inputs": {"latent_image": [59, 0]}}, "59": {"class_type": "NotVAE", "inputs": {}}}
    with pytest.raises(CameraAdapterError, match="VAEEncode"):
        verify_img2img_path(graph, {"img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27}})


def _prompt_build():
    return {"prompt": "subject, action", "negative_prompt": "lowres"}


def test_img2img_patch_binds_prompt_and_g1_image_without_topology_mutation():
    graph = json.loads((FIXTURES / "camera-img2img-api-minimal.json").read_text(encoding="utf-8"))
    original = copy.deepcopy(graph)
    patched = patch_img2img_graph(
        graph,
        _prompt_build(),
        "runs/lineage/shot.png",
        {"img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27, "load_image_node_id": 21}},
    )
    assert graph == original
    assert patched["21"]["inputs"]["image"] == "runs/lineage/shot.png"
    assert patched["24"]["inputs"]["wildcard_text"] == "subject, action"
    assert patched["25"]["inputs"]["populated_text"] == "lowres"
    assert patched["27"] == original["27"]


def test_img2img_patch_rejects_path_traversal_and_broken_graph():
    graph = json.loads((FIXTURES / "camera-img2img-api-minimal.json").read_text(encoding="utf-8"))
    with pytest.raises(CameraAdapterError, match="relative Comfy input"):
        patch_img2img_graph(
            graph,
            _prompt_build(),
            "../shot.png",
            {"img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27, "load_image_node_id": 21}},
        )
    broken = copy.deepcopy(graph)
    broken["27"]["inputs"]["latent_image"] = [100, 0]
    with pytest.raises(CameraAdapterError, match="missing API node"):
        patch_img2img_graph(
            broken,
            _prompt_build(),
            "shot.png",
            {"img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27, "load_image_node_id": 21}},
        )
