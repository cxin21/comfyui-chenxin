"""Config surface schema and StageConfig contract.

Implements the P2 slice of the config-surface design
(docs/superpowers/specs/2026-08-05-config-surface-lora-unit-design.md).

``validate_config_surface`` is additive: profiles without a ``config_surface``
section fall back to the legacy fingerprint-locked behavior (returns None).
``build_stage_config`` assembles the single canonical configuration object
for one execution; ``stack_text`` is always derived from selections so text
and list representations cannot diverge at construction time.
"""

from __future__ import annotations

import copy
import re

from .contracts import canonical_json, content_hash
from .lora_discovery import LoraSelection, render_lora_stack


class ConfigSurfaceError(ValueError):
    """Raised when a config surface or StageConfig violates its contract."""


_STAGES = frozenset({"character-base", "shot-image"})
_SURFACE_KEYS = frozenset({"schema_version", "prompts", "camera", "group_controllers", "lora_unit"})
_SURFACE_OPTIONAL_KEYS = frozenset({"pinned_groups"})
_PROMPT_FIELDS = ["wildcard_text", "populated_text"]
_CAMERA_EXTRA_KEYS = frozenset(
    {
        "extreme_type", "extreme_weight",
        "lens_enabled", "lens_value",
        "dof_enabled", "dof_value", "dof_weight",
        "movement_enabled", "movement_value",
        "composition_enabled", "composition_value",
        "style_enabled", "style_value",
    }
)
_IMG2IMG_GROUP = "\u52a0\u8f7d\u56fe\u7247\uff08G1\uff09"
_SELECTION_KEYS = frozenset({"name", "strength_model", "strength_clip", "active", "trigger_words"})
_SHA_RE = re.compile(r"[0-9a-f]{64}")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigSurfaceError(f"{label} must be a non-empty string")
    return value


def _int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ConfigSurfaceError(f"{label} must be a non-negative integer")
    return value


def validate_config_surface(profile: object) -> dict | None:
    """Validate the optional config_surface section of a workflow profile."""
    if not isinstance(profile, dict):
        raise ConfigSurfaceError("profile must be an object")
    surface = profile.get("config_surface")
    if surface is None:
        return None
    if not isinstance(surface, dict) or (
        set(surface) != _SURFACE_KEYS
        and set(surface) != _SURFACE_KEYS | _SURFACE_OPTIONAL_KEYS
    ):
        raise ConfigSurfaceError("config_surface schema is incomplete or has unexpected fields")
    if surface.get("schema_version") != "1.0":
        raise ConfigSurfaceError("config_surface schema_version is unsupported")
    prompts = surface.get("prompts")
    if (
        not isinstance(prompts, dict)
        or prompts.get("nodes") != [24, 25]
        or prompts.get("fields") != _PROMPT_FIELDS
    ):
        raise ConfigSurfaceError("config_surface prompts section is invalid")
    camera = surface.get("camera")
    if not isinstance(camera, dict) or set(camera) != {"angle_node", "extra_node"}:
        raise ConfigSurfaceError("config_surface camera section is invalid")
    for label in ("angle_node", "extra_node"):
        _int(camera.get(label), f"config_surface camera {label}")
    controllers = surface.get("group_controllers")
    if not isinstance(controllers, dict) or set(controllers) != {"g1", "g2"}:
        raise ConfigSurfaceError("config_surface group_controllers section is invalid")
    for key in ("g1", "g2"):
        controller = controllers.get(key)
        if not isinstance(controller, dict) or set(controller) != {"node_id", "match_title"}:
            raise ConfigSurfaceError(f"config_surface group controller {key} is invalid")
        _int(controller.get("node_id"), f"config_surface group controller {key} node_id")
        _text(controller.get("match_title"), f"config_surface group controller {key} match_title")
    pinned = surface.get("pinned_groups")
    if pinned is not None:
        if not isinstance(pinned, dict) or set(pinned) != {"g1", "g2"}:
            raise ConfigSurfaceError("config_surface pinned_groups section is invalid")
        for key in ("g1", "g2"):
            titles = pinned.get(key)
            if not isinstance(titles, list) or any(
                not isinstance(title, str) or not title.strip() for title in titles
            ):
                raise ConfigSurfaceError(f"config_surface pinned_groups {key} is invalid")
            if len(set(titles)) != len(titles):
                raise ConfigSurfaceError(f"config_surface pinned_groups {key} contains duplicates")
    unit = surface.get("lora_unit")
    if not isinstance(unit, dict):
        raise ConfigSurfaceError("config_surface lora_unit section is invalid")
    expected_unit_keys = {
        "loader_node", "stack_widget_index", "list_widget_index", "trigger_toggle_node",
        "binding", "inventory_source", "metadata_source", "policy",
    }
    if set(unit) != expected_unit_keys:
        raise ConfigSurfaceError("config_surface lora_unit section is incomplete or has unexpected fields")
    for label in ("loader_node", "stack_widget_index", "list_widget_index", "trigger_toggle_node"):
        _int(unit.get(label), f"config_surface lora_unit {label}")
    if unit.get("binding") != "atomic":
        raise ConfigSurfaceError("config_surface lora_unit binding must be atomic")
    if unit.get("inventory_source") != "mcp:list_local_models":
        raise ConfigSurfaceError("config_surface lora_unit inventory_source is unsupported")
    if unit.get("metadata_source") != "mcp:model_metadata":
        raise ConfigSurfaceError("config_surface lora_unit metadata_source is unsupported")
    if unit.get("policy") != "recommend-then-approve":
        raise ConfigSurfaceError("config_surface lora_unit policy is unsupported")
    result = copy.deepcopy(surface)
    if pinned is None:
        result["pinned_groups"] = {"g1": [], "g2": []}
    return result


