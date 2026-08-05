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
_FLAT_PROFILE_ID = "flux2-klein-multiview-flat-v2"
_FLAT_WORKFLOW_ID = "prompt-forge-flat-v2"
_FLAT_WORKFLOW_NAME = "PromptForge-Flux2-Klein-multiview-flat-v2.json"
_VIEW_PROFILE_ID = "flux2-klein-view-selection-v1"
_VIEW_PLAN_KEYS = frozenset(("views", "switches", "prompts", "seeds", "dimensions", "base_image", "orientation_evidence"))


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


def _profile_paths(value: object, label: str) -> dict[str, dict]:
    if not isinstance(value, dict):
        raise FluxAdapterError(f"view profile {label} must be an object")
    paths = {}
    for node_id, descriptor in value.items():
        if not isinstance(node_id, str) or not node_id.isdigit() or not isinstance(descriptor, dict) or not isinstance(descriptor.get("type"), str) or not descriptor["type"]:
            raise FluxAdapterError(f"view profile {label} contains an invalid node descriptor")
        paths[node_id] = copy.deepcopy(descriptor)
    return paths


def _validated_view_profile(profile: object) -> dict:
    if not isinstance(profile, dict):
        raise FluxAdapterError("view-selection profile must be an object")
    if profile.get("profile_id") != _VIEW_PROFILE_ID or profile.get("base_profile_id") != _FLAT_PROFILE_ID or profile.get("workflow_id") != _FLAT_WORKFLOW_ID or profile.get("workflow_name") != _FLAT_WORKFLOW_NAME:
        raise FluxAdapterError("view selection is supported only for the production flat-v2 workflow")
    for field in ("workflow_fingerprint", "source_api_graph_hash"):
        value = profile.get(field)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise FluxAdapterError(f"view profile {field} must be a SHA-256 digest")
    slots = profile.get("slots")
    if not isinstance(slots, dict) or any(not isinstance(item, dict) or item.get("type") != _NODE_CLASS for item in slots.values()):
        raise FluxAdapterError("view profile base-image slots must resolve to LoadImage")
    resolved_slots = _validated_slots({name: item.get("id") if isinstance(item, dict) else None for name, item in slots.items()})
    spec = profile.get("view_plan")
    if not isinstance(spec, dict) or set(spec) != {"switches", "prompt_slots", "seed_slots", "dimension_slots"}:
        raise FluxAdapterError("view profile view_plan schema is invalid")
    outputs = profile.get("output_nodes")
    if not isinstance(outputs, dict) or not outputs:
        raise FluxAdapterError("view profile output map is missing")
    labels = set()
    for node_id, descriptor in outputs.items():
        if not isinstance(node_id, str) or not node_id.isdigit() or not isinstance(descriptor, dict) or descriptor.get("artifact_type") != "CharacterAngleView" or not isinstance(descriptor.get("view_label"), str) or not descriptor["view_label"]:
            raise FluxAdapterError("view profile output map contains an invalid entry")
        labels.add(descriptor["view_label"])
    pose_ids = profile.get("immutable_roles", {}).get("pose_references")
    if not isinstance(pose_ids, list) or any(not isinstance(node_id, int) or isinstance(node_id, bool) for node_id in pose_ids) or len(set(pose_ids)) != len(pose_ids):
        raise FluxAdapterError("view profile immutable pose references are invalid")
    mutable = set(resolved_slots.values())
    for field in spec:
        mutable.update(int(node_id) for node_id in spec[field])
    if mutable.intersection(pose_ids):
        raise FluxAdapterError("view profile cannot allowlist an immutable pose reference")
    return {
        "slots": resolved_slots, "switches": _profile_paths(spec["switches"], "switches"),
        "prompts": _profile_paths(spec["prompt_slots"], "prompt_slots"), "seeds": _profile_paths(spec["seed_slots"], "seed_slots"),
        "dimensions": _profile_paths(spec["dimension_slots"], "dimension_slots"), "output_nodes": copy.deepcopy(outputs),
        "output_labels": labels, "pose_ids": list(pose_ids),
    }


def _validated_patch_map(value: object, label: str, allowlist: dict[str, dict]) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise FluxAdapterError(f"view plan {label} must be an object")
    unknown = sorted(set(value).difference(allowlist))
    if unknown:
        raise FluxAdapterError(f"view plan {label} contains a node outside the allowlisted profile: " + ", ".join(unknown))
    return copy.deepcopy(value)


def validate_view_plan(view_plan: object, profile: object) -> dict:
    """Validate and normalize one flat-v2 view plan without touching a graph."""
    contract = _validated_view_profile(profile)
    if not isinstance(view_plan, dict):
        raise FluxAdapterError("view plan must be an object")
    unexpected = sorted(set(view_plan).difference(_VIEW_PLAN_KEYS))
    if unexpected:
        raise FluxAdapterError("view plan contains unexpected fields: " + ", ".join(unexpected))
    views = view_plan.get("views")
    if not isinstance(views, list) or not views or any(not isinstance(view, str) or not view or view != view.strip() for view in views) or len(set(views)) != len(views):
        raise FluxAdapterError("view plan views must be a non-empty unique string list")
    unmapped = sorted(set(views).difference(contract["output_labels"]))
    if unmapped:
        raise FluxAdapterError("view plan output label is not mapped by the profile: " + ", ".join(unmapped))
    switches = _validated_patch_map(view_plan.get("switches"), "switches", contract["switches"])
    prompts = _validated_patch_map(view_plan.get("prompts"), "prompts", contract["prompts"])
    seeds = _validated_patch_map(view_plan.get("seeds"), "seeds", contract["seeds"])
    dimensions = _validated_patch_map(view_plan.get("dimensions"), "dimensions", contract["dimensions"])
    if any(not isinstance(value, bool) for value in switches.values()):
        raise FluxAdapterError("view plan switch values must be booleans")
    if any(not isinstance(value, str) or not value.strip() for value in prompts.values()):
        raise FluxAdapterError("view plan prompt values must be non-empty strings")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 2**64 - 1 for value in seeds.values()):
        raise FluxAdapterError("view plan seed values must be unsigned 64-bit integers")
    for node_id, value in dimensions.items():
        inputs = contract["dimensions"][node_id].get("inputs")
        if isinstance(inputs, list):
            if not isinstance(value, dict) or set(value) != set(inputs):
                raise FluxAdapterError("view plan dimension object does not match the profiled inputs")
            values = value.values()
        else:
            values = (value,)
        if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 or item > 16384 for item in values):
            raise FluxAdapterError("view plan dimensions must be positive integers at most 16384")
    base_image = view_plan.get("base_image")
    if base_image is not None:
        _validated_image_name(base_image)
    orientation = view_plan.get("orientation_evidence", {})
    if not isinstance(orientation, dict):
        raise FluxAdapterError("view plan orientation_evidence must be an object")
    return {
        "views": list(views), "switches": switches, "prompts": prompts, "seeds": seeds, "dimensions": dimensions,
        "base_image": base_image, "orientation_evidence": copy.deepcopy(orientation),
        "output_map": {node_id: item for node_id, item in sorted(contract["output_nodes"].items()) if item["view_label"] in views},
    }


def _profiled_node(graph: dict, node_id: str, descriptor: dict, label: str) -> dict:
    node = graph.get(node_id)
    if not isinstance(node, dict) or node.get("class_type") != descriptor["type"]:
        raise FluxAdapterError(f"profiled {label} node {node_id} is missing or has the wrong type")
    if not isinstance(node.get("inputs"), dict):
        raise FluxAdapterError(f"profiled {label} node {node_id} requires inputs")
    return node


def validate_pose_references(graph: dict, profile: dict) -> None:
    """Require every profiled pose image to remain a concrete LoadImage input."""
    for node_id in _validated_view_profile(profile)["pose_ids"]:
        value = _node_for_slot(graph, f"pose_reference_{node_id}", node_id)["inputs"][_INPUT]
        _validated_image_name(value)


def _without_allowlisted_inputs(graph: dict, paths: set[tuple[str, str]]) -> dict:
    normalized = copy.deepcopy(graph)
    for node_id, input_name in paths:
        node = normalized.get(node_id)
        if isinstance(node, dict) and isinstance(node.get("inputs"), dict):
            node["inputs"][input_name] = _REMOVED
    return normalized


def patch_view_plan(graph: dict, view_plan: dict, profile: dict) -> dict:
    """Apply only profiled flat-v2 view controls and preserve all other graph data."""
    contract = _validated_view_profile(profile)
    safe = validate_view_plan(view_plan, profile)
    validate_pose_references(graph, profile)
    original_pose = {str(node_id): copy.deepcopy(graph[str(node_id)]) for node_id in contract["pose_ids"]}
    if safe["base_image"] is None:
        assert_dual_input_sync(graph, contract["slots"])
        image_name = _node_for_slot(graph, "base_image_primary", contract["slots"]["base_image_primary"])["inputs"][_INPUT]
    else:
        image_name = safe["base_image"]
    patched = patch_base_images(graph, image_name, contract["slots"])
    allowed = {(str(node_id), _INPUT) for node_id in contract["slots"].values()}
    for label in ("switches", "prompts", "seeds"):
        for node_id, value in safe[label].items():
            descriptor = contract[label][node_id]
            input_name = descriptor.get("input")
            node = _profiled_node(patched, node_id, descriptor, label)
            if not isinstance(input_name, str) or input_name not in node["inputs"]:
                raise FluxAdapterError(f"profiled {label} node {node_id} has no valid input")
            node["inputs"][input_name] = value
            allowed.add((node_id, input_name))
    for node_id, value in safe["dimensions"].items():
        descriptor = contract["dimensions"][node_id]
        node = _profiled_node(patched, node_id, descriptor, "dimensions")
        input_names = descriptor.get("inputs")
        if isinstance(input_names, list):
            for input_name in input_names:
                if input_name not in node["inputs"]:
                    raise FluxAdapterError(f"profiled dimensions node {node_id} is missing input {input_name}")
                node["inputs"][input_name] = value[input_name]
                allowed.add((node_id, input_name))
        else:
            input_name = descriptor.get("input")
            if not isinstance(input_name, str) or input_name not in node["inputs"]:
                raise FluxAdapterError(f"profiled dimensions node {node_id} has no valid input")
            node["inputs"][input_name] = value
            allowed.add((node_id, input_name))
    if {str(node_id): patched[str(node_id)] for node_id in contract["pose_ids"]} != original_pose:
        raise FluxAdapterError("view plan changed immutable pose references")
    try:
        source = canonical_json(_without_allowlisted_inputs(graph, allowed))
        result = canonical_json(_without_allowlisted_inputs(patched, allowed))
    except (TypeError, ValueError) as exc:
        raise FluxAdapterError(f"API graph must be canonical JSON: {exc}") from exc
    if source != result:
        raise FluxAdapterError("view plan changed data outside the allowlisted inputs")
    return patched


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
