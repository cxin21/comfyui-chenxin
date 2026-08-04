"""Pure, auditable intents for reusable visual asset boards.

This module deliberately describes boards and scene variants instead of
generating images.  The plans keep the source evidence alongside the visual
constraints so a later rendering stage can be audited before it performs work.
"""

from __future__ import annotations

import copy
from typing import Any

from .contracts import ContractError, validate_json_compatible
from .story_assets import (
    art_bible_hash,
    asset_card_hash,
    validate_art_bible,
    validate_asset_card,
    validate_story_breakdown,
)


class AssetPlanError(ValueError):
    """Raised when a board or variant would violate a locked visual contract."""


_TIER_KEYS = (
    "explicit_evidence",
    "reasonable_inference",
    "prohibited_expansion",
)
_BIBLE_FIELDS = (
    "style",
    "medium",
    "visual_grammar",
    "palette",
    "materials",
    "lighting",
    "motifs",
    "world_taboos",
    "continuity_strategy",
    "style_prompt",
)
_VARIANT_FORBIDDEN_FIELDS = {
    "environment_anchor_changes": "fixed visual anchor",
    "layout_changes": "fixed environment layout",
    "material_changes": "fixed environment materials",
    "lighting_changes": "fixed environment light logic",
}
_VARIANT_FIXED_DELTA_FIELDS = {
    "environment_anchors": "fixed visual anchor",
    "spatial_layout": "fixed environment layout",
    "layout": "fixed environment layout",
    "materials": "fixed environment materials",
    "lighting": "fixed environment light logic",
}


def _copy_tiers(value: dict[str, Any]) -> dict[str, list[Any]]:
    """Return the known evidence tiers without inventing missing evidence."""
    provenance = value.get("provenance", value)
    if not isinstance(provenance, dict):
        return {key: [] for key in _TIER_KEYS}
    return {
        key: copy.deepcopy(provenance.get(key, []))
        if isinstance(provenance.get(key, []), list)
        else []
        for key in _TIER_KEYS
    }


def _merged_tiers(art_bible: dict[str, Any], asset: dict[str, Any]) -> dict[str, list[Any]]:
    bible_tiers = _copy_tiers(art_bible)
    asset_tiers = _copy_tiers(asset)
    merged: dict[str, list[Any]] = {}
    for key in _TIER_KEYS:
        values: list[Any] = []
        for value in bible_tiers[key] + asset_tiers[key]:
            if value not in values:
                values.append(value)
        merged[key] = values
    return merged


def _require_object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssetPlanError(f"{label} must be an object")
    return value


def _raise_contract_error(action: str, error: ContractError) -> None:
    raise AssetPlanError(f"{action}: {error}") from error


def _validate_bible(value: dict) -> dict:
    try:
        return validate_art_bible(value)
    except ContractError as error:
        _raise_contract_error("invalid art bible", error)


def _validate_asset(value: dict, expected_type: str) -> dict:
    try:
        return validate_asset_card(value, expected_type=expected_type)
    except ContractError as error:
        _raise_contract_error("invalid asset card", error)


def _style_value(
    visual_system: dict[str, Any], style_override: dict[str, Any], field: str
) -> Any:
    """Keep story-provided evidence authoritative over an optional override."""
    if field == "style":
        for story_field in ("primary_style", "style"):
            if story_field in visual_system:
                return copy.deepcopy(visual_system[story_field])
    elif field in visual_system:
        return copy.deepcopy(visual_system[field])
    if field in style_override:
        return copy.deepcopy(style_override[field])
    story_field = "primary_style" if field == "style" else field
    raise AssetPlanError(
        f"story visual_system must provide '{story_field}' or style_override must provide '{field}'"
    )


def build_art_bible(story: dict, *, style_override: dict | None = None) -> dict:
    """Compile an art bible while refusing to overwrite explicit story style facts."""
    try:
        story_copy = validate_story_breakdown(story)
    except ContractError as error:
        _raise_contract_error("invalid story breakdown", error)
    if style_override is None:
        style_override = {}
    _require_object(style_override, "style_override")
    try:
        validate_json_compatible(style_override, "style_override")
    except ContractError as error:
        _raise_contract_error("invalid style_override", error)

    visual_system = _require_object(story_copy["visual_system"], "story visual_system")
    art_bible = {
        field: _style_value(visual_system, style_override, field)
        for field in _BIBLE_FIELDS
    }
    art_bible.update(_copy_tiers(story_copy))
    return _validate_bible(art_bible)


