from __future__ import annotations

import pytest

from camera_image.runtime.config_schema import RunConfig


def test_only_prompt_artifact_is_accepted_as_prompt_input() -> None:
    config = RunConfig.from_envelope({"prompt_artifact": {"artifact_version": 1}})
    assert config.prompt_artifact == {"artifact_version": 1}
    for forbidden in ("prompt", "negative", "evidence", "profile_id", "draft", "dialect_id"):
        with pytest.raises((TypeError, ValueError)):
            RunConfig.from_envelope({"prompt_artifact": {}, forbidden: {}})
        with pytest.raises((TypeError, ValueError)):
            RunConfig.from_envelope({"prompt_artifact": {}}, **{forbidden: {}})
