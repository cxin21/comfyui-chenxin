"""Structural contracts for the fixed multiview API graph."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], (str, int))
        and isinstance(value[1], int)
    )


def validate_api_graph(graph: Mapping[str, Any]) -> None:
    """Reject an incomplete graph before it reaches ComfyUI."""
    if not isinstance(graph, Mapping) or not graph:
        raise ValueError("multiview API graph must be a non-empty mapping")

    node_ids = {str(node_id) for node_id in graph}
    output_count = 0
    for node_id, node in graph.items():
        label = str(node_id)
        if not isinstance(node, Mapping):
            raise ValueError(f"node {label} is not an object")
        class_type = node.get("class_type")
        inputs = node.get("inputs")
        if not isinstance(class_type, str) or not class_type:
            raise ValueError(f"node {label} has no class_type")
        if not isinstance(inputs, Mapping):
            raise ValueError(f"node {label} has no inputs object")
        if class_type in {"easy getNode", "easy setNode", "Reroute"}:
            raise ValueError(f"frontend-only node {label} ({class_type}) reached API graph")
        if class_type in {"SaveImage", "PreviewImage"}:
            output_count += 1
            images = inputs.get("images")
            if not _is_link(images):
                raise ValueError(f"output node {label} has no images link")
        for input_name, value in inputs.items():
            if _is_link(value) and str(value[0]) not in node_ids:
                raise ValueError(
                    f"node {label} input {input_name!r} references missing node {value[0]}"
                )
    if output_count == 0:
        raise ValueError("multiview API graph has no image output")

    for node_id, expected in {"111": "full body", "667": "face"}.items():
        node = graph.get(node_id)
        if not isinstance(node, Mapping) or node.get("class_type") != "LoadImage":
            raise ValueError(f"configured {expected} node {node_id} is missing")
        image = node.get("inputs", {}).get("image")
        if not isinstance(image, str) or not image.strip():
            raise ValueError(f"configured {expected} node {node_id} has no image")
