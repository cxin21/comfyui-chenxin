"""P3 adapters for the bound lora_unit slot and the emulated group controllers.

Implements the P3 slice of the config-surface design
(docs/superpowers/specs/2026-08-05-config-surface-lora-unit-design.md).

``patch_lora_unit`` writes node 26 (Lora Loader) and node 66 (TriggerWord
Toggle) as one atomic slot: stack text + structured list on the loader, word
table + concatenated string on the toggle, then proves the unit invariants on
the patched graph.

``patch_group_toggles`` emulates the two Fast Groups Bypasser controllers by
flipping member-node modes.  Nodes owned by other declared slots (prompts,
camera, lora_unit, the controllers themselves) are exempt, so a suffixed group
drawn around a declared variable can never bypass that variable.
"""

from __future__ import annotations

import copy

from ..config_surface import ConfigSurfaceError, validate_config_surface
from ..contracts import canonical_json
from ..lora_discovery import (
    LoraDiscoveryError,
    LoraSelection,
    render_lora_stack,
    normalize_lora_reference,
    validate_unit_invariants,
)


class LoraUnitAdapterError(ValueError):
    """Raised when the lora_unit or group-toggle patch cannot be applied safely."""


_LOADER_CLASS = "Lora Loader (LoraManager)"
_TOGGLE_CLASS = "TriggerWord Toggle (LoraManager)"
_CONTROLLER_CLASS = "Fast Groups Bypasser (rgthree)"
_TOGGLE_WORDS_INDEX = 3
_TOGGLE_CONCAT_INDEX = 4
_TOGGLE_MIN_WIDGETS = 5
_SELECTION_KEYS = frozenset(
    {"name", "strength_model", "strength_clip", "active", "trigger_words"}
)
_STACK_SENTINEL = "__LORA_UNIT_STACK__"
_LIST_SENTINEL = "__LORA_UNIT_LIST__"
_WORDS_SENTINEL = "__LORA_UNIT_WORDS__"
_CONCAT_SENTINEL = "__LORA_UNIT_CONCAT__"
_MODE_ACTIVE = 0
_MODE_BYPASS = 4


def _require_surface(profile: object) -> dict:
    try:
        surface = validate_config_surface(profile)
    except ConfigSurfaceError as exc:
        raise LoraUnitAdapterError(f"profile config_surface is invalid: {exc}") from exc
    if surface is None:
        raise LoraUnitAdapterError("profile must declare a config_surface section")
    return surface


def _ui_node(workflow: dict, node_id: int) -> dict:
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        raise LoraUnitAdapterError("camera UI workflow requires a nodes list")
    matches = [node for node in nodes if isinstance(node, dict) and node.get("id") == node_id]
    if len(matches) != 1:
        raise LoraUnitAdapterError(f"node {node_id} is missing or ambiguous")
    return matches[0]


def _validated_plan(plan: object) -> tuple[list[LoraSelection], str]:
    if not isinstance(plan, dict):
        raise LoraUnitAdapterError("lora_plan must be an object")
    required = {"base_model", "selections", "inventory_hash", "recommendation_hash", "stack_text"}
    if set(plan) != required:
        raise LoraUnitAdapterError("lora_plan is incomplete or has unexpected fields")
    base_model = plan.get("base_model")
    if not isinstance(base_model, str) or not base_model.strip():
        raise LoraUnitAdapterError("lora_plan base_model must be a non-empty string")
    raw_selections = plan.get("selections")
    if not isinstance(raw_selections, list) or not raw_selections:
        raise LoraUnitAdapterError("lora_plan requires at least one selection")
    selections: list[LoraSelection] = []
    for selection in raw_selections:
        if not isinstance(selection, dict) or set(selection) != _SELECTION_KEYS:
            raise LoraUnitAdapterError("lora selection schema is invalid")
        name = selection.get("name")
        if not isinstance(name, str) or not name.strip():
            raise LoraUnitAdapterError("lora selection name must be a non-empty string")
        strengths = {}
        for label in ("strength_model", "strength_clip"):
            value = selection.get(label)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise LoraUnitAdapterError(
                    f"lora selection {label} must be a non-negative number"
                )
            strengths[label] = float(value)
        active = selection.get("active")
        if not isinstance(active, bool):
            raise LoraUnitAdapterError("lora selection active must be boolean")
        words = selection.get("trigger_words")
        if not isinstance(words, list) or any(
            not isinstance(word, str) or not word.strip() for word in words
        ):
            raise LoraUnitAdapterError("lora selection trigger_words must be a list of strings")
        selections.append(
            LoraSelection(
                name=name,
                strength_model=strengths["strength_model"],
                strength_clip=strengths["strength_clip"],
                active=active,
                trigger_words=list(words),
            )
        )
    stack_text = plan.get("stack_text")
    if not isinstance(stack_text, str):
        raise LoraUnitAdapterError("lora_plan stack_text must be a string")
    if stack_text != render_lora_stack(selections):
        raise LoraUnitAdapterError("lora_plan stack_text does not match the selections")
    for label in ("inventory_hash", "recommendation_hash"):
        value = plan.get(label)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise LoraUnitAdapterError(
                f"lora_plan {label} must be a lowercase SHA-256 digest"
            )
    return selections, stack_text


def _strength_widget(value: float):
    return int(value) if float(value).is_integer() else float(value)


def _structured_entry(selection: LoraSelection) -> dict:
    return {
        "name": normalize_lora_reference(selection.name),
        "strength": _strength_widget(selection.strength_model),
        "active": selection.active,
        "expanded": False,
        "clipStrength": _strength_widget(selection.strength_clip),
        "selected": False,
        "locked": False,
    }


def _word_entry(word: str) -> dict:
    inner = {"text": word, "active": True, "highlighted": False, "strength": None}
    return {**inner, "items": [dict(inner)]}


def _render_concat(words: list[str]) -> str:
    return ", ".join(f"{word}," for word in words)


def _render_stack_from_list(entries: list[dict]) -> str:
    parts = []
    for entry in entries:
        strength = float(entry["strength"])
        clip = float(entry["clipStrength"])
        if abs(clip - strength) < 1e-9:
            parts.append(f"<lora:{normalize_lora_reference(entry['name'])}:{strength:.2f}>")
        else:
            parts.append(f"<lora:{normalize_lora_reference(entry['name'])}:{strength:.2f}:{clip:.2f}>")
    return "".join(parts)


def _without_lora_unit_values(workflow: dict, unit: dict) -> dict:
    normalized = copy.deepcopy(workflow)
    loader = _ui_node(normalized, unit["loader_node"])
    loader_values = loader.get("widgets_values")
    stack_index = unit["stack_widget_index"]
    list_index = unit["list_widget_index"]
    if not isinstance(loader_values, list) or len(loader_values) <= max(stack_index, list_index):
        raise LoraUnitAdapterError("lora loader widgets_values is incomplete")
    loader_values[stack_index] = _STACK_SENTINEL
    loader_values[list_index] = _LIST_SENTINEL
    toggle = _ui_node(normalized, unit["trigger_toggle_node"])
    toggle_values = toggle.get("widgets_values")
    if not isinstance(toggle_values, list) or len(toggle_values) < _TOGGLE_MIN_WIDGETS:
        raise LoraUnitAdapterError("trigger toggle widgets_values is incomplete")
    toggle_values[_TOGGLE_WORDS_INDEX] = _WORDS_SENTINEL
    toggle_values[_TOGGLE_CONCAT_INDEX] = _CONCAT_SENTINEL
    return normalized


def patch_lora_unit(workflow: dict, lora_plan: dict, profile: dict) -> dict:
    """Patch the bound LoraManager loader + trigger toggle pair atomically."""
    if not isinstance(workflow, dict):
        raise LoraUnitAdapterError("camera UI workflow must be an object")
    surface = _require_surface(profile)
    unit = surface["lora_unit"]
    selections, stack_text = _validated_plan(lora_plan)

    loader = _ui_node(workflow, unit["loader_node"])
    if loader.get("type") != _LOADER_CLASS:
        raise LoraUnitAdapterError("lora loader node has an unexpected class")
    toggle = _ui_node(workflow, unit["trigger_toggle_node"])
    if toggle.get("type") != _TOGGLE_CLASS:
        raise LoraUnitAdapterError("trigger toggle node has an unexpected class")
    loader_values = loader.get("widgets_values")
    stack_index = unit["stack_widget_index"]
    list_index = unit["list_widget_index"]
    if not isinstance(loader_values, list) or len(loader_values) <= max(stack_index, list_index):
        raise LoraUnitAdapterError("lora loader widgets_values is incomplete")
    toggle_values = toggle.get("widgets_values")
    if not isinstance(toggle_values, list) or len(toggle_values) < _TOGGLE_MIN_WIDGETS:
        raise LoraUnitAdapterError("trigger toggle widgets_values is incomplete")

    active_words = [
        word
        for selection in selections
        if selection.active
        for word in selection.trigger_words
    ]

    patched = copy.deepcopy(workflow)
    patched_loader = _ui_node(patched, unit["loader_node"])
    patched_loader["widgets_values"][stack_index] = stack_text
    patched_loader["widgets_values"][list_index] = [
        _structured_entry(selection) for selection in selections
    ]
    patched_toggle = _ui_node(patched, unit["trigger_toggle_node"])
    patched_toggle["widgets_values"][_TOGGLE_WORDS_INDEX] = [
        _word_entry(word) for word in active_words
    ]
    patched_toggle["widgets_values"][_TOGGLE_CONCAT_INDEX] = _render_concat(active_words)

    try:
        source_identity = canonical_json(_without_lora_unit_values(workflow, unit))
        patched_identity = canonical_json(_without_lora_unit_values(patched, unit))
    except (TypeError, ValueError) as exc:
        raise LoraUnitAdapterError(f"camera UI workflow must be canonical JSON: {exc}") from exc
    if source_identity != patched_identity:
        raise LoraUnitAdapterError("lora_unit patch changed data outside the allowlist")

    written_list = _ui_node(patched, unit["loader_node"])["widgets_values"][list_index]
    if _render_stack_from_list(written_list) != stack_text:
        raise LoraUnitAdapterError("lora_unit stack text and structured list diverged")
    written_words = [
        entry["text"]
        for entry in _ui_node(patched, unit["trigger_toggle_node"])["widgets_values"][
            _TOGGLE_WORDS_INDEX
        ]
    ]
    try:
        validate_unit_invariants(selections, written_words)
    except LoraDiscoveryError as exc:
        raise LoraUnitAdapterError(f"lora_unit invariants failed after patch: {exc}") from exc
    return patched


def _group_area(group: dict) -> float:
    bounding = group.get("bounding")
    try:
        width, height = float(bounding[2]), float(bounding[3])
    except (TypeError, ValueError, IndexError) as exc:
        raise LoraUnitAdapterError("suffixed group bounding box is invalid") from exc
    if width < 0 or height < 0:
        raise LoraUnitAdapterError("suffixed group bounding box is invalid")
    return width * height


def _group_contains(group: dict, node: dict) -> bool:
    bounding = group.get("bounding")
    position = node.get("pos")
    if (
        not isinstance(bounding, list)
        or len(bounding) < 4
        or not isinstance(position, list)
        or len(position) < 2
    ):
        return False
    try:
        x, y, width, height = (float(value) for value in bounding[:4])
        node_x, node_y = float(position[0]), float(position[1])
    except (TypeError, ValueError):
        return False
    return x <= node_x <= x + width and y <= node_y <= y + height


def _exempt_node_ids(surface: dict) -> set[int]:
    exempt = set(surface["prompts"]["nodes"])
    exempt.add(surface["camera"]["angle_node"])
    exempt.add(surface["camera"]["extra_node"])
    exempt.add(surface["lora_unit"]["loader_node"])
    exempt.add(surface["lora_unit"]["trigger_toggle_node"])
    exempt.add(surface["group_controllers"]["g1"]["node_id"])
    exempt.add(surface["group_controllers"]["g2"]["node_id"])
    return exempt


def _without_group_modes(workflow: dict, node_ids: set[int]) -> dict:
    normalized = copy.deepcopy(workflow)
    for node_id in node_ids:
        _ui_node(normalized, node_id).pop("mode", None)
    return normalized


def patch_group_toggles(workflow: dict, groups: dict, profile: dict) -> dict:
    """Emulate both Fast Groups Bypasser controllers via member-node modes."""
    if not isinstance(workflow, dict):
        raise LoraUnitAdapterError("camera UI workflow must be an object")
    surface = _require_surface(profile)
    controllers = surface["group_controllers"]
    if not isinstance(groups, dict) or set(groups) != {"enabled_g1", "enabled_g2"}:
        raise LoraUnitAdapterError("groups must carry enabled_g1 and enabled_g2")
    enabled: dict[str, list[str]] = {}
    for controller_key, groups_key in (("g1", "enabled_g1"), ("g2", "enabled_g2")):
        titles = groups[groups_key]
        if not isinstance(titles, list) or any(
            not isinstance(title, str) or not title.strip() for title in titles
        ):
            raise LoraUnitAdapterError(f"{groups_key} must be a list of group titles")
        if len(set(titles)) != len(titles):
            raise LoraUnitAdapterError(f"{groups_key} contains duplicates")
        enabled[controller_key] = list(titles)
    for controller_key in ("g1", "g2"):
        controller = _ui_node(workflow, controllers[controller_key]["node_id"])
        if controller.get("type") != _CONTROLLER_CLASS:
            raise LoraUnitAdapterError(
                f"group controller {controller_key} has an unexpected class"
            )
    all_groups = workflow.get("groups")
    if not isinstance(all_groups, list):
        raise LoraUnitAdapterError("camera UI workflow must expose groups")
    suffixed: dict[str, dict[str, dict]] = {}
    for controller_key in ("g1", "g2"):
        suffix = controllers[controller_key]["match_title"]
        found: dict[str, dict] = {}
        for group in all_groups:
            if not isinstance(group, dict):
                continue
            title = group.get("title")
            if isinstance(title, str) and title.endswith(suffix):
                if title in found:
                    raise LoraUnitAdapterError(f"group title {title} is ambiguous")
                found[title] = group
        for title in enabled[controller_key]:
            if title not in found:
                raise LoraUnitAdapterError(
                    f"group title {title} is not controlled by {controller_key}"
                )
        suffixed[controller_key] = found
    pinned_titles: dict[str, set[str]] = {}
    pinned = surface.get("pinned_groups") or {"g1": [], "g2": []}
    for controller_key in ("g1", "g2"):
        suffix = controllers[controller_key]["match_title"]
        for title in pinned.get(controller_key, []):
            if not title.endswith(suffix):
                raise LoraUnitAdapterError(
                    f"pinned group {title} is not controlled by {controller_key}"
                )
            if title in enabled[controller_key]:
                raise LoraUnitAdapterError(
                    f"pinned group {title} cannot be toggled via the enabled set"
                )
            if title not in suffixed[controller_key]:
                raise LoraUnitAdapterError(f"pinned group {title} does not exist")
        pinned_titles[controller_key] = set(pinned.get(controller_key, []))
    exempt = _exempt_node_ids(surface)
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        raise LoraUnitAdapterError("camera UI workflow requires a nodes list")
    assignments: dict[int, tuple[str, str]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if isinstance(node_id, bool) or not isinstance(node_id, int) or node_id in exempt:
            continue
        candidates = []
        for controller_key, found in suffixed.items():
            for title, group in found.items():
                if _group_contains(group, node):
                    candidates.append((controller_key, title, _group_area(group)))
        if not candidates:
            continue
        candidates.sort(key=lambda candidate: candidate[2])
        if len(candidates) > 1 and candidates[1][2] == candidates[0][2]:
            raise LoraUnitAdapterError(
                f"node {node_id} has ambiguous innermost group membership"
            )
        assignments[node_id] = (candidates[0][0], candidates[0][1])
    patched = copy.deepcopy(workflow)
    for node_id, (controller_key, title) in assignments.items():
        if title in pinned_titles[controller_key]:
            mode = _MODE_ACTIVE
        else:
            mode = _MODE_ACTIVE if title in enabled[controller_key] else _MODE_BYPASS
        _ui_node(patched, node_id)["mode"] = mode
    try:
        source_identity = canonical_json(_without_group_modes(workflow, set(assignments)))
        patched_identity = canonical_json(_without_group_modes(patched, set(assignments)))
    except (TypeError, ValueError) as exc:
        raise LoraUnitAdapterError(f"camera UI workflow must be canonical JSON: {exc}") from exc
    if source_identity != patched_identity:
        raise LoraUnitAdapterError("group toggle patch changed data outside the allowlist")
    return patched



