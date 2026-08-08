"""Declarative API graph patching for camera workflows.

Single signature `patch_graph(*, stage, config, mcp_list_loras=None)` accepts
a `RunConfig` (defined in runtime.config_schema) and writes every tunable
into the fixed workflow.json. Anything not set on the config falls through
to workflow.json's static value.

Tunable surface (also enumerated by NODE_FIELD_MAP for the helper):
- prompts (24/25)                              — from config.draft via prompt-forge gate
- camera (583)                                 — from config.camera
- camera_extra (585)                           — from config.camera_extra
- lora (26/66)                                 — from config.lora
- sampling (50/51)                             — from config.sampling
- seed (65)                                    — from config.seed
- image_size (68/71)                           — from config.image_size
- controlnet_image (129)                       — from config.controlnet_image
                                                only if group "ControlNet LLLite（G1）" enabled
- groups (G1/G2 by title)                      — from config.groups
- reference_image (21)                         — from config.reference_image (i2i only)
"""

from __future__ import annotations

from typing import Any, Callable

from .camera_mapper import (
    CameraCoords,
    map_camera,
    validate_camera_extra,
    CAMERA_EXTRA_FIELDS,
)
from .config_schema import (
    DEFAULT_ENABLED_G1,
    DEFAULT_ENABLED_G2,
    GROUPS,
    I2I_NODES,
    MANDATORY_GROUPS_BY_STAGE,
    REFERENCE_IMAGE_NODE,
    CONTROLNET_IMAGE_NODE,
    RunConfig,
    SamplingConfig,
    ImageSizeConfig,
    GroupsConfig,
    STAGES,
    WORKFLOW_CONVENTIONS,
)
from .group_controller import apply_group_modes, MODE_ACTIVE
from .lora_resolver import build_lora_patch, DEFAULT_LORA_STACK_TEXT
from .workflow_loader import load_workflow, load_groups, list_group_titles


# Single source of truth — patcher and describe_config both read this.
NODE_FIELD_MAP: dict[str, tuple[str, str]] = {
    "sampling.steps_first":    ("50", "steps"),
    "sampling.cfg":            ("50", "cfg"),
    "sampling.sampler":        ("50", "sampler"),
    "sampling.scheduler":      ("50", "scheduler"),
    "sampling.denoise_first":  ("50", "denoise"),
    "sampling.steps_refine":   ("51", "steps"),
    "sampling.denoise_refine": ("51", "denoise"),
    "seed":                    ("65", "seed"),
    "image_size.width":        ("68", "value"),
    "image_size.height":       ("71", "value"),
    "controlnet_image":        ("129", "image"),
}


def _set_prompt(graph: dict, node_id: str, text: str) -> None:
    if node_id not in graph:
        raise KeyError(f"prompt node {node_id} missing from workflow")
    graph[node_id]["inputs"]["wildcard_text"] = text
    graph[node_id]["inputs"]["populated_text"] = text


def _set_camera(graph: dict, coords: CameraCoords) -> None:
    node = graph.get("583")
    if not node:
        raise KeyError("node 583 (CameraAngleNode) missing from workflow")
    node["inputs"]["pos_x"] = coords.pos_x
    node["inputs"]["pos_y"] = coords.pos_y
    node["inputs"]["pos_z"] = coords.pos_z
    node["inputs"]["roll"] = coords.roll


def _set_camera_partial(
    graph: dict,
    *,
    direction=None,
    elevation=None,
    distance=None,
    roll=None,
) -> None:
    """Write only the camera fields the caller provided.

    None means "keep workflow.json's static value for node 583".
    """
    node = graph.get("583")
    if not node:
        raise KeyError("node 583 (CameraAngleNode) missing from workflow")
    if direction is not None:
        node["inputs"]["pos_x"] = map_camera(direction=direction).pos_x
    if elevation is not None:
        node["inputs"]["pos_y"] = map_camera(elevation=elevation).pos_y
    if distance is not None:
        node["inputs"]["pos_z"] = map_camera(distance=distance).pos_z
    if roll is not None:
        node["inputs"]["roll"] = float(roll)


def _set_camera_extra(graph: dict, extra: dict) -> None:
    node = graph.get("585")
    if not node:
        raise KeyError("node 585 (CameraExtraConfigNode) missing from workflow")
    for field in CAMERA_EXTRA_FIELDS:
        if field in extra:
            node["inputs"][field] = extra[field]


def _set_lora(graph: dict, lora_patch: dict) -> None:
    if "26" in graph:
        graph["26"]["inputs"]["text"] = lora_patch["node_26"]["text"]
    if "66" in graph:
        for key, value in lora_patch["node_66"].items():
            graph["66"]["inputs"][key] = value


def _apply_sampling(graph: dict, s: SamplingConfig) -> None:
    if s.steps_first is not None:    graph["50"]["inputs"]["steps"]    = s.steps_first
    if s.cfg is not None:            graph["50"]["inputs"]["cfg"]      = s.cfg
    if s.sampler is not None:        graph["50"]["inputs"]["sampler"]  = s.sampler
    if s.scheduler is not None:      graph["50"]["inputs"]["scheduler"] = s.scheduler
    if s.denoise_first is not None:  graph["50"]["inputs"]["denoise"]  = s.denoise_first
    if s.steps_refine is not None:   graph["51"]["inputs"]["steps"]    = s.steps_refine
    if s.denoise_refine is not None: graph["51"]["inputs"]["denoise"]  = s.denoise_refine


