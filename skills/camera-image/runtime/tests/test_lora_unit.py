"""P3 tests for runtime.adapters.lora_unit (config-surface-lora-unit design)."""

from __future__ import annotations

import copy

import pytest

from runtime.config_surface import ConfigSurfaceError, validate_config_surface

from runtime.adapters.lora_unit import (
    LoraUnitAdapterError,
    patch_group_toggles,
    patch_lora_unit,
)
from runtime.lora_discovery import (
    LoraDiscoveryError,
    LoraSelection,
    render_lora_stack,
    to_lora_reference,
)

SURFACE_PROFILE = {
    "config_surface": {
        "schema_version": "1.0",
        "prompts": {"nodes": [24, 25], "fields": ["wildcard_text", "populated_text"]},
        "camera": {"angle_node": 583, "extra_node": 585},
        "group_controllers": {
            "g1": {"node_id": 23, "match_title": "（G1）"},
            "g2": {"node_id": 90, "match_title": "（G2）"},
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


def _word_entry(text):
    return {
        "text": text,
        "active": True,
        "highlighted": False,
        "strength": None,
        "items": [{"text": text, "active": True, "highlighted": False, "strength": None}],
    }


def _ui_workflow():
    return {
        "nodes": [
            {"id": 23, "type": "Fast Groups Bypasser (rgthree)", "pos": [720, 740], "mode": 0},
            {
                "id": 90,
                "type": "Fast Groups Bypasser (rgthree)",
                "title": "Fast Groups Bypasser Post Processing",
                "pos": [3800, 60],
                "mode": 0,
            },
            {"id": 24, "type": "ImpactWildcardProcessor", "pos": [-820, 740], "mode": 0, "widgets_values": ["pos", "pos"]},
            {"id": 25, "type": "ImpactWildcardProcessor", "pos": [-390, 1110], "mode": 0, "widgets_values": ["neg", "neg"]},
            {
                "id": 26,
                "type": "Lora Loader (LoraManager)",
                "pos": [1500, 740],
                "mode": 0,
                "widgets_values": [
                    {"version": 1, "textWidgetName": "text"},
                    "<lora:legacy:1.00>",
                    [
                        {
                            "name": "legacy",
                            "strength": 1,
                            "active": True,
                            "expanded": False,
                            "clipStrength": 1,
                            "selected": False,
                            "locked": False,
                        }
                    ],
                ],
            },
            {
                "id": 66,
                "type": "TriggerWord Toggle (LoraManager)",
                "pos": [1200, 1430],
                "mode": 0,
                "widgets_values": [True, True, False, [_word_entry("legacy")], "legacy,"],
            },
            {"id": 21, "type": "LoadImage", "pos": [60, 740], "mode": 4, "widgets_values": ["old.png"]},
            {"id": 58, "type": "PrimitiveInt", "pos": [60, 900], "mode": 4, "widgets_values": [0]},
            {"id": 27, "type": "KSampler", "pos": [2400, 700], "mode": 0, "widgets_values": [1]},
            {"id": 96, "type": "AdjustContrast", "pos": [3760, 140], "mode": 0, "widgets_values": [1.0]},
            {"id": 111, "type": "ImageSharpen", "pos": [4010, 320], "mode": 0, "widgets_values": ["simple"]},
            {"id": 583, "type": "CameraAngleNode", "pos": [-820, 80], "mode": 0, "widgets_values": [0, 0, 0, 0]},
            {"id": 585, "type": "CameraExtraConfigNode", "pos": [-440, 120], "mode": 0, "widgets_values": ["none"]},
        ],
        "groups": [
            {"id": 3, "title": "加载图片（G1）", "bounding": [50, 670, 320, 600]},
            {"id": 15, "title": "第二轮采样器（G1）", "bounding": [2310, 670, 400, 930]},
            {"id": 117, "title": "对比度（G2）", "bounding": [3750, 70, 230, 140]},
            {"id": 107, "title": "图像锐化（G2）", "bounding": [4000, 250, 230, 190]},
            {"id": 132, "title": "相机视角生图（G1）", "bounding": [-830, 10, 1200, 650]},
            {"id": 124, "title": "文生图（模块）", "bounding": [-860, -30, 6860, 1880]},
        ],
        "links": [],
    }


def _selections():
    return [
        {
            "name": "Anima\\anima-base-1-masterpiece-v51",
            "strength_model": 1.0,
            "strength_clip": 1.0,
            "active": True,
            "trigger_words": ["masterpiece"],
        },
        {
            "name": "Anima\\Anima_in_real_epoch_10",
            "strength_model": 0.8,
            "strength_clip": 0.9,
            "active": False,
            "trigger_words": ["realistic"],
        },
    ]


def _lora_plan(selections=None, stack_text=None):
    chosen = selections if selections is not None else _selections()
    if stack_text is None:
        stack_text = render_lora_stack([LoraSelection(**selection) for selection in chosen])
    return {
        "base_model": "miaomiaoHarem_anima15.safetensors",
        "selections": chosen,
        "stack_text": stack_text,
        "inventory_hash": "a" * 64,
        "recommendation_hash": "b" * 64,
    }


def _node(workflow, node_id):
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def test_to_lora_reference_strips_extension():
    assert (
        to_lora_reference("Anima\\anima-base-1-masterpiece-v51.safetensors")
        == "Anima\\anima-base-1-masterpiece-v51"
    )
    assert to_lora_reference("flat.safetensors") == "flat"


def test_to_lora_reference_rejects_bad_names():
    for bad in ("Anima\\foo", "", "   ", ".safetensors", 123, None):
        with pytest.raises(LoraDiscoveryError):
            to_lora_reference(bad)


def test_patch_lora_unit_writes_bound_pair():
    workflow = _ui_workflow()
    patched = patch_lora_unit(workflow, _lora_plan(), SURFACE_PROFILE)
    loader = _node(patched, 26)
    toggle = _node(patched, 66)
    assert loader["widgets_values"][0] == {"version": 1, "textWidgetName": "text"}
    assert loader["widgets_values"][1] == (
        "<lora:Anima\\anima-base-1-masterpiece-v51:1.00>"
        "<lora:Anima\\Anima_in_real_epoch_10:0.80:0.90>"
    )
    assert loader["widgets_values"][2] == [
        {
            "name": "Anima\\anima-base-1-masterpiece-v51",
            "strength": 1,
            "active": True,
            "expanded": False,
            "clipStrength": 1,
            "selected": False,
            "locked": False,
        },
        {
            "name": "Anima\\Anima_in_real_epoch_10",
            "strength": 0.8,
            "active": False,
            "expanded": False,
            "clipStrength": 0.9,
            "selected": False,
            "locked": False,
        },
    ]
    assert toggle["widgets_values"][0:3] == [True, True, False]
    assert toggle["widgets_values"][3] == [_word_entry("masterpiece")]
    assert toggle["widgets_values"][4] == "masterpiece,"
    source_loader = _node(workflow, 26)
    assert source_loader["widgets_values"][1] == "<lora:legacy:1.00>"


def test_patch_lora_unit_clears_words_when_all_inactive():
    plan = _lora_plan(selections=[_selections()[1]])
    patched = patch_lora_unit(_ui_workflow(), plan, SURFACE_PROFILE)
    toggle = _node(patched, 66)
    assert toggle["widgets_values"][3] == []
    assert toggle["widgets_values"][4] == ""


def test_patch_lora_unit_rejects_tampered_stack_text():
    plan = _lora_plan(stack_text="<lora:evil:1.00>")
    with pytest.raises(LoraUnitAdapterError):
        patch_lora_unit(_ui_workflow(), plan, SURFACE_PROFILE)


def test_patch_lora_unit_rejects_invalid_selection():
    plan = _lora_plan()
    del plan["selections"][0]["trigger_words"]
    with pytest.raises(LoraUnitAdapterError):
        patch_lora_unit(_ui_workflow(), plan, SURFACE_PROFILE)
    plan = _lora_plan()
    plan["selections"][0]["strength_model"] = -1
    with pytest.raises(LoraUnitAdapterError):
        patch_lora_unit(_ui_workflow(), plan, SURFACE_PROFILE)


def test_patch_lora_unit_requires_surface_profile():
    with pytest.raises(LoraUnitAdapterError):
        patch_lora_unit(_ui_workflow(), _lora_plan(), {"profile_id": "x"})


def test_patch_lora_unit_rejects_wrong_node_classes():
    workflow = _ui_workflow()
    _node(workflow, 66)["type"] = "SomethingElse"
    with pytest.raises(LoraUnitAdapterError):
        patch_lora_unit(workflow, _lora_plan(), SURFACE_PROFILE)


def test_patch_group_toggles_stage1_disables_effects_and_protects_camera():
    workflow = _ui_workflow()
    patched = patch_group_toggles(
        workflow, {"enabled_g1": [], "enabled_g2": ["对比度（G2）"]}, SURFACE_PROFILE
    )
    assert _node(patched, 21)["mode"] == 4
    assert _node(patched, 58)["mode"] == 4
    assert _node(patched, 27)["mode"] == 4
    assert _node(patched, 96)["mode"] == 0
    assert _node(patched, 111)["mode"] == 4
    assert _node(patched, 583)["mode"] == 0
    assert _node(patched, 585)["mode"] == 0
    for node_id in (23, 90, 24, 25, 26, 66):
        assert _node(patched, node_id)["mode"] == 0
    assert _node(patched, 21)["widgets_values"] == ["old.png"]
    assert _node(workflow, 27)["mode"] == 0


def test_patch_group_toggles_stage3_enables_img2img_group():
    patched = patch_group_toggles(
        _ui_workflow(),
        {"enabled_g1": ["加载图片（G1）"], "enabled_g2": ["对比度（G2）"]},
        SURFACE_PROFILE,
    )
    assert _node(patched, 21)["mode"] == 0
    assert _node(patched, 58)["mode"] == 0
    assert _node(patched, 27)["mode"] == 4
    assert _node(patched, 96)["mode"] == 0


def test_patch_group_toggles_rejects_unknown_group_title():
    with pytest.raises(LoraUnitAdapterError):
        patch_group_toggles(
            _ui_workflow(), {"enabled_g1": ["不存在（G1）"], "enabled_g2": []}, SURFACE_PROFILE
        )


def test_patch_group_toggles_rejects_title_under_wrong_controller():
    with pytest.raises(LoraUnitAdapterError):
        patch_group_toggles(
            _ui_workflow(), {"enabled_g1": ["对比度（G2）"], "enabled_g2": []}, SURFACE_PROFILE
        )


def test_patch_group_toggles_rejects_duplicates():
    with pytest.raises(LoraUnitAdapterError):
        patch_group_toggles(
            _ui_workflow(),
            {"enabled_g1": ["加载图片（G1）", "加载图片（G1）"], "enabled_g2": []},
            SURFACE_PROFILE,
        )


def test_patch_group_toggles_innermost_group_wins():
    workflow = _ui_workflow()
    workflow["groups"].append({"id": 500, "title": "外层（G1）", "bounding": [0, 0, 1000, 1000]})
    workflow["groups"].append({"id": 501, "title": "内层（G2）", "bounding": [100, 100, 200, 200]})
    workflow["nodes"].append({"id": 700, "type": "Note", "pos": [150, 150], "mode": 0})
    workflow["nodes"].append({"id": 701, "type": "Note", "pos": [500, 500], "mode": 4})
    patched = patch_group_toggles(
        workflow, {"enabled_g1": ["外层（G1）"], "enabled_g2": []}, SURFACE_PROFILE
    )
    assert _node(patched, 700)["mode"] == 4
    assert _node(patched, 701)["mode"] == 0


def test_patch_group_toggles_controller_inside_group_stays_active():
    workflow = _ui_workflow()
    _node(workflow, 23)["pos"] = [60, 700]
    patched = patch_group_toggles(
        workflow, {"enabled_g1": [], "enabled_g2": []}, SURFACE_PROFILE
    )
    assert _node(patched, 23)["mode"] == 0


def test_patch_group_toggles_requires_surface_profile():
    with pytest.raises(LoraUnitAdapterError):
        patch_group_toggles(_ui_workflow(), {"enabled_g1": [], "enabled_g2": []}, {})


def _surface_with_pinned():
    profile = copy.deepcopy(SURFACE_PROFILE)
    profile["config_surface"]["pinned_groups"] = {
        "g1": ["第二轮采样器（G1）", "保存图片（G1）"],
        "g2": [],
    }
    return profile


def _workflow_with_saver():
    workflow = _ui_workflow()
    workflow["groups"].append(
        {"id": 4, "title": "保存图片（G1）", "bounding": [5390, 670, 570, 1140]}
    )
    workflow["nodes"].append(
        {"id": 35, "type": "Image Saver Simple", "pos": [5400, 700], "mode": 0, "widgets_values": []}
    )
    return workflow


def test_patch_group_toggles_pinned_groups_stay_active():
    patched = patch_group_toggles(
        _workflow_with_saver(),
        {"enabled_g1": [], "enabled_g2": ["对比度（G2）"]},
        _surface_with_pinned(),
    )
    assert _node(patched, 27)["mode"] == 0
    assert _node(patched, 35)["mode"] == 0
    assert _node(patched, 21)["mode"] == 4
    assert _node(patched, 111)["mode"] == 4


def test_patch_group_toggles_rejects_toggling_pinned_group():
    with pytest.raises(LoraUnitAdapterError, match="pinned"):
        patch_group_toggles(
            _workflow_with_saver(),
            {"enabled_g1": ["第二轮采样器（G1）"], "enabled_g2": []},
            _surface_with_pinned(),
        )


def test_patch_group_toggles_rejects_unknown_pinned_group():
    profile = _surface_with_pinned()
    profile["config_surface"]["pinned_groups"]["g1"].append("不存在（G1）")
    with pytest.raises(LoraUnitAdapterError, match="does not exist"):
        patch_group_toggles(
            _workflow_with_saver(), {"enabled_g1": [], "enabled_g2": []}, profile
        )


def test_patch_group_toggles_rejects_pinned_group_wrong_controller():
    profile = _surface_with_pinned()
    profile["config_surface"]["pinned_groups"]["g2"].append("第二轮采样器（G1）")
    with pytest.raises(LoraUnitAdapterError, match="not controlled"):
        patch_group_toggles(
            _workflow_with_saver(), {"enabled_g1": [], "enabled_g2": []}, profile
        )


def test_validate_config_surface_pinned_groups_optional_and_validated():
    surface = validate_config_surface(SURFACE_PROFILE)
    assert surface["pinned_groups"] == {"g1": [], "g2": []}
    surface = validate_config_surface(_surface_with_pinned())
    assert surface["pinned_groups"]["g1"] == ["第二轮采样器（G1）", "保存图片（G1）"]
    bad = _surface_with_pinned()
    bad["config_surface"]["pinned_groups"] = {"g1": "not-a-list"}
    with pytest.raises(ConfigSurfaceError):
        validate_config_surface(bad)
    bad = _surface_with_pinned()
    bad["config_surface"]["pinned_groups"]["g1"].append("x")
    bad["config_surface"]["pinned_groups"]["g1"].append("x")
    with pytest.raises(ConfigSurfaceError):
        validate_config_surface(bad)