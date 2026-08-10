"""Load and verify the bundled multiview API workflow and pose assets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class AssetError(ValueError):
    """Raised when a fixed multiview asset is missing or altered."""


ASSET_ROOT = Path(__file__).with_name("workflow_assets")
WORKFLOW_NAME = "Flux2-Klein人物一键多视图工作流.json"
WORKFLOW_PATH = ASSET_ROOT / WORKFLOW_NAME
MANIFEST_PATH = ASSET_ROOT / "manifest.json"

USER_IMAGE_NODES: dict[str, str] = {
    "full_body_image": "111",
    "face_image": "667",
}

POSE_NODES: dict[str, str] = {
    f"pose_{index}": node_id
    for index, node_id in (
        (1, "152"),
        (2, "154"),
        (3, "360"),
        (4, "364"),
        (5, "148"),
        (6, "149"),
        (7, "147"),
        (8, "373"),
        (9, "150"),
        (10, "367"),
        (11, "368"),
        (12, "151"),
        (13, "757"),
    )
}

EXPECTED_WORKFLOW_SHA256 = "33584a54b6587914fce078cdcddbab7915e7d834ca741ded06a44a3ba484252e"


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise AssetError(f"fixed asset is unreadable: {path}") from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AssetError(f"fixed API workflow is invalid: {path}") from exc
    if not isinstance(value, dict) or not value:
        raise AssetError("fixed API workflow must be a non-empty object")
    return value


def _load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AssetError(f"fixed asset manifest is invalid: {MANIFEST_PATH}") from exc
    if not isinstance(value, dict):
        raise AssetError("fixed asset manifest must be an object")
    return value


def _node_title(node: dict[str, Any]) -> str:
    meta = node.get("_meta")
    return str(meta.get("title", "")) if isinstance(meta, dict) else ""


def _verify_node(node_id: str, workflow: dict[str, Any], expected_title: str) -> dict[str, Any]:
    node = workflow.get(node_id)
    if not isinstance(node, dict) or node.get("class_type") != "LoadImage":
        raise AssetError(f"fixed LoadImage node {node_id} is missing or has the wrong class")
    if _node_title(node) != expected_title:
        raise AssetError(
            f"fixed LoadImage node {node_id} title changed: {_node_title(node)!r}"
        )
    inputs = node.get("inputs")
    if not isinstance(inputs, dict) or not isinstance(inputs.get("image"), str):
        raise AssetError(f"fixed LoadImage node {node_id} has no image input")
    return node


def load_fixed_workflow() -> dict[str, Any]:
    """Load the immutable API graph and verify its input topology."""
    if not WORKFLOW_PATH.is_file():
        raise AssetError(f"fixed API workflow is missing: {WORKFLOW_PATH}")
    manifest = _load_manifest()
    workflow_hash = _sha256(WORKFLOW_PATH)
    if workflow_hash != EXPECTED_WORKFLOW_SHA256:
        raise AssetError(
            f"fixed API workflow hash changed: expected {EXPECTED_WORKFLOW_SHA256}, got {workflow_hash}"
        )
    manifest_workflow = manifest.get("workflow")
    if not isinstance(manifest_workflow, dict) or manifest_workflow.get("sha256") != workflow_hash:
        raise AssetError("fixed asset manifest does not match the API workflow")
    workflow = _load_json(WORKFLOW_PATH)
    expected_node_count = manifest_workflow.get("node_count")
    if expected_node_count != len(workflow):
        raise AssetError(
            f"fixed API workflow node count changed: expected {expected_node_count}, got {len(workflow)}"
        )
    for node_id, expected in USER_IMAGE_NODES.items():
        title = "加载图像（人物全身）" if node_id == "full_body_image" else "加载图像（人物面部）"
        _verify_node(expected, workflow, title)
    for index, node_id in ((int(key.removeprefix("pose_")), value) for key, value in POSE_NODES.items()):
        node = _verify_node(node_id, workflow, f"姿势骨架{index}")
        expected_file = f"姿势骨架{index}.png"
        if node["inputs"]["image"] != expected_file:
            raise AssetError(
                f"pose node {node_id} must reference {expected_file!r}, "
                f"got {node['inputs']['image']!r}"
            )
    if any(
        not isinstance(node, dict)
        or not isinstance(node.get("class_type"), str)
        or not isinstance(node.get("inputs"), dict)
        for node in workflow.values()
    ):
        raise AssetError("fixed API workflow contains an invalid node")
    return workflow


def pose_assets() -> tuple[tuple[str, Path], ...]:
    """Return verified ``(pose filename, local path)`` pairs in numeric order."""
    result: list[tuple[str, Path]] = []
    pose_root = ASSET_ROOT / "pose"
    manifest = _load_manifest()
    manifest_poses = manifest.get("poses")
    if not isinstance(manifest_poses, list):
        raise AssetError("fixed asset manifest has no pose list")
    expected_hashes = {
        item.get("filename"): item.get("sha256")
        for item in manifest_poses
        if isinstance(item, dict)
    }
    for index in range(1, 14):
        filename = f"姿势骨架{index}.png"
        path = pose_root / filename
        if not path.is_file():
            raise AssetError(f"fixed pose asset is missing: {path}")
        actual_hash = _sha256(path)
        if expected_hashes.get(filename) != actual_hash:
            raise AssetError(f"fixed pose asset hash changed: {filename}")
        result.append((filename, path))
    return tuple(result)