def _apply_seed(graph: dict, seed: int) -> None:
    graph["65"]["inputs"]["seed"] = seed


def _apply_image_size(graph: dict, size: ImageSizeConfig) -> None:
    if size.width is not None:
        graph["68"]["inputs"]["value"] = size.width
    if size.height is not None:
        graph["71"]["inputs"]["value"] = size.height


def _apply_controlnet_image(graph: dict, image_name: str) -> None:
    graph["129"]["inputs"]["image"] = image_name


def _node_static_default(graph: dict, node_id: str, field: str) -> Any:
    """Read workflow.json static value for (node, input). Returns None if missing."""
    node = graph.get(node_id)
    if not node:
        return None
    return node.get("inputs", {}).get(field)


def _activate_img2img(graph: dict, image_name: str) -> None:
    """Rewire KSampler latent from EmptyLatentImage to VAEEncode for i2i.

    Reads node ids from I2I_NODES (single source). After this function:
    - I2I_NODES.LOAD_IMAGE[image] = image_name (uploaded filename)
    - I2I_NODES.VAE_ENCODE[pixels]  = [I2I_NODES.LOAD_IMAGE, 0]
    - I2I_NODES.KSAMPLER[latent_image] = [I2I_NODES.VAE_ENCODE, 0]
    - I2I_NODES.KSAMPLER[denoise]   = 0.6
    - All nodes in I2I_NODES.LOAD_IMAGE_CHAIN set mode = MODE_ACTIVE
    """
    n = I2I_NODES
    for nid in n.LOAD_IMAGE_CHAIN:
        if nid in graph:
            graph[nid]["mode"] = MODE_ACTIVE
    if n.LOAD_IMAGE in graph:
        graph[n.LOAD_IMAGE]["inputs"]["image"] = image_name
    if n.VAE_ENCODE in graph and n.LOAD_IMAGE in graph:
        graph[n.VAE_ENCODE]["inputs"]["pixels"] = [n.LOAD_IMAGE, 0]
    if n.KSAMPLER in graph and n.VAE_ENCODE in graph:
        graph[n.KSAMPLER]["inputs"]["latent_image"] = [n.VAE_ENCODE, 0]
    if n.KSAMPLER in graph:
        graph[n.KSAMPLER]["inputs"]["denoise"] = 0.6


