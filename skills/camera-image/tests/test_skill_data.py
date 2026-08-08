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


def test_skill_data_has_no_apply_fn_field():
    """The apply_fn contract is gone — config is now applied inside prepare_fn."""
    sd = get_skill_data()
    # SkillData no longer carries apply_fn (merged into prepare_fn).
    assert not hasattr(sd, "apply_fn")


def test_dependency_rules_cover_region_prompts():
    """区域提示词（G1） implies 3 images + 3 text prompts (forward direction)."""
    from camera_image.runtime.config_schema import GROUPS

    sd = get_skill_data()
    region_rules = [
        r for r in sd.dependency_rules
        if r.condition == f"group:{GROUPS.AREA_PROMPT}"
        and r.direction == "forward"
    ]
    assert len(region_rules) == 6, (
        f"expected 6 forward rules for 区域提示词 (3 images + 3 prompts), got {len(region_rules)}"
    )
    implied = {r.implies for r in region_rules}
    assert implied == {
        "config:red_image",
        "config:green_image",
        "config:blue_image",
        "config:red_prompt",
        "config:green_prompt",
        "config:blue_prompt",
    }


def test_dependency_rules_region_prompts_are_forward_only():
    """region prompt rules must NOT be bidirectional — text alone must not force group on."""
    from camera_image.runtime.config_schema import GROUPS
    sd = get_skill_data()
    for r in sd.dependency_rules:
        if r.condition == f"group:{GROUPS.AREA_PROMPT}":
            assert r.direction == "forward", (
                f"region rule must be forward only, got {r.direction}"
            )
            # Reverse-direction check: bidirectional would also write the
            # group side from the config side, which is wrong semantics.
            assert r.direction != "bidirectional"


def test_run_config_accepts_region_prompt_fields():
    """RunConfig.from_envelope surfaces red/green/blue_prompt tunables."""
    from camera_image.runtime.config_schema import RunConfig

    cfg = RunConfig.from_envelope(
        {"evidence": {}, "draft": {"positive": "x", "negative": "y"}},
        red_prompt="red dress",
        green_prompt="green hair",
        blue_prompt="blue eyes",
    )
    assert cfg.red_prompt == "red dress"
    assert cfg.green_prompt == "green hair"
    assert cfg.blue_prompt == "blue eyes"


def test_run_config_region_prompts_default_none():
    """RunConfig region prompt fields default to None (not required)."""
    from camera_image.runtime.config_schema import RunConfig

    cfg = RunConfig.from_envelope(
        {"evidence": {}, "draft": {"positive": "x", "negative": "y"}},
    )
    assert cfg.red_prompt is None
    assert cfg.green_prompt is None
    assert cfg.blue_prompt is None