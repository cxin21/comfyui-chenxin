from __future__ import annotations

import copy
import pytest

from runtime.stage_config_surface import (StageSurfaceError, apply_stage_patch, compile_fixed_stage_patch, read_fixed_stage_config, read_stage_config, surface_for, validate_surface)


def _graph():
    graph = {"111": {"class_type": "LoadImage", "inputs": {"image": "a.png"}}, "667": {"class_type": "LoadImage", "inputs": {"image": "a.png"}}, "218": {"class_type": "CR Text", "inputs": {"text": "front"}}, "174": {"class_type": "YusuLTXDirector", "inputs": {"local_prompts": "move", "timeline_data": "{}", "segment_lengths": "24", "duration_seconds": 1.0, "frame_rate": 24}}, "175": {"class_type": "YusuLTXDirector", "inputs": {"image": "shot.png"}}, "195": {"class_type": "CLIPTextEncode", "inputs": {"text": "bad"}}, "359": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "FLux\\f2k_consis.safetensors", "strength_model": 0.35}}, "764": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "FLux\\bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors", "strength_model": 0.45}}}
    graph["80"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "LTX\\\\Ltx2.3-Licon-VBVR-I2V-240K-R32.safetensors", "strength_model": 0.7}}
    graph["114"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "LTX\\\\ltx-2.3-22b-ic-lora-refocus.safetensors", "strength_model": 0.7}}
    for node_id in (727, 730, 731, 734, 735, 738, 741, 742, 743, 746, 747, 749, 750, 756, 759, 769, 772):
        graph[str(node_id)] = {"class_type": "Switch any [Crystools]", "inputs": {"boolean": False}}
    for node_id in (219, 220, 221, 361, 365, 374):
        graph[str(node_id)] = {"class_type": "CR Text", "inputs": {"text": "view"}}
    return graph


def test_all_production_stages_have_surfaces_without_internal_fields():
    for stage in ("character-base", "multiview", "shot-image", "video"):
        surface = validate_surface(surface_for(stage))
        assert surface["workflow_asset"].endswith(".json")
        assert not {item["input"] for values in surface["slots"].values() for item in values}.intersection({"seed", "sampler_name", "scheduler", "steps", "cfg"})


def test_multiview_reads_only_declared_slots():
    result = read_stage_config(_graph(), surface_for("multiview"))
    assert set(result) == {"base_image", "view_switches", "view_prompts", "lora_unit", "trigger_words"}
    assert set(result["base_image"]) == {"111.image", "667.image"}


def test_video_patch_is_local_and_sampler_is_not_a_slot():
    graph = _graph()
    original = copy.deepcopy(graph)
    patched = apply_stage_patch(graph, surface_for("video"), {"positive_prompt": {"174.local_prompts": "slow dolly in"}, "negative_prompt": {"195.text": "watermark"}})
    assert patched["174"]["inputs"]["local_prompts"] == "slow dolly in" and patched["195"]["inputs"]["text"] == "watermark"
    assert patched["111"] == original["111"]
    with pytest.raises(StageSurfaceError, match="not declared|forbidden"):
        apply_stage_patch(graph, surface_for("video"), {"sampler": {"128.sampler_name": "euler"}})


def test_surface_fails_closed_on_node_type_drift():
    graph = _graph()
    graph["111"]["class_type"] = "KSampler"
    with pytest.raises(StageSurfaceError, match="class_type"):
        read_stage_config(graph, surface_for("multiview"))


def test_fixed_asset_read_and_compile_return_only_surface_provenance():
    graph = _graph()
    read = read_fixed_stage_config("multiview", graph)
    assert read["workflow_asset"] == "flux2-klein-multiview-flat-v2.json"
    assert set(read["values"]) == {"base_image", "view_switches", "view_prompts", "lora_unit", "trigger_words"}
    compiled = compile_fixed_stage_patch(
        "video",
        graph,
        {"positive_prompt": {"174.local_prompts": "a slow dolly"}},
    )
    assert compiled["api_graph"]["174"]["inputs"]["local_prompts"] == "a slow dolly"
    assert "seed" not in compiled["api_graph"]
    assert "sampler_name" not in compiled["api_graph"]
    assert set(compiled) == {"stage", "workflow_asset", "workflow_fingerprint", "config_surface_hash", "patch_hash", "api_graph"}


