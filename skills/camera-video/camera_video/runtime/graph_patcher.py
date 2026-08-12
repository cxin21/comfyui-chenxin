"""Patch only the declared prompt, duration, and reference-image inputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .assets import scene_spec
from .config_schema import IMAGE_FIELDS, RunConfig


def apply_run_config(graph: dict[str, Any], stage: str, config: RunConfig) -> dict[str, Any]:
    """Return a graph with only the stage's declared inputs changed."""
    config.validate_stage(stage)
    from comfyui_chenxin_mcp.engine.prompt_forge import validate_prompt_artifact

    reference_count = len(IMAGE_FIELDS.get(stage, ()))
    artifact = validate_prompt_artifact(
        config.prompt_artifact,
        expected_task="h3_ref2va" if reference_count else "h3_t2va",
        expected_reference_count=reference_count,
        expected_duration=config.duration,
    )
    spec = scene_spec(stage)
    result = deepcopy(graph)
    result[str(spec["prompt_node"])]["inputs"]["value"] = artifact["prompt"]["text"]
    result[str(spec["duration_node"])]["inputs"]["value"] = config.duration
    for index, node_id in enumerate(spec.get("image_nodes", []), start=1):
        result[str(node_id)]["inputs"]["image"] = getattr(config, f"reference_image_{index}")
    return result


def describe_config(stage: str) -> dict[str, Any]:
    """Describe exactly the user-configurable surface for one video scene."""
    spec = scene_spec(stage)
    fields: dict[str, dict[str, Any]] = {
        "prompt_artifact": {
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
            "node_title": "加载图像",
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
