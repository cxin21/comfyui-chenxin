"""Registry tests - entry-point discovery returns SkillData."""
from unittest.mock import patch
from comfyui_chenxin_mcp.registry import discover_skills
from comfyui_chenxin_mcp.engine.skill_data import SkillData


class FakeEntryPoint:
    def __init__(self, name, fn):
        self.name = name
        self._fn = fn
    def load(self):
        return self._fn


def _fake_skill_data(name="camera-image"):
    return SkillData(
        name=name,
        stages=("t2i-camera", "i2i-camera"),
        source_workflow_path="workflow/source/test.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map={},
        dependency_rules=(),
        stage_images={},
        output_type="images",
        describe_fn=lambda stage: {},
        prepare_fn=lambda mcp, stage, config=None, groups=None, **kw: {},
        build_config_fn=lambda envelope, **kw: {},
    )


def test_discover_returns_skill_data_list():
    def get_skill_data():
        return _fake_skill_data()
    with patch("comfyui_chenxin_mcp.registry.importlib.metadata.entry_points") as m:
        m.return_value.select = lambda group: [FakeEntryPoint("camera-image", get_skill_data)]
        skills = discover_skills()
    assert len(skills) == 1
    assert isinstance(skills[0], SkillData)
    assert skills[0].name == "camera-image"


def test_discover_empty_when_no_skills():
    with patch("comfyui_chenxin_mcp.registry.importlib.metadata.entry_points") as m:
        m.return_value.select = lambda group: []
        skills = discover_skills()
    assert skills == []
