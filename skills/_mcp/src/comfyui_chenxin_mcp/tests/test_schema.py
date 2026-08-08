"""Tests for schema discovery + validation."""
import pytest
from unittest.mock import patch
from comfyui_chenxin_mcp.schema import describe_skill, validate_config, _load_validator


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
        with pytest.raises(ValueError):
            describe_skill("nonexistent-skill")


def test_validate_config_delegates_to_skill_validator():
    with patch("comfyui_chenxin_mcp.schema._load_validator",
               return_value=lambda s, st, c: {"valid": True, "errors": [], "warnings": []}):
        out = validate_config("camera-image", "t2i-camera", {"draft": {"positive": "x", "negative": "y"}})
    assert out["valid"] is True


def test_load_validator_returns_validator_for_requested_skill():
    """_load_validator must return the validator for the REQUESTED skill, not the first found."""
    def _make_reg(name, mod_name):
        fn = lambda m: None
        fn.__module__ = mod_name
        return type("R", (), {"name": name, "register_fn": fn, "stages": ()})()

    mod_a = type("M", (), {"validate_config": staticmethod(lambda s, st, c: {"from": "A"})})()
    mod_b = type("M", (), {"validate_config": staticmethod(lambda s, st, c: {"from": "B"})})()

    fake_regs = [
        _make_reg("camera-image", "mod_a"),
        _make_reg("camera-multiview", "mod_b"),
    ]

    from comfyui_chenxin_mcp import schema as schema_mod
    schema_mod._VALIDATORS.clear()
    try:
        with patch("comfyui_chenxin_mcp.schema._discover_skills", return_value=fake_regs):
            with patch("comfyui_chenxin_mcp.schema.importlib.import_module",
                       side_effect=lambda n: mod_a if n == "mod_a" else mod_b):
                validator = _load_validator("camera-multiview")
    finally:
        schema_mod._VALIDATORS.clear()

    assert validator is not None
    result = validator("camera-multiview", "stage", {})
    assert result == {"from": "B"}