def _board_base(art_bible: dict, asset: dict, plan_type: str) -> dict:
    bible = _validate_bible(art_bible)
    tiers = _merged_tiers(bible, asset)
    return {
        "plan_type": plan_type,
        "asset_id": asset["asset_id"],
        "asset_type": asset["asset_type"],
        "art_bible_hash": art_bible_hash(bible),
        "asset_card_hash": asset_card_hash(asset),
        **{field: copy.deepcopy(bible[field]) for field in _BIBLE_FIELDS},
        **tiers,
    }


def build_environment_board_plan(art_bible: dict, asset: dict) -> dict:
    """Describe the required four-region, people-free environment board."""
    environment = _validate_asset(asset, "environment")
    plan = _board_base(art_bible, environment, "environment_board")
    plan.update(
        {
            "layout": ["panorama", "top_down", "material_detail", "cross_section"],
            "regions": [
                {"region": "panorama", "focus": "complete fixed environment"},
                {"region": "top_down", "focus": "fixed spatial layout"},
                {"region": "material_detail", "focus": "environment materials"},
                {"region": "cross_section", "focus": "structural depth"},
            ],
            "no_people": True,
            "environment_anchors": copy.deepcopy(environment["environment_anchors"]),
            "spatial_layout": copy.deepcopy(environment.get("spatial_layout")),
        }
    )
    return plan


def build_character_board_plan(art_bible: dict, asset: dict) -> dict:
    """Describe a single-subject character board without scene or props."""
    character = _validate_asset(asset, "character")
    plan = _board_base(art_bible, character, "character_board")
    plan.update(
        {
            "layout": ["head_close_up", "front", "side_90", "rear"],
            "single_subject": True,
            "no_scene_or_props": True,
            "identity_lock": copy.deepcopy(character["identity_lock"]),
            "face_lock": copy.deepcopy(character["face_lock"]),
        }
    )
    return plan


def build_prop_board_plan(art_bible: dict, asset: dict) -> dict:
    """Describe a people- and hands-free prop construction board."""
    prop = _validate_asset(asset, "prop")
    plan = _board_base(art_bible, prop, "prop_board")
    plan.update(
        {
            "layout": ["master", "exploded_structure", "material_slice", "function_state"],
            "no_people": True,
            "no_hands": True,
            "scale": copy.deepcopy(prop["scale"]),
            "function": copy.deepcopy(prop["function"]),
        }
    )
    return plan


def _fingerprint_values(asset: dict, feature: str) -> list[str]:
    return [
        part["value"]
        for part in asset["visual_fingerprint"]
        if part["feature"].casefold() == feature
    ]


def _fixed_change_error(value: object) -> str | None:
    if isinstance(value, dict):
        for field, child in value.items():
            if field in _VARIANT_FORBIDDEN_FIELDS:
                return _VARIANT_FORBIDDEN_FIELDS[field]
            if field in _VARIANT_FIXED_DELTA_FIELDS:
                return _VARIANT_FIXED_DELTA_FIELDS[field]
            nested_error = _fixed_change_error(child)
            if nested_error is not None:
                return nested_error
    elif isinstance(value, list):
        for child in value:
            nested_error = _fixed_change_error(child)
            if nested_error is not None:
                return nested_error
    return None


def build_scene_variant_plan(environment_asset: dict, shot_intent: dict) -> dict:
    """Compile declared shot deltas without allowing environment contract drift."""
    environment = _validate_asset(environment_asset, "environment")
    intent = _require_object(shot_intent, "shot_intent")
    try:
        validate_json_compatible(intent, "shot_intent")
    except ContractError as error:
        _raise_contract_error("invalid shot_intent", error)

    for field, message in _VARIANT_FORBIDDEN_FIELDS.items():
        if field in intent:
            raise AssetPlanError(f"scene variant cannot replace {message}")

    extra_fields = set(intent) - {"shot_deltas", "shot_id", "scene_id"}
    if extra_fields:
        raise AssetPlanError("scene variant permits only declared shot deltas")
    shot_deltas = intent.get("shot_deltas")
    if not isinstance(shot_deltas, dict):
        raise AssetPlanError("shot_intent requires a shot_deltas object")
    fixed_change = _fixed_change_error(shot_deltas)
    if fixed_change is not None:
        raise AssetPlanError(f"scene variant cannot replace {fixed_change}")

    plan = {
        "plan_type": "scene_variant",
        "asset_id": environment["asset_id"],
        "asset_card_hash": asset_card_hash(environment),
        "environment_anchors": copy.deepcopy(environment["environment_anchors"]),
        "spatial_layout": copy.deepcopy(environment.get("spatial_layout")),
        "materials": _fingerprint_values(environment, "materials"),
        "lighting": _fingerprint_values(environment, "lighting"),
        "shot_deltas": copy.deepcopy(shot_deltas),
        **_copy_tiers(environment),
    }
    for key in ("shot_id", "scene_id"):
        if key in intent:
            plan[key] = copy.deepcopy(intent[key])
    return plan
