"""Small, immutable state machine for resumable Prompt Forge stages."""

from __future__ import annotations

import copy


class PipelineStateError(ValueError):
    """Raised when a pipeline transition or reuse check is invalid."""


ORDER = [
    "DISCOVERED",
    "BASE_PREFLIGHTED",
    "BASE_READY",
    "SHEET_PREFLIGHTED",
    "SHEET_READY",
    "SHOT_PREFLIGHTED",
    "SHOT_READY",
    "VIDEO_PREFLIGHTED",
    "VIDEO_READY",
]


def advance_state(state: dict, transition: str) -> dict:
    """Advance exactly one state-machine edge without mutating ``state``."""
    if not isinstance(state, dict):
        raise PipelineStateError("pipeline state must be an object")
    current = state.get("status")
    if current not in ORDER:
        raise PipelineStateError("pipeline state status is unknown")
    if not isinstance(transition, str) or transition not in ORDER:
        raise PipelineStateError("pipeline transition is unknown")
    expected_index = ORDER.index(current) + 1
    if expected_index >= len(ORDER) or ORDER[expected_index] != transition:
        next_state = ORDER[expected_index] if expected_index < len(ORDER) else "VIDEO_READY"
        try:
            target_index = ORDER.index(transition)
        except ValueError:
            target_index = expected_index
        skipped = ", ".join(ORDER[expected_index:target_index])
        raise PipelineStateError(
            f"pipeline must transition to {next_state} next; skipped stages: {skipped or 'none'}"
        )
    result = copy.deepcopy(state)
    result["status"] = transition
    history = result.setdefault("history", [])
    if not isinstance(history, list):
        raise PipelineStateError("pipeline history must be a list")
    history.append(transition)
    return result


def stage_is_reusable(
    saved: dict,
    input_hash: str,
    prompt_build_hash: str,
    workflow_hash: str,
    profile_version: str,
) -> bool:
    """Return true only when every stage identity component is unchanged."""
    if not isinstance(saved, dict):
        return False
    expected = {
        "input_hash": input_hash,
        "prompt_build_hash": prompt_build_hash,
        "workflow_hash": workflow_hash,
        "profile_version": profile_version,
    }
    if any(not isinstance(value, str) or not value for value in expected.values()):
        return False
    if any(saved.get(key) != value for key, value in expected.items()):
        return False
    if "accepted" in saved and saved.get("accepted") is not True:
        return False
    if "status" in saved and saved.get("status") not in {"READY", "accepted", "succeeded"}:
        return False
    return True
