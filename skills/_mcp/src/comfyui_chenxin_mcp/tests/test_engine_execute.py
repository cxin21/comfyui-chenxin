"""Engine run_skill tests - mock McpClient, verify call sequence."""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec
from comfyui_chenxin_mcp.engine.execute import run_skill
from runtime.config_schema import RunConfig


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
        prepare_fn=lambda mcp, stage, g1, g2: {"nodes": [], "links": []},
    )


def _config(stage="t2i-camera", **overrides):
    envelope = {
        "evidence": {},
        "draft": {"positive": "1girl", "negative": "lowres"},
        "dialect_id": "anima",
    }
    tunables = {}
    for k, v in overrides.items():
        if k in ("evidence", "draft", "dialect_id"):
            envelope[k] = v
        else:
            tunables[k] = v
    return RunConfig.from_envelope(envelope, **tunables)


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


@patch("runtime.prompt_forge_bridge.compile_envelope",
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


@patch("runtime.prompt_forge_bridge.compile_envelope",
       return_value={"quality": {}, "warnings": []})
def test_run_skill_i2i_requires_reference(mock_compile, tmp_path):
    sd = _skill_data()
    config = _config(stage="i2i-camera")  # no reference_image
    mcp = _mock_mcp()
    payload, code = run_skill(mcp=mcp, skill_data=sd, stage="i2i-camera", config=config,
                              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert code == 1
    assert "reference_image" in payload.get("error", "")


@patch("runtime.prompt_forge_bridge.compile_envelope",
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


@patch("runtime.prompt_forge_bridge.compile_envelope",
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


@patch("runtime.prompt_forge_bridge.compile_envelope",
       return_value={"quality": {}, "warnings": []})
def test_run_skill_calls_prepare_and_apply(mock_compile, tmp_path):
    sd = _skill_data()
    config = _config()
    mcp = _mock_mcp()
    prepare_called = []
    apply_called = []

    def track_prepare(m, stage, g1, g2):
        prepare_called.append((stage, g1, g2))
        return {"nodes": [], "links": []}

    def track_apply(graph, stage, config, **kw):
        apply_called.append(stage)

    sd = SkillData(
        name=sd.name, stages=sd.stages, source_workflow_path=sd.source_workflow_path,
        groups_dir_pattern=sd.groups_dir_pattern, field_map=sd.field_map,
        dependency_rules=sd.dependency_rules, stage_images=sd.stage_images,
        output_type=sd.output_type, describe_fn=sd.describe_fn,
        apply_fn=track_apply, prepare_fn=track_prepare,
    )
    run_skill(mcp=mcp, skill_data=sd, stage="t2i-camera", config=config,
              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert len(prepare_called) == 1
    assert prepare_called[0][0] == "t2i-camera"
    assert len(apply_called) == 1
