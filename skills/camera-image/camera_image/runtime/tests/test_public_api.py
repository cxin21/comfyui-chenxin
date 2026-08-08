"""Verify the public API surface of the runtime package."""
import runtime


def test_public_api_exposes_all_dataclasses():
    assert hasattr(runtime, "RunConfig")
    assert hasattr(runtime, "SamplingConfig")
    assert hasattr(runtime, "ImageSizeConfig")
    assert hasattr(runtime, "GroupsConfig")
    assert hasattr(runtime, "CameraConfig")


def test_public_api_exposes_constants():
    assert hasattr(runtime, "STAGES")
    assert hasattr(runtime, "GROUPS")
    assert hasattr(runtime, "MANDATORY_GROUPS_BY_STAGE")
    assert hasattr(runtime, "WORKFLOW_CONVENTIONS")
    assert hasattr(runtime, "REFERENCE_IMAGE_NODE")
    assert hasattr(runtime, "CONTROLNET_IMAGE_NODE")
    assert hasattr(runtime, "I2I_NODES")
    assert hasattr(runtime, "NODE_FIELD_MAP")


def test_stages_constants_have_expected_values():
    assert runtime.STAGES.T2I == "t2i-camera"
    assert runtime.STAGES.I2I == "i2i-camera"


def test_groups_constants_have_expected_values():
    assert "加载图片" in runtime.GROUPS.LOAD_IMAGE
    assert "ControlNet LLLite" in runtime.GROUPS.CONTROLNET_LLLITE