def _validated_prompts(prompts: object) -> dict:
    if not isinstance(prompts, dict) or set(prompts) != {"positive", "negative"}:
        raise ConfigSurfaceError("StageConfig prompts must carry positive and negative")
    positive = _text(prompts.get("positive"), "StageConfig positive prompt")
    negative = prompts.get("negative")
    if not isinstance(negative, str):
        raise ConfigSurfaceError("StageConfig negative prompt must be a string")
    return {"positive": positive, "negative": negative}


def _validated_camera(camera: object, stage: str) -> dict:
    if not isinstance(camera, dict) or set(camera) != {"direction", "elevation", "distance", "roll"}:
        raise ConfigSurfaceError("StageConfig camera must carry direction, elevation, distance, roll")
    direction = _text(camera.get("direction"), "StageConfig camera direction")
    elevation = _text(camera.get("elevation"), "StageConfig camera elevation")
    distance = _text(camera.get("distance"), "StageConfig camera distance")
    roll = camera.get("roll")
    if isinstance(roll, bool) or not isinstance(roll, (int, float)):
        raise ConfigSurfaceError("StageConfig camera roll must be a number")
    if stage == "character-base":
        if direction != "front" or elevation != "eye-level":
            raise ConfigSurfaceError("character-base camera must stay front and eye-level")
        if distance not in {"medium", "full_body"}:
            raise ConfigSurfaceError("character-base camera distance must be medium or full_body")
        if float(roll) != 0.0:
            raise ConfigSurfaceError("character-base camera roll must stay 0")
    return {"direction": direction, "elevation": elevation, "distance": distance, "roll": float(roll)}


def _validated_camera_extra(extra: object) -> dict:
    if not isinstance(extra, dict) or set(extra) != _CAMERA_EXTRA_KEYS:
        raise ConfigSurfaceError("StageConfig camera_extra must carry the exact 13-field set")
    for key in _CAMERA_EXTRA_KEYS:
        value = extra[key]
        if key.endswith("_enabled"):
            if not isinstance(value, bool):
                raise ConfigSurfaceError(f"camera_extra {key} must be boolean")
        elif key in {"extreme_weight", "dof_weight"}:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigSurfaceError(f"camera_extra {key} must be a number")
        else:
            if not isinstance(value, str):
                raise ConfigSurfaceError(f"camera_extra {key} must be a string")
    return copy.deepcopy(extra)


def _validated_groups(groups: object, stage: str) -> dict:
    if not isinstance(groups, dict) or set(groups) != {"enabled_g1", "enabled_g2"}:
        raise ConfigSurfaceError("StageConfig groups must carry enabled_g1 and enabled_g2")
    for key in ("enabled_g1", "enabled_g2"):
        entries = groups.get(key)
        if not isinstance(entries, list) or any(not isinstance(item, str) or not item.strip() for item in entries):
            raise ConfigSurfaceError(f"StageConfig {key} must be a list of group titles")
        if len(set(entries)) != len(entries):
            raise ConfigSurfaceError(f"StageConfig {key} contains duplicates")
    if stage == "character-base" and groups["enabled_g1"]:
        raise ConfigSurfaceError("character-base must keep every G1 group disabled")
    if stage == "shot-image" and groups["enabled_g1"]:
        raise ConfigSurfaceError("shot-image img2img G1 is fixed by the profile and is not a user-configurable group")
    return copy.deepcopy(groups)


def _validated_lora_plan(plan: object, *, allow_stack_text: bool = False) -> dict:
    if not isinstance(plan, dict):
        raise ConfigSurfaceError("StageConfig lora_plan must be an object")
    required = {"base_model", "selections", "inventory_hash", "recommendation_hash"}
    if allow_stack_text:
        required = required | {"stack_text"}
    if set(plan) != required:
        raise ConfigSurfaceError("StageConfig lora_plan is incomplete or has unexpected fields")
    base_model = _text(plan.get("base_model"), "StageConfig lora base_model")
    selections = plan.get("selections")
    if not isinstance(selections, list) or not selections:
        raise ConfigSurfaceError("StageConfig lora_plan requires at least one selection")
    clean_selections = []
    for selection in selections:
        if not isinstance(selection, dict) or set(selection) != _SELECTION_KEYS:
            raise ConfigSurfaceError("lora selection schema is invalid")
        name = _text(selection.get("name"), "lora selection name")
        strengths = {}
        for label in ("strength_model", "strength_clip"):
            value = selection.get(label)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ConfigSurfaceError(f"lora selection {label} must be a non-negative number")
            strengths[label] = float(value)
        active = selection.get("active")
        if not isinstance(active, bool):
            raise ConfigSurfaceError("lora selection active must be boolean")
        words = selection.get("trigger_words")
        if not isinstance(words, list) or any(not isinstance(w, str) or not w.strip() for w in words):
            raise ConfigSurfaceError("lora selection trigger_words must be a list of strings")
        clean_selections.append(
            {
                "name": name,
                "strength_model": strengths["strength_model"],
                "strength_clip": strengths["strength_clip"],
                "active": active,
                "trigger_words": list(words),
            }
        )
    for label in ("inventory_hash", "recommendation_hash"):
        if not isinstance(plan.get(label), str) or not _SHA_RE.fullmatch(plan[label]):
            raise ConfigSurfaceError(f"lora_plan {label} must be a lowercase SHA-256 digest")
    stack_text = render_lora_stack([LoraSelection(**selection) for selection in clean_selections])
    if allow_stack_text and plan.get("stack_text") != stack_text:
        raise ConfigSurfaceError("lora_plan stack_text does not match the selections")
    return {
        "base_model": base_model,
        "selections": clean_selections,
        "stack_text": stack_text,
        "inventory_hash": plan["inventory_hash"],
        "recommendation_hash": plan["recommendation_hash"],
    }


def validate_lora_plan(plan: object) -> dict:
    return _validated_lora_plan(plan, allow_stack_text=False)


def build_stage_config(
    *,
    stage: str,
    prompts: dict,
    camera: dict,
    camera_extra: dict,
    groups: dict,
    lora_plan: dict,
    reference_image: str | None = None,
) -> dict:
    """Assemble the canonical StageConfig for one execution."""
    if stage not in _STAGES:
        raise ConfigSurfaceError(f"StageConfig stage must be one of {sorted(_STAGES)}")
    if stage == "character-base" and reference_image is not None:
        raise ConfigSurfaceError("character-base cannot carry a reference image")
    if stage == "shot-image":
        _text(reference_image, "shot-image reference_image")
    config = {
        "schema_version": "1.0",
        "stage": stage,
        "prompts": _validated_prompts(prompts),
        "camera": _validated_camera(camera, stage),
        "camera_extra": _validated_camera_extra(camera_extra),
        "groups": _validated_groups(groups, stage),
        "lora_plan": _validated_lora_plan(lora_plan),
        "reference_image": reference_image,
    }
    config["config_hash"] = content_hash(config)
    return config


def validate_stage_config(config: object) -> dict:
    """Re-validate one StageConfig end to end, including hash self-consistency."""
    if not isinstance(config, dict):
        raise ConfigSurfaceError("StageConfig must be an object")
    expected_keys = {
        "schema_version", "stage", "prompts", "camera", "camera_extra",
        "groups", "lora_plan", "reference_image", "config_hash",
    }
    if set(config) != expected_keys:
        raise ConfigSurfaceError("StageConfig schema is incomplete or has unexpected fields")
    if config.get("schema_version") != "1.0":
        raise ConfigSurfaceError("StageConfig schema_version is unsupported")
    stage = config.get("stage")
    if stage not in _STAGES:
        raise ConfigSurfaceError("StageConfig stage is unsupported")
    rebuilt = {
        "schema_version": "1.0",
        "stage": stage,
        "prompts": _validated_prompts(config.get("prompts")),
        "camera": _validated_camera(config.get("camera"), stage),
        "camera_extra": _validated_camera_extra(config.get("camera_extra")),
        "groups": _validated_groups(config.get("groups"), stage),
        "lora_plan": _validated_lora_plan(config.get("lora_plan"), allow_stack_text=True),
        "reference_image": config.get("reference_image"),
    }
    claimed = config.get("config_hash")
    if not isinstance(claimed, str) or claimed != content_hash(rebuilt):
        raise ConfigSurfaceError("StageConfig config_hash is not self-consistent")
    canonical_json(rebuilt)
    return copy.deepcopy(config)
