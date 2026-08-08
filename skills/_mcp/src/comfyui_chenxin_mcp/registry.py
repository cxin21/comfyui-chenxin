"""Skill discovery via Python entry-points.

Each skill package declares an entry-point in its pyproject.toml:
    [project.entry-points."comfyui_chenxin_mcp.skills"]
    camera-image = "camera_image.mcp_bridge:register"

`register` must be a callable that takes a `Server` and binds tool handlers.
Optional `SKILL_INFO` attribute exposes metadata for `list_skills`.

No hardcoded skill names here. Adding a new skill = pip-install it; the
next `comfyui-chenxin-mcp-server` start picks it up.
"""
from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from typing import Any, Callable


ENTRY_POINT_GROUP = "comfyui_chenxin_mcp.skills"


@dataclass(frozen=True)
class SkillRegistration:
    name: str
    label: str
    description: str
    stages: tuple[str, ...]
    register_fn: Callable[[Any], None]


def discover() -> list[SkillRegistration]:
    """Iterate installed packages' entry-points in ENTRY_POINT_GROUP.

    Each entry-point's callable must:
      - Bind MCP tools via the provided Server
      - Optionally expose `register_fn.SKILL_INFO` (SkillRegistration) for list_skills

    Returns the discovered list. Empty if no skill is installed.
    """
    out: list[SkillRegistration] = []
    eps = importlib.metadata.entry_points()
    # Python 3.10+ uses select(group=...), older uses dict-style. Handle both.
    if hasattr(eps, "select"):
        selected = eps.select(group=ENTRY_POINT_GROUP)
    else:
        selected = eps.get(ENTRY_POINT_GROUP, [])
    for ep in selected:
        register_fn = ep.load()
        info = getattr(register_fn, "SKILL_INFO", None)
        if info is None:
            # Auto-derive minimal metadata from entry-point name + docstring
            info = SkillRegistration(
                name=ep.name,
                label=ep.name,
                description=(register_fn.__doc__ or "").strip().split("\n")[0],
                stages=(),
                register_fn=register_fn,
            )
        out.append(info)
    return out