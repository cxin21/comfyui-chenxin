"""Declarative UI/API graph patching for camera workflows.

Single signature ``apply_run_config(graph, *, config, mcp_list_loras=None)``
accepts a ``RunConfig`` (defined in runtime.config_schema) and writes every
tunable into the graph produced by ``source_workflow.prepare_temporary_workflow``.

Format-aware: the patcher detects UI vs API by the shape of
``graph[node_id]["inputs"]`` and writes to the correct slot:

- API format (after strip): ``inputs`` is a dict; write to
  ``graph[node_id]["inputs"][name] = value``.
- UI format (source workflow, pre-strip): ``inputs`` is a list of
  connection refs; literal values live in ``widgets_values`` (list).
  Write to ``graph[node_id]["widgets_values"][_UI_INDEX[(node_id, name)]]``.

Hardcoded UI widget index map (_UI_WIDGET_INDEX) is derived from
``camera_image/runtime/workflow_assets/camera-anima.json`` structure. The strip step is
the source of truth for converting widget values to API inputs; we
only need to write the right index.

Order:
1.  Prompts (24/25) from ``config.prompt``.
2.  Camera (583) + camera_extra (585).
3.  LoRA (26/66).
4.  Sampling (50/51), seed (65), image_size (68/71).
5.  Cross-validate controlnet_image <-> ControlNet LLLite group.
6.  ControlNet image (129).
7.  WORKFLOW_CONVENTIONS per stage (e.g. i2i denoise=0.6).
8.  i2i activation (after group validation so the upload path is
    enforced).
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
    GROUPS,
    CONTROLNET_IMAGE_NODE,
    RunConfig,
    SamplingConfig,
    ImageSizeConfig,
    STAGES,
)
from .lora_resolver import build_lora_patch, DEFAULT_LORA_STACK_TEXT
from .source_workflow import (
    SOURCE_WORKFLOW_PATH,
    compute_enabled_groups,
    _load_groups,
)


# Single source of truth — patcher and describe_config both read this.
# NOTE: sampler / scheduler are intentionally absent; they are pinned to
# the static values baked into workflow.json (forbidden_inputs in the
# manifest). Patcher does not write them and describe_config does not surface them.
NODE_FIELD_MAP: dict[str, tuple[str, str]] = {
    "sampling.steps_first":    ("50", "steps"),
    "sampling.cfg":            ("50", "cfg"),
    "sampling.denoise_first":  ("50", "denoise"),
    "sampling.steps_refine":   ("51", "steps"),
    "sampling.denoise_refine": ("51", "denoise"),
    "seed":                    ("65", "seed"),
    "image_size.width":        ("68", "value"),
    "image_size.height":       ("71", "value"),
    "controlnet_image":        ("129", "image"),
}


# UI widget index map.
#
# Maps (node_id, input_name) -> position in the node's widgets_values
# list. Derived by inspecting ``camera_image/runtime/workflow_assets/camera-anima.json``
# (committed UI workflow). Used when the patcher is called against a
# UI-format graph (pre-strip) so the value lands in the slot that
# ComfyUI's strip will lift into the API dict.
_UI_WIDGET_INDEX: dict[tuple[str, str], int] = {
    # ImpactWildcardProcessor (24 / 25) — positive / negative main prompts.
    ("24", "wildcard_text"): 0,
    ("24", "populated_text"): 1,
    ("25", "wildcard_text"): 0,
    ("25", "populated_text"): 1,
    # ImpactWildcardProcessor (3 / 4 / 5) — region prompts (Red/Green/Blue)
    # used by 区域提示词（G1）. Same widget layout as 24/25.
    ("3", "wildcard_text"): 0,
    ("3", "populated_text"): 1,
    ("4", "wildcard_text"): 0,
    ("4", "populated_text"): 1,
    ("5", "wildcard_text"): 0,
    ("5", "populated_text"): 1,
    # LoRA Text Loader (26) exposes one ordinary STRING widget.
    ("26", "lora_syntax"): 0,
    # Input Parameters / Image Saver (50) — first-pass sampling
    # widgets_values layout: [seed, control_after_generate, steps,
    # cfg, sampler, scheduler, denoise]; widget input positions skip
    # the hidden control_after_generate.
    # NOTE: sampler / scheduler widgets are intentionally NOT registered
    # here — they are pinned to the static values baked into workflow.json
    # and the patcher must not write them.
    ("50", "seed"): 0,
    ("50", "steps"): 2,
    ("50", "cfg"): 3,
    ("50", "denoise"): 6,
    # KSampler (51) — refine pass; same widget layout as node 50.
    ("51", "seed"): 0,
    ("51", "steps"): 2,
    ("51", "cfg"): 3,
    ("51", "denoise"): 6,
    # Seed (rgthree) (65) — all implicit widgets.
    ("65", "seed"): 0,
    # easy int (68 / 71) — single value widget.
    ("68", "value"): 0,
    ("71", "value"): 0,
    # LoadImage (129) — controlnet image.
    ("129", "image"): 0,
    # LoadImage (21) — i2i reference image.
    ("21", "image"): 0,
    # PrimitiveInt (58) — select the VAE-encoded reference branch.
    ("58", "value"): 0,
    # CameraAngleNode (583) — pos_x/y/z/roll at front of widgets_values.
    ("583", "pos_x"): 0,
    ("583", "pos_y"): 1,
    ("583", "pos_z"): 2,
    ("583", "roll"): 3,
    # CameraExtraConfigNode (585) — 1:1 with widget input positions.
    ("585", "extreme_type"): 0,
    ("585", "extreme_weight"): 1,
    ("585", "lens_enabled"): 2,
    ("585", "lens_value"): 3,
    ("585", "dof_enabled"): 4,
    ("585", "dof_value"): 5,
    ("585", "dof_weight"): 6,
    ("585", "movement_enabled"): 7,
    ("585", "movement_value"): 8,
    ("585", "composition_enabled"): 9,
    ("585", "composition_value"): 10,
    ("585", "style_enabled"): 11,
    ("585", "style_value"): 12,
}


def _is_api_graph(graph: dict[str, Any]) -> bool:
    """True if graph uses API format (top-level keys are node IDs as strings).

    UI format keeps nodes inside a ``nodes`` list; API format is keyed by
    node id. This distinction drives whether writes go to
    ``widgets_values`` (UI) or ``inputs[name]`` (API).
    """
    if "nodes" in graph and isinstance(graph["nodes"], list):
        return False
    sample = next(iter(graph.values()), None)
    if not isinstance(sample, dict):
        return False
    return isinstance(sample.get("inputs"), dict)


def _get_node(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    """Fetch a node from either UI (nodes=list) or API (keyed by id) graph."""
    if _is_api_graph(graph):
        return graph.get(node_id)
    for node in graph.get("nodes", []):
        if isinstance(node, dict) and str(node.get("id")) == str(node_id):
            return node
    return None


def _set_value(graph: dict[str, Any], node_id: str, name: str, value: Any) -> None:
    """Write one literal value into either UI or API graph.

    API: ``graph[node_id]["inputs"][name] = value``.
    UI:  ``graph[<nodes-entry-for-node_id>]["widgets_values"][idx] = value``
         where ``idx`` is looked up in ``_UI_WIDGET_INDEX``.
    """
    node = _get_node(graph, node_id)
    if node is None:
        raise KeyError(f"node {node_id} missing from workflow")
    inputs = node.get("inputs")
    if isinstance(inputs, dict):
        # API format.
        inputs[name] = value
        return
    if isinstance(inputs, list):
        # UI format — write to widgets_values.
        key = (node_id, name)
        if key not in _UI_WIDGET_INDEX:
            raise KeyError(
                f"no UI widget index mapping for node {node_id} input {name!r}; "
                "add an entry to _UI_WIDGET_INDEX in graph_patcher.py"
            )
        idx = _UI_WIDGET_INDEX[key]
        widgets = node.get("widgets_values")
        if not isinstance(widgets, list) or idx >= len(widgets):
            raise KeyError(
                f"node {node_id} widgets_values missing or too short for input {name!r} "
                f"(expected index {idx}, got length {len(widgets) if isinstance(widgets, list) else 0})"
            )
        widgets[idx] = value
        return
    raise ValueError(
        f"node {node_id} inputs field has unexpected type {type(inputs).__name__}; "
        "expected dict (API) or list (UI)"
    )


def _set_prompt(graph: dict, node_id: str, text: str) -> None:
    _set_value(graph, node_id, "wildcard_text", text)
    _set_value(graph, node_id, "populated_text", text)


def _set_region_prompt(graph: dict, channel: str, text: str) -> None:
    """Write a region prompt (Red/Green/Blue) into its ImpactWildcardProcessor.

    Channel -> node id:
      red   -> "3"
      green -> "4"
      blue  -> "5"
    """
    _node_id = {"red": "3", "green": "4", "blue": "5"}[channel]
    _set_value(graph, _node_id, "wildcard_text", text)
    _set_value(graph, _node_id, "populated_text", text)


def _set_camera(graph: dict, coords: CameraCoords) -> None:
    _set_value(graph, "583", "pos_x", coords.pos_x)
    _set_value(graph, "583", "pos_y", coords.pos_y)
    _set_value(graph, "583", "pos_z", coords.pos_z)
    _set_value(graph, "583", "roll", coords.roll)


def _set_camera_partial(
    graph: dict,
    *,
    direction=None,
    elevation=None,
    distance=None,
    roll=None,
) -> None:
    """Write only the camera fields the caller provided.

    None means "keep source UI workflow's static value for node 583".
    """
    if direction is not None:
        _set_value(graph, "583", "pos_x", map_camera(direction=direction).pos_x)
    if elevation is not None:
        _set_value(graph, "583", "pos_y", map_camera(elevation=elevation).pos_y)
    if distance is not None:
        _set_value(graph, "583", "pos_z", map_camera(distance=distance).pos_z)
    if roll is not None:
        _set_value(graph, "583", "roll", float(roll))


def _set_camera_extra(graph: dict, extra: dict) -> None:
    for field in CAMERA_EXTRA_FIELDS:
        if field in extra:
            _set_value(graph, "585", field, extra[field])


def _set_lora(graph: dict, lora_patch: dict) -> None:
    # Use _get_node (format-aware) instead of "26" in graph —
    # UI format has nodes in a list, not keyed by id.
    node_26 = _get_node(graph, "26")
    if node_26 is not None:
        # The ordinary STRING widget is converter-visible and becomes the
        # API lora_syntax literal.
        _set_value(graph, "26", "lora_syntax", lora_patch["node_26"]["text"])
    node_66 = _get_node(graph, "66")
    if node_66 is not None and isinstance(node_66.get("inputs"), dict):
        for key, value in lora_patch["node_66"].items():
            node_66["inputs"][key] = value


def _apply_sampling(graph: dict, s: SamplingConfig) -> None:
    # NOTE: sampler / scheduler are intentionally not written — they are
    # pinned to workflow.json static values.
    if s.steps_first is not None:    _set_value(graph, "50", "steps",    s.steps_first)
    if s.cfg is not None:            _set_value(graph, "50", "cfg",      s.cfg)
    if s.denoise_first is not None:  _set_value(graph, "50", "denoise",  s.denoise_first)
    if s.steps_refine is not None:   _set_value(graph, "51", "steps",    s.steps_refine)
    if s.denoise_refine is not None: _set_value(graph, "51", "denoise",  s.denoise_refine)


def _apply_seed(graph: dict, seed: int) -> None:
    _set_value(graph, "65", "seed", seed)


def _apply_image_size(graph: dict, size: ImageSizeConfig) -> None:
    if size.width is not None:
        _set_value(graph, "68", "value", size.width)
    if size.height is not None:
        _set_value(graph, "71", "value", size.height)


def _apply_controlnet_image(graph: dict, image_name: str) -> None:
    _set_value(graph, "129", "image", image_name)


def apply_run_config(
    graph: dict[str, Any],
    *,
    stage: str = STAGES.T2I,
    config: RunConfig,
    mcp_list_loras: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Write every tunable into the graph (UI or API format).

    Caller supplies a RunConfig (with evidence + prompt artifact + tunables) and
    a graph produced by ``source_workflow.prepare_temporary_workflow``.
    Format is detected automatically: UI (pre-strip, inputs=list) writes
    to ``widgets_values``; API (post-strip, inputs=dict) writes to
    ``inputs[name]``. Group enablement is already baked into the graph
    (mode fields were applied before strip removed them); this function
    only writes the *values*.

    Order:
    1.  Prompts (24/25) from ``config.prompt`` after revalidation.
    2.  Camera (583) + camera_extra (585).
    3.  LoRA (26/66).
    4.  Sampling (50/51), seed (65), image_size (68/71).
    5.  Cross-validate controlnet_image <-> ControlNet LLLite group.
        Group state is read from the per-stage groups.json (matches what
        the strip step applied).
    6.  ControlNet image (129).
    7.  i2i reference image, branch selection, and denoise are written to
        the UI graph before strip so the converter owns the final API shape.
    """
    enabled_g1, _ = compute_enabled_groups(stage, config.groups)

    # 1. Prompts.
    from comfyui_chenxin_mcp.engine.prompt_forge import validate_prompt_artifact

    if config.prompt_ref is not None:
        prompt = validate_prompt_artifact(
            config.prompt_ref, expected_task="anima"
        )
    else:
        prompt = dict(config.prompt)
    _set_prompt(graph, "24", prompt["positive"].strip())
    _set_prompt(graph, "25", prompt["negative"].strip())

    # 1b. Region prompts (Red/Green/Blue) — only when the G1 group is on.
    if GROUPS.AREA_PROMPT in enabled_g1:
        raise ValueError("regional prompt group is outside the PromptArtifact contract")

    # 2. Camera + camera_extra.
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

    # 3. LoRA syntax is written before strip so the converter emits the
    # selected stack as the node's ordinary API input.
    lora_patch = build_lora_patch(
        run_config_lora=config.lora,
        mcp_list_loras=mcp_list_loras,
    )
    _set_lora(graph, lora_patch)

    # 4. Sampling / seed / image_size.
    if config.sampling:
        _apply_sampling(graph, config.sampling)
    if config.seed is not None:
        _apply_seed(graph, config.seed)
    if config.image_size:
        _apply_image_size(graph, config.image_size)

    # 5. Cross-validate controlnet_image <-> ControlNet LLLite group.
    cn_node_for_stage = CONTROLNET_IMAGE_NODE.get(stage)
    if config.controlnet_image is not None and cn_node_for_stage is None:
        raise ValueError(f"controlnet_image not supported in stage={stage!r}")
    if (
        config.controlnet_image is not None
        and GROUPS.CONTROLNET_LLLITE not in enabled_g1
    ):
        raise ValueError(
            f"controlnet_image provided but {GROUPS.CONTROLNET_LLLITE!r} is not in groups.g1; "
            "either enable the group or omit controlnet_image"
        )
    if (
        GROUPS.CONTROLNET_LLLITE in enabled_g1
        and config.controlnet_image is None
    ):
        raise ValueError(
            f"groups.g1 contains {GROUPS.CONTROLNET_LLLITE!r} but controlnet_image is None; "
            "ControlNet LLLite requires node 129 'Load Image ControlNet' to have an image"
        )

    # 6. ControlNet image (node 129).
    if config.controlnet_image is not None:
        _apply_controlnet_image(graph, config.controlnet_image)

    if stage == STAGES.I2I:
        if not config.reference_image:
            raise ValueError("reference_image is required for i2i-camera")
        _set_value(graph, "21", "image", config.reference_image)
        _set_value(graph, "58", "value", 2)
        _set_value(graph, "50", "denoise", 0.6)
    elif config.reference_image is not None:
        raise ValueError("reference_image is only supported in i2i-camera")

    return graph


