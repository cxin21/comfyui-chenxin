"""Tests for skill discovery via Python entry-points.

Adaptation note: The plan template set ``m.select = fake_eps`` directly on the
mock, but ``patch`` replaces the ``entry_points`` *function* — the impl calls
``entry_points()`` first (returning ``m.return_value``), then
``.select(group=...)`` on that.  We therefore set ``m.return_value.select``
and use ``group`` as the parameter name to match the real call signature.
"""
from unittest.mock import patch
from comfyui_chenxin_mcp.registry import discover, SkillRegistration


class FakeEntryPoint:
    def __init__(self, name, fn):
        self.name = name
        self._fn = fn
    def load(self):
        return self._fn


def fake_eps(group=None):
    def register(mcp): pass
    register.SKILL_INFO = SkillRegistration(
        name="camera-image", label="X", description="t2i/i2i",
        stages=("t2i-camera", "i2i-camera"), register_fn=register,
    )
    return [FakeEntryPoint("camera-image", register)]


def test_discover_picks_up_entry_points():
    with patch("comfyui_chenxin_mcp.registry.importlib.metadata.entry_points") as m:
        m.return_value.select = fake_eps
        regs = discover()
    assert any(r.name == "camera-image" for r in regs)


def test_discover_auto_derives_metadata_when_skill_info_missing():
    def register(mcp):
        """t2i-camera and i2i-camera skill bridge."""
        pass
    with patch("comfyui_chenxin_mcp.registry.importlib.metadata.entry_points") as m:
        m.return_value.select = lambda group=None: [FakeEntryPoint("auto-skill", register)]
        regs = discover()
    assert regs[0].name == "auto-skill"
    assert "t2i-camera" in regs[0].description  # derived from docstring first line
    assert regs[0].stages == ()
