"""Load the fixed workflow.json and groups.json for a camera stage.

The workflow JSON is a known-executable ComfyUI API graph validated by
MCP validate_workflow at build time. Runtime loads it directly — no strip,
no UI-to-API conversion, no fingerprint drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_WORKFLOW_DIR = Path(__file__).resolve().parent.parent / "workflow"


def load_workflow(stage: str = "t2i-camera") -> dict[str, Any]:
    """Load the fixed API graph for a camera stage."""
    if stage not in ("t2i-camera", "i2i-camera"):
        raise ValueError(f"unsupported camera stage: {stage}")
    path = _WORKFLOW_DIR / stage / "workflow.json"
    if not path.is_file():
        raise FileNotFoundError(f"workflow asset missing: {path}")
    with path.open("r", encoding="utf-8") as f:
        graph = json.load(f)
    if not isinstance(graph, dict) or not graph:
        raise ValueError(f"workflow asset is invalid: {path}")
    return graph


def load_groups(stage: str = "t2i-camera") -> dict[str, Any]:
    """Load G1/G2 group membership metadata."""
    if stage not in ("t2i-camera", "i2i-camera"):
        raise ValueError(f"unsupported camera stage: {stage}")
    path = _WORKFLOW_DIR / stage / "groups.json"
    if not path.is_file():
        raise FileNotFoundError(f"groups asset missing: {path}")
    with path.open("r", encoding="utf-8") as f:
        groups = json.load(f)
    if not isinstance(groups, dict) or "g1" not in groups or "g2" not in groups:
        raise ValueError(f"groups asset is invalid: {path}")
    return groups


def list_group_titles(stage: str = "t2i-camera") -> dict[str, list[str]]:
    """Return available G1/G2 group titles for configuration."""
    groups = load_groups(stage)
    return {
        "g1": sorted(groups.get("g1", {}).keys()),
        "g2": sorted(groups.get("g2", {}).keys()),
    }
