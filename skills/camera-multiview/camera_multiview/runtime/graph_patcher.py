"""Patch the two declared user image inputs in the fixed API graph."""

from __future__ import annotations

from typing import Any

from .config_schema import RunConfig, STAGE


USER_IMAGE_NODES: dict[str, str] = {
    "full_body_image": "111",
    "face_image": "667",
}


def apply_run_config(graph: dict[str, Any], config: RunConfig) -> dict[str, Any]:
    """Write only the two user image filenames into an API graph copy."""
    if not config.full_body_image:
        raise ValueError("full_body_image is required")
    if not config.face_image:
        raise ValueError("face_image is required")
    for field, node_id in USER_IMAGE_NODES.items():
        node = graph.get(node_id)
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            raise ValueError(f"configured LoadImage node {node_id} is missing")
        node["inputs"]["image"] = getattr(config, field)
    return graph


def describe_config(stage: str) -> dict[str, Any]:
    if stage != STAGE:
        raise ValueError(f"unsupported multiview stage: {stage}")
    return {
        "stage": STAGE,
        "config_fields": {
            "full_body_image": {
                "type": "local_image_path",
                "required": True,
                "node_id": "111",
                "node_title": "加载图像（人物全身）",
            },
            "face_image": {
                "type": "local_image_path",
                "required": True,
                "node_id": "667",
                "node_title": "加载图像（人物面部）",
            },
        },
        "fixed_inputs": {
            "pose_nodes": 13,
            "pose_directory": "runtime/workflow_assets/pose",
            "workflow": "runtime/workflow_assets/Flux2-Klein人物一键多视图工作流.json",
        },
        "groups": None,
    }
