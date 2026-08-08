"""camera-image skill_data tests - verify against real workflow source."""
from camera_image.skill_data import get_skill_data
from comfyui_chenxin_mcp.engine.skill_data import SkillData


def test_get_skill_data_returns_correct_fields():
    sd = get_skill_data()
    assert isinstance(sd, SkillData)
    assert sd.name == "camera-image"
    assert sd.stages == ("t2i-camera", "i2i-camera")
    assert sd.output_type == "images"
    assert sd.dialect_id == "anima"


def test_field_map_is_populated():
    sd = get_skill_data()
    assert len(sd.field_map) > 0
    assert any("sampling" in k for k in sd.field_map)


def test_dependency_rules_cover_controlnet():
    sd = get_skill_data()
    rule_strs = [r.condition + "->" + r.implies for r in sd.dependency_rules]
    assert any("controlnet_image" in r and "lllite" in r.lower() for r in rule_strs)


def test_stage_images_cover_both_stages():
    sd = get_skill_data()
    assert "t2i-camera" in sd.stage_images
    assert "i2i-camera" in sd.stage_images
    i2i_specs = {s.config_key: s for s in sd.stage_images["i2i-camera"]}
    assert "reference_image" in i2i_specs
    assert i2i_specs["reference_image"].required is True


def test_describe_fn_works_with_real_workflow():
    """describe_fn must return a real schema from the source workflow."""
    sd = get_skill_data()
    result = sd.describe_fn("t2i-camera")
    assert result["stage"] == "t2i-camera"
    assert "slots" in result
    assert "sampling" in result["slots"]
    assert "groups" in result["slots"]


def test_prepare_fn_is_callable():
    sd = get_skill_data()
    assert callable(sd.prepare_fn)


def test_apply_fn_is_callable():
    sd = get_skill_data()
    assert callable(sd.apply_fn)
