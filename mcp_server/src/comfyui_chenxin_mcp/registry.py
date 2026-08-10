"""Skill discovery via Python entry-points.

Each skill package declares an entry-point in its pyproject.toml:
    [project.entry-points."comfyui_chenxin_mcp.skills"]
    camera-image = "camera_image.skill_data:get_skill_data"

The callable must return a SkillData instance.
"""
from __future__ import annotations

import importlib.metadata

from .engine.skill_data import SkillData

ENTRY_POINT_GROUP = "comfyui_chenxin_mcp.skills"


def discover_skills() -> list[SkillData]:
    """Discover installed skills via entry-points.

    Returns a list of SkillData. Empty if no skill is installed.
    """
    out: list[SkillData] = []
    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        selected = eps.select(group=ENTRY_POINT_GROUP)
    else:
        selected = eps.get(ENTRY_POINT_GROUP, [])
    for ep in selected:
        get_data_fn = ep.load()
        out.append(get_data_fn())
    return out
