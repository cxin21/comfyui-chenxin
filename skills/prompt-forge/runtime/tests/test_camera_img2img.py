from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime.adapters.camera import (
    CameraAdapterError,
    activate_g1,
    normalize_camera_api_graph,
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
    assert proof["traversed_node_ids"] == [27, 75, 59]


def test_path_proof_can_bind_the_vae_back_to_the_selected_load_image():
    graph = json.loads((FIXTURES / "camera-img2img-api-minimal.json").read_text(encoding="utf-8"))
    proof = verify_img2img_path(
        graph,
        {"img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27, "load_image_node_id": 21, "expected_path_node_ids": [27, 75, 59]}},
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


def test_img2img_patch_binds_declared_camera_direction_and_framing():
    graph = json.loads((FIXTURES / "camera-img2img-api-minimal.json").read_text(encoding="utf-8"))
    graph["583"] = {
        "class_type": "CameraAngleNode",
        "inputs": {"pos_x": 0.0, "pos_y": 0.0, "pos_z": 0.0, "roll": 0.0},
    }
    profile = {
        "img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27, "load_image_node_id": 21},
        "slots": {"camera_angle": {"id": 583, "type": "CameraAngleNode"}},
    }
    patched = patch_img2img_graph(
        graph,
        _prompt_build(),
        "runs/lineage/shot.png",
        profile,
        camera={"direction": "left_45", "distance": "full_body", "elevation": "eye-level"},
    )
    assert patched["583"]["inputs"]["pos_x"] == -0.25
    assert patched["583"]["inputs"]["pos_y"] == 0.0
    assert patched["583"]["inputs"]["pos_z"] == -0.5


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


def _normalization_profile():
    return {
        "schema_version": "1.0",
        "profile_id": "camera-anima-v1",
        "api_normalization": {
            "schema_version": "1.0",
            "literal_inputs": [
                {"node_id": 26, "input_name": "text", "ui_node_id": 26, "widget_index": 1}
            ],
            "output_fallbacks": [
                {"source_node_id": 111, "output_index": 0, "target_node_id": 35, "target_input": "images"},
                {"source_node_id": 111, "output_index": 0, "target_node_id": 490, "target_input": "images"},
            ],
            "remove_nodes": [28, 41, 52, 62, 67, 70, 77],
        },
    }


def _broken_camera_api_graph():
    return {
        "26": {"class_type": "Lora Loader (LoraManager)", "inputs": {"model": ["22", 0]}},
        "35": {"class_type": "Image Saver Simple", "inputs": {"metadata": ["89", 0]}},
        "490": {"class_type": "PreviewImage", "inputs": {}},
        "76": {"class_type": "VAEDecode", "inputs": {"samples": ["51", 0], "vae": ["48", 0]}},
        "96": {"class_type": "AdjustContrast", "inputs": {"images": ["76", 0]}},
        "111": {"class_type": "ImageSharpen", "inputs": {"image": ["96", 0]}},
        **{
            str(node_id): {"class_type": "Optional", "inputs": {}}
            for node_id in (28, 41, 52, 62, 67, 70, 77)
        },
    }


def _camera_ui_with_lora_text():
    return {
        "nodes": [
            {
                "id": 26,
                "type": "Lora Loader (LoraManager)",
                "widgets_values": [{"version": 1}, "<lora:anima:1.0>"],
            }
        ]
    }


def test_camera_api_normalization_repairs_converter_loss_without_mutating_sources():
    graph = _broken_camera_api_graph()
    ui = _camera_ui_with_lora_text()
    original = copy.deepcopy((graph, ui))
    normalized = normalize_camera_api_graph(graph, ui, _normalization_profile())

    assert normalized["26"]["inputs"]["text"] == "<lora:anima:1.0>"
    assert normalized["35"]["inputs"]["images"] == ["111", 0]
    assert normalized["490"]["inputs"]["images"] == ["111", 0]
    assert all(str(node_id) not in normalized for node_id in (28, 41, 52, 62, 67, 70, 77))
    assert all(str(node_id) in normalized for node_id in (76, 96, 111))
    assert (graph, ui) == original


def test_camera_api_normalization_rejects_partial_source_instead_of_guessing():
    graph = _broken_camera_api_graph()
    del graph["76"]
    with pytest.raises(CameraAdapterError, match="normalization source"):
        normalize_camera_api_graph(graph, _camera_ui_with_lora_text(), _normalization_profile())


def test_camera_api_normalization_rejects_malformed_target_inputs_cleanly():
    graph = _broken_camera_api_graph()
    graph["35"]["inputs"] = None
    with pytest.raises(CameraAdapterError, match="normalization target"):
        normalize_camera_api_graph(graph, _camera_ui_with_lora_text(), _normalization_profile())


def test_camera_api_normalization_does_not_trust_idempotent_links_with_wrong_classes():
    graph = _broken_camera_api_graph()
    for node_id in (28, 41, 52, 62, 67, 70, 77):
        del graph[str(node_id)]
    graph["26"]["inputs"]["text"] = "<lora:anima:1.0>"
    graph["35"]["inputs"]["images"] = ["111", 0]
    graph["490"]["inputs"]["images"] = ["111", 0]
    graph["26"]["class_type"] = "UnexpectedNode"
    with pytest.raises(CameraAdapterError, match="unexpected class"):
        normalize_camera_api_graph(graph, _camera_ui_with_lora_text(), _normalization_profile())


def test_camera_api_normalization_ignores_non_numeric_metadata_keys():
    graph = _broken_camera_api_graph()
    graph["_meta"] = {"note": "not a node"}
    normalized = normalize_camera_api_graph(graph, _camera_ui_with_lora_text(), _normalization_profile())
    assert normalized["35"]["inputs"]["images"] == ["111", 0]


def test_camera_api_normalization_rejects_graph_without_pinned_topology_markers():
    graph = {"24": {"class_type": "ImpactWildcardProcessor", "inputs": {}}}
    with pytest.raises(CameraAdapterError, match="topology markers"):
        normalize_camera_api_graph(graph, _camera_ui_with_lora_text(), _normalization_profile())


def test_camera_api_normalization_requires_the_profiled_ui_node_type():
    ui = _camera_ui_with_lora_text()
    ui["nodes"][0]["type"] = "UnexpectedNode"
    with pytest.raises(CameraAdapterError, match="UI LoRA node type"):
        normalize_camera_api_graph(_broken_camera_api_graph(), ui, _normalization_profile())


def test_camera_api_normalization_rejects_conflicting_existing_lora_text():
    graph = _broken_camera_api_graph()
    graph["26"]["inputs"]["text"] = "<lora:other:1.0>"
    with pytest.raises(CameraAdapterError, match="conflicts with UI"):
        normalize_camera_api_graph(graph, _camera_ui_with_lora_text(), _normalization_profile())


def test_camera_api_normalization_allows_edges_within_removed_orphan_branch():
    graph = _broken_camera_api_graph()
    graph["28"]["inputs"]["branch"] = ["41", 0]
    normalized = normalize_camera_api_graph(graph, _camera_ui_with_lora_text(), _normalization_profile())
    assert "28" not in normalized and "41" not in normalized


def test_camera_api_normalization_rejects_a_forged_postprocess_source():
    graph = _broken_camera_api_graph()
    graph["111"]["inputs"]["image"] = ["999", 0]
    with pytest.raises(CameraAdapterError, match="post-process chain"):
        normalize_camera_api_graph(graph, _camera_ui_with_lora_text(), _normalization_profile())


def test_camera_api_normalization_rejects_dangling_reference_to_absent_orphan():
    graph = _broken_camera_api_graph()
    del graph["28"]
    graph["76"]["inputs"]["samples"] = ["28", 0]
    with pytest.raises(CameraAdapterError, match="still feeds node 76"):
        normalize_camera_api_graph(graph, _camera_ui_with_lora_text(), _normalization_profile())


def test_camera_api_normalization_rejects_missing_pinned_profile_for_marked_graph():
    profile = _normalization_profile()
    profile.pop("api_normalization")
    with pytest.raises(CameraAdapterError, match="pinned contract"):
        normalize_camera_api_graph(_broken_camera_api_graph(), _camera_ui_with_lora_text(), profile)
