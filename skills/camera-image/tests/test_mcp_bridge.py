"""camera-image MCP bridge tests - tool handlers dispatch to runtime.*.

Verifies that the tool handlers registered by ``camera_image.mcp_bridge.register``
are thin glue: they marshal arguments, call the appropriate ``runtime.*``
function, and return the result. External dependencies (McpClient subprocess,
runtime execution) are mocked; assertions target the bridge's dispatch logic.
"""
import json

import pytest
from unittest.mock import MagicMock, patch

from comfyui_chenxin_mcp.protocol import Server
from camera_image.mcp_bridge import register, SKILL_INFO


def _server():
    s = Server(name="t", version="0")
    register(s)
    return s


def test_skill_info_exposed():
    assert SKILL_INFO.name == "camera-image"
    assert "t2i-camera" in SKILL_INFO.stages
    assert "i2i-camera" in SKILL_INFO.stages


@pytest.mark.asyncio
async def test_describe_camera_config_delegates_to_graph_patcher():
    fake_schema = {"stage": "t2i-camera", "slots": {}}
    with patch("camera_image.mcp_bridge.describe_config", return_value=fake_schema) as dc:
        s = _server()
        out = await s._tools["describe_camera_config"]["handler"](stage="t2i-camera")
    assert out is fake_schema
    dc.assert_called_once_with("t2i-camera")


@pytest.mark.asyncio
async def test_validate_camera_config_delegates_to_runtime():
    fake = {"valid": True, "errors": [], "warnings": []}
    with patch("camera_image.mcp_bridge.validate_config", return_value=fake) as vc:
        s = _server()
        out = await s._tools["validate_camera_config"]["handler"](
            stage="t2i-camera", config={"draft": {}}
        )
    assert out is fake
    vc.assert_called_once_with("camera-image", "t2i-camera", {"draft": {}})


@pytest.mark.asyncio
async def test_list_camera_loras_invokes_mcp_and_filters_anima():
    fake_mcp = MagicMock()
    fake_mcp.__enter__ = lambda s: fake_mcp
    fake_mcp.__exit__ = lambda *a: False
    fake_mcp.list_loras.return_value = (
        "## loras (3)\n- Anima\\foo.safetensors\n- other\\bar.safetensors"
    )
    with patch("camera_image.mcp_bridge._spawn_mcp", return_value=fake_mcp):
        s = _server()
        out = await s._tools["list_camera_loras"]["handler"]()
    assert "anima_loras" in out
    assert "Anima\\foo.safetensors" in out["anima_loras"]
    assert "other\\bar.safetensors" not in out["anima_loras"]
    assert "default_stack_text" in out
    fake_mcp.list_loras.assert_called_once()


@pytest.mark.asyncio
async def test_run_t2i_camera_calls_runtime_run_t2i():
    fake_mcp = MagicMock()
    fake_mcp.__enter__ = lambda m: fake_mcp
    fake_mcp.__exit__ = lambda *a: False
    envelope = {
        "evidence": {},
        "draft": {"positive": "1girl", "negative": "lowres"},
        "dialect_id": "anima",
    }
    # run_t2i is imported lazily inside the handler, so patch the source module.
    with patch("camera_image.mcp_bridge._spawn_mcp", return_value=fake_mcp), \
         patch(
             "runtime.t2i_camera.run_t2i",
             return_value=({"accepted": True, "prompt_id": "p"}, 0),
         ) as rt:
        s = _server()
        out = await s._tools["run_t2i_camera"]["handler"](
            envelope=envelope, seed=12345
        )
    assert out["exit_code"] == 0
    assert out["payload"]["accepted"] is True
    rt.assert_called_once()
    # Verify the patched _spawn_mcp was used as context manager.
    fake_mcp.list_loras  # touch - ensure no error


@pytest.mark.asyncio
async def test_run_t2i_camera_passes_seed_through():
    """Seed flows from tool kwarg through _kwargs_to_run_config into run_t2i."""
    fake_mcp = MagicMock()
    fake_mcp.__enter__ = lambda m: fake_mcp
    fake_mcp.__exit__ = lambda *a: False
    envelope = {
        "evidence": {},
        "draft": {"positive": "1girl", "negative": "lowres"},
        "dialect_id": "anima",
    }
    captured = {}

    def _capture_run_t2i(mcp, output_dir, config, timeout):
        captured["config"] = config
        captured["mcp"] = mcp
        return {"accepted": True}, 0

    with patch("camera_image.mcp_bridge._spawn_mcp", return_value=fake_mcp), \
         patch("runtime.t2i_camera.run_t2i", side_effect=_capture_run_t2i):
        s = _server()
        out = await s._tools["run_t2i_camera"]["handler"](
            envelope=envelope, seed=42
        )
    assert out["exit_code"] == 0
    assert captured["config"].seed == 42
    assert captured["mcp"] is fake_mcp
