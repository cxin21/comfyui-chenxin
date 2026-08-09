"""Canonical serialization primitives shared by workflow contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize contract data deterministically for hashing and comparison."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    """Return the SHA-256 digest of canonical contract data."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_api_graph(
    graph: Mapping[str, Any],
    *,
    output_class_types: frozenset[str] = frozenset(
        {"Image Saver Simple", "PreviewImage"}
    ),
) -> None:
    """Validate structural invariants after group selection and API conversion."""
    if not isinstance(graph, Mapping) or not graph:
        raise ValueError("compiled API graph must be a non-empty mapping")

    node_ids = {str(node_id) for node_id in graph}
    output_nodes: list[str] = []

    for node_id, node in graph.items():
        node_label = str(node_id)
        if not isinstance(node, Mapping):
            raise ValueError(f"node {node_label} is not an object")
        class_type = node.get("class_type")
        if not isinstance(class_type, str) or not class_type:
            raise ValueError(f"node {node_label} has no class_type")
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping):
            raise ValueError(f"node {node_label} has no API inputs object")

        if class_type in output_class_types:
            output_nodes.append(node_label)
            if "images" not in inputs:
                raise ValueError(
                    f"output node {node_label} ({class_type}) has no images input"
                )
            if not _is_link_reference(inputs["images"]):
                raise ValueError(
                    f"output node {node_label} ({class_type}) images input is not a link"
                )

        for input_name, value in inputs.items():
            if not _is_link_reference(value):
                continue
            target_id = str(value[0])
            if target_id not in node_ids:
                raise ValueError(
                    f"node {node_label} input {input_name!r} has dangling input reference "
                    f"to node {target_id}"
                )

    if not output_nodes:
        raise ValueError("compiled API graph has no image output node")


def _is_link_reference(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], (str, int))
        and isinstance(value[1], int)
    )