def patch_graph(
    *,
    stage: str = STAGES.T2I,
    config: RunConfig,
    mcp_list_loras: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Build a fully patched, ready-to-submit API graph.

    Single signature: caller passes RunConfig; this function applies all
    non-prompt tunables to the loaded workflow. Prompt text (positive /
    negative) comes from `config.draft` — caller must run the prompt-forge
    gate BEFORE patch_graph and pass the validated draft.
    """
    graph = load_workflow(stage)
    groups_meta = load_groups(stage)

    # 1. Prompts (from prompt-forge-validated draft).
    _set_prompt(graph, "24", config.draft["positive"].strip())
    _set_prompt(graph, "25", config.draft["negative"].strip())

    # 2. Camera coords (583) + extra (585).
    if config.camera:
        _set_camera_partial(
            graph,
            direction=config.camera.direction,
            elevation=config.camera.elevation,
            distance=config.camera.distance,
            roll=config.camera.roll,
        )
    if config.camera_extra:
        _set_camera_extra(graph, validate_camera_extra(config.camera_extra))

    # 3. LoRA (26/66).
    if config.lora is not None:
        lora_patch = build_lora_patch(
            run_config_lora=config.lora,
            mcp_list_loras=mcp_list_loras,
        )
        _set_lora(graph, lora_patch)

    # 4. New tunables: sampling (50/51), seed (65), image size (68/71).
    if config.sampling:
        _apply_sampling(graph, config.sampling)
    if config.seed is not None:
        _apply_seed(graph, config.seed)
    if config.image_size:
        _apply_image_size(graph, config.image_size)

    # 5. Group merging: defaults + user + stage-mandatory.
    user_g1 = list((config.groups.g1 if config.groups else []) or [])
    user_g2 = list((config.groups.g2 if config.groups else []) or [])
    final_g1 = list(set(user_g1) | set(DEFAULT_ENABLED_G1))
    final_g2 = list(set(user_g2) | set(DEFAULT_ENABLED_G2))
    for mandatory in MANDATORY_GROUPS_BY_STAGE.get(stage, []):
        if mandatory not in final_g1:
            final_g1.append(mandatory)

    # 6. Cross-validate controlnet_image <-> ControlNet LLLite group.
    cn_node_for_stage = CONTROLNET_IMAGE_NODE.get(stage)
    if config.controlnet_image is not None and cn_node_for_stage is None:
        raise ValueError(f"controlnet_image not supported in stage={stage!r}")
    if config.controlnet_image is not None and GROUPS.CONTROLNET_LLLITE not in final_g1:
        raise ValueError(
            f"controlnet_image provided but {GROUPS.CONTROLNET_LLLITE!r} is not in groups.g1; "
            "either enable the group or omit controlnet_image"
        )
    if GROUPS.CONTROLNET_LLLITE in final_g1 and config.controlnet_image is None:
        raise ValueError(
            f"groups.g1 contains {GROUPS.CONTROLNET_LLLITE!r} but controlnet_image is None; "
            "ControlNet LLLite requires node 129 'Load Image ControlNet' to have an image"
        )

    graph = apply_group_modes(graph, groups_meta, final_g1, final_g2)

    # 7. ControlNet LLLite image (node 129) — only after group is confirmed active.
    if config.controlnet_image is not None:
        _apply_controlnet_image(graph, config.controlnet_image)

    # 8. WORKFLOW_CONVENTIONS per stage.
    if stage in WORKFLOW_CONVENTIONS:
        for nid, value in WORKFLOW_CONVENTIONS[stage].get("denoise_override", {}).items():
            graph[nid]["inputs"]["denoise"] = value

    # 9. i2i activation (after group validation so the upload path is enforced).
    if stage == STAGES.I2I:
        if not config.reference_image:
            raise ValueError("reference_image is required for i2i-camera")
        _activate_img2img(graph, config.reference_image)

    return graph


def describe_config(stage: str = STAGES.T2I) -> dict[str, Any]:
    """Return all configurable slots for the current workflow.

    Reads NODE_FIELD_MAP + workflow.json static values + groups.json titles.
    No hand-written field table.
    """
    graph = load_workflow(stage)
    titles = list_group_titles(stage)

    slots: dict[str, Any] = {}

    # Walk NODE_FIELD_MAP: cluster by top-level key.
    grouped: dict[str, list[tuple[str, str, str]]] = {}
    for path, (nid, fld) in NODE_FIELD_MAP.items():
        group = path.split(".", 1)[0] if "." in path else path
        grouped.setdefault(group, []).append((path, nid, fld))

    for group, items in grouped.items():
        if group == "sampling":
            slots[group] = {
                "source": f"config.{group}",
                "nodes": sorted({nid for _, nid, _ in items}),
                "fields": {
                    p.split(".", 1)[1]: {
                        "node": nid,
                        "default": _node_static_default(graph, nid, fld),
                    }
                    for p, nid, fld in items
                },
            }
        elif group == "image_size":
            slots[group] = {
                "source": f"config.{group}",
                "nodes": sorted({nid for _, nid, _ in items}),
                "default": {
                    p.split(".", 1)[1]: _node_static_default(graph, nid, fld)
                    for p, nid, fld in items
                },
            }
        else:
            path, nid, fld = items[0]
            slots[group] = {
                "source": f"config.{group}",
                "node": nid,
                "default": _node_static_default(graph, nid, fld),
            }

    # Special slots that don't map to NODE_FIELD_MAP.
    slots["positive"] = {
        "source": "envelope.draft.positive",
        "node": "24",
        "type": "ImpactWildcardProcessor",
        "required": True,
    }
    slots["negative"] = {
        "source": "envelope.draft.negative",
        "node": "25",
        "type": "ImpactWildcardProcessor",
        "required": True,
    }
    slots["camera"] = {
        "source": "config.camera",
        "node": "583",
        "type": "CameraAngleNode",
        "required": False,
        "default": "front / eye-level / full_body / 0",
        "fields": {
            "direction": ["front", "back", "left", "right"],
            "elevation": ["high", "eye-level", "low"],
            "distance": [
                "extreme_close_up", "close_up", "medium",
                "cowboy_shot", "full_body", "wide",
            ],
            "roll": "[0, 1]",
        },
    }
    slots["camera_extra"] = {
        "source": "config.camera_extra",
        "node": "585",
        "type": "CameraExtraConfigNode",
        "required": False,
        "fields": list(CAMERA_EXTRA_FIELDS),
    }
    slots["lora"] = {
        "source": "config.lora",
        "loader_node": "26",
        "trigger_node": "66",
        "required": False,
        "default_stack": DEFAULT_LORA_STACK_TEXT,
    }
    slots["reference_image"] = {
        "source": "config.reference_image",
        "node": "21",
        "type": "LoadImage",
        "required_if": 'stage == "i2i-camera"',
        "default": None,
    }
    slots["controlnet_image"] = {
        "source": "config.controlnet_image",
        "node": "129",
        "type": "Load Image ControlNet",
        "required_if": f'groups.g1 contains {GROUPS.CONTROLNET_LLLITE!r}',
        "default": None,
    }
    slots["groups"] = {
        "source": "config.groups",
        "g1_titles": titles["g1"],
        "g2_titles": titles["g2"],
        "auto_appended_g1": {
            GROUPS.CONTROLNET_LLLITE: "when controlnet_image provided",
            GROUPS.LOAD_IMAGE: "when stage == 'i2i-camera'",
        },
    }

    return {"stage": stage, "workflow": stage, "slots": slots}