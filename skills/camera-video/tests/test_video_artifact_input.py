from __future__ import annotations

import pytest

from camera_video.runtime.config_schema import RunConfig


def test_video_config_accepts_artifact_and_rejects_raw_prompt_fields() -> None:
    config = RunConfig.from_envelope(
        {"prompt_artifact": {"artifact_version": 1}}, duration=5.0
    )
    assert config.prompt_artifact == {"artifact_version": 1}
    for forbidden in ("prompt", "negative", "evidence", "profile_id", "draft", "dialect_id"):
        with pytest.raises((TypeError, ValueError)):
            RunConfig.from_envelope(
                {"prompt_artifact": {}, forbidden: "legacy"}, duration=5.0
            )
