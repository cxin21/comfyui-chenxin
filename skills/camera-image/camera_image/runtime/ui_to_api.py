"""Local UI-to-API workflow converter.

This replaces the upstream ``comfyui_chenxin_mcp.engine.strip_workflow``.
It only operates on the bundled fixed UI asset (``camera-anima.json``);
it cannot be used to strip arbitrary user workflows.

The conversion is intentionally minimal:

* Each node's UI-only ``mode`` field is dropped.
* Each node's ``widgets_values`` list is rewritten as ``inputs`` keyed by
  ``value_0`` / ``value_1`` / ... so subsequent validators that scan for
  ``inputs`` see the same shape as MCP's strip step.

The validator in :mod:`camera_image.runtime.contracts` (``validate_api_graph``)
inspects the result; this module raises if the upstream asset stops being a
recognisable ComfyUI UI workflow.
"""

from __future__ import annotations

from typing import Any


def strip_workflow(ui: dict[str, Any]) -> dict[str, Any]:
    """Convert a ComfyUI UI workflow dict into an API-format workflow dict."""

    if not isinstance(ui, dict):
        raise ValueError("UI workflow must be a JSON object")
    nodes = ui.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("UI workflow has no 'nodes' list")

    api_graph: dict[str, Any] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        raw_id = node.get("id")
        if raw_id is None:
            continue
        node_id = str(raw_id)
        class_type = node.get("type") or node.get("class_type")
        if not isinstance(class_type, str) or not class_type:
            raise ValueError(f"node {node_id} has no class_type")

        inputs: dict[str, Any] = {}
        existing_inputs = node.get("inputs")
        if isinstance(existing_inputs, dict):
            for input_name, value in existing_inputs.items():
                inputs[str(input_name)] = value
        widgets = node.get("widgets_values")
        if isinstance(widgets, list):
            for index, value in enumerate(widgets):
                key = f"value_{index}"
                inputs.setdefault(key, value)

        api_node: dict[str, Any] = {
            "class_type": class_type,
            "inputs": inputs,
        }
        if "title" in node:
            api_node["title"] = node["title"]
        api_graph[node_id] = api_node

    if not api_graph:
        raise ValueError("strip_workflow returned an empty API graph")
    return api_graph
