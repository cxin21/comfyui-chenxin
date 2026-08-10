"""Load and verify the bundled fixed workflow assets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .workflow_profile import structure_fingerprint


class WorkflowAssetError(ValueError):
    """Raised when a fixed workflow asset is missing or altered."""


ASSET_ROOT = Path(__file__).with_name("workflow_assets")
MANIFEST_PATH = ASSET_ROOT / "manifest.json"


def _manifest() -> dict:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowAssetError("fixed workflow manifest is unreadable") from exc
    if not isinstance(value, dict) or value.get("asset_policy") != "bundled-fixed-json":
        raise WorkflowAssetError("fixed workflow manifest policy is invalid")
    return value


def asset_descriptor(asset_name: str) -> dict:
    """Return the trusted descriptor for one bundled UI workflow asset."""
    manifest = _manifest()
    entry = manifest.get("assets", {}).get(asset_name)
    required = {
        "stage", "workflow_name", "source", "profile_id", "asset_sha256",
        "workflow_id", "workflow_schema_version", "workflow_fingerprint",
        "config_surface_stages", "slot_map", "forbidden_inputs",
    }
    if not isinstance(entry, dict) or not required.issubset(entry):
        raise WorkflowAssetError(f"fixed workflow descriptor is incomplete: {asset_name}")
    if entry["workflow_schema_version"] != "comfyui-ui-v1":
        raise WorkflowAssetError(f"fixed workflow schema version is unsupported: {asset_name}")
    return dict(entry)


def load_fixed_workflow(asset_name: str) -> dict:
    entry = asset_descriptor(asset_name)
    path = (ASSET_ROOT / asset_name).resolve()
    if not path.is_file() or not path.is_relative_to(ASSET_ROOT.resolve()):
        raise WorkflowAssetError(f"fixed workflow asset is missing: {asset_name}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != entry["asset_sha256"]:
        raise WorkflowAssetError(f"fixed workflow asset hash mismatch: {asset_name}")
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowAssetError(f"fixed workflow asset is invalid JSON: {asset_name}") from exc
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise WorkflowAssetError(f"fixed workflow asset is not a ComfyUI UI workflow: {asset_name}")
    if structure_fingerprint(workflow) != entry["workflow_fingerprint"]:
        raise WorkflowAssetError(f"fixed workflow structure fingerprint mismatch: {asset_name}")
    return workflow
