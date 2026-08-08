"""Strict Stage 1 patches for the verified camera API graph."""

from __future__ import annotations

import copy
import math
import re
from pathlib import PurePosixPath

from ..contracts import canonical_json
from ..execution import ExecutionError


_SLOTS = frozenset(("positive_prompt", "negative_prompt"))
_INPUTS = ("wildcard_text", "populated_text")
_NODE_CLASS = "ImpactWildcardProcessor"
_REMOVED = "__PROMPT_FORGE_ALLOWLISTED_VALUE__"
_CAMERA_API_NORMALIZATION = {
    "schema_version": "1.0",
    "literal_inputs": [
        {"node_id": 26, "input_name": "text", "ui_node_id": 26, "widget_index": 1}
    ],
    "output_fallbacks": [
        {"source_node_id": 111, "output_index": 0, "target_node_id": 35, "target_input": "images"},
        {"source_node_id": 111, "output_index": 0, "target_node_id": 490, "target_input": "images"},
    ],
    "remove_nodes": [28, 41, 52, 62, 67, 70, 77],
}
_CAMERA_MARKER_IDS = frozenset(
    {
        26,
        35,
        490,
        76,
        96,
        111,
        *_CAMERA_API_NORMALIZATION["remove_nodes"],
    }
)
_NORMALIZATION_CLASSES = {
    26: "Lora Loader (LoraManager)",
    35: "Image Saver Simple",
    490: "PreviewImage",
    76: "VAEDecode",
    96: "AdjustContrast",
    111: "ImageSharpen",
}
_POSTPROCESS_LINKS = (
    (96, "images", 76, 0),
    (111, "image", 96, 0),
)
_CAMERA_PROFILE_ID = "camera-anima-v1"
_CAMERA_PROFILE_ALIASES = frozenset(
    (
        "camera-anima-base-v1",
        "camera-anima-asset-board-environment-v1",
        "camera-anima-asset-board-character-v1",
        "camera-anima-asset-board-prop-v1",
    )
)
_PINNED_CAMERA_WORKFLOW_FINGERPRINT = "7fa7a85e005182c6be42a3f3193add3fb41531ef0fae28e1cbd54a791e72e20a"
_CAMERA_CONTROL_SELECTORS = {
    "camera_angle": {"id": 583, "type": "CameraAngleNode"},
    "camera_extra": {"id": 585, "type": "CameraExtraConfigNode"},
}

# CameraAngleNode expresses azimuth as a normalized half-turn.  Keep this
# mapping explicit so a Stage 3 plan cannot silently degrade into the UI's
# default front/cowboy framing.
_CAMERA_DIRECTION_POS_X = {
    "front": 0.0,
    "right_45": 0.25,
    "right": 0.5,
    "rear_45": 0.75,
    "rear": 1.0,
    "left": -0.5,
    "left_45": -0.25,
}
_CAMERA_ELEVATION_POS_Y = {"high": 0.5, "high-angle": 0.5, "eye-level": 0.0, "low": -0.5, "low-angle": -0.5}
_CAMERA_DISTANCE_POS_Z = {
    "extreme_close_up": 0.9,
    "close_up": 0.5,
    "medium": 0.1,
    "cowboy_shot": -0.2,
    "full_body": -0.5,
    "wide": -0.9,
}
_CAMERA_ANGLE_FIELDS = frozenset(("pos_x", "pos_y", "pos_z", "roll"))
_CAMERA_EXTRA_FIELDS = frozenset((
    "extreme_type", "extreme_weight", "lens_enabled", "lens_value",
    "dof_enabled", "dof_value", "dof_weight", "movement_enabled",
    "movement_value", "composition_enabled", "composition_value",
    "style_enabled", "style_value",
))
_BOARD_ROLES = frozenset(("environment", "character", "prop"))
_BOARD_MUTATIONS = [
    "positive_prompt.wildcard_text", "positive_prompt.populated_text",
    "negative_prompt.wildcard_text", "negative_prompt.populated_text",
]


class CameraAdapterError(ValueError):
    """Raised when a camera UI/API graph cannot be patched safely."""


def is_pinned_camera_normalization_profile(profile: object) -> bool:
    """Return whether a profile carries the exact production camera bridge."""
    if not isinstance(profile, dict) or profile.get("api_normalization") != _CAMERA_API_NORMALIZATION:
        return False
    profile_id = profile.get("profile_id")
    return (
        profile_id == _CAMERA_PROFILE_ID
        or (
            profile_id in _CAMERA_PROFILE_ALIASES
            and profile.get("source_profile_id") == _CAMERA_PROFILE_ID
            and profile.get("execution_profile_id") == _CAMERA_PROFILE_ID
        )
    )


