"""Tests for workflow directory scanning.

Adaptation note: The plan template patched ``wd._SKILLS_ROOT``, but Task 2's
``workflow_dir.py`` was redesigned to discover skill packages via
``registry.discover()`` + ``importlib.import_module().__file__`` instead of
scanning a hardcoded root.  These tests preserve the original INTENT (find
JSON files, handle missing dirs, skip bad JSON) but patch the actual entry
points: ``_discover_skills`` returns fake registrations and
``importlib.import_module`` returns a fake module whose ``__file__`` points
at ``tmp_path``.
"""
import json
from unittest.mock import patch
from comfyui_chenxin_mcp.workflow_dir import list_workflows


def _make_fake_reg(name, module_name):
    """Build a fake SkillRegistration-like object with a register_fn
    whose ``__module__`` points at *module_name*."""
    def register(mcp): pass
    register.__module__ = module_name
    return type("R", (), {"name": name, "register_fn": register})()


def _make_fake_mod(pkg_dir):
    """Build a fake module whose ``__file__`` is ``pkg_dir / __init__.py``."""
    return type("M", (), {"__file__": str(pkg_dir / "__init__.py")})()


def test_list_workflows_finds_camera_image(tmp_path):
    skill_dir = tmp_path / "camera_image"
    src_dir = skill_dir / "workflow" / "source"
    src_dir.mkdir(parents=True)
    (src_dir / "文生图相机视角.json").write_text(
        json.dumps({"nodes": [{"id": 1}]}), encoding="utf-8"
    )

    fake_reg = _make_fake_reg("camera-image", "camera_image.mcp_bridge")
    fake_mod = _make_fake_mod(skill_dir)

    with patch("comfyui_chenxin_mcp.workflow_dir._discover_skills",
               return_value=[fake_reg]):
        with patch("comfyui_chenxin_mcp.workflow_dir.importlib.import_module",
                   return_value=fake_mod):
            wf = list_workflows()

    assert len(wf) == 1
    assert wf[0]["skill"] == "camera-image"
    assert wf[0]["workflow"] == "文生图相机视角"
    assert wf[0]["node_count"] == 1


def test_list_workflows_handles_missing_source_dir(tmp_path):
    pkg_dir = tmp_path / "no_skill"
    pkg_dir.mkdir()

    fake_reg = _make_fake_reg("no-skill", "no_skill.mcp_bridge")
    fake_mod = _make_fake_mod(pkg_dir)

    with patch("comfyui_chenxin_mcp.workflow_dir._discover_skills",
               return_value=[fake_reg]):
        with patch("comfyui_chenxin_mcp.workflow_dir.importlib.import_module",
                   return_value=fake_mod):
            assert list_workflows() == []


def test_list_workflows_skips_unparseable_json(tmp_path):
    pkg_dir = tmp_path / "s"
    src_dir = pkg_dir / "workflow" / "source"
    src_dir.mkdir(parents=True)
    (src_dir / "bad.json").write_text("not json", encoding="utf-8")

    fake_reg = _make_fake_reg("s", "s.mcp_bridge")
    fake_mod = _make_fake_mod(pkg_dir)

    with patch("comfyui_chenxin_mcp.workflow_dir._discover_skills",
               return_value=[fake_reg]):
        with patch("comfyui_chenxin_mcp.workflow_dir.importlib.import_module",
                   return_value=fake_mod):
            assert list_workflows() == []
