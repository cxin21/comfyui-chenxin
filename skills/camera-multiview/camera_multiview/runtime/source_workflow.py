"""Compile and prepare the fixed Flux2-Klein API graph."""

from __future__ import annotations

import copy
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from .assets import POSE_NODES, load_fixed_workflow, pose_assets
from .config_schema import RunConfig, STAGE
from .contracts import validate_api_graph
from .graph_patcher import apply_run_config


def _uploaded_name(result: Any) -> str:
    if isinstance(result, dict):
        name = result.get("name")
        subfolder = result.get("subfolder", "")
        if isinstance(name, str) and name:
            return f"{subfolder}/{name}" if subfolder else name
    if isinstance(result, str):
        for line in result.splitlines():
            if line.strip().startswith("Filename:"):
                return line.split(":", 1)[1].strip()
    raise RuntimeError(f"fixed pose upload returned no filename: {result!r}")


def _upload_fixed_poses(mcp: Any) -> dict[str, str]:
    uploaded: dict[str, str] = {}
    for filename, path in pose_assets():
        if _input_image_exists(mcp, filename):
            uploaded[filename] = filename
        else:
            uploaded[filename] = _uploaded_name(mcp.upload_image(str(path)))
    return uploaded


def _input_image_exists(mcp: Any, filename: str) -> bool:
    """Reuse a verified fixed asset already present in ComfyUI input."""
    base_url = getattr(mcp, "_comfyui_url", None)
    if not isinstance(base_url, str) or not base_url:
        return False
    query = urlencode({"filename": filename, "type": "input"})
    try:
        with urlopen(f"{base_url.rstrip('/')}/view?{query}", timeout=5) as response:
            return response.status == 200 and response.headers.get_content_type().startswith("image/")
    except Exception:
        return False


def _bind_fixed_poses(graph: dict[str, Any], uploaded: dict[str, str]) -> None:
    for index in range(1, 14):
        filename = f"姿势骨架{index}.png"
        node_id = POSE_NODES[f"pose_{index}"]
        node = graph.get(node_id)
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            raise ValueError(f"fixed pose node {node_id} is missing")
        node["inputs"]["image"] = uploaded[filename]


def prepare_workflow(
    mcp: Any,
    *,
    stage: str = STAGE,
    config: RunConfig,
    groups: None = None,
    **_: Any,
) -> dict[str, Any]:
    """Load, patch, hydrate fixed poses, and return the exact API graph."""
    if stage != STAGE:
        raise ValueError(f"unsupported multiview stage: {stage}")
    graph = copy.deepcopy(load_fixed_workflow())
    apply_run_config(graph, config)
    _bind_fixed_poses(graph, _upload_fixed_poses(mcp))
    validate_api_graph(graph)
    return graph