def test_fixed_asset_compiler_rejects_internal_fields():
    with pytest.raises(StageSurfaceError, match="not declared|forbidden"):
        compile_fixed_stage_patch("video", _graph(), {"sampler": {"128.sampler_name": "euler"}})


def test_every_declared_slot_has_product_metadata():
    for stage in ("character-base", "multiview", "shot-image", "video"):
        surface = validate_surface(surface_for(stage))
        for bindings in surface["slots"].values():
            for binding in bindings:
                assert {"default", "allowed_values", "validation"}.issubset(binding)


def test_fixed_camera_ui_surface_reads_and_compiles_without_internal_sampler_fields():
    import json
    from pathlib import Path
    from runtime.config_surface import build_stage_config
    from runtime.stage_config_surface import compile_fixed_ui_stage_patch, read_fixed_ui_stage_config
    from runtime.workflow_assets import load_fixed_workflow

    workflow = load_fixed_workflow("camera-anima.json")
    extra = {
        "extreme_type": "none", "extreme_weight": 0.0,
        "lens_enabled": False, "lens_value": "", "dof_enabled": False, "dof_value": "", "dof_weight": 0.0,
        "movement_enabled": False, "movement_value": "", "composition_enabled": False, "composition_value": "",
        "style_enabled": False, "style_value": "",
    }
    plan = {
        "base_model": "base.safetensors",
        "selections": [{"name": "test.safetensors", "strength_model": 1.0, "strength_clip": 1.0, "active": True, "trigger_words": ["hero"]}],
        "inventory_hash": "a" * 64, "recommendation_hash": "b" * 64,
    }
    config = build_stage_config(
        stage="character-base", prompts={"positive": "hero", "negative": "lowres"},
        camera={"direction": "front", "elevation": "eye-level", "distance": "full_body", "roll": 0.0},
        camera_extra=extra, groups={"enabled_g1": [], "enabled_g2": []}, lora_plan=plan,
    )
    read = read_fixed_ui_stage_config("character-base", workflow)
    assert set(read["values"]) == {"positive_prompt", "negative_prompt", "camera_angle", "camera_extra", "groups", "lora_unit"}
    compiled = compile_fixed_ui_stage_patch("character-base", workflow, config)
    assert compiled["workflow_asset"] == "camera-anima.json"
    assert "27.sampler_name" not in json.dumps(compiled)
    nodes = {node["id"]: node for node in compiled["ui_workflow"]["nodes"]}
    assert nodes[24]["widgets_values"][0] == "hero"
    assert nodes[26]["widgets_values"][1].startswith("<lora:test:")
    assert nodes[66]["widgets_values"][4] == "hero,"


