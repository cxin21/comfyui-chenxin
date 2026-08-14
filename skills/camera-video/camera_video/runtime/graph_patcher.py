"""Patch only the declared prompt, duration, and reference-image inputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .assets import scene_spec
from .config_schema import IMAGE_FIELDS, RunConfig


def apply_run_config(graph: dict[str, Any], stage: str, config: RunConfig) -> dict[str, Any]:
    """Return a graph with only the stage's declared inputs changed."""
    config.validate_stage(stage)
    prompt = dict(config.prompt)
    spec = scene_spec(stage)
    result = deepcopy(graph)
    result[str(spec["prompt_node"])]["inputs"]["value"] = prompt["text"]
    result[str(spec["duration_node"])]["inputs"]["value"] = config.duration
    for index, node_id in enumerate(spec.get("image_nodes", []), start=1):
        result[str(node_id)]["inputs"]["image"] = getattr(config, f"reference_image_{index}")
    return result


def describe_config(stage: str) -> dict[str, Any]:
    """Describe exactly the user-configurable surface for one video scene."""
    spec = scene_spec(stage)
    fields: dict[str, dict[str, Any]] = {
        "prompt": {
            "type": "object",
            "required": True,
            "node_id": str(spec["prompt_node"]),
            "node_title": "Input Text (Prompt)",
        },
        "duration": {
            "type": "float",
            "required": True,
            "minimum": 2.0,
            "maximum": 15.0,
            "node_id": str(spec["duration_node"]),
            "node_title": "Float (Duration)",
        },
    }
    for index, node_id in enumerate(spec.get("image_nodes", []), start=1):
        fields[f"reference_image_{index}"] = {
            "type": "local_image_path",
            "required": True,
            "node_id": str(node_id),
            "node_title": "鍔犺浇鍥惧儚",
        }
    return {
        "stage": stage,
        "config_fields": fields,
        "fixed_inputs": {
            "workflow": f"runtime/workflow_assets/{spec['workflow']}",
            "node_count": spec["node_count"],
            "output_type": "video",
            "artifact_mode": "all",
        },
        "groups": None,
    }

