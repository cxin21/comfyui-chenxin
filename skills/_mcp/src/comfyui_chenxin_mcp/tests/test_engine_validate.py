"""Engine validate_config tests - declarative dependency rules."""
from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec
from comfyui_chenxin_mcp.engine.validate import validate_config


def _skill_data(rules=()):
    return SkillData(
        name="camera-image",
        stages=("t2i-camera", "i2i-camera"),
        source_workflow_path="workflow/source/文生图相机视角.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map={},
        dependency_rules=rules,
        stage_images={},
        output_type="images",
        describe_fn=lambda stage: {},
        prepare_fn=lambda mcp, stage, config=None, groups=None, **kw: {},
        build_config_fn=lambda envelope, **kw: {},
    )


def test_valid_config_no_errors():
    sd = _skill_data()
    config = {"draft": {"positive": "1girl", "negative": "lowres"}}
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is True
    assert result["errors"] == []


def test_missing_draft_positive():
    sd = _skill_data()
    config = {"draft": {"positive": "", "negative": "lowres"}}
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("positive" in e for e in result["errors"])


def test_missing_draft_negative():
    sd = _skill_data()
    config = {"draft": {"positive": "1girl", "negative": ""}}
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("negative" in e for e in result["errors"])


def test_missing_draft_entirely():
    sd = _skill_data()
    config = {}
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("draft" in e for e in result["errors"])


def test_config_implies_group_violation():
    """controlnet_image provided but group not enabled -> error."""
    sd = _skill_data(rules=(
        Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）"),
    ))
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "controlnet_image": "/path/to/img.png",
        "groups": {"g1": []},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("ControlNet LLLite" in e for e in result["errors"])


def test_config_implies_group_satisfied():
    """controlnet_image provided AND group enabled -> ok."""
    sd = _skill_data(rules=(
        Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）"),
    ))
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "controlnet_image": "/path/to/img.png",
        "groups": {"g1": ["ControlNet LLLite（G1）"]},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is True


def test_group_implies_config_violation():
    """group enabled but controlnet_image not provided -> error."""
    sd = _skill_data(rules=(
        Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）"),
    ))
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "groups": {"g1": ["ControlNet LLLite（G1）"]},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("controlnet_image" in e for e in result["errors"])


def test_stage_implies_group_auto_forward_only():
    """stage=i2i-camera implies group_auto=加载图片（G1）(forward, not bidirectional)."""
    sd = _skill_data(rules=(
        Rule(condition="stage:i2i-camera", implies="group_auto:加载图片（G1）", direction="forward"),
    ))
    config = {"draft": {"positive": "1girl", "negative": "lowres"}}
    result = validate_config(sd, "i2i-camera", config)
    # forward rule: stage->group_auto is informational, not a validation error
    assert result["ok"] is True


# --- Region prompts (text) dependency rules ---
# When the user enables 区域提示词（G1）, the 3 R/G/B text prompts
# (red_prompt, green_prompt, blue_prompt) are required — same gating
# pattern as the corresponding red/green/blue images.

_REGION_PROMPT_RULES = (
    Rule(condition="group:区域提示词（G1）", implies="config:red_prompt", direction="forward"),
    Rule(condition="group:区域提示词（G1）", implies="config:green_prompt", direction="forward"),
    Rule(condition="group:区域提示词（G1）", implies="config:blue_prompt", direction="forward"),
)


def test_region_prompt_group_enabled_all_provided_ok():
    sd = _skill_data(rules=_REGION_PROMPT_RULES)
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "red_prompt": "red dress",
        "green_prompt": "green hair",
        "blue_prompt": "blue eyes",
        "groups": {"g1": ["区域提示词（G1）"]},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is True, result["errors"]


def test_region_prompt_group_enabled_missing_red():
    sd = _skill_data(rules=_REGION_PROMPT_RULES)
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "green_prompt": "green hair",
        "blue_prompt": "blue eyes",
        "groups": {"g1": ["区域提示词（G1）"]},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("red_prompt" in e for e in result["errors"])


def test_region_prompt_group_enabled_missing_green():
    sd = _skill_data(rules=_REGION_PROMPT_RULES)
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "red_prompt": "red dress",
        "blue_prompt": "blue eyes",
        "groups": {"g1": ["区域提示词（G1）"]},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("green_prompt" in e for e in result["errors"])


def test_region_prompt_group_enabled_missing_blue():
    sd = _skill_data(rules=_REGION_PROMPT_RULES)
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "red_prompt": "red dress",
        "green_prompt": "green hair",
        "groups": {"g1": ["区域提示词（G1）"]},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("blue_prompt" in e for e in result["errors"])


def test_region_prompt_group_disabled_none_provided_ok():
    """Forward-only: providing text does NOT force the group on."""
    sd = _skill_data(rules=_REGION_PROMPT_RULES)
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "groups": {"g1": []},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is True


def test_region_prompt_text_alone_no_group_ok():
    """Forward-only: providing text alone (without group) is fine."""
    sd = _skill_data(rules=_REGION_PROMPT_RULES)
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "red_prompt": "red dress",
        "green_prompt": "green hair",
        "blue_prompt": "blue eyes",
        "groups": {"g1": []},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is True


def test_config_not_dict():
    sd = _skill_data()
    result = validate_config(sd, "t2i-camera", "not a dict")
    assert result["ok"] is False
    assert any("object" in e for e in result["errors"])