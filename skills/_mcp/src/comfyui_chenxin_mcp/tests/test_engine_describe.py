"""Engine describe_config tests - dispatches to skill's describe_fn."""
from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec
from comfyui_chenxin_mcp.engine.describe import describe_config


def _skill_data(describe_fn=None):
    def fake_describe(stage):
        return {"stage": stage, "slots": {"sampling": {"fields": {"steps": {"default": 40}}}}}
    return SkillData(
        name="camera-image",
        stages=("t2i-camera", "i2i-camera"),
        source_workflow_path="workflow/source/文生图相机视角.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map={},
        dependency_rules=(),
        stage_images={},
        output_type="images",
        describe_fn=describe_fn or fake_describe,
        prepare_fn=lambda mcp, stage, config=None, groups=None, **kw: {},
        build_config_fn=lambda envelope, **kw: {},
    )


def test_describe_dispatches_to_skill_fn():
    sd = _skill_data()
    result = describe_config(sd, "t2i-camera")
    assert result["stage"] == "t2i-camera"
    assert "sampling" in result["slots"]


def test_describe_unknown_stage_raises():
    sd = _skill_data()
    try:
        describe_config(sd, "nonexistent-stage")
        assert False, "should have raised ValueError"
    except ValueError as e:
        assert "nonexistent-stage" in str(e)


def test_describe_returns_skill_fn_result_unchanged():
    """Engine does not modify the describe_fn output."""
    def custom_describe(stage):
        return {"stage": stage, "custom": True, "slots": {}}
    sd = _skill_data(describe_fn=custom_describe)
    result = describe_config(sd, "t2i-camera")
    assert result["custom"] is True