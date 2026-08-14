from __future__ import annotations

import pytest

from camera_multiview.runtime.config_schema import RunConfig
from camera_multiview.skill_data import get_skill_data
from comfyui_chenxin_mcp.engine.validate import validate_config


def test_multiview_accepts_only_an_empty_envelope() -> None:
    skill = get_skill_data()
    result = validate_config(
        skill,
        "multiview",
        {},
        {"full_body_image": "body.png", "face_image": "face.png"},
    )
    assert result == {
        "ok": True,
        "errors": [],
        "stage": "multiview",
        "skill": "camera-multiview",
    }


@pytest.mark.parametrize(
    "envelope",
    [
        {"dialect_id": "anima"},
        {"draft": {}},
        {"evidence": {}},
        {"prompt": {}},
    ],
)
def test_multiview_rejects_every_prompt_envelope(envelope: dict) -> None:
    skill = get_skill_data()
    result = validate_config(
        skill,
        "multiview",
        envelope,
        {"full_body_image": "body.png", "face_image": "face.png"},
    )
    assert not result["ok"]
    assert result["errors"] == ["camera-multiview envelope must be empty"]


def test_multiview_run_config_has_no_prompt_compatibility_fields() -> None:
    config = RunConfig.from_envelope(
        {}, full_body_image="body.png", face_image="face.png"
    )
    assert not hasattr(config, "draft")
    assert not hasattr(config, "evidence")
    assert not hasattr(config, "dialect_id")