def is_pinned_camera_profile(profile: object) -> bool:
    """Return whether a Stage 1/3 profile is a complete verified camera contract."""
    if not is_pinned_camera_normalization_profile(profile):
        return False
    if not isinstance(profile, dict):
        return False
    if (
        profile.get("schema_version") != "1.0"
        or profile.get("runtime_classification") != "local"
        or profile.get("expected_outputs") != ["image/png"]
    ):
        return False
    workflow_fingerprint = profile.get("workflow_fingerprint")
    if not isinstance(workflow_fingerprint, str) or len(workflow_fingerprint) != 64:
        return False
    if any(character not in "0123456789abcdef" for character in workflow_fingerprint):
        return False
    slots = profile.get("slots")
    if not isinstance(slots, dict):
        return False
    expected_slots = {
        "positive_prompt": {"id": 24, "type": "ImpactWildcardProcessor", "title": "POSITIVE"},
        "negative_prompt": {"id": 25, "type": "ImpactWildcardProcessor", "title": "NEGATIVE"},
    }
    if any(slots.get(name) != selector for name, selector in expected_slots.items()):
        return False
    img2img = profile.get("img2img")
    if not isinstance(img2img, dict):
        return False
    return (
        img2img.get("group_id") == 3
        and img2img.get("node_ids") == [21, 58, 57, 59]
        and img2img.get("load_image_node_id") == 21
        and img2img.get("vae_encode_node_id") == 59
        and img2img.get("latent_switch_node_id") == 75
        and img2img.get("sampler_node_id") == 27
        and img2img.get("expected_path_node_ids") == [27, 75, 59]
    )


def normalize_camera_api_graph(
    graph: dict,
    ui_workflow: dict | None,
    profile: dict,
) -> dict:
    """Repair only the known UI-to-API conversion losses of the camera source.

    The live ComfyUI converter omits widget-only LoRA text and drops a muted
    optional image-switch branch, leaving the real saver/preview nodes without
    ``images``.  This function is an explicit, idempotent normalization bridge:
    it copies the exact literal from the source UI, reconnects both output sinks
    to the profiled post-processed image, and removes only the profiled orphan
    nodes.
    It never saves or mutates the user's workflow.

    Profiles without this pinned contract remain unchanged so compact adapters
    can be tested independently.  A profile carrying the contract but a graph
    without its topology markers fails closed rather than guessing a topology.
    """
    if not isinstance(graph, dict):
        raise CameraAdapterError("camera API graph must be an object")
    if not isinstance(profile, dict):
        raise CameraAdapterError("camera profile is required for API normalization")
    config = profile.get("api_normalization")
    if config is None:
        present_markers = {
            int(node_id) if isinstance(node_id, str) and node_id.isdigit() else node_id
            for node_id in graph
        }.intersection(_CAMERA_MARKER_IDS)
        if (
            profile.get("profile_id") == _CAMERA_PROFILE_ID
            or profile.get("source_profile_id") == _CAMERA_PROFILE_ID
        ) and present_markers:
            raise CameraAdapterError("camera API normalization requires the pinned contract")
        return copy.deepcopy(graph)
    if not is_pinned_camera_normalization_profile(profile):
        raise CameraAdapterError("camera API normalization profile is not the pinned contract")

    literal = config["literal_inputs"][0]
    literal_id = literal["node_id"]
    literal_node = graph.get(str(literal_id))
    fallback_ids = {
        item["source_node_id"]
        for item in config["output_fallbacks"]
    } | {
        item["target_node_id"]
        for item in config["output_fallbacks"]
    }
    marker_ids = fallback_ids | {literal_id} | set(config["remove_nodes"])
    present_markers = marker_ids.intersection(
        int(node_id) if isinstance(node_id, str) and node_id.isdigit() else node_id
        for node_id in graph
    )
    if not present_markers:
        raise CameraAdapterError("camera API normalization source has no pinned topology markers")
    if not isinstance(ui_workflow, dict):
        raise CameraAdapterError("camera API normalization requires the source UI workflow")
    ui_nodes = ui_workflow.get("nodes")
    if not isinstance(ui_nodes, list):
        raise CameraAdapterError("camera UI workflow requires nodes for API normalization")
    ui_matches = [node for node in ui_nodes if isinstance(node, dict) and node.get("id") == literal["ui_node_id"]]
    if len(ui_matches) != 1:
        raise CameraAdapterError("camera UI LoRA node is missing or ambiguous")
    if ui_matches[0].get("type") != _NORMALIZATION_CLASSES[literal_id]:
        raise CameraAdapterError("camera UI LoRA node type is unexpected")
    widget_values = ui_matches[0].get("widgets_values")
    widget_index = literal["widget_index"]
    if (
        not isinstance(widget_values, list)
        or not isinstance(widget_index, int)
        or isinstance(widget_index, bool)
        or widget_index < 0
        or widget_index >= len(widget_values)
        or not isinstance(widget_values[widget_index], str)
        or not widget_values[widget_index].strip()
    ):
        raise CameraAdapterError("camera UI LoRA text widget is invalid")
    ui_lora_text = widget_values[widget_index]

    required_ids = set(_NORMALIZATION_CLASSES) | fallback_ids
    missing_ids = sorted(node_id for node_id in required_ids if str(node_id) not in graph)
    if missing_ids:
        raise CameraAdapterError(
            "camera API normalization source is incomplete: missing node(s) "
            + ", ".join(str(node_id) for node_id in missing_ids)
        )
    for node_id, expected_class in _NORMALIZATION_CLASSES.items():
        node = graph.get(str(node_id))
        if not isinstance(node, dict) or node.get("class_type") != expected_class:
            raise CameraAdapterError(f"camera API normalization node {node_id} has an unexpected class")
        if not isinstance(node.get("inputs"), dict):
            label = "target" if node_id in {item["target_node_id"] for item in config["output_fallbacks"]} else "source"
            raise CameraAdapterError(f"camera API normalization {label} node {node_id} requires inputs")

    for consumer_id, input_name, source_id, output_index in _POSTPROCESS_LINKS:
        link = graph[str(consumer_id)]["inputs"].get(input_name)
        if (
            not isinstance(link, (list, tuple))
            or len(link) < 2
            or str(link[0]) != str(source_id)
            or link[1] != output_index
        ):
            raise CameraAdapterError(
                "camera API normalization post-process chain must be 76 -> 96 -> 111"
            )

    literal_inputs = literal_node["inputs"]
    existing_text = literal_inputs.get(literal["input_name"])
    if (
        literal["input_name"] in literal_inputs
        and isinstance(existing_text, str)
        and existing_text.strip()
        and existing_text != ui_lora_text
    ):
        raise CameraAdapterError("camera API LoRA text conflicts with UI")
    literal_text = existing_text == ui_lora_text
    def _fallback_is_ready(item: dict) -> bool:
        target = graph.get(str(item["target_node_id"]))
        inputs = target.get("inputs") if isinstance(target, dict) else None
        return isinstance(inputs, dict) and inputs.get(item["target_input"]) == [
            str(item["source_node_id"]),
            item["output_index"],
        ]

    fallback_ready = all(_fallback_is_ready(item) for item in config["output_fallbacks"])
    remove_present = set(config["remove_nodes"]).intersection(present_markers)
    if literal_text and fallback_ready and not remove_present:
        return copy.deepcopy(graph)

    patched = copy.deepcopy(graph)
    patched[str(literal_id)]["inputs"][literal["input_name"]] = ui_lora_text
    for item in config["output_fallbacks"]:
        target = patched[str(item["target_node_id"])]
        inputs = target.get("inputs")
        if not isinstance(inputs, dict):
            raise CameraAdapterError("camera API normalization target requires inputs")
        expected_link = [str(item["source_node_id"]), item["output_index"]]
        existing = inputs.get(item["target_input"])
        if existing is not None and existing != expected_link:
            raise CameraAdapterError("camera API normalization would overwrite a non-empty output")
        inputs[item["target_input"]] = expected_link

    remove_ids = set(config["remove_nodes"])
    remove_keys = {str(node_id) for node_id in remove_ids}
    for node_id in remove_ids:
        for consumer_id, node in patched.items():
            if str(consumer_id) in remove_keys or not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            if any(
                isinstance(value, (list, tuple))
                and value
                and str(value[0]) == str(node_id)
                for value in inputs.values()
            ):
                raise CameraAdapterError(
                    f"camera API normalization node {node_id} still feeds node {consumer_id}"
                )
    for node_id in remove_ids:
        patched.pop(str(node_id), None)
    return patched


def _node_for_slot(graph: dict, slot_name: str, node_id: object) -> dict:
    if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id < 0:
        raise ExecutionError(f"slot '{slot_name}' node id must be a non-negative integer")
    node = graph.get(str(node_id))
    if not isinstance(node, dict):
        raise ExecutionError(f"slot '{slot_name}' references a missing API node")
    if node.get("class_type") != _NODE_CLASS:
        raise ExecutionError(f"slot '{slot_name}' has unexpected class_type")
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        raise ExecutionError(f"slot '{slot_name}' requires an inputs object")
    for input_name in _INPUTS:
        if input_name not in inputs:
            raise ExecutionError(f"slot '{slot_name}' is missing input '{input_name}'")
        if not isinstance(inputs[input_name], str):
            raise ExecutionError(f"slot '{slot_name}' input '{input_name}' must be a string")
    return node


def _without_allowlisted_values(
    graph: dict,
    slots: dict[str, int],
    camera_node_id: int | None = None,
) -> dict:
    normalized = copy.deepcopy(graph)
    for slot_name in _SLOTS:
        node = normalized[str(slots[slot_name])]
        for input_name in _INPUTS:
            node["inputs"][input_name] = _REMOVED
    if camera_node_id is not None:
        camera = normalized.get(str(camera_node_id))
        if isinstance(camera, dict) and isinstance(camera.get("inputs"), dict):
            for input_name in ("pos_x", "pos_y", "pos_z"):
                if input_name in camera["inputs"]:
                    camera["inputs"][input_name] = _REMOVED
    return normalized


def _patch_camera_angle(graph: dict, camera: object, profile: dict) -> tuple[dict, int | None]:
    """Apply the declared Stage 3 framing to the profiled camera node."""
    if not isinstance(camera, dict):
        return copy.deepcopy(graph), None
    slots = profile.get("slots") if isinstance(profile, dict) else None
    selector = slots.get("camera_angle") if isinstance(slots, dict) else None
    if not isinstance(selector, dict):
        # Compact test profiles and non-camera graphs have no camera slot.
        return copy.deepcopy(graph), None
    node_id = selector.get("id")
    if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id < 0:
        raise CameraAdapterError("camera profile camera_angle slot is invalid")
    node = graph.get(str(node_id))
    if not isinstance(node, dict) or node.get("class_type") != selector.get("type"):
        raise CameraAdapterError("camera angle node does not match the profile")
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        raise CameraAdapterError("camera angle node inputs are invalid")
    patched = copy.deepcopy(graph)
    target = patched[str(node_id)]["inputs"]
    for field, mapping in (
        ("direction", _CAMERA_DIRECTION_POS_X),
        ("elevation", _CAMERA_ELEVATION_POS_Y),
        ("distance", _CAMERA_DISTANCE_POS_Z),
    ):
        value = camera.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or value not in mapping:
            raise CameraAdapterError(f"camera {field} is unsupported: {value!r}")
        input_name = {"direction": "pos_x", "elevation": "pos_y", "distance": "pos_z"}[field]
        if input_name not in target:
            raise CameraAdapterError(f"camera angle node is missing {input_name}")
        target[input_name] = mapping[value]
    return patched, node_id


def _profiled_node(graph: dict, profile: dict, slot_name: str) -> tuple[int, dict]:
    slots = profile.get("slots") if isinstance(profile, dict) else None
    selector = slots.get(slot_name) if isinstance(slots, dict) else None
    if not isinstance(selector, dict):
        raise CameraAdapterError(f"camera profile requires the {slot_name} slot")
    node_id = selector.get("id")
    if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id < 0:
        raise CameraAdapterError(f"camera profile {slot_name} node id is invalid")
    node = graph.get(str(node_id))
    if not isinstance(node, dict) or node.get("class_type") != selector.get("type"):
        raise CameraAdapterError(f"camera {slot_name} node does not match the profile")
    if not isinstance(node.get("inputs"), dict):
        raise CameraAdapterError(f"camera {slot_name} node inputs are invalid")
    return node_id, node


def _require_exact_allowlist(profile: dict, field: str, expected: frozenset[str]) -> None:
    values = profile.get(field)
    if not isinstance(values, list) or len(values) != len(expected) or set(values) != expected:
        raise CameraAdapterError(f"camera profile {field} is incomplete")


def _masked_camera_graph(graph: dict, angle_id: int, extra_id: int) -> dict:
    masked = copy.deepcopy(graph)
    for node_id, fields in ((angle_id, _CAMERA_ANGLE_FIELDS), (extra_id, _CAMERA_EXTRA_FIELDS)):
        for field in fields:
            masked[str(node_id)]["inputs"][field] = _REMOVED
    return masked


def _finite_number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise CameraAdapterError(f"camera {label} must be a finite number")
    return float(value)


def patch_camera_controls(
    graph: dict,
    *,
    camera: dict,
    camera_extra: dict,
    profile: dict,
    workflow_fingerprint: str,
) -> dict:
    """Patch only the complete profiled CameraAngle and CameraExtra contract."""
    if not isinstance(graph, dict) or not isinstance(profile, dict):
        raise CameraAdapterError("camera graph and profile must be objects")
    if (
        workflow_fingerprint != profile.get("workflow_fingerprint")
        or not isinstance(workflow_fingerprint, str)
        or not re.fullmatch(r"[0-9a-f]{64}", workflow_fingerprint)
    ):
        raise CameraAdapterError("camera workflow fingerprint does not match the profile")
    if workflow_fingerprint != _PINNED_CAMERA_WORKFLOW_FINGERPRINT:
        raise CameraAdapterError("camera workflow fingerprint is not the pinned contract")
    slots = profile.get("slots")
    if not isinstance(slots, dict) or any(
        slots.get(name) != selector
        for name, selector in _CAMERA_CONTROL_SELECTORS.items()
    ):
        raise CameraAdapterError("camera profile must use fixed slots 583 and 585")
    if profile.get("expected_outputs") != ["image/png"]:
        raise CameraAdapterError("camera profile output contract is invalid")
    topology = profile.get("output_topology")
    if not isinstance(topology, list) or not topology:
        raise CameraAdapterError("camera profile output topology is required")
    for output in topology:
        if (
            not isinstance(output, dict)
            or set(output) != {"id", "type"}
            or not isinstance(output["id"], int)
            or isinstance(output["id"], bool)
            or not isinstance(output["type"], str)
            or graph.get(str(output["id"]), {}).get("class_type") != output["type"]
        ):
            raise CameraAdapterError("camera graph output topology does not match the profile")
    if not isinstance(camera, dict) or set(camera) != {"direction", "elevation", "distance", "roll"}:
        raise CameraAdapterError("camera controls require direction, elevation, distance and roll")
    if not isinstance(camera_extra, dict) or set(camera_extra) != _CAMERA_EXTRA_FIELDS:
        raise CameraAdapterError("camera_extra must provide the complete allowlisted field set")
    _require_exact_allowlist(profile, "camera_angle_allowlist", _CAMERA_ANGLE_FIELDS)
    _require_exact_allowlist(profile, "camera_extra_allowlist", _CAMERA_EXTRA_FIELDS)
    angle_id, angle_node = _profiled_node(graph, profile, "camera_angle")
    extra_id, extra_node = _profiled_node(graph, profile, "camera_extra")
    if missing := sorted(_CAMERA_ANGLE_FIELDS.difference(angle_node["inputs"])):
        raise CameraAdapterError("camera angle node is missing: " + ", ".join(missing))
    if missing := sorted(_CAMERA_EXTRA_FIELDS.difference(extra_node["inputs"])):
        raise CameraAdapterError("CameraExtra node is missing: " + ", ".join(missing))
    direction, elevation, distance = camera["direction"], camera["elevation"], camera["distance"]
    if direction not in _CAMERA_DIRECTION_POS_X:
        raise CameraAdapterError(f"camera direction is unsupported: {direction!r}")
    if elevation not in _CAMERA_ELEVATION_POS_Y:
        raise CameraAdapterError(f"camera elevation is unsupported: {elevation!r}")
    if distance not in _CAMERA_DISTANCE_POS_Z:
        raise CameraAdapterError(f"camera distance is unsupported: {distance!r}")
    for field in ("lens_enabled", "dof_enabled", "movement_enabled", "composition_enabled", "style_enabled"):
        if not isinstance(camera_extra[field], bool):
            raise CameraAdapterError(f"camera_extra {field} must be a boolean")
    for field in ("extreme_type", "lens_value", "dof_value", "movement_value", "composition_value", "style_value"):
        if not isinstance(camera_extra[field], str):
            raise CameraAdapterError(f"camera_extra {field} must be a string")
    for enabled, value in (("lens_enabled", "lens_value"), ("dof_enabled", "dof_value"), ("movement_enabled", "movement_value"), ("composition_enabled", "composition_value"), ("style_enabled", "style_value")):
        if camera_extra[enabled] and not camera_extra[value].strip():
            raise CameraAdapterError(f"camera_extra {value} is required when enabled")
    for field in ("extreme_weight", "dof_weight"):
        if _finite_number(camera_extra[field], field) < 0:
            raise CameraAdapterError(f"camera_extra {field} must be non-negative")
    patched = copy.deepcopy(graph)
    patched[str(angle_id)]["inputs"].update({
        "pos_x": _CAMERA_DIRECTION_POS_X[direction],
        "pos_y": _CAMERA_ELEVATION_POS_Y[elevation],
        "pos_z": _CAMERA_DISTANCE_POS_Z[distance],
        "roll": _finite_number(camera["roll"], "roll"),
    })
    for field in _CAMERA_EXTRA_FIELDS:
        patched[str(extra_id)]["inputs"][field] = copy.deepcopy(camera_extra[field])
    if canonical_json(_masked_camera_graph(graph, angle_id, extra_id)) != canonical_json(_masked_camera_graph(patched, angle_id, extra_id)):
        raise CameraAdapterError("camera controls changed data outside the allowlist")
    return patched


def _board_term_present(prompt: str, term: str) -> bool:
    return re.search(
        rf"(?<![A-Za-z_]){re.escape(term)}(?![A-Za-z_])",
        prompt,
        re.IGNORECASE,
    ) is not None


def patch_asset_board_prompt(graph: dict, positive: str, negative: str, profile: dict) -> dict:
    """Patch prompt slots while enforcing one board role and no optional branches."""
    if not isinstance(profile, dict) or profile.get("schema_version") != "1.0":
        raise CameraAdapterError("asset board requires a versioned profile")
    role = profile.get("board_role")
    if role not in _BOARD_ROLES or profile.get("profile_id") != f"camera-anima-asset-board-{role}-v1":
        raise CameraAdapterError("asset board profile role is invalid")
    fingerprint = profile.get("workflow_fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise CameraAdapterError(f"{role} board workflow fingerprint is invalid")
    if profile.get("enabled_groups") != [] or profile.get("enabled_optional_branches") != []:
        raise CameraAdapterError(f"{role} board must keep groups and optional branches disabled")
    if profile.get("allowed_mutations") != _BOARD_MUTATIONS or profile.get("expected_outputs") != ["image/png"]:
        raise CameraAdapterError(f"{role} board profile contract is invalid")
    if not isinstance(positive, str) or not positive.strip() or not isinstance(negative, str):
        raise CameraAdapterError(f"{role} board prompts are invalid")
    forbidden, constraints = profile.get("forbidden_positive_terms"), profile.get("negative_constraints")
    if not isinstance(forbidden, list) or not forbidden or not isinstance(constraints, list) or not constraints:
        raise CameraAdapterError(f"{role} board role constraints are incomplete")
    if not all(isinstance(item, str) and item.strip() for item in (*forbidden, *constraints)):
        raise CameraAdapterError(f"{role} board role constraints are incomplete")
    if contamination := next((term for term in forbidden if _board_term_present(positive, term)), None):
        raise CameraAdapterError(f"{role} board prompt violates role isolation: {contamination}")
    parts = [part.strip() for part in negative.split(",") if part.strip()]
    present = {part.casefold() for part in parts}
    parts.extend(term for term in constraints if term.casefold() not in present)
    slots = profile.get("slots")
    selectors = {
        "positive_prompt": {"id": 24, "type": _NODE_CLASS, "title": "POSITIVE"},
        "negative_prompt": {"id": 25, "type": _NODE_CLASS, "title": "NEGATIVE"},
    }
    if not isinstance(slots, dict) or any(slots.get(name) != value for name, value in selectors.items()):
        raise CameraAdapterError(f"{role} board prompt slots are invalid")
    try:
        return patch_character_base(graph, {"prompt": positive.strip(), "negative_prompt": ", ".join(parts)}, {name: value["id"] for name, value in selectors.items()})
    except ExecutionError as exc:
        raise CameraAdapterError(f"{role} board camera graph is invalid: {exc}") from exc


def patch_character_base(graph: dict, prompt_build: dict, slots: dict[str, int]) -> dict:
    """Deep-copy and patch exactly four prompt inputs in a camera API graph."""
    if not isinstance(graph, dict):
        raise ExecutionError("API graph must be an object")
    if not isinstance(prompt_build, dict):
        raise ExecutionError("PromptBuild must be an object")
    if not isinstance(slots, dict):
        raise ExecutionError("resolved slots must be an object")
    missing = sorted(_SLOTS.difference(slots))
    if missing:
        raise ExecutionError("resolved slots are missing: " + ", ".join(missing))
    unexpected = sorted(set(slots).difference(_SLOTS))
    if unexpected:
        raise ExecutionError("resolved slots contain unexpected entries: " + ", ".join(unexpected))

    prompt = prompt_build.get("prompt")
    negative_prompt = prompt_build.get("negative_prompt")
    if not isinstance(prompt, str) or not prompt:
        raise ExecutionError("PromptBuild prompt must be a non-empty string")
    if not isinstance(negative_prompt, str) or not negative_prompt:
        raise ExecutionError("PromptBuild negative_prompt must be a non-empty string")

    _node_for_slot(graph, "positive_prompt", slots["positive_prompt"])
    _node_for_slot(graph, "negative_prompt", slots["negative_prompt"])
    if slots != {"positive_prompt": 24, "negative_prompt": 25}:
        raise ExecutionError("character-base requires fixed positive/negative prompt slots")
    patched = copy.deepcopy(graph)
    positive = _node_for_slot(patched, "positive_prompt", slots["positive_prompt"])
    negative = _node_for_slot(patched, "negative_prompt", slots["negative_prompt"])
    for input_name in _INPUTS:
        positive["inputs"][input_name] = prompt
        negative["inputs"][input_name] = negative_prompt

    try:
        source_identity = canonical_json(_without_allowlisted_values(graph, slots))
        patched_identity = canonical_json(_without_allowlisted_values(patched, slots))
    except (KeyError, TypeError, ValueError) as exc:
        raise ExecutionError(f"API graph must be canonical JSON: {exc}") from exc
    if source_identity != patched_identity:
        raise ExecutionError("camera patch changed data outside the allowlist")
    return patched


def _img2img_config(profile: object) -> dict:
    if not isinstance(profile, dict) or not isinstance(profile.get("img2img"), dict):
        raise CameraAdapterError("camera profile requires an img2img section")
    config = profile["img2img"]
    required = {"group_id", "node_ids", "load_image_node_id"}
    if not required.issubset(config):
        raise CameraAdapterError("img2img profile must identify the complete G1 group")
    group_id = config["group_id"]
    node_ids = config["node_ids"]
    load_id = config["load_image_node_id"]
    if not isinstance(group_id, int) or isinstance(group_id, bool) or group_id < 0:
        raise CameraAdapterError("img2img group_id must be a non-negative integer")
    if (
        not isinstance(node_ids, list)
        or len(node_ids) != 4
        or len(set(node_ids)) != 4
        or any(not isinstance(node_id, int) or isinstance(node_id, bool) or node_id < 0 for node_id in node_ids)
    ):
        raise CameraAdapterError("img2img profile must identify the complete G1 group")
    if load_id not in node_ids:
        raise CameraAdapterError("img2img load_image_node_id must belong to the complete G1 group")
    return config


def _path_config(profile: object) -> dict:
    if not isinstance(profile, dict) or not isinstance(profile.get("img2img"), dict):
        raise CameraAdapterError("camera profile requires an img2img section")
    return profile["img2img"]


def _safe_image_name(image_name: object) -> str:
    if not isinstance(image_name, str) or not image_name or image_name != image_name.strip():
        raise CameraAdapterError("image_name must be a non-empty safe Comfy input reference")
    if "\\" in image_name or ":" in image_name:
        raise CameraAdapterError("image_name must be a relative Comfy input reference")
    path = PurePosixPath(image_name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise CameraAdapterError("image_name must be a relative Comfy input reference")
    return image_name


def _group_record(workflow: dict, group_id: int) -> dict:
    groups = workflow.get("groups")
    if not isinstance(groups, list):
        raise CameraAdapterError("camera UI workflow must expose groups for G1 activation")
    matches = [group for group in groups if isinstance(group, dict) and group.get("id") == group_id]
    if len(matches) != 1:
        raise CameraAdapterError("img2img G1 group is missing or ambiguous")
    return matches[0]


def _node_group_id(node: dict, group: dict) -> bool:
    group_id = group.get("id")
    for key in ("group_id", "group"):
        if key in node:
            value = node[key]
            if isinstance(value, dict):
                value = value.get("id")
            return value == group_id
    bounding = group.get("bounding")
    position = node.get("pos")
    if isinstance(bounding, list) and len(bounding) >= 4 and isinstance(position, list) and len(position) >= 2:
        try:
            x, y, width, height = (float(value) for value in bounding[:4])
            node_x, node_y = float(position[0]), float(position[1])
        except (TypeError, ValueError):
            return False
        return x <= node_x <= x + width and y <= node_y <= y + height
    return False


def _ui_node(workflow: dict, node_id: int) -> dict:
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        raise CameraAdapterError("camera UI workflow requires a nodes list")
    matches = [node for node in nodes if isinstance(node, dict) and node.get("id") == node_id]
    if len(matches) != 1:
        raise CameraAdapterError(f"G1 node {node_id} is missing or ambiguous")
    return matches[0]


def _without_g1_values(workflow: dict, node_ids: list[int], load_image_node_id: int) -> dict:
    normalized = copy.deepcopy(workflow)
    for node_id in node_ids:
        node = _ui_node(normalized, node_id)
        node.pop("mode", None)
        if node_id == load_image_node_id:
            values = node.get("widgets_values")
            if not isinstance(values, list) or not values:
                raise CameraAdapterError("G1 LoadImage node requires widgets_values[0]")
            values[0] = "__PROMPT_FORGE_G1_IMAGE__"
    return normalized


def activate_g1(workflow: dict, image_name: str, profile: dict) -> dict:
    """Atomically enable all four nodes in the verified camera G1 group."""
    if not isinstance(workflow, dict):
        raise CameraAdapterError("camera UI workflow must be an object")
    image_name = _safe_image_name(image_name)
    config = _img2img_config(profile)
    node_ids = list(config["node_ids"])
    load_image_node_id = config["load_image_node_id"]
    group = _group_record(workflow, config["group_id"])

    all_nodes = workflow.get("nodes")
    group_members = [
        node for node in all_nodes if isinstance(node, dict) and _node_group_id(node, group)
    ]
    member_ids = {node.get("id") for node in group_members}
    if member_ids != set(node_ids):
        raise CameraAdapterError("img2img profile must identify the complete G1 group")

    source_nodes = [_ui_node(workflow, node_id) for node_id in node_ids]
    modes = [node.get("mode") for node in source_nodes]
    if any(not isinstance(mode, int) or isinstance(mode, bool) for mode in modes) or len(set(modes)) != 1:
        raise CameraAdapterError("all complete G1 nodes must share one initial mode")
    load_values = source_nodes[node_ids.index(load_image_node_id)].get("widgets_values")
    if not isinstance(load_values, list) or not load_values:
        raise CameraAdapterError("G1 LoadImage node requires widgets_values[0]")

    patched = copy.deepcopy(workflow)
    for node_id in node_ids:
        node = _ui_node(patched, node_id)
        node["mode"] = 0
    _ui_node(patched, load_image_node_id)["widgets_values"][0] = image_name

    try:
        source_identity = canonical_json(_without_g1_values(workflow, node_ids, load_image_node_id))
        patched_identity = canonical_json(_without_g1_values(patched, node_ids, load_image_node_id))
    except (TypeError, ValueError) as exc:
        raise CameraAdapterError(f"camera UI workflow must be canonical JSON: {exc}") from exc
    if source_identity != patched_identity:
        raise CameraAdapterError("G1 activation changed data outside the allowlist")
    return patched


def _linked_node_id(value: object) -> int | None:
    if not isinstance(value, (list, tuple)) or len(value) < 1:
        return None
    node_id = value[0]
    if isinstance(node_id, bool):
        return None
    if isinstance(node_id, int):
        return node_id if node_id >= 0 else None
    if isinstance(node_id, str) and node_id.isdigit():
        return int(node_id)
    return None


def _api_node(graph: dict, node_id: int) -> dict:
    node = graph.get(str(node_id))
    if not isinstance(node, dict):
        raise CameraAdapterError(f"img2img path references missing API node {node_id}")
    if not isinstance(node.get("inputs"), dict):
        raise CameraAdapterError(f"img2img API node {node_id} requires inputs")
    return node


def verify_img2img_path(graph: dict, profile: dict) -> dict:
    """Prove that the sampler latent input is fed by the profiled VAEEncode node."""
    if not isinstance(graph, dict):
        raise CameraAdapterError("img2img API graph must be an object")
    config = _path_config(profile)
    sampler_id = config.get("sampler_node_id")
    vae_id = config.get("vae_encode_node_id")
    if not isinstance(sampler_id, int) or not isinstance(vae_id, int):
        raise CameraAdapterError("img2img profile requires sampler_node_id and vae_encode_node_id")
    sampler = _api_node(graph, sampler_id)
    if sampler.get("class_type") not in {"KSampler", "KSamplerAdvanced", "SamplerCustom", "SamplerCustomAdvanced"}:
        raise CameraAdapterError("img2img sampler node has an unexpected class_type")
    if vae_id not in graph and str(vae_id) not in graph:
        raise CameraAdapterError("img2img path references a missing VAEEncode node")
    vae = _api_node(graph, vae_id)
    if vae.get("class_type") != "VAEEncode":
        raise CameraAdapterError("img2img path target must be a VAEEncode node")
    first = _linked_node_id(sampler["inputs"].get("latent_image"))
    if first is None:
        raise CameraAdapterError("img2img sampler latent_image must be a link")

    cycle_seen = False

    def _search(current: int, path: list[int], active: set[int], target_id: int) -> list[int] | None:
        nonlocal cycle_seen
        if current in active:
            cycle_seen = True
            return None
        node = _api_node(graph, current)
        next_path = path + [current]
        if current == target_id:
            return next_path
        next_active = active | {current}
        links = [
            linked
            for value in node["inputs"].values()
            if (linked := _linked_node_id(value)) is not None
        ]
        for linked in links:
            result = _search(linked, next_path, next_active, target_id)
            if result is not None:
                return result
        return None

    path = _search(first, [sampler_id], {sampler_id}, vae_id)
    if path is None:
        if cycle_seen:
            raise CameraAdapterError("img2img path contains a cycle")
        raise CameraAdapterError("img2img sampler latent path does not reach VAEEncode")
    result = {
        "sampler_node_id": sampler_id,
        "vae_encode_node_id": vae_id,
        "traversed_node_ids": path,
    }
    expected_path = config.get("expected_path_node_ids")
    if expected_path is not None and path != expected_path:
        raise CameraAdapterError("img2img sampler path does not match the profiled path")

    load_id = config.get("load_image_node_id")
    if load_id is not None:
        if not isinstance(load_id, int) or isinstance(load_id, bool):
            raise CameraAdapterError("img2img load_image_node_id is invalid")
        load_node = _api_node(graph, load_id)
        if load_node.get("class_type") != "LoadImage":
            raise CameraAdapterError("img2img load image node has an unexpected class_type")
        image_links = [
            linked
            for value in vae["inputs"].values()
            if (linked := _linked_node_id(value)) is not None
        ]
        image_path = None
        image_cycle = False
        for linked in image_links:
            cycle_seen = False
            candidate = _search(linked, [vae_id], {vae_id}, load_id)
            if candidate is not None:
                image_path = candidate
                break
            image_cycle = image_cycle or cycle_seen
        if image_path is None:
            if image_cycle:
                raise CameraAdapterError("img2img image path contains a cycle")
            raise CameraAdapterError("img2img VAE path does not reach LoadImage")
        result["image_path_node_ids"] = image_path
    return result


def patch_img2img_graph(
    graph: dict,
    prompt_build: dict,
    image_name: str,
    profile: dict,
    slots: dict[str, int] | None = None,
    *,
    camera: dict | None = None,
) -> dict:
    """Patch the approved camera img2img graph without changing its topology.

    Prompt inputs use the same fixed camera slots as the character-base run.  The
    only additional mutation is the profiled G1 ``LoadImage.image`` input; the
    path proof is recomputed after patching so a stale or disconnected conversion
    cannot be submitted.
    """
    if not isinstance(graph, dict):
        raise CameraAdapterError("img2img API graph must be an object")
    if slots is None:
        slots = {"positive_prompt": 24, "negative_prompt": 25}
    if slots != {"positive_prompt": 24, "negative_prompt": 25}:
        raise CameraAdapterError("img2img requires fixed positive/negative prompt slots")
    safe_image = _safe_image_name(image_name)
    config = _path_config(profile)
    load_id = config.get("load_image_node_id")
    if not isinstance(load_id, int) or isinstance(load_id, bool):
        raise CameraAdapterError("img2img profile requires load_image_node_id")
    source = copy.deepcopy(graph)
    patched = patch_character_base(source, prompt_build, slots)
    patched, camera_node_id = _patch_camera_angle(patched, camera, profile)
    load_node = _api_node(patched, load_id)
    if load_node.get("class_type") != "LoadImage":
        raise CameraAdapterError("img2img load image node has an unexpected class_type")
    image_value = load_node["inputs"].get("image")
    if not isinstance(image_value, str):
        raise CameraAdapterError("img2img LoadImage.image must be a string")
    load_node["inputs"]["image"] = safe_image
    verify_img2img_path(patched, profile)

    try:
        source_identity_graph = _without_allowlisted_values(source, slots, camera_node_id)
        patched_identity_graph = _without_allowlisted_values(patched, slots, camera_node_id)
        _api_node(source_identity_graph, load_id)["inputs"]["image"] = _REMOVED
        _api_node(patched_identity_graph, load_id)["inputs"]["image"] = _REMOVED
        source_identity = canonical_json(source_identity_graph)
        patched_identity = canonical_json(patched_identity_graph)
    except (KeyError, TypeError, ValueError) as exc:
        raise CameraAdapterError(f"img2img API graph must be canonical JSON: {exc}") from exc
    if source_identity != patched_identity:
        raise CameraAdapterError("img2img patch changed data outside the allowlist")
    return patched

