"""Structured effective configuration and LoRA evidence for image results."""

from __future__ import annotations

import copy

from .contracts import content_hash


def _inputs(graph: dict, node_id: str) -> dict:
    node = graph.get(node_id)
    values = node.get("inputs") if isinstance(node, dict) else None
    return copy.deepcopy(values) if isinstance(values, dict) else {}


def build_effective_camera_result(graph: dict, *, ui_workflow: dict | None = None, artifact: dict | None = None) -> dict:
    """Build the user-facing config snapshot from the executable API graph."""
    if isinstance(graph, list) and len(graph) >= 3 and isinstance(graph[2], dict):
        graph = graph[2]
    if not isinstance(graph, dict):
        raise ValueError("result graph must be an object")
    positive = _inputs(graph, "24")
    negative = _inputs(graph, "25")
    lora = _inputs(graph, "26")
    trigger = _inputs(graph, "66")
    angle = _inputs(graph, "583")
    extra = _inputs(graph, "585")
    snapshot = {
        "config": {
            "prompts": {
                "positive": positive.get("populated_text", positive.get("wildcard_text", "")),
                "negative": negative.get("populated_text", negative.get("wildcard_text", "")),
            },
            "camera_angle": angle,
            "camera_extra": extra,
            "groups": {},
        },
        "lora": {
            "stack_text": lora.get("text", ""),
            "loader": lora,
            "trigger_word_toggle": trigger,
        },
    }
    if isinstance(ui_workflow, dict):
        try:
            from .stage_config_surface import read_fixed_ui_stage_config
            ui_values = read_fixed_ui_stage_config("character-base", ui_workflow)["values"]
            snapshot["config"]["groups"] = copy.deepcopy(ui_values.get("groups", {}))
        except (KeyError, TypeError, ValueError):
            pass
    snapshot["config_hash"] = content_hash(snapshot)
    if artifact is not None:
        snapshot["artifact"] = copy.deepcopy(artifact)
    return snapshot
