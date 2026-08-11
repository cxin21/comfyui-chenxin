"""Data contract every skill provides via entry-points."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ImageSpec:
    """An image to upload before workflow execution."""
    config_key: str
    required: bool
    requires_group: str | None = None


@dataclass(frozen=True)
class Rule:
    """A declarative group-config dependency.

    condition/implies use prefixes: "config:", "group:", "stage:", "group_auto:".
    direction="bidirectional" means A->B AND B->A.
    direction="forward" means A->B only.
    """
    condition: str
    implies: str
    direction: str = "bidirectional"


@dataclass(frozen=True)
class SkillData:
    """Pure data + function pointers describing a skill.

    The engine calls describe_fn/prepare_fn via these pointers.
    prepare_fn loads the UI workflow, applies the RunConfig tunables
    AND the G1/G2 mode toggles to the UI, uploads the fully-patched
    UI to ComfyUI, and returns the stripped API graph (so every
    config value is baked into the returned API dict).

    Skills provide this via entry-points; the MCP server never imports
    runtime.* directly.
    """
    name: str
    stages: tuple[str, ...]
    source_workflow_path: str
    groups_dir_pattern: str
    field_map: dict[str, tuple[int, str]]
    dependency_rules: tuple[Rule, ...]
    stage_images: dict[str, tuple[ImageSpec, ...]]
    output_type: str
    describe_fn: Callable[..., dict[str, Any]]
    prepare_fn: Callable[..., dict[str, Any]]
    build_config_fn: Callable[..., Any]
    artifact_mode: str = "first"
    prompt_gate_fn: Callable[[Any], dict[str, Any]] | None = None
    envelope_validate_fn: Callable[[dict[str, Any]], list[str]] | None = None
