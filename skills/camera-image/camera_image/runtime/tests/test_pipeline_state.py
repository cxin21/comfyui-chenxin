from __future__ import annotations

import pytest

from runtime.pipeline_state import PipelineStateError, advance_state, stage_is_reusable


def test_stage_order_is_enforced():
    with pytest.raises(PipelineStateError, match="SHOT_READY"):
        advance_state({"status": "BASE_READY", "stages": {}}, "VIDEO_READY")


def test_state_advances_only_to_immediate_next_transition():
    current = {"status": "BASE_READY", "stages": {"base": {"accepted": True}}}
    advanced = advance_state(current, "SHEET_PREFLIGHTED")
    assert advanced["status"] == "SHEET_PREFLIGHTED"
    assert current["status"] == "BASE_READY"


def test_reuse_requires_all_hashes():
    saved = {
        "input_hash": "a",
        "prompt_build_hash": "b",
        "workflow_hash": "c",
        "profile_version": "1",
    }
    assert stage_is_reusable(saved, "a", "b", "c", "1")
    assert not stage_is_reusable(saved, "a", "changed", "c", "1")
