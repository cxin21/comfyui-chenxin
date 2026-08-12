from __future__ import annotations

import pytest

from camera_image.runtime.config_schema import RunConfig


def test_only_prompt_and_prompt_ref_are_accepted_as_prompt_input() -> None:
    config = RunConfig.from_envelope({"prompt": {"positive": "1girl"}})
    assert config.prompt == {"positive": "1girl"}
    assert config.prompt_ref is None
    config_ref = RunConfig.from_envelope(
        {"prompt": {"positive": "1girl"}, "prompt_ref": "a" * 32}
    )
    assert config_ref.prompt_ref == "a" * 32
    for forbidden in ("prompt_artifact", "negative", "evidence", "profile_id", "draft", "dialect_id"):
        with pytest.raises((TypeError, ValueError)):
            RunConfig.from_envelope({"prompt": {}, forbidden: {}})
        with pytest.raises((TypeError, ValueError)):
            RunConfig.from_envelope({"prompt": {}}, **{forbidden: {}})


def test_prompt_must_be_an_object() -> None:
    for bad in (None, "positive", 1, ["positive"]):
        with pytest.raises((TypeError, ValueError)):
            RunConfig.from_envelope({"prompt": bad})
