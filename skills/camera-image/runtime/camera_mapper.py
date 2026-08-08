"""Semantic camera values to Anima CameraAngleNode coordinate mapping.

The CameraAngleNode (node 583) accepts pos_x/pos_y/pos_z/roll as FLOATs in
[-1, 1] (verified via MCP get_node_info). This module maps human-readable
semantic values to those coordinates using the correct ranges from the
legacy adapters/camera.py, now consolidated here.
"""

from __future__ import annotations

from dataclasses import dataclass


DIRECTION_MAP: dict[str, float] = {
    "front": 0.0,
    "right_45": 0.25,
    "right": 0.5,
    "rear_45": 0.75,
    "rear": 1.0,
    "back": 1.0,
    "left": -0.5,
    "left_45": -0.25,
}

ELEVATION_MAP: dict[str, float] = {
    "high": 0.5,
    "high-angle": 0.5,
    "eye-level": 0.0,
    "low": -0.5,
    "low-angle": -0.5,
}

DISTANCE_MAP: dict[str, float] = {
    "extreme_close_up": 0.9,
    "close_up": 0.5,
    "medium": 0.1,
    "cowboy_shot": -0.2,
    "full_body": -0.5,
    "wide": -0.9,
}

CAMERA_EXTRA_FIELDS = (
    "extreme_type", "extreme_weight",
    "lens_enabled", "lens_value",
    "dof_enabled", "dof_value", "dof_weight",
    "movement_enabled", "movement_value",
    "composition_enabled", "composition_value",
    "style_enabled", "style_value",
)

CAMERA_EXTRA_DEFAULTS: dict[str, object] = {
    "extreme_type": "无",
    "extreme_weight": 10,
    "lens_enabled": True,
    "lens_value": "85mm lens",
    "dof_enabled": False,
    "dof_value": "shallow depth of field",
    "dof_weight": 1.3,
    "movement_enabled": False,
    "movement_value": "handheld camera",
    "composition_enabled": True,
    "composition_value": "rule of thirds",
    "style_enabled": False,
    "style_value": "cinematic",
}

EXTREME_TYPE_OPTIONS = ("无", "极限俯视", "极限仰视")


@dataclass(frozen=True)
class CameraCoords:
    pos_x: float
    pos_y: float
    pos_z: float
    roll: float


def map_camera(
    direction: str = "front",
    elevation: str = "eye-level",
    distance: str = "full_body",
    roll: float = 0.0,
) -> CameraCoords:
    """Map semantic camera values to node 583 coordinates."""
    if direction not in DIRECTION_MAP:
        raise ValueError(f"unknown camera direction: {direction!r}")
    if elevation not in ELEVATION_MAP:
        raise ValueError(f"unknown camera elevation: {elevation!r}")
    if distance not in DISTANCE_MAP:
        raise ValueError(f"unknown camera distance: {distance!r}")
    if not 0.0 <= roll <= 1.0:
        raise ValueError(f"camera roll must be in [0, 1], got {roll}")
    return CameraCoords(
        pos_x=DIRECTION_MAP[direction],
        pos_y=ELEVATION_MAP[elevation],
        pos_z=DISTANCE_MAP[distance],
        roll=roll,
    )


def validate_camera_extra(extra: dict) -> dict:
    """Validate and fill defaults for camera_extra (node 585)."""
    if not isinstance(extra, dict):
        raise ValueError("camera_extra must be a dict")
    result = dict(CAMERA_EXTRA_DEFAULTS)
    for key in CAMERA_EXTRA_FIELDS:
        if key in extra:
            result[key] = extra[key]
    if result["extreme_type"] not in EXTREME_TYPE_OPTIONS:
        raise ValueError(f"extreme_type must be one of {EXTREME_TYPE_OPTIONS}")
    for bool_key in ("lens_enabled", "dof_enabled", "movement_enabled",
                     "composition_enabled", "style_enabled"):
        if not isinstance(result[bool_key], bool):
            raise ValueError(f"{bool_key} must be a boolean")
    for str_key in ("lens_value", "dof_value", "movement_value",
                    "composition_value", "style_value"):
        if not isinstance(result[str_key], str):
            raise ValueError(f"{str_key} must be a string")
    for num_key in ("extreme_weight", "dof_weight"):
        val = result[num_key]
        if not isinstance(val, (int, float)) or isinstance(val, bool) or val < 0:
            raise ValueError(f"{num_key} must be a non-negative number")
    return result
