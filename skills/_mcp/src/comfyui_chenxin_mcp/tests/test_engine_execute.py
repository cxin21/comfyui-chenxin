"""Engine run_skill tests - mock McpClient, verify call sequence."""
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
from pathlib import Path

from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec
from comfyui_chenxin_mcp.engine.execute import run_skill


@dataclass(frozen=True)
class _TestGroups:
    g1: list = None
    g2: list = None


@dataclass(frozen=True)
class _TestConfig:
    """Minimal config stand-in for engine tests (no runtime import needed)."""
    evidence: dict
    draft: dict
    dialect_id: str = "anima"
    camera: object = None
    camera_extra: dict = None
    lora: dict = None
    groups: _TestGroups = None
    sampling: object = None
    seed: int = None
    image_size: object = None
    reference_image: str = None
    controlnet_image: str = None


def _skill_data():
    return SkillData(
        name="camera-image",
        stages=("t2i-camera", "i2i-camera"),
        source_workflow_path="workflow/source/文生图相机视角.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map={},
        dependency_rules=(),
        stage_images={
            "t2i-camera": (ImageSpec("controlnet_image", required=False),),
            "i2i-camera": (
                ImageSpec("reference_image", required=True),
                ImageSpec("controlnet_image", required=False),
            ),
        },
        output_type="images",
        describe_fn=lambda stage: {},
        apply_fn=lambda graph, stage, config, **kw: None,
        prepare_fn=lambda mcp, stage, groups: {"nodes": [], "links": []},
        build_config_fn=lambda envelope, **kw: _config(),
    )


def _config(stage="t2i-camera", **overrides):
    envelope = {
        "evidence": {},
        "draft": {"positive": "1girl", "negative": "lowres"},
        "dialect_id": "anima",
    }
    for k in ("evidence", "draft", "dialect_id"):
        if k in overrides:
            envelope[k] = overrides.pop(k)
    groups_override = overrides.get("groups")
    return _TestConfig(
        evidence=envelope["evidence"],
        draft=envelope["draft"],
        dialect_id=envelope["dialect_id"],
        reference_image=overrides.get("reference_image"),
        controlnet_image=overrides.get("controlnet_image"),
        groups=_TestGroups(**groups_override) if isinstance(groups_override, dict) else (groups_override if groups_override else None),
        lora=overrides.get("lora"),
    )


def _mock_mcp():
    mcp = MagicMock()
    mcp.__enter__ = lambda s: mcp
    mcp.__exit__ = lambda *a: False
    mcp.health.return_value = {"queue": {"running": [], "pending": []}}
    mcp.validate_workflow.return_value = {"error_count": 0}
    mcp.check_runtime.return_value = {"runtime": "local"}
    mcp.enqueue.return_value = {"prompt_id": "test-prompt-123"}
    mcp.get_history.return_value = {
        "test-prompt-123": {
            "status": {"status_str": "success"},
            "outputs": {"35": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
        }
    }
    mcp.get_image.return_value = b"\x89PNG fake image data"
    return mcp


@patch("comfyui_chenxin_mcp.engine.prompt_forge.compile_envelope",
       return_value={"quality": {}, "warnings": []})
def test_run_skill_t2i_success(mock_compile, tmp_path):
    sd = _skill_data()
    config = _config()
    mcp = _mock_mcp()
    payload, code = run_skill(mcp=mcp, skill_data=sd, stage="t2i-camera", config=config,
                              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert code == 0
    assert payload["accepted"] is True
    assert payload["prompt_id"] == "test-prompt-123"
    assert "artifact" in payload
    assert (tmp_path / "out.png").exists()


@patch("comfyui_chenxin_mcp.engine.prompt_forge.compile_envelope",
       return_value={"quality": {}, "warnings": []})
def test_run_skill_i2i_requires_reference(mock_compile, tmp_path):
    sd = _skill_data()
    config = _config(stage="i2i-camera")  # no reference_image
    mcp = _mock_mcp()
    payload, code = run_skill(mcp=mcp, skill_data=sd, stage="i2i-camera", config=config,
                              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert code == 1
    assert "reference_image" in payload.get("error", "")


@patch("comfyui_chenxin_mcp.engine.prompt_forge.compile_envelope",
       return_value={"quality": {}, "warnings": []})
def test_run_skill_i2i_uploads_reference(mock_compile, tmp_path):
    sd = _skill_data()
    config = _config(stage="i2i-camera", reference_image="/fake/path.png")
    mcp = _mock_mcp()
    mcp.upload_image.return_value = {"name": "ref.png", "subfolder": ""}
    payload, code = run_skill(mcp=mcp, skill_data=sd, stage="i2i-camera", config=config,
                              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert code == 0
    mcp.upload_image.assert_any_call("/fake/path.png")


@patch("comfyui_chenxin_mcp.engine.prompt_forge.compile_envelope",
       return_value={"quality": {}, "warnings": []})
def test_run_skill_health_check_fails(mock_compile, tmp_path):
    sd = _skill_data()
    config = _config()
    mcp = _mock_mcp()
    mcp.health.return_value = {"queue": {"running": ["job1"], "pending": []}}
    payload, code = run_skill(mcp=mcp, skill_data=sd, stage="t2i-camera", config=config,
                              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert code == 1
    assert "queue" in payload["error"].lower()


@patch("comfyui_chenxin_mcp.engine.prompt_forge.compile_envelope",
       return_value={"quality": {}, "warnings": []})
def test_run_skill_calls_prepare_and_apply(mock_compile, tmp_path):
    sd = _skill_data()
    config = _config()
    mcp = _mock_mcp()
    prepare_called = []
    apply_called = []

    def track_prepare(m, stage, groups):
        prepare_called.append((stage, groups))
        return {"nodes": [], "links": []}

    def track_apply(graph, stage, config, **kw):
        apply_called.append(stage)

    sd = SkillData(
        name=sd.name, stages=sd.stages, source_workflow_path=sd.source_workflow_path,
        groups_dir_pattern=sd.groups_dir_pattern, field_map=sd.field_map,
        dependency_rules=sd.dependency_rules, stage_images=sd.stage_images,
        output_type=sd.output_type, describe_fn=sd.describe_fn,
        apply_fn=track_apply, prepare_fn=track_prepare,
        build_config_fn=sd.build_config_fn,
    )
    run_skill(mcp=mcp, skill_data=sd, stage="t2i-camera", config=config,
              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert len(prepare_called) == 1
    assert prepare_called[0][0] == "t2i-camera"
    assert prepare_called[0][1] is None  # groups=None when not provided
    assert len(apply_called) == 1


@patch("comfyui_chenxin_mcp.engine.prompt_forge.compile_envelope",
       return_value={"quality": {}, "warnings": []})
def test_run_skill_passes_groups_g2_none_to_prepare(mock_compile, tmp_path):
    """Regression: previously crashed at list(None) when groups.g1 set but g2=None."""
    sd = _skill_data()
    config = _config(groups={"g1": ["移除背景（G1）"], "g2": None})
    mcp = _mock_mcp()
    prepare_called = []

    def track_prepare(m, stage, groups):
        prepare_called.append((stage, groups))
        return {"nodes": [], "links": []}

    sd = SkillData(
        name=sd.name, stages=sd.stages, source_workflow_path=sd.source_workflow_path,
        groups_dir_pattern=sd.groups_dir_pattern, field_map=sd.field_map,
        dependency_rules=sd.dependency_rules, stage_images=sd.stage_images,
        output_type=sd.output_type, describe_fn=sd.describe_fn,
        apply_fn=sd.apply_fn, prepare_fn=track_prepare,
        build_config_fn=sd.build_config_fn,
    )
    payload, code = run_skill(mcp=mcp, skill_data=sd, stage="t2i-camera", config=config,
                              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert code == 0
    assert prepare_called[0][1].g1 == ["移除背景（G1）"]
    assert prepare_called[0][1].g2 is None
