"""Stage-wide configuration surfaces for the fixed workflow assets.

This is deliberately separate from the legacy execution adapters.  A surface
is a product contract: it names semantic slots and their exact graph inputs;
it never serializes the source graph as configuration.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from .contracts import content_hash
from .workflow_assets import asset_descriptor, asset_for_stage, load_fixed_workflow
from .workflow_profile import structure_fingerprint
from .config_surface import validate_lora_plan, validate_stage_config
from .adapters.lora_unit import patch_group_toggles, patch_lora_unit


class StageSurfaceError(ValueError):
    """Raised when a stage surface or its local patch is invalid."""


_STAGES = frozenset({"character-base", "multiview", "shot-image", "video"})
_VALUE_TYPES = frozenset({"text", "image", "boolean", "integer", "number", "json"})
_FORBIDDEN = ["seed", "sampler", "sampler_name", "scheduler", "steps", "cfg"]


def _binding(node_id: int, input_name: str, value_type: str, class_type: str | None = None) -> dict:
    defaults = {
        "text": ("", "any string", "isinstance(value, str)"),
        "image": (None, "image filename", "isinstance(value, str) and bool(value.strip())"),
        "boolean": (False, [False, True], "isinstance(value, bool)"),
        "integer": (24, {"min": 1}, "isinstance(value, int) and not isinstance(value, bool)"),
        "number": (0.0, {"kind": "number"}, "isinstance(value, (int, float)) and not isinstance(value, bool)"),
        "json": ({}, "JSON object", "isinstance(value, (dict, list))"),
    }
    default, allowed, validation = defaults[value_type]
    result = {
        "node_id": node_id,
        "input": input_name,
        "type": value_type,
        "default": copy.deepcopy(default),
        "allowed_values": copy.deepcopy(allowed),
        "validation": validation,
    }
    if class_type is not None:
        result["class_type"] = class_type
    return result


_SURFACES = {
    "character-base": {
        "schema_version": "1.0", "stage": "character-base", "workflow_asset": "camera-anima.json",
        "slots": {
            "positive_prompt": [_binding(24, "wildcard_text", "text", "ImpactWildcardProcessor"), _binding(24, "populated_text", "text", "ImpactWildcardProcessor")],
            "negative_prompt": [_binding(25, "wildcard_text", "text", "ImpactWildcardProcessor"), _binding(25, "populated_text", "text", "ImpactWildcardProcessor")],
            "camera_angle": [_binding(583, "pos_x", "number", "CameraAngleNode"), _binding(583, "pos_y", "number", "CameraAngleNode"), _binding(583, "pos_z", "number", "CameraAngleNode"), _binding(583, "roll", "number", "CameraAngleNode")],
            "camera_extra": [_binding(585, "extreme_type", "text", "CameraExtraConfigNode"), _binding(585, "extreme_weight", "number", "CameraExtraConfigNode"), _binding(585, "lens_enabled", "boolean", "CameraExtraConfigNode"), _binding(585, "lens_value", "text", "CameraExtraConfigNode"), _binding(585, "dof_enabled", "boolean", "CameraExtraConfigNode"), _binding(585, "dof_value", "text", "CameraExtraConfigNode"), _binding(585, "dof_weight", "number", "CameraExtraConfigNode"), _binding(585, "movement_enabled", "boolean", "CameraExtraConfigNode"), _binding(585, "movement_value", "text", "CameraExtraConfigNode"), _binding(585, "composition_enabled", "boolean", "CameraExtraConfigNode"), _binding(585, "composition_value", "text", "CameraExtraConfigNode"), _binding(585, "style_enabled", "boolean", "CameraExtraConfigNode"), _binding(585, "style_value", "text", "CameraExtraConfigNode")],
            "fast_groups": [_binding(23, "mode", "boolean")],
            "fast_groups_post_processing": [_binding(90, "mode", "boolean")],
            "lora_unit": [_binding(26, "text", "json"), _binding(66, "trigger_words", "json")],
        },
    },
    "shot-image": {
        "schema_version": "1.0", "stage": "shot-image", "workflow_asset": "camera-anima.json",
        "slots": {
            "positive_prompt": [_binding(24, "wildcard_text", "text", "ImpactWildcardProcessor"), _binding(24, "populated_text", "text", "ImpactWildcardProcessor")],
            "negative_prompt": [_binding(25, "wildcard_text", "text", "ImpactWildcardProcessor"), _binding(25, "populated_text", "text", "ImpactWildcardProcessor")],
            "reference_image": [_binding(21, "image", "image", "LoadImage")],
            "camera_angle": [_binding(583, "pos_x", "number", "CameraAngleNode"), _binding(583, "pos_y", "number", "CameraAngleNode"), _binding(583, "pos_z", "number", "CameraAngleNode"), _binding(583, "roll", "number", "CameraAngleNode")],
            "camera_extra": [_binding(585, "extreme_type", "text", "CameraExtraConfigNode"), _binding(585, "extreme_weight", "number", "CameraExtraConfigNode"), _binding(585, "lens_enabled", "boolean", "CameraExtraConfigNode"), _binding(585, "lens_value", "text", "CameraExtraConfigNode"), _binding(585, "dof_enabled", "boolean", "CameraExtraConfigNode"), _binding(585, "dof_value", "text", "CameraExtraConfigNode"), _binding(585, "dof_weight", "number", "CameraExtraConfigNode"), _binding(585, "movement_enabled", "boolean", "CameraExtraConfigNode"), _binding(585, "movement_value", "text", "CameraExtraConfigNode"), _binding(585, "composition_enabled", "boolean", "CameraExtraConfigNode"), _binding(585, "composition_value", "text", "CameraExtraConfigNode"), _binding(585, "style_enabled", "boolean", "CameraExtraConfigNode"), _binding(585, "style_value", "text", "CameraExtraConfigNode")],
            "fast_groups": [_binding(23, "mode", "boolean")],
            "fast_groups_post_processing": [_binding(90, "mode", "boolean")],
            "lora_unit": [_binding(26, "text", "json"), _binding(66, "trigger_words", "json")],
        },
    },
    "multiview": {
        "schema_version": "1.0", "stage": "multiview", "workflow_asset": "flux2-klein-multiview-flat-v2.json",
        "slots": {
            "base_image": [_binding(111, "image", "image", "LoadImage"), _binding(667, "image", "image", "LoadImage")],
            "view_switches": [_binding(node_id, "boolean", "boolean") for node_id in (727, 730, 731, 734, 735, 738, 741, 742, 743, 746, 747, 749, 750, 756, 759, 769, 772)],
            "view_prompts": [_binding(node_id, "text", "text") for node_id in (218, 219, 220, 221, 361, 365, 374)],
            "lora_unit": [_binding(359, "lora_name", "json", "LoraLoaderModelOnly"), _binding(359, "strength_model", "number", "LoraLoaderModelOnly"), _binding(764, "lora_name", "json", "LoraLoaderModelOnly"), _binding(764, "strength_model", "number", "LoraLoaderModelOnly")],
            "trigger_words": [_binding(node_id, "text", "text", "CR Text") for node_id in (218, 219, 220, 221, 361, 365, 374)],
        },
    },    "video": {
        "schema_version": "1.0", "stage": "video", "workflow_asset": "ltx-yusu-director.json",
        "slots": {
            "reference_image": [_binding(174, "timeline_data", "json", "YusuLTXDirector")],
            "positive_prompt": [_binding(174, "local_prompts", "text", "YusuLTXDirector")],
            "negative_prompt": [_binding(195, "text", "text", "CLIPTextEncode")],
            "motion_timeline": [_binding(174, "timeline_data", "json", "YusuLTXDirector"), _binding(174, "segment_lengths", "text", "YusuLTXDirector")],
            "output_timing": [_binding(174, "start_second", "number", "YusuLTXDirector"), _binding(174, "end_second", "number", "YusuLTXDirector"), _binding(174, "duration_seconds", "number", "YusuLTXDirector"), _binding(174, "start_frame", "integer", "YusuLTXDirector"), _binding(174, "end_frame", "integer", "YusuLTXDirector"), _binding(174, "duration_frames", "integer", "YusuLTXDirector"), _binding(174, "frame_rate", "integer", "YusuLTXDirector")],
        },
    },
}


def surface_for(stage: str) -> dict:
    if stage not in _STAGES:
        raise StageSurfaceError(f"unsupported stage: {stage}")
    result = copy.deepcopy(_SURFACES[stage])
    result["forbidden_inputs"] = list(_FORBIDDEN)
    return result


def validate_surface(surface: object) -> dict:
    if not isinstance(surface, dict) or set(surface) != {"schema_version", "stage", "workflow_asset", "slots", "forbidden_inputs"}:
        raise StageSurfaceError("surface schema is incomplete")
    if surface["schema_version"] != "1.0" or surface["stage"] not in _STAGES:
        raise StageSurfaceError("surface identity is invalid")
    if not isinstance(surface["workflow_asset"], str) or not surface["workflow_asset"].endswith(".json"):
        raise StageSurfaceError("surface workflow_asset is invalid")
    if not isinstance(surface["forbidden_inputs"], list) or set(surface["forbidden_inputs"]) != set(_FORBIDDEN):
        raise StageSurfaceError("surface forbidden_inputs must include only the internal execution fields")
    slots = surface["slots"]
    if not isinstance(slots, dict) or not slots:
        raise StageSurfaceError("surface slots are required")
    for name, bindings in slots.items():
        if not isinstance(name, str) or not isinstance(bindings, list) or not bindings:
            raise StageSurfaceError(f"surface slot {name!r} is invalid")
        for item in bindings:
            if not isinstance(item, dict) or not {"node_id", "input", "type", "default", "allowed_values", "validation"}.issubset(item):
                raise StageSurfaceError(f"surface slot {name!r} has an invalid binding")
            if not isinstance(item["node_id"], int) or not isinstance(item["input"], str) or item["type"] not in _VALUE_TYPES or not isinstance(item["validation"], str) or not item["validation"]:
                raise StageSurfaceError(f"surface slot {name!r} has an invalid binding type")
    return copy.deepcopy(surface)


def _node(graph: dict, binding: dict, name: str) -> dict:
    node = graph.get(str(binding["node_id"]))
    if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
        raise StageSurfaceError(f"slot {name!r} references a missing node")
    if binding.get("class_type") and node.get("class_type") != binding["class_type"]:
        raise StageSurfaceError(f"slot {name!r} class_type drifted")
    if binding["input"] not in node["inputs"]:
        raise StageSurfaceError(f"slot {name!r} input {binding['input']!r} is missing")
    return node


def read_stage_config(graph: object, surface: object) -> dict:
    checked = validate_surface(surface)
    if not isinstance(graph, dict):
        raise StageSurfaceError("graph must be an object")
    result = {}
    for name, bindings in checked["slots"].items():
        result[name] = {
            str(item["node_id"])+"."+item["input"]: copy.deepcopy(_node(graph, item, name)["inputs"][item["input"]])
            for item in bindings
        }
    return result


def apply_stage_patch(graph: object, surface: object, patch: object) -> dict:
    checked = validate_surface(surface)
    if not isinstance(graph, dict) or not isinstance(patch, dict):
        raise StageSurfaceError("graph and patch must be objects")
    unknown = sorted(set(patch) - set(checked["slots"]))
    if unknown:
        raise StageSurfaceError("patch slot is not declared: " + ", ".join(unknown))
    result = copy.deepcopy(graph)
    for name, values in patch.items():
        bindings = checked["slots"][name]
        if not isinstance(values, dict):
            raise StageSurfaceError(f"patch slot {name!r} must be an object keyed by node input")
        allowed = {str(item["node_id"])+"."+item["input"]: item for item in bindings}
        unknown_values = sorted(set(values) - set(allowed))
        if unknown_values:
            raise StageSurfaceError(f"patch field for {name!r} is not declared")
        for key, value in values.items():
            item = allowed[key]
            if item["input"] in checked["forbidden_inputs"]:
                raise StageSurfaceError(f"patch field {key!r} is forbidden")
            node = _node(result, item, name)
            node["inputs"][item["input"]] = copy.deepcopy(value)
    return result


def _fixed_surface(stage: str) -> tuple[str, dict, dict]:
    surface = validate_surface(surface_for(stage))
    asset_name = asset_for_stage(stage)
    descriptor = asset_descriptor(asset_name)
    if surface["workflow_asset"] != asset_name:
        raise StageSurfaceError(f"stage {stage} is bound to the wrong fixed workflow asset")
    if descriptor["slot_map"].get(stage) != surface["slots"]:
        raise StageSurfaceError(f"stage {stage} slot map does not match its fixed asset")
    if descriptor["forbidden_inputs"] != surface["forbidden_inputs"]:
        raise StageSurfaceError(f"stage {stage} forbidden input policy does not match its fixed asset")
    load_fixed_workflow(asset_name)
    return asset_name, descriptor, surface


def read_fixed_stage_config(stage: str, graph: object) -> dict:
    """Read only declared slots after verifying the fixed asset contract."""
    asset_name, descriptor, surface = _fixed_surface(stage)
    return {
        "stage": stage,
        "workflow_asset": asset_name,
        "workflow_fingerprint": descriptor["workflow_fingerprint"],
        "config_surface_hash": content_hash(surface),
        "values": read_stage_config(graph, surface),
    }


def compile_fixed_stage_patch(stage: str, graph: object, patch: object) -> dict:
    """Compile an allowlisted local patch into an API graph with provenance."""
    asset_name, descriptor, surface = _fixed_surface(stage)
    compiled = apply_stage_patch(graph, surface, patch)
    return {
        "stage": stage,
        "workflow_asset": asset_name,
        "workflow_fingerprint": descriptor["workflow_fingerprint"],
        "config_surface_hash": content_hash(surface),
        "patch_hash": content_hash(patch),
        "api_graph": compiled,
    }



def _camera_ui_node(workflow: dict, node_id: int, class_type: str) -> dict:
    matches = [node for node in workflow.get("nodes", [])
               if isinstance(node, dict) and node.get("id") == node_id]
    if len(matches) != 1 or matches[0].get("type") != class_type:
        raise StageSurfaceError(f"camera UI node {node_id} does not match {class_type}")
    if not isinstance(matches[0].get("widgets_values"), list):
        raise StageSurfaceError(f"camera UI node {node_id} has no widgets")
    return matches[0]


def _load_camera_profile() -> dict:
    path = Path(__file__).with_name("profiles") / "camera-anima.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StageSurfaceError("camera profile is unreadable") from exc


def _camera_ui_contract(stage: str, workflow: object) -> tuple[dict, dict]:
    if stage not in {"character-base", "shot-image"}:
        raise StageSurfaceError("UI transport is only defined for camera stages")
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise StageSurfaceError("camera UI workflow must be an object with nodes")
    asset_name, descriptor, _ = _fixed_surface(stage)
    if asset_name != "camera-anima.json":
        raise StageSurfaceError("camera stages must use camera-anima.json")
    if structure_fingerprint(workflow) != descriptor["workflow_fingerprint"]:
        raise StageSurfaceError("camera UI workflow fingerprint does not match the fixed asset")
    return workflow, _load_camera_profile()


def _read_camera_group_state(workflow: dict, suffix: str) -> list[str]:
    groups = workflow.get("groups")
    nodes = workflow.get("nodes")
    if not isinstance(groups, list) or not isinstance(nodes, list):
        raise StageSurfaceError("camera workflow group state is invalid")
    enabled = []
    for group in groups:
        title = group.get("title") if isinstance(group, dict) else None
        bounds = group.get("bounding") if isinstance(group, dict) else None
        if not isinstance(title, str) or not title.endswith(suffix):
            continue
        if not isinstance(bounds, list) or len(bounds) != 4:
            raise StageSurfaceError(f"camera group {title!r} has invalid bounds")
        x, y, width, height = bounds
        members = []
        for node in nodes:
            if not isinstance(node, dict) or not isinstance(node.get("pos"), list) or len(node["pos"]) < 2:
                continue
            px, py = node["pos"][:2]
            if x <= px <= x + width and y <= py <= y + height:
                members.append(node)
        if members and all(node.get("mode", 0) != 2 for node in members):
            enabled.append(title)
    return enabled

def read_fixed_ui_stage_config(stage: str, workflow: object) -> dict:
    """Read semantic camera controls from the fixed UI workflow only."""
    workflow, profile = _camera_ui_contract(stage, workflow)
    positive = _camera_ui_node(workflow, 24, "ImpactWildcardProcessor")["widgets_values"]
    negative = _camera_ui_node(workflow, 25, "ImpactWildcardProcessor")["widgets_values"]
    angle = _camera_ui_node(workflow, 583, "CameraAngleNode")["widgets_values"]
    extra = _camera_ui_node(workflow, 585, "CameraExtraConfigNode")["widgets_values"]
    lora_loader = _camera_ui_node(workflow, 26, "Lora Loader (LoraManager)")["widgets_values"]
    trigger_toggle = _camera_ui_node(workflow, 66, "TriggerWord Toggle (LoraManager)")["widgets_values"]
    result = {
        "stage": stage,
        "workflow_asset": "camera-anima.json",
        "workflow_fingerprint": profile["workflow_fingerprint"],
        "config_surface_hash": content_hash(surface_for(stage)),
        "values": {
            "positive_prompt": copy.deepcopy(positive[0]),
            "negative_prompt": copy.deepcopy(negative[0]),
            "camera_angle": {"pos_x": angle[0], "pos_y": angle[1], "pos_z": angle[2], "roll": angle[3]},
            "camera_extra": {
                "extreme_type": extra[0], "extreme_weight": extra[1], "lens_enabled": extra[2],
                "lens_value": extra[3], "dof_enabled": extra[4], "dof_value": extra[5],
                "dof_weight": extra[6], "movement_enabled": extra[7], "movement_value": extra[8],
                "composition_enabled": extra[9], "composition_value": extra[10],
                "style_enabled": extra[11], "style_value": extra[12],
            },
            "groups": {
                "enabled_g1": [
                    title for title in _read_camera_group_state(workflow, "\uff08G1\uff09")
                    if title not in set(profile["config_surface"]["pinned_groups"]["g1"])
                ],
                "enabled_g2": [
                    title for title in _read_camera_group_state(workflow, "\uff08G2\uff09")
                    if title not in set(profile["config_surface"]["pinned_groups"]["g2"])
                ],
            },
            "lora_unit": {
                "loader_stack": copy.deepcopy(lora_loader[1]),
                "loader_entries": copy.deepcopy(lora_loader[2]),
                "trigger_words": copy.deepcopy(trigger_toggle[3]),
            },
        },
    }
    if stage == "shot-image":
        result["values"]["reference_image"] = copy.deepcopy(
            _camera_ui_node(workflow, 21, "LoadImage")["widgets_values"][0]
        )
    return result


def compile_fixed_ui_stage_patch(stage: str, workflow: object, stage_config: object) -> dict:
    """Compile a validated semantic camera config into the fixed UI workflow."""
    source, profile = _camera_ui_contract(stage, workflow)
    config = validate_stage_config(stage_config)
    if config["stage"] != stage:
        raise StageSurfaceError("stage config does not match the requested stage")
    patched = copy.deepcopy(source)
    _camera_ui_node(patched, 24, "ImpactWildcardProcessor")["widgets_values"][0] = config["prompts"]["positive"]
    _camera_ui_node(patched, 24, "ImpactWildcardProcessor")["widgets_values"][1] = config["prompts"]["positive"]
    _camera_ui_node(patched, 25, "ImpactWildcardProcessor")["widgets_values"][0] = config["prompts"]["negative"]
    _camera_ui_node(patched, 25, "ImpactWildcardProcessor")["widgets_values"][1] = config["prompts"]["negative"]
    angle = _camera_ui_node(patched, 583, "CameraAngleNode")["widgets_values"]
    extra = _camera_ui_node(patched, 585, "CameraExtraConfigNode")["widgets_values"]
    camera = config["camera"]
    direction = {"front": 0, "back": 180, "left": -90, "right": 90}.get(camera["direction"])
    elevation = {"eye-level": 0, "high": 45, "high-angle": 45, "low": -45, "low-angle": -45}.get(camera["elevation"])
    distance = {"medium": 0, "full_body": 1}.get(camera["distance"])
    if direction is None or elevation is None or distance is None:
        raise StageSurfaceError("camera semantic value is not supported by the fixed UI contract")
    angle[:4] = [direction, elevation, distance, camera["roll"]]
    extra[:] = [config["camera_extra"][key] for key in (
        "extreme_type", "extreme_weight", "lens_enabled", "lens_value", "dof_enabled",
        "dof_value", "dof_weight", "movement_enabled", "movement_value", "composition_enabled",
        "composition_value", "style_enabled", "style_value")]
    if stage == "shot-image":
        _camera_ui_node(patched, 21, "LoadImage")["widgets_values"][0] = config["reference_image"]
    patched = patch_lora_unit(patched, config["lora_plan"], profile)
    patched = patch_group_toggles(patched, config["groups"], profile)
    return {
        "stage": stage,
        "workflow_asset": "camera-anima.json",
        "workflow_fingerprint": profile["workflow_fingerprint"],
        "config_surface_hash": content_hash(surface_for(stage)),
        "config_hash": config["config_hash"],
        "ui_workflow": patched,
    }






_MODEL_LORA_NODES = {
    "multiview": (359, 764),
    "video": (80, 114),
}

def _model_lora_filename(name: str) -> str:
    return name if name.endswith(".safetensors") else name + ".safetensors"

def _model_lora_patch(graph: dict, stage: str, lora_plan: object, prompt_node_ids: tuple[int, ...] = ()) -> dict:
    """Create one atomic model-only LoRA + trigger-word patch for a stage."""
    safe = validate_lora_plan(lora_plan)
    active = [item for item in safe["selections"] if item["active"]]
    nodes = _MODEL_LORA_NODES[stage]
    if len(active) > len(nodes):
        raise StageSurfaceError(f"{stage} supports at most {len(nodes)} active LoRAs")
    patch = {"lora_unit": {}}
    for node_id, selection in zip(nodes, active):
        key = str(node_id)
        node = graph.get(key)
        if not isinstance(node, dict) or node.get("class_type") != "LoraLoaderModelOnly":
            raise StageSurfaceError(f"{stage} LoRA node {node_id} is missing or has the wrong type")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or "lora_name" not in inputs or "strength_model" not in inputs:
            raise StageSurfaceError(f"{stage} LoRA node {node_id} is missing declared inputs")
        patch["lora_unit"][f"{key}.lora_name"] = _model_lora_filename(selection["name"])
        patch["lora_unit"][f"{key}.strength_model"] = selection["strength_model"]
    words = []
    for selection in active:
        for word in selection["trigger_words"]:
            if word not in words:
                words.append(word)
    if prompt_node_ids and words:
        suffix = ", " + ", ".join(words)
        for node_id in prompt_node_ids:
            key = str(node_id)
            node = graph.get(key)
            if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict) or not isinstance(node["inputs"].get("text"), str):
                raise StageSurfaceError(f"{stage} trigger-word prompt node {node_id} is invalid")
            patch.setdefault("trigger_words", {})[f"{key}.text"] = node["inputs"]["text"].rstrip() + suffix
    return patch

def compile_fixed_multiview_plan(graph: object, view_plan: object) -> dict:
    """Compile the declared multiview plan into a fixed API graph."""
    if not isinstance(view_plan, dict):
        raise StageSurfaceError("multiview view_plan must be an object")
    if "dimensions" in view_plan:
        raise StageSurfaceError("multiview dimensions are not a declared Config Surface slot")
    allowed = {"views", "switches", "prompts", "base_image", "orientation_evidence", "lora_plan"}
    unknown = sorted(set(view_plan) - allowed)
    if unknown:
        raise StageSurfaceError("multiview view_plan contains undeclared fields: " + ", ".join(unknown))
    patch = {}
    image = view_plan.get("base_image")
    if image is not None:
        if not isinstance(image, str) or not image.strip():
            raise StageSurfaceError("multiview base_image must be a non-empty filename")
        patch["base_image"] = {"111.image": image, "667.image": image}
    for slot_name, input_name in (("switches", "boolean"), ("prompts", "text")):
        values = view_plan.get(slot_name) or {}
        if not isinstance(values, dict):
            raise StageSurfaceError(f"multiview {slot_name} must be an object")
        patch["view_switches" if slot_name == "switches" else "view_prompts"] = {
            f"{node_id}.{input_name}": value for node_id, value in values.items()
        }
    if "lora_plan" in view_plan:
        lora_patch = _model_lora_patch(
            graph,
            "multiview",
            view_plan["lora_plan"],
            (218, 219, 220, 221, 361, 365, 374),
        )
        for slot_name, values in lora_patch.items():
            patch.setdefault(slot_name, {}).update(values)
    return compile_fixed_stage_patch("multiview", graph, patch)


def compile_fixed_video_plan(
    graph: object,
    image_ref: object,
    prompt: str,
    negative_prompt: str,
    frames: int,
    fps: int,
    profile: dict,
    *,
    timeline_segments: list[dict] | None = None,
    lora_plan: dict | None = None,
) -> dict:
    """Normalize Yusu timeline domain data, then compile only declared video slots."""
    from .adapters.yusu_timeline import patch_yusu_timeline

    normalized = patch_yusu_timeline(
        graph,
        image_ref,
        prompt,
        frames,
        fps,
        profile,
        timeline_segments=timeline_segments,
        negative_prompt=negative_prompt if negative_prompt.strip() else None,
    )
    director_id = int(profile["director_node_id"])
    negative_id = int(profile["negative_node_id"])
    director_inputs = normalized[str(director_id)]["inputs"]
    patch = {
        "reference_image": {"174.timeline_data": director_inputs["timeline_data"]},
        "positive_prompt": {"174.local_prompts": director_inputs["local_prompts"]},
        "negative_prompt": {f"{negative_id}.text": normalized[str(negative_id)]["inputs"]["text"]},
        "motion_timeline": {
            "174.timeline_data": director_inputs["timeline_data"],
            "174.segment_lengths": director_inputs["segment_lengths"],
        },
        "output_timing": {
            "174.start_second": director_inputs["start_second"],
            "174.end_second": director_inputs["end_second"],
            "174.duration_seconds": director_inputs["duration_seconds"],
            "174.start_frame": director_inputs["start_frame"],
            "174.end_frame": director_inputs["end_frame"],
            "174.duration_frames": director_inputs["duration_frames"],
            "174.frame_rate": director_inputs["frame_rate"],
        },
    }
    if lora_plan is not None:
        lora_patch = _model_lora_patch(normalized, "video", lora_plan)
        normalized = apply_stage_patch(normalized, surface_for("video"), lora_patch)
        for slot_name, values in lora_patch.items():
            patch.setdefault(slot_name, {}).update(values)
    compiled = compile_fixed_stage_patch("video", graph, patch)
    if compiled["api_graph"] != normalized:
        raise StageSurfaceError("video domain normalization changed an undeclared graph field")
    return compiled

def compile_fixed_camera_api_plan(
    stage: str,
    source_api_graph: dict,
    ui_workflow: dict,
    stage_config: dict,
    profile: dict,
    *,
    image_name: str | None = None,
    prompt_build: dict | None = None,
) -> dict:
    """Compile semantic camera config through the fixed UI asset, then transport it to API."""
    from .adapters.camera import normalize_camera_api_graph, patch_img2img_graph

    compiled_ui = compile_fixed_ui_stage_patch(stage, ui_workflow, stage_config)
    transport_source = copy.deepcopy(source_api_graph)
    try:
        ui_nodes = {node["id"]: node for node in compiled_ui["ui_workflow"]["nodes"] if isinstance(node, dict)}
        widgets = {node_id: ui_nodes[node_id]["widgets_values"] for node_id in (24, 25, 26, 66, 583, 585)}
        api_inputs = {node_id: transport_source[str(node_id)]["inputs"] for node_id in (24, 25, 26, 66, 583, 585)}
        for node_id in (24, 25):
            api_inputs[node_id]["wildcard_text"] = widgets[node_id][0]
            api_inputs[node_id]["populated_text"] = widgets[node_id][1]
        api_inputs[26]["text"] = widgets[26][1]
        api_inputs[26]["loras"] = {"__value__": copy.deepcopy(widgets[26][2])}
        api_inputs[66]["toggle_trigger_words"] = {"__value__": copy.deepcopy(widgets[66][3])}
        api_inputs[66]["orinalMessage"] = widgets[66][4]
        api_inputs[66]["trigger_words"] = ["26", 2]
        for field, index in (("pos_x", 0), ("pos_y", 1), ("pos_z", 2), ("roll", 3)):
            api_inputs[583][field] = widgets[583][index]
        for field, index in zip((
            "extreme_type", "extreme_weight", "lens_enabled", "lens_value", "dof_enabled",
            "dof_value", "dof_weight", "movement_enabled", "movement_value",
            "composition_enabled", "composition_value", "style_enabled", "style_value",
        ), range(13)):
            api_inputs[585][field] = widgets[585][index]
    except (KeyError, StopIteration, TypeError, IndexError) as exc:
        raise StageSurfaceError("camera API configuration transport surface is incomplete") from exc
    normalized = normalize_camera_api_graph(transport_source, compiled_ui["ui_workflow"], profile)
    values = validate_stage_config(stage_config)["prompts"]
    effective_prompt = {"prompt": values["positive"], "negative_prompt": values["negative"]}
    if isinstance(prompt_build, dict):
        effective_prompt.update(prompt_build)
        effective_prompt["prompt"] = values["positive"]
        effective_prompt["negative_prompt"] = values["negative"]
    if stage == "shot-image":
        if image_name is None:
            raise StageSurfaceError("shot-image camera compilation requires an image name")
        api_graph = patch_img2img_graph(
            normalized, effective_prompt, image_name, profile, camera=stage_config["camera"]
        )
    else:
        api_graph = normalized
    return {**compiled_ui, "api_graph": api_graph}

def compile_fixed_character_base_plan(graph: object, prompt_build: dict) -> dict:
    """Compile the four declared character-base prompt fields only."""
    if not isinstance(prompt_build, dict):
        raise StageSurfaceError("character-base prompt build must be an object")
    positive = prompt_build.get("prompt")
    negative = prompt_build.get("negative_prompt")
    if not isinstance(positive, str) or not positive.strip():
        raise StageSurfaceError("character-base positive prompt is required")
    if not isinstance(negative, str):
        raise StageSurfaceError("character-base negative prompt must be a string")
    return compile_fixed_stage_patch("character-base", graph, {
        "positive_prompt": {"24.wildcard_text": positive, "24.populated_text": positive},
        "negative_prompt": {"25.wildcard_text": negative, "25.populated_text": negative},
    })





