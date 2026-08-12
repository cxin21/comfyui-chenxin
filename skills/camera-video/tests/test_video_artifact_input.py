from __future__ import annotations

import pytest

from camera_video.runtime.config_schema import RunConfig


def test_video_config_accepts_prompt_and_rejects_raw_prompt_fields() -> None:
    config = RunConfig.from_envelope(
        {"prompt": {"text": "production prompt"}}, duration=5.0
    )
    assert config.prompt == {"text": "production prompt"}
    assert config.prompt_ref is None
    for forbidden in ("prompt_artifact", "negative", "evidence", "profile_id", "draft", "dialect_id"):
        with pytest.raises((TypeError, ValueError)):
            RunConfig.from_envelope(
                {"prompt": {}, forbidden: "legacy"}, duration=5.0
            )


def test_video_prompt_must_be_an_object() -> None:
    for bad in (None, "text", 1, ["text"]):
        with pytest.raises((TypeError, ValueError)):
            RunConfig.from_envelope({"prompt": bad}, duration=5.0)
