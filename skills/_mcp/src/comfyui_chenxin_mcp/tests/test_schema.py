"""Tests for schema discovery + validation."""
from unittest.mock import patch
from comfyui_chenxin_mcp.schema import describe_skill, validate_config


class FakeEntryPoint:
    def __init__(self, name, fn): self.name = name; self._fn = fn
    def load(self): return self._fn


def _make_eps():
    def describe_config(stage):
        return {"stage": stage, "slots": {"sampling": {"fields": {"steps_first": {"default": 40}}}}}
    def validate_config(skill, stage, config):
        return {"valid": True, "errors": [], "warnings": []}
    mod = type("M", (), {"describe_config": describe_config, "validate_config": validate_config})
    return [FakeEntryPoint("camera-image", lambda m: mod)]


def test_describe_skill_dispatches_to_skill_entry_point():
    with patch("comfyui_chenxin_mcp.schema._discover_skills", return_value=[
        type("R", (), {"name": "camera-image",
                       "register_fn": lambda m: None,
                       "stages": ("t2i-camera",)})()
    ]):
        with patch("comfyui_chenxin_mcp.schema.importlib.import_module",
                   return_value=type("M", (), {
                       "describe_config": staticmethod(lambda s: {"stage": s, "slots": {}})
                   })()):
            out = describe_skill("camera-image", stage="t2i-camera")
    assert out["stage"] == "t2i-camera"


def test_describe_skill_unknown_skill_raises():
    with patch("comfyui_chenxin_mcp.schema._discover_skills", return_value=[]):
        import pytest
        with pytest.raises(ValueError):
            describe_skill("nonexistent-skill")


def test_validate_config_delegates_to_skill_validator():
    with patch("comfyui_chenxin_mcp.schema._load_validator",
               return_value=lambda s, st, c: {"valid": True, "errors": [], "warnings": []}):
        out = validate_config("camera-image", "t2i-camera", {"draft": {"positive": "x", "negative": "y"}})
    assert out["valid"] is True
