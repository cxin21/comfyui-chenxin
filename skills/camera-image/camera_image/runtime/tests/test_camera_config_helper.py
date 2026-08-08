import copy

from runtime.camera_config_helper import (
    build_fixed_camera_config,
    compile_fixed_camera_config,
    load_fixed_camera_bundle,
    read_fixed_camera_config,
)


def _plan():
    return {
        "base_model": "anima-base.safetensors",
        "selections": [{
            "name": "Anima\\anima-base-1-masterpiece-v51.safetensors",
            "strength_model": 1.0,
            "strength_clip": 1.0,
            "active": True,
            "trigger_words": ["masterpiece"],
        }],
        "inventory_hash": "a" * 64,
        "recommendation_hash": "b" * 64,
    }


def _extra():
    return {
        "extreme_type": "none", "extreme_weight": 0.0,
        "lens_enabled": False, "lens_value": "",
        "dof_enabled": True, "dof_value": "shallow depth of field", "dof_weight": 1.1,
        "movement_enabled": False, "movement_value": "",
        "composition_enabled": True, "composition_value": "rule of thirds",
        "style_enabled": False, "style_value": "",
    }


def test_helper_reads_only_the_declared_camera_surface():
    bundle = load_fixed_camera_bundle("shot-image")
    values = read_fixed_camera_config(bundle)

    assert bundle["workflow_asset"] == "camera-anima.json"
    assert len(values["values"]["camera_extra"]) == 13
    assert "sampler" not in values["values"]
    assert "seed" not in values["values"]


def test_helper_patches_all_declared_camera_controls_and_preserves_internals():
    bundle = load_fixed_camera_bundle("shot-image")
    config = build_fixed_camera_config(
        stage="shot-image",
        prompts={"positive": "hero, front view", "negative": "low quality"},
        camera={"direction": "left", "elevation": "low-angle", "distance": "full_body", "roll": 12.0},
        camera_extra=_extra(),
        groups={"enabled_g1": [], "enabled_g2": []},
        lora_plan=_plan(),
        reference_image="input.png",
    )
    result = compile_fixed_camera_config(bundle, config, image_name="input.png")
    before = {node["id"]: node for node in bundle["ui_workflow"]["nodes"]}
    after = {node["id"]: node for node in result["ui_workflow"]["nodes"]}

    assert after[24]["widgets_values"][0] == "hero, front view"
    assert after[25]["widgets_values"][0] == "low quality"
    assert after[583]["widgets_values"][:4] == [-90, -45, 1, 12.0]
    assert after[585]["widgets_values"][:13] == [
        "none", 0.0, False, "", True, "shallow depth of field", 1.1,
        False, "", True, "rule of thirds", False, "",
    ]
    assert after[26]["widgets_values"][1] == "<lora:Anima\\anima-base-1-masterpiece-v51:1.00>"
    assert after[66]["widgets_values"][4] == "masterpiece,"
    assert result["api_graph"]["24"]["inputs"]["wildcard_text"] == "hero, front view"
    assert result["api_graph"]["25"]["inputs"]["populated_text"] == "low quality"
    assert result["api_graph"]["583"]["inputs"]["pos_y"] == -0.5
    assert result["api_graph"]["585"]["inputs"]["dof_value"] == "shallow depth of field"
    assert result["api_graph"]["26"]["inputs"]["text"] == "<lora:Anima\\anima-base-1-masterpiece-v51:1.00>"
    assert result["api_graph"]["66"]["inputs"]["orinalMessage"] == "masterpiece,"
    assert after[27]["widgets_values"] == before[27]["widgets_values"]
    assert after[27]["mode"] == before[27]["mode"]







