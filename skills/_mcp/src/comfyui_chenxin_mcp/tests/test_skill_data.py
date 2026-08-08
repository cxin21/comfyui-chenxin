"""SkillData / Rule / ImageSpec dataclass tests."""
from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec


def test_image_spec_defaults():
    spec = ImageSpec(config_key="reference_image", required=True)
    assert spec.config_key == "reference_image"
    assert spec.required is True
    assert spec.requires_group is None


def test_image_spec_with_group():
    spec = ImageSpec(config_key="controlnet_image", required=False, requires_group="ControlNet LLLite（G1）")
    assert spec.requires_group == "ControlNet LLLite（G1）"


def test_rule_bidirectional():
    rule = Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）")
    assert rule.direction == "bidirectional"


def test_rule_forward():
    rule = Rule(condition="stage:i2i-camera", implies="group_auto:加载图片（G1）", direction="forward")
    assert rule.direction == "forward"


def test_skill_data_construction():
    def fake_describe(stage): return {"stage": stage}
    def fake_apply(graph, stage, config, **kw): pass
    def fake_prepare(mcp, stage, g1, g2): return {}

    sd = SkillData(
        name="camera-image",
        stages=("t2i-camera", "i2i-camera"),
        source_workflow_path="workflow/source/文生图相机视角.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map={"sampling.steps": (50, "steps")},
        dependency_rules=(
            Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）"),
        ),
        stage_images={
            "t2i-camera": (ImageSpec("controlnet_image", required=False),),
        },
        output_type="images",
        describe_fn=fake_describe,
        apply_fn=fake_apply,
        prepare_fn=fake_prepare,
        build_config_fn=lambda envelope, **kw: {},
    )
    assert sd.name == "camera-image"
    assert sd.stages == ("t2i-camera", "i2i-camera")
    assert sd.output_type == "images"
    assert sd.dialect_id == "anima"
    assert callable(sd.describe_fn)