"""P2 tests for runtime.config_surface (config-surface-lora-unit design)."""

from __future__ import annotations

import copy

import pytest

from runtime.config_surface import (
    ConfigSurfaceError,
    build_stage_config,
    validate_config_surface,
    validate_stage_config,
)

NEUTRAL_EXTRA = {
    "extreme_type": "none", "extreme_weight": 0.0,
    "lens_enabled": False, "lens_value": "",
    "dof_enabled": False, "dof_value": "", "dof_weight": 0.0,
    "movement_enabled": False, "movement_value": "",
    "composition_enabled": False, "composition_value": "",
    "style_enabled": False, "style_value": "",
}

SURFACE_PROFILE = {
    "config_surface": {
        "schema_version": "1.0",
        "prompts": {"nodes": [24, 25], "fields": ["wildcard_text", "populated_text"]},
        "camera": {"angle_node": 583, "extra_node": 585},
        "group_controllers": {
            "g1": {"node_id": 23, "match_title": "\uff08G1\uff09"},
            "g2": {"node_id": 90, "match_title": "\uff08G2\uff09"},
        },
        "lora_unit": {
            "loader_node": 26, "stack_widget_index": 1, "list_widget_index": 2,
            "trigger_toggle_node": 66, "binding": "atomic",
            "inventory_source": "mcp:list_local_models",
            "metadata_source": "mcp:model_metadata",
            "policy": "recommend-then-approve",
        },
    }
}


def _lora_plan():
    return {
        "base_model": "miaomiaoHarem_anima15.safetensors",
        "selections": [
            {
                "name": "Anima\\anima-base-1-masterpiece-v51",
                "strength_model": 1.0, "strength_clip": 1.0,
                "active": True, "trigger_words": ["masterpiece"],
            }
        ],
        "inventory_hash": "a" * 64,
        "recommendation_hash": "b" * 64,
    }


def _stage1(**overrides):
    payload = {
        "stage": "character-base",
        "prompts": {"positive": "hero portrait", "negative": "lowres"},
        "camera": {"direction": "front", "elevation": "eye-level", "distance": "full_body", "roll": 0.0},
        "camera_extra": copy.deepcopy(NEUTRAL_EXTRA),
        "groups": {"enabled_g1": [], "enabled_g2": ["\u5bf9\u6bd4\u5ea6\uff08G2\uff09"]},
        "lora_plan": _lora_plan(),
    }
    payload.update(overrides)
    return build_stage_config(**payload)


def _stage3(**overrides):
    payload = {
        "stage": "shot-image",
        "prompts": {"positive": "shot", "negative": ""},
        "camera": {"direction": "back", "elevation": "high-angle", "distance": "medium", "roll": 5.0},
        "camera_extra": copy.deepcopy(NEUTRAL_EXTRA),
        "groups": {"enabled_g1": [], "enabled_g2": ["\u5bf9\u6bd4\u5ea6\uff08G2\uff09"]},
        "lora_plan": _lora_plan(),
        "reference_image": "reference.png",
    }
    payload.update(overrides)
    return build_stage_config(**payload)


def test_stage1_config_builds_with_self_consistent_hash():
    config = _stage1()
    assert config["config_hash"]
    assert config["lora_plan"]["stack_text"] == "<lora:Anima\\anima-base-1-masterpiece-v51:1.00>"
    assert validate_stage_config(config) == config


def test_validate_returns_deep_copy():
    config = _stage1()
    validated = validate_stage_config(config)
    validated["prompts"]["positive"] = "tampered"
    assert config["prompts"]["positive"] == "hero portrait"


def test_stage3_requires_reference_and_keeps_img2img_group_fixed():
    assert _stage3()["reference_image"] == "reference.png"
    with pytest.raises(ConfigSurfaceError):
        _stage3(reference_image=None)


def test_stage1_rejects_nonempty_g1_and_reference():
    with pytest.raises(ConfigSurfaceError):
        _stage1(groups={"enabled_g1": ["\u52a0\u8f7d\u56fe\u7247\uff08G1\uff09"], "enabled_g2": []})
    with pytest.raises(ConfigSurfaceError):
        _stage1(reference_image="x.png")


def test_stage1_camera_must_be_neutral():
    camera = {"direction": "back", "elevation": "eye-level", "distance": "full_body", "roll": 0.0}
    with pytest.raises(ConfigSurfaceError):
        _stage1(camera=camera)


def test_camera_extra_requires_exact_field_set():
    extra = copy.deepcopy(NEUTRAL_EXTRA)
    del extra["style_value"]
    with pytest.raises(ConfigSurfaceError):
        _stage1(camera_extra=extra)
    extra = copy.deepcopy(NEUTRAL_EXTRA)
    extra["surprise"] = 1
    with pytest.raises(ConfigSurfaceError):
        _stage1(camera_extra=extra)


def test_stack_text_is_derived_and_tamper_proof():
    config = _stage1()
    config["lora_plan"]["stack_text"] = "<lora:evil:1.00>"
    with pytest.raises(ConfigSurfaceError):
        validate_stage_config(config)


def test_selection_schema_enforced():
    plan = _lora_plan()
    del plan["selections"][0]["trigger_words"]
    with pytest.raises(ConfigSurfaceError):
        _stage1(lora_plan=plan)
    plan = _lora_plan()
    plan["selections"][0]["strength_model"] = -1
    with pytest.raises(ConfigSurfaceError):
        _stage1(lora_plan=plan)


def test_unknown_stage_rejected():
    with pytest.raises(ConfigSurfaceError):
        _stage1(stage="video")


def test_config_hash_tamper_detected():
    config = _stage1()
    config["prompts"]["positive"] = "tampered"
    with pytest.raises(ConfigSurfaceError):
        validate_stage_config(config)


def test_validate_config_surface_absent_returns_none():
    assert validate_config_surface({"profile_id": "x"}) is None


def test_validate_config_surface_accepts_full_profile():
    surface = validate_config_surface(SURFACE_PROFILE)
    assert surface["lora_unit"]["binding"] == "atomic"
    assert surface["group_controllers"]["g1"]["match_title"] == "\uff08G1\uff09"


def test_validate_config_surface_rejects_bad_shapes():
    bad = copy.deepcopy(SURFACE_PROFILE)
    bad["config_surface"]["schema_version"] = "2.0"
    with pytest.raises(ConfigSurfaceError):
        validate_config_surface(bad)
    bad = copy.deepcopy(SURFACE_PROFILE)
    bad["config_surface"]["prompts"]["nodes"] = [24]
    with pytest.raises(ConfigSurfaceError):
        validate_config_surface(bad)
    bad = copy.deepcopy(SURFACE_PROFILE)
    bad["config_surface"]["lora_unit"]["policy"] = "auto"
    with pytest.raises(ConfigSurfaceError):
        validate_config_surface(bad)
    with pytest.raises(ConfigSurfaceError):
        validate_config_surface({"config_surface": "nope"})