def describe_config(stage: str = STAGES.T2I) -> dict[str, Any]:
    """Return all configurable slots for the current workflow.

    Reads NODE_FIELD_MAP + the source UI workflow's static values + the
    per-stage groups.json titles. No hand-written field table.

    Note: the source UI workflow values are *literal* (not the active
    defaults after strip). Stripped values match the source's literal
    values for all non-mode inputs.
    """
    from .source_workflow import _load_source_ui  # local import: not a hot path

    ui = _load_source_ui()
    nodes_by_id: dict[int, dict] = {
        n.get("id"): n for n in ui.get("nodes", []) if isinstance(n, dict)
    }
    titles = _list_group_titles(stage)

    def _static(node_id: int, field: str) -> Any:
        node = nodes_by_id.get(node_id)
        if not node:
            return None
        widgets = node.get("widgets_values") or []
        inputs = node.get("inputs") or []
        # source UI format stores literal widget values in widgets_values
        # (list) and connection refs in inputs (list of dicts). The API
        # graph we ship uses inputs[<name>]=<literal-or-ref>. The strip
        # step preserves the literals faithfully; for describe_config we
        # surface the widget value if present, falling back to no value.
        if widgets and len(widgets) >= 1 and isinstance(widgets[-1], (int, float)):
            return widgets[-1]
        return None

    # Build slot defaults from NODE_FIELD_MAP.
    grouped: dict[str, list[tuple[str, int, str]]] = {}
    for path, (nid, fld) in NODE_FIELD_MAP.items():
        group = path.split(".", 1)[0] if "." in path else path
        grouped.setdefault(group, []).append((path, int(nid), fld))

    slots: dict[str, Any] = {}
    for group, items in grouped.items():
        if group == "sampling":
            slots[group] = {
                "source": f"config.{group}",
                "nodes": sorted({str(nid) for _, nid, _ in items}),
                "fields": {
                    p.split(".", 1)[1]: {
                        "node": str(nid),
                        "default": _static(nid, fld),
                    }
                    for p, nid, fld in items
                },
            }
        elif group == "image_size":
            slots[group] = {
                "source": f"config.{group}",
                "nodes": sorted({str(nid) for _, nid, _ in items}),
                "default": {
                    p.split(".", 1)[1]: _static(nid, fld)
                    for p, nid, fld in items
                },
            }
        else:
            path, nid, fld = items[0]
            slots[group] = {
                "source": f"config.{group}",
                "node": str(nid),
                "default": _static(nid, fld),
            }

    # Special slots that don't map to NODE_FIELD_MAP.
    slots["positive"] = {
        "source": "envelope.prompt.positive",
        "node": "24",
        "type": "ImpactWildcardProcessor",
        "required": True,
    }
    slots["negative"] = {
        "source": "envelope.prompt.negative",
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

    return {
        "stage": stage,
        "workflow": stage,
        "source_workflow": str(SOURCE_WORKFLOW_PATH),
        "slots": slots,
    }


def _list_group_titles(stage: str) -> dict[str, list[str]]:
    """Return available G1/G2 group titles for the given stage."""
    groups = _load_groups(stage)
    return {
        "g1": sorted(groups.get("g1", {}).keys()),
        "g2": sorted(groups.get("g2", {}).keys()),
    }
