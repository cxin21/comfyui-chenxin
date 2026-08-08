"""End-to-end run_t2i / run_i2i tests with mocked McpClient + source_workflow."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from runtime import t2i_camera, i2i_camera
from runtime import source_workflow as _source
from runtime.config_schema import GROUPS, GroupsConfig, RunConfig


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


@pytest.fixture
def fake_strip(monkeypatch):
    """Stub prepare_temporary_workflow to return a small graph fixture
    matching the node ids apply_run_config writes to.

    Without this, every test would need a live MCP + source.json to
    succeed; the unit-level contract is what matters here.
    """
    graph = {
        "21": {"inputs": {"image": ""}, "class_type": "LoadImage"},
        "24": {"inputs": {"wildcard_text": "", "populated_text": ""},
               "class_type": "ImpactWildcardProcessor"},
        "25": {"inputs": {"wildcard_text": "", "populated_text": ""},
               "class_type": "ImpactWildcardProcessor"},
        "26": {"inputs": {"text": "<lora:default:1.00>"},
               "class_type": "Lora Loader (LoraManager)"},
        "27": {"inputs": {"denoise": 1.0, "latent_image": ["86", 0]},
               "class_type": "KSampler"},
        "35": {"inputs": {}, "class_type": "Image Saver Simple"},
        "50": {"inputs": {"steps": 40, "cfg": 4, "sampler": "dpmpp_2m",
                          "scheduler": "karras", "denoise": 1.0}},
        "51": {"inputs": {"steps": 25, "denoise": 0.2}},
        "57": {"inputs": {}, "class_type": "ImageResizeKJv2"},
        "58": {"inputs": {}, "class_type": "PrimitiveInt"},
        "59": {"inputs": {}, "class_type": "VAEEncode"},
        "65": {"inputs": {"seed": -1}},
        "66": {"inputs": {"trigger_words": ["26", 2], "orinalMessage": ""}},
        "68": {"inputs": {"value": 1216}},
        "71": {"inputs": {"value": 832}},
        "129": {"inputs": {"image": ""}, "class_type": "Load Image ControlNet"},
        "583": {"inputs": {"pos_x": 0.0, "pos_y": 0.0, "pos_z": -0.5, "roll": 0.0}},
        "585": {"inputs": {}},
    }

    def fake_prepare(mcp, *, stage, user_g1=None, user_g2=None):
        # record the call for assertions
        fake_prepare.calls.append({
            "stage": stage,
            "user_g1": list(user_g1) if user_g1 else None,
            "user_g2": list(user_g2) if user_g2 else None,
        })
        # return a fresh deep copy so the test graph is not mutated across tests
        import copy
        return copy.deepcopy(graph)
    fake_prepare.calls = []
    monkeypatch.setattr(t2i_camera, "prepare_temporary_workflow", fake_prepare)
    monkeypatch.setattr(i2i_camera, "prepare_temporary_workflow", fake_prepare)
    return fake_prepare


def _base_config(**overrides):
    return RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl, solo", "negative": "lowres"},
        **overrides,
    )


def test_run_t2i_new_signature_accepts_config_object(tmp_path: Path, fake_mcp, fake_strip):
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
    assert "prompt_forge_warnings" in payload
    # strip was invoked with stage=t2i
    assert fake_strip.calls[-1]["stage"] == "t2i-camera"


def test_run_t2i_no_longer_accepts_old_kwargs(tmp_path: Path, fake_mcp, fake_strip):
    """Old kwargs (camera dict / lora_selections list / enabled_g1/g2 list)
    are no longer accepted — TypeError."""
    with pytest.raises(TypeError):
        t2i_camera.run_t2i(
            mcp=fake_mcp,
            output_dir=tmp_path,
            config=_base_config(),
            camera={"direction": "front"},  # OLD kwarg, no longer supported
        )


def test_run_i2i_new_signature_accepts_config_object(tmp_path: Path, fake_mcp, fake_strip):
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
    # strip was invoked with stage=i2i
    assert fake_strip.calls[-1]["stage"] == "i2i-camera"


def test_run_i2i_payload_includes_prompt_forge_warnings_always(
    tmp_path: Path, fake_mcp, fake_strip
):
    payload, code = i2i_camera.run_i2i(
        mcp=fake_mcp,
        output_dir=tmp_path,
        config=_base_config(reference_image="/tmp/ref.png"),
        timeout=10,
    )
    assert code == 0
    assert "prompt_forge_warnings" in payload


def test_run_i2i_uploads_controlnet_image_when_provided(
    tmp_path: Path, fake_mcp, fake_strip
):
    payload, code = i2i_camera.run_i2i(
        mcp=fake_mcp,
        output_dir=tmp_path,
        config=_base_config(
            reference_image="/tmp/ref.png",
            controlnet_image="/tmp/pose.png",
            groups=GroupsConfig(g1=[GROUPS.CONTROLNET_LLLITE]),
        ),
        timeout=10,
    )
    assert code == 0
    assert fake_mcp.upload_image.call_count == 2
    uploaded_paths = sorted(call.args[0] for call in fake_mcp.upload_image.call_args_list)
    assert uploaded_paths == ["/tmp/pose.png", "/tmp/ref.png"]


def test_run_t2i_strips_with_user_groups(tmp_path: Path, fake_mcp, fake_strip):
    """User-provided g1/g2 reach prepare_temporary_workflow."""
    t2i_camera.run_t2i(
        mcp=fake_mcp,
        output_dir=tmp_path,
        config=_base_config(groups=GroupsConfig(g1=["移除背景（G1）"])),
        timeout=10,
    )
    call = fake_strip.calls[-1]
    assert call["user_g1"] == ["移除背景（G1）"]