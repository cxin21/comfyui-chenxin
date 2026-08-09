"""Tests for source_workflow: source UI -> API strip pipeline."""
import json
from unittest.mock import MagicMock

import pytest

from runtime import source_workflow
from runtime.config_schema import GroupsConfig, STAGES


def _source_ui():
    """Minimal UI workflow JSON fixture for unit tests."""
    return {
        "id": "test",
        "nodes": [
            {"id": 35, "type": "Image Saver Simple", "mode": 0, "inputs": []},
            {"id": 51, "type": "KSampler", "mode": 0, "inputs": []},
            {"id": 583, "type": "CameraAngleNode", "mode": 0, "inputs": []},
            {"id": 585, "type": "CameraExtraConfigNode", "mode": 0, "inputs": []},
            {"id": 96, "type": "AdjustContrast", "mode": 0, "inputs": []},
            {"id": 111, "type": "ImageSharpen", "mode": 0, "inputs": []},
            {"id": 21, "type": "LoadImage", "mode": 4, "inputs": []},
            {"id": 57, "type": "ImageResizeKJv2", "mode": 4, "inputs": []},
            {"id": 58, "type": "PrimitiveInt", "mode": 4, "inputs": []},
            {"id": 59, "type": "VAEEncode", "mode": 4, "inputs": []},
            {"id": 124, "type": "RemoveBackground", "mode": 4, "inputs": []},
            {"id": 129, "type": "Load Image ControlNet", "mode": 4, "inputs": []},
            {"id": 130, "type": "ControlNetApplyLLLite", "mode": 4, "inputs": []},
        ],
        "links": [],
        "groups": [
            {"id": 1, "title": "保存图片（G1）", "bounding": [0, 0, 100, 100]},
            {"id": 2, "title": "第二轮采样器（G1）", "bounding": [0, 0, 100, 100]},
            {"id": 3, "title": "相机视角生图（G1）", "bounding": [0, 0, 100, 100]},
            {"id": 4, "title": "图像锐化（G2）", "bounding": [0, 0, 100, 100]},
            {"id": 5, "title": "对比度（G2）", "bounding": [0, 0, 100, 100]},
            {"id": 6, "title": "加载图片（G1）", "bounding": [0, 0, 100, 100]},
            {"id": 7, "title": "移除背景（G1）", "bounding": [0, 0, 100, 100]},
            {"id": 8, "title": "ControlNet LLLite（G1）", "bounding": [0, 0, 100, 100]},
        ],
        "config": {},
        "extra": {},
        "version": 1,
    }


def test_compute_enabled_groups_with_none_groups():
    """GroupsConfig=None -> defaults only, no crash."""
    g1, g2 = source_workflow.compute_enabled_groups(STAGES.T2I, None)
    assert "保存图片（G1）" in g1
    assert "图像锐化（G2）" in g2


def test_compute_enabled_groups_with_groups_g2_none():
    """GroupsConfig(g1=[...], g2=None) -> g1 used, g2 falls back to defaults.
    Regression: previously crashed at list(None) inside callers."""
    groups = GroupsConfig(g1=["移除背景（G1）"], g2=None)
    g1, g2 = source_workflow.compute_enabled_groups(STAGES.T2I, groups)
    assert "移除背景（G1）" in g1
    assert "图像锐化（G2）" in g2  # default G2 still active


def test_compute_enabled_groups_with_full_groups():
    """GroupsConfig with both g1 and g2 sets."""
    groups = GroupsConfig(g1=["移除背景（G1）"], g2=["对比度（G2）"])
    g1, g2 = source_workflow.compute_enabled_groups(STAGES.T2I, groups)
    assert "移除背景（G1）" in g1
    assert "对比度（G2）" in g2


def test_compute_enabled_groups_i2i_auto_appends_load_image():
    g1, _ = source_workflow.compute_enabled_groups(STAGES.I2I, None)
    assert "加载图片（G1）" in g1


def test_compute_enabled_groups_user_cannot_remove_defaults():
    """Even if user explicitly lists empty, defaults still win."""
    groups = GroupsConfig(g1=[], g2=[])
    g1, g2 = source_workflow.compute_enabled_groups(STAGES.T2I, groups)
    assert "保存图片（G1）" in g1
    assert "图像锐化（G2）" in g2


def test_compute_enabled_groups_rejects_unknown_group_title():
    with pytest.raises(ValueError, match="unknown group"):
        source_workflow.compute_enabled_groups(
            STAGES.T2I,
            GroupsConfig(g1=["group-that-does-not-exist"]),
        )


def test_load_source_ui_returns_dict():
    ui = source_workflow._load_source_ui()
    assert isinstance(ui, dict)
    assert "nodes" in ui
    assert "groups" in ui
    assert len(ui["nodes"]) > 100


def test_load_groups_for_known_stage():
    g = source_workflow._load_groups(STAGES.T2I)
    assert "g1" in g and "g2" in g
    assert "保存图片（G1）" in g["g1"]
    assert "图像锐化（G2）" in g["g2"]


def test_load_groups_rejects_unknown_stage():
    with pytest.raises(ValueError, match="unsupported camera stage"):
        source_workflow._load_groups("not-a-stage")


def test_apply_modes_sets_active_and_bypass():
    """Mode=0 for nodes in enabled groups; mode=4 for nodes in disabled."""
    ui = _source_ui()
    groups_meta = {
        "g1": {
            "保存图片（G1）": [35],
            "第二轮采样器（G1）": [51],
            "相机视角生图（G1）": [583, 585],
            "加载图片（G1）": [21, 57, 58, 59],
            "移除背景（G1）": [124],
            "ControlNet LLLite（G1）": [129, 130],
        },
        "g2": {
            "图像锐化（G2）": [111],
            "对比度（G2）": [96],
        },
    }
    # t2i: defaults only — 124/129/130 should be bypassed
    enabled_g1, enabled_g2 = source_workflow.compute_enabled_groups(STAGES.T2I, None)
    source_workflow._apply_modes_to_ui(ui, enabled_g1, enabled_g2, groups_meta)

    nodes = {n["id"]: n for n in ui["nodes"]}
    # enabled (defaults)
    assert nodes[35]["mode"] == 0
    assert nodes[51]["mode"] == 0
    assert nodes[583]["mode"] == 0
    assert nodes[585]["mode"] == 0
    assert nodes[111]["mode"] == 0
    assert nodes[96]["mode"] == 0
    # not enabled (other G1 groups)
    assert nodes[21]["mode"] == 4
    assert nodes[124]["mode"] == 4
    assert nodes[129]["mode"] == 4


def test_apply_modes_user_can_enable_extra_groups():
    ui = _source_ui()
    groups_meta = {
        "g1": {
            "保存图片（G1）": [35],
            "移除背景（G1）": [124],
        },
        "g2": {},
    }
    enabled_g1, _ = {"移除背景（G1）"}, set()
    source_workflow._apply_modes_to_ui(ui, enabled_g1, set(), groups_meta)
    nodes = {n["id"]: n for n in ui["nodes"]}
    assert nodes[124]["mode"] == 0  # user-enabled
    assert nodes[35]["mode"] == 4   # not in enabled set


def test_prepare_temporary_workflow_uses_inline_strip_only():
    mcp = MagicMock()
    api_graph = {
        "111": {"class_type": "ImageSharpen", "inputs": {}},
        "35": {"class_type": "Image Saver Simple", "inputs": {"images": ["111", 0]}},
    }
    mcp.strip_workflow.return_value = api_graph

    result = source_workflow.prepare_temporary_workflow(mcp, stage=STAGES.T2I)

    assert result is api_graph
    mcp.strip_workflow.assert_called_once()
    submitted_ui = mcp.strip_workflow.call_args.args[0]
    assert submitted_ui["nodes"]
    assert not hasattr(mcp, "save_workflow") or not mcp.save_workflow.called
    assert not hasattr(mcp, "get_workflow") or not mcp.get_workflow.called


def test_prepare_temporary_workflow_rejects_dangling_api_reference():
    mcp = MagicMock()
    mcp.strip_workflow.return_value = {
        "35": {
            "class_type": "Image Saver Simple",
            "inputs": {"images": ["missing-node", 0]},
        },
    }

    with pytest.raises(ValueError, match="dangling input reference"):
        source_workflow.prepare_temporary_workflow(mcp, stage=STAGES.T2I)


def test_prepare_temporary_workflow_rejects_output_without_image_link():
    mcp = MagicMock()
    mcp.strip_workflow.return_value = {
        "35": {
            "class_type": "Image Saver Simple",
            "inputs": {"filename": "output"},
        },
    }

    with pytest.raises(ValueError, match="output node.*images"):
        source_workflow.prepare_temporary_workflow(mcp, stage=STAGES.T2I)
