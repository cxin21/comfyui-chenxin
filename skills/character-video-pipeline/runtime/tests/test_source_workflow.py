"""Tests for source_workflow: source UI -> API strip pipeline."""
import json
from unittest.mock import MagicMock

import pytest

from runtime import source_workflow
from runtime.config_schema import STAGES


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


def test_compute_enabled_groups_unions_defaults_user_and_mandatory():
    g1, g2 = source_workflow.compute_enabled_groups(
        STAGES.T2I,
        user_g1=["移除背景（G1）"],
        user_g2=["对比度（G2）"],
    )
    # defaults
    assert "保存图片（G1）" in g1
    assert "第二轮采样器（G1）" in g1
    assert "相机视角生图（G1）" in g1
    assert "图像锐化（G2）" in g2
    assert "对比度（G2）" in g2
    # user
    assert "移除背景（G1）" in g1
    # t2i has no stage-mandatory
    assert "加载图片（G1）" not in g1


def test_compute_enabled_groups_i2i_auto_appends_load_image():
    g1, _ = source_workflow.compute_enabled_groups(
        STAGES.I2I, user_g1=None, user_g2=None,
    )
    assert "加载图片（G1）" in g1


def test_compute_enabled_groups_user_cannot_remove_defaults():
    """Even if user explicitly lists empty, defaults still win."""
    g1, g2 = source_workflow.compute_enabled_groups(
        STAGES.T2I, user_g1=None, user_g2=None,
    )
    assert "保存图片（G1）" in g1
    assert "图像锐化（G2）" in g2


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
    enabled_g1, enabled_g2 = source_workflow.compute_enabled_groups(
        STAGES.T2I, user_g1=None, user_g2=None,
    )
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


def test_prepare_temporary_workflow_writes_temp_file_and_strips(tmp_path, monkeypatch):
    """End-to-end: prepare_temporary_workflow writes a temp file, hands it
    to MCP save_workflow, asks strip_workflow for the API graph, deletes
    the temp file, and returns the API graph."""
    mcp = MagicMock()
    api_graph = {
        "35": {"class_type": "Image Saver Simple", "inputs": {"images": ["111", 0]}},
    }
    mcp.get_workflow.return_value = api_graph

    captured: dict = {}

    real_mkstemp = source_workflow.tempfile.mkstemp

    def fake_mkstemp(*args, **kwargs):
        prefix = kwargs.get("prefix", args[0] if args else "temp_")
        suffix = kwargs.get("suffix", args[1] if len(args) > 1 else ".json")
        # route to tmp_path for test isolation
        fd, path = real_mkstemp(prefix=prefix, suffix=suffix, dir=str(tmp_path))
        captured["path"] = path
        return fd, path

    monkeypatch.setattr(source_workflow.tempfile, "mkstemp", fake_mkstemp)

    g = source_workflow.prepare_temporary_workflow(
        mcp,
        stage=STAGES.T2I,
        user_g1=None,
        user_g2=None,
    )

    # mcp.save_workflow was called with the temp filename + the modified UI
    mcp.save_workflow.assert_called_once()
    save_args = mcp.save_workflow.call_args
    temp_filename = save_args[0][0]
    uploaded_ui = save_args[0][1]
    assert temp_filename.startswith("temp_")
    assert temp_filename.endswith(".json")
    assert isinstance(uploaded_ui, dict)
    assert "nodes" in uploaded_ui

    # mcp.get_workflow was called with the temp filename
    mcp.get_workflow.assert_called_once()
    gw_kwargs = mcp.get_workflow.call_args.kwargs
    assert gw_kwargs["filename"] == temp_filename
    assert gw_kwargs["format"] == "api"

    # the API graph was returned
    assert g is api_graph

    # local temp file was deleted
    import os
    assert not os.path.exists(captured["path"])