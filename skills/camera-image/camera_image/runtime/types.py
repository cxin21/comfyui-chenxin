"""Local SkillData types — replaces the upstream comfyui_chenxin_mcp shapes.

These frozen dataclasses are the only contract the camera-image CLI exposes
to the harness. Keeping them local means the Skill installs and runs without
``comfyui-chenxin-mcp`` ever being a runtime dependency.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Rule:
    """A single dependency rule between config keys and group titles."""

    condition: str
    implies: str
    direction: str = "bidirectional"


@dataclass(frozen=True)
class ImageSpec:
    """Per-stage image-input descriptor: name, requirement, group gating."""

    name: str
    required: bool = False
    requires_group: str | None = None


@dataclass(frozen=True)
class SkillData:
    """Bundled Skill metadata consumed by the CLI dispatcher."""

    name: str
    stages: tuple[str, ...]
    source_workflow_path: str
    groups_dir_pattern: str
    field_map: dict[str, Any]
    dependency_rules: tuple[Rule, ...] = field(default_factory=tuple)
    stage_images: dict[str, tuple[ImageSpec, ...]] = field(default_factory=dict)
    output_type: str = "images"
    describe_fn: Callable[..., Any] | None = None
    prepare_fn: Callable[..., Any] | None = None
    build_config_fn: Callable[..., Any] | None = None
    envelope_validate_fn: Callable[..., Any] | None = None
