"""Schema discovery + validation.

Single source of truth per skill: each skill's mcp_bridge module exposes
``describe_config`` and ``validate_config``. This module dispatches to the
skill's own schema via the entry-point registry.

Module loading uses ``importlib.import_module`` (not the bare ``__import__``
builtin) so that tests can mock the call site via
``unittest.mock.patch("comfyui_chenxin_mcp.schema.importlib.import_module")``.
"""
from __future__ import annotations

import importlib
from typing import Any

from .registry import discover as _discover_skills


_VALIDATORS: dict[str, Any] = {
    # Each skill registers a validator via the entry-point.
    # Default per-skill validators live in skills/<skill>/mcp_bridge.py.
}


def _load_validator(skill: str):
    if skill in _VALIDATORS:
        return _VALIDATORS[skill]
    # Discover via entry-points; each skill exposes validate_config(skill, stage, config).
    for reg in _discover_skills():
        if reg.name != skill:
            continue
        ep_module = reg.register_fn.__module__  # e.g. "camera_image.mcp_bridge"
        mod = importlib.import_module(ep_module)
        validator = getattr(mod, "validate_config", None)
        if validator is not None:
            _VALIDATORS[skill] = validator
            return validator
    return None


def describe_skill(skill: str, stage: str | None = None) -> dict[str, Any]:
    """Dispatch to the skill's own describe_config (or describe_<skill>_config)."""
    for reg in _discover_skills():
        if reg.name != skill:
            continue
        ep_module = reg.register_fn.__module__
        mod = importlib.import_module(ep_module)
        fn = getattr(mod, "describe_config", None) or getattr(
            mod, f"describe_{skill.replace('-', '_')}_config", None
        )
        if fn is None:
            raise ValueError(f"skill {skill!r} entry-point has no describe_config function")
        return fn(stage or reg.stages[0] if reg.stages else "default")
    raise ValueError(
        f"unknown skill: {skill!r}; installed skills: {[r.name for r in _discover_skills()]}"
    )


def validate_config(skill: str, stage: str, config: dict[str, Any]) -> dict[str, Any]:
    """Dispatch to the skill's own validate_config."""
    validator = _load_validator(skill)
    if validator is None:
        raise ValueError(f"no validator registered for skill: {skill!r}")
    return validator(skill, stage, config)