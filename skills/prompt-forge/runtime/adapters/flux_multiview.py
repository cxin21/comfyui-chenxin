"""Fail-closed base-image patching for the verified Flux2-Klein workflow."""

from __future__ import annotations

import copy
from pathlib import PurePosixPath

from ..contracts import canonical_json


class FluxAdapterError(ValueError):
    """Raised when the Flux multiview graph cannot be patched safely."""


_SLOTS = frozenset(("base_image_primary", "base_image_secondary"))
_NODE_CLASS = "LoadImage"
_INPUT = "image"
_REMOVED = "__PROMPT_FORGE_ALLOWLISTED_BASE_IMAGE__"


def _validated_slots(slots: object) -> dict[str, int]:
    if not isinstance(slots, dict):
        raise FluxAdapterError("resolved slots must be an object")
    missing = sorted(_SLOTS.difference(slots))
    unexpected = sorted(set(slots).difference(_SLOTS))
    if missing:
        raise FluxAdapterError("resolved slots are missing: " + ", ".join(missing))
    if unexpected:
        raise FluxAdapterError("resolved slots contain unexpected entries: " + ", ".join(unexpected))
    if any(not isinstance(slots[name], int) or isinstance(slots[name], bool) or slots[name] < 0 for name in _SLOTS):
        raise FluxAdapterError("Flux slot ids must be non-negative integers")
    if slots["base_image_primary"] == slots["base_image_secondary"]:
        raise FluxAdapterError("Flux base-image slots must be different nodes")
    return {name: slots[name] for name in _SLOTS}


def _validated_image_name(image_name: object) -> str:
    if not isinstance(image_name, str) or not image_name or image_name != image_name.strip():
        raise FluxAdapterError("image_name must be a non-empty safe Comfy input reference")
    if "\\" in image_name or ":" in image_name:
        raise FluxAdapterError("image_name must be a relative Comfy input reference")
    path = PurePosixPath(image_name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise FluxAdapterError("image_name must be a relative Comfy input reference")
    return image_name


def _node_for_slot(graph: object, slot_name: str, node_id: int) -> dict:
    if not isinstance(graph, dict):
        raise FluxAdapterError("API graph must be an object")
    node = graph.get(str(node_id))
    if not isinstance(node, dict):
        raise FluxAdapterError(f"slot '{slot_name}' references a missing API node")
    if node.get("class_type") != _NODE_CLASS:
        raise FluxAdapterError(f"slot '{slot_name}' must resolve to LoadImage")
    if not isinstance(node.get("inputs"), dict):
        raise FluxAdapterError(f"slot '{slot_name}' requires an inputs object")
    if _INPUT not in node["inputs"]:
        raise FluxAdapterError(f"slot '{slot_name}' is missing input '{_INPUT}'")
    return node


def _without_base_images(graph: dict, slots: dict[str, int]) -> dict:
    normalized = copy.deepcopy(graph)
    for slot_name, node_id in slots.items():
        _node_for_slot(normalized, slot_name, node_id)["inputs"][_INPUT] = _REMOVED
    return normalized


def assert_dual_input_sync(graph: dict, slots: dict[str, int]) -> None:
    """Ensure the two verified LoadImage nodes contain one safe image reference."""
    resolved = _validated_slots(slots)
    first = _node_for_slot(graph, "base_image_primary", resolved["base_image_primary"])["inputs"][_INPUT]
    second = _node_for_slot(graph, "base_image_secondary", resolved["base_image_secondary"])["inputs"][_INPUT]
    if not isinstance(first, str) or not first or first != second:
        raise FluxAdapterError("Flux base-image slots must contain the same image")
    _validated_image_name(first)


def patch_base_images(graph: dict, image_name: str, slots: dict[str, int]) -> dict:
    """Deep-copy a graph and change exactly both synchronized base-image inputs."""
    image_name = _validated_image_name(image_name)
    resolved = _validated_slots(slots)
    for slot_name, node_id in resolved.items():
        _node_for_slot(graph, slot_name, node_id)

    patched = copy.deepcopy(graph)
    for slot_name, node_id in resolved.items():
        _node_for_slot(patched, slot_name, node_id)["inputs"][_INPUT] = image_name
    assert_dual_input_sync(patched, resolved)

    try:
        unchanged_source = canonical_json(_without_base_images(graph, resolved))
        unchanged_patched = canonical_json(_without_base_images(patched, resolved))
    except (TypeError, ValueError) as exc:
        raise FluxAdapterError(f"API graph must be canonical JSON: {exc}") from exc
    if unchanged_source != unchanged_patched:
        raise FluxAdapterError("Flux patch changed data outside the two base-image inputs")
    return patched
