"""Strict Stage 1 patches for the verified camera API graph."""

from __future__ import annotations

import copy
from pathlib import PurePosixPath

from ..contracts import canonical_json
from ..execution import ExecutionError


_SLOTS = frozenset(("positive_prompt", "negative_prompt"))
_INPUTS = ("wildcard_text", "populated_text")
_NODE_CLASS = "ImpactWildcardProcessor"
_REMOVED = "__PROMPT_FORGE_ALLOWLISTED_VALUE__"


class CameraAdapterError(ValueError):
    """Raised when a camera UI/API graph cannot be patched safely."""


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


def _without_allowlisted_values(graph: dict, slots: dict[str, int]) -> dict:
    normalized = copy.deepcopy(graph)
    for slot_name in _SLOTS:
        node = normalized[str(slots[slot_name])]
        for input_name in _INPUTS:
            node["inputs"][input_name] = _REMOVED
    return normalized


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
    load_node = _api_node(patched, load_id)
    if load_node.get("class_type") != "LoadImage":
        raise CameraAdapterError("img2img load image node has an unexpected class_type")
    image_value = load_node["inputs"].get("image")
    if not isinstance(image_value, str):
        raise CameraAdapterError("img2img LoadImage.image must be a string")
    load_node["inputs"]["image"] = safe_image
    verify_img2img_path(patched, profile)

    try:
        source_identity_graph = _without_allowlisted_values(source, slots)
        patched_identity_graph = _without_allowlisted_values(patched, slots)
        _api_node(source_identity_graph, load_id)["inputs"]["image"] = _REMOVED
        _api_node(patched_identity_graph, load_id)["inputs"]["image"] = _REMOVED
        source_identity = canonical_json(source_identity_graph)
        patched_identity = canonical_json(patched_identity_graph)
    except (KeyError, TypeError, ValueError) as exc:
        raise CameraAdapterError(f"img2img API graph must be canonical JSON: {exc}") from exc
    if source_identity != patched_identity:
        raise CameraAdapterError("img2img patch changed data outside the allowlist")
    return patched
