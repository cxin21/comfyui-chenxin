"""End-to-end run_t2i / run_i2i tests with mocked McpClient."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from runtime import t2i_camera, i2i_camera
from runtime.config_schema import GROUPS, GroupsConfig, RunConfig


@pytest.fixture
def complete_workflow(monkeypatch):
    """Augment load_workflow with group member nodes that groups.json
    references but the tracked 25-node workflow.json stub omits.

    Mirrors the fixture in test_graph_patcher.py. Needed by the ControlNet
    end-to-end test because _apply_controlnet_image writes node 129 strictly
    (fail-loud). When workflow.json grows to its full node set, this is a no-op.
    """
    from runtime import graph_patcher as _gp

    real_load = _gp.load_workflow
    extras = {"129": {"inputs": {"image": ""}, "class_type": "LoadImage"}}

    def augmented(stage):
        merged = dict(real_load(stage))
        merged.update(extras)
        return merged

    monkeypatch.setattr(_gp, "load_workflow", augmented)
    return augmented


@pytest.fixture
def fake_mcp():
    """Mock McpClient that returns canned responses for the camera run."""
    mcp = MagicMock()
    mcp.health.return_value = {"queue": {"running": [], "pending": []}}
    mcp.validate_workflow.return_value = {"error_count": 0}
    mcp.check_runtime.return_value = {"runtime": "local"}
    mcp.enqueue.return_value = {"prompt_id": "test-prompt-id"}
    mcp.get_history.return_value = {
        "## Execution: test-prompt-id": [
            "**Status**: success",
            "**Duration**: 10s",
            "**Cached nodes**: 0",
            "### Outputs (1 nodes)",
            "- Node 35: images -> **dummy.png (type=output)**",
        ]
    }
    mcp.get_image.return_value = {
        "type": "image",
        "data": "iVBORw0KGgo=",
        "mimeType": "image/png",
    }
    mcp.upload_image.return_value = {"name": "uploaded-ref.png"}
    return mcp


def _base_config(**overrides):
    return RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl, solo", "negative": "lowres"},
        **overrides,
    )


def test_run_t2i_new_signature_accepts_config_object(tmp_path: Path, fake_mcp):
    payload, code = t2i_camera.run_t2i(
        mcp=fake_mcp,
        output_dir=tmp_path,
        config=_base_config(),
        timeout=10,
    )
    assert code == 0
    assert payload["accepted"] is True
    assert payload["stage"] == "t2i-camera"
    assert payload["prompt_id"] == "test-prompt-id"
    assert "prompt_forge_warnings" in payload  # may be empty or populated


def test_run_t2i_no_longer_accepts_old_kwargs(tmp_path: Path, fake_mcp):
    """Old kwargs (camera dict / lora_selections list / enabled_g1/g2 list)
    are no longer accepted — TypeError."""
    with pytest.raises(TypeError):
        t2i_camera.run_t2i(
            mcp=fake_mcp,
            output_dir=tmp_path,
            config=_base_config(),
            camera={"direction": "front"},  # OLD kwarg, no longer supported
        )


def test_run_i2i_new_signature_accepts_config_object(tmp_path: Path, fake_mcp):
    payload, code = i2i_camera.run_i2i(
        mcp=fake_mcp,
        output_dir=tmp_path,
        config=_base_config(reference_image="/tmp/ref.png"),
        timeout=10,
    )
    assert code == 0
    assert payload["accepted"] is True
    assert payload["stage"] == "i2i-camera"
    fake_mcp.upload_image.assert_called_once_with("/tmp/ref.png")


def test_run_i2i_payload_includes_prompt_forge_warnings_always(
    tmp_path: Path, fake_mcp
):
    payload, code = i2i_camera.run_i2i(
        mcp=fake_mcp,
        output_dir=tmp_path,
        config=_base_config(reference_image="/tmp/ref.png"),
        timeout=10,
    )
    assert code == 0
    assert "prompt_forge_warnings" in payload  # may be empty or populated


def test_run_i2i_uploads_controlnet_image_when_provided(
    tmp_path: Path, fake_mcp, complete_workflow
):
    payload, code = i2i_camera.run_i2i(
        mcp=fake_mcp,
        output_dir=tmp_path,
        config=_base_config(
            reference_image="/tmp/ref.png",
            controlnet_image="/tmp/pose.png",
            # controlnet_image is cross-validated against the group: supplying
            # the image requires enabling ControlNet LLLite（G1）.
            groups=GroupsConfig(g1=[GROUPS.CONTROLNET_LLLITE]),
        ),
        timeout=10,
    )
    assert code == 0
    # upload_image should have been called twice: once for reference, once for controlnet
    assert fake_mcp.upload_image.call_count == 2
    uploaded_paths = sorted(call.args[0] for call in fake_mcp.upload_image.call_args_list)
    assert uploaded_paths == ["/tmp/pose.png", "/tmp/ref.png"]