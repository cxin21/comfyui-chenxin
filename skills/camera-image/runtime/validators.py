"""RunConfig validation for camera-image skill.

This is skill-side validation logic (prompt-forge envelope shape, stage-specific
requirements). It lives in ``runtime/`` so the MCP bridge stays a thin dispatch
shim. ``camera_image.mcp_bridge`` re-exports ``validate_config`` for back-compat
with test patch targets.
"""
from __future__ import annotations

from typing import Any


def validate_config(skill: str, stage: str, config: dict[str, Any]) -> dict[str, Any]:
    """Validate a RunConfig dict before run_t2i_camera / run_i2i_camera.

    The runtime's graph_patcher exposes ``describe_config`` for shape
    introspection but does not yet ship a ``validate_config`` callable. The
    MCP layer therefore delegates to this thin validator that checks
    prompt-forge gate presence and stage-specific reference_image
    requirements. Richer validation lands with the runtime tools in Task 4.
    """
    if not isinstance(config, dict):
        return {"ok": False, "stage": stage, "skill": skill, "error": "config must be an object"}
    errors: list[str] = []
    draft = config.get("draft")
    if not isinstance(draft, dict):
        errors.append("config.draft must be an object (prompt-forge envelope)")
    else:
        for key in ("positive", "negative"):
            if not isinstance(draft.get(key), str) or not draft[key].strip():
                errors.append(f"config.draft.{key} must be a non-empty string")
    if stage == "i2i-camera" and not config.get("reference_image"):
        errors.append("config.reference_image is required for i2i-camera")
    if errors:
        return {"ok": False, "stage": stage, "skill": skill, "errors": errors}
    return {"ok": True, "stage": stage, "skill": skill}