def test_fixed_camera_ui_surface_compiles_img2img_reference_without_user_group_toggle():
    import json
    from pathlib import Path
    from runtime.config_surface import build_stage_config
    from runtime.stage_config_surface import compile_fixed_ui_stage_patch
    from runtime.workflow_assets import load_fixed_workflow

    profile = json.loads((Path(__file__).parents[1] / "profiles" / "camera-anima.json").read_text(encoding="utf-8"))
    extra = {
        "extreme_type": "none", "extreme_weight": 0.0,
        "lens_enabled": False, "lens_value": "", "dof_enabled": False, "dof_value": "", "dof_weight": 0.0,
        "movement_enabled": False, "movement_value": "", "composition_enabled": False, "composition_value": "",
        "style_enabled": False, "style_value": "",
    }
    plan = {
        "base_model": "base.safetensors",
        "selections": [{"name": "test.safetensors", "strength_model": 1.0, "strength_clip": 1.0, "active": True, "trigger_words": ["hero"]}],
        "inventory_hash": "a" * 64, "recommendation_hash": "b" * 64,
    }
    config = build_stage_config(
        stage="shot-image", prompts={"positive": "hero", "negative": "lowres"},
        camera={"direction": "back", "elevation": "high-angle", "distance": "medium", "roll": 0.0},
        camera_extra=extra, groups={"enabled_g1": [], "enabled_g2": []},
        lora_plan=plan, reference_image="input.png",
    )
    result = compile_fixed_ui_stage_patch("shot-image", load_fixed_workflow("camera-anima.json"), config)
    nodes = {node["id"]: node for node in result["ui_workflow"]["nodes"]}
    assert nodes[21]["widgets_values"][0] == "input.png"
    assert nodes[23]["mode"] == 0
    assert result["workflow_asset"] == "camera-anima.json"




def test_multiview_plan_compiles_only_declared_view_slots():
    from runtime.stage_config_surface import compile_fixed_multiview_plan

    result = compile_fixed_multiview_plan(_graph(), {
        "views": ["front"],
        "base_image": "new.png",
        "switches": {"727": True, "741": False},
        "prompts": {"218": "front view"},
        "orientation_evidence": {"front": {"verified": True}},
    })
    graph = result["api_graph"]
    assert graph["111"]["inputs"]["image"] == "new.png"
    assert graph["667"]["inputs"]["image"] == "new.png"
    assert graph["727"]["inputs"]["boolean"] is True
    assert graph["218"]["inputs"]["text"] == "front view"
    with pytest.raises(StageSurfaceError, match="dimensions"):
        compile_fixed_multiview_plan(_graph(), {"views": ["front"], "dimensions": {"702": {"width": 1}}})


def test_character_base_plan_compiles_only_declared_prompt_slots():
    from runtime.stage_config_surface import compile_fixed_character_base_plan

    graph = {
        "24": {"class_type": "ImpactWildcardProcessor", "inputs": {"wildcard_text": "old", "populated_text": "old"}},
        "25": {"class_type": "ImpactWildcardProcessor", "inputs": {"wildcard_text": "old", "populated_text": "old"}},
        "27": {"class_type": "KSampler", "inputs": {"sampler_name": "euler", "seed": 1}},
    }
    result = compile_fixed_character_base_plan(graph, {"prompt": "hero", "negative_prompt": "lowres"})
    assert result["api_graph"]["24"]["inputs"]["wildcard_text"] == "hero"
    assert result["api_graph"]["25"]["inputs"]["populated_text"] == "lowres"
    assert result["api_graph"]["27"] == graph["27"]
    with pytest.raises(StageSurfaceError):
        compile_fixed_character_base_plan({}, {"prompt": "hero", "negative_prompt": "lowres"})

def test_multiview_lora_and_trigger_words_are_one_declared_patch():
    from runtime.stage_config_surface import compile_fixed_multiview_plan

    plan = {
        "base_model": "flux-klein-9b",
        "selections": [{
            "name": "FLux\\f2k_consis",
            "strength_model": 0.35,
            "strength_clip": 0.35,
            "active": True,
            "trigger_words": ["f2k_consis"],
        }],
        "inventory_hash": "a" * 64,
        "recommendation_hash": "b" * 64,
    }
    result = compile_fixed_multiview_plan(_graph(), {
        "views": ["front"],
        "base_image": "new.png",
        "switches": {"727": True},
        "prompts": {"218": "front view"},
        "orientation_evidence": {},
        "lora_plan": plan,
    })["api_graph"]
    assert result["359"]["inputs"]["lora_name"].endswith(".safetensors")
    assert result["359"]["inputs"]["strength_model"] == 0.35
    assert result["218"]["inputs"]["text"].endswith("f2k_consis")
    assert result["764"]["inputs"]["lora_name"].endswith(".safetensors")
