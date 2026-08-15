"""Local SkillData types — replaces the upstream comfyui_chenxin_mcp shapes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Rule:
    condition: str
    implies: str
    direction: str = "bidirectional"


@dataclass(frozen=True)
class ImageSpec:
    name: str
    required: bool = False
    requires_group: str | None = None


@dataclass(frozen=True)
class SkillData:
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
