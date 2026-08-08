"""Runtime source UI workflow -> API workflow pipeline.

Single source of truth: ``workflow/source/文生图相机视角.json`` (UI workflow).
Per-stage ``groups.json`` (committed mapping of group titles to node id
lists) drives which G1/G2 groups are enabled for the run.

Every run performs:
1.  Load source UI workflow from disk.
2.  Compute enabled G1/G2 titles (DEFAULT + user + stage-mandatory).
3.  Apply ``mode=0`` / ``mode=4`` to nodes in a temporary copy.
4.  Write the copy to a unique ``temp_*.json`` file in the system temp
    dir.
5.  Hand the file to the ComfyUI server via MCP ``save_workflow``.
6.  ``get_workflow(filename, format="api")`` returns the API graph.
7.  Local temp file is deleted.

The returned API dict has no ``mode`` fields — strip removed them.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .config_schema import (
    DEFAULT_ENABLED_G1,
    DEFAULT_ENABLED_G2,
    MANDATORY_GROUPS_BY_STAGE,
    STAGES,
)
from .mcp_client import McpClient


SOURCE_WORKFLOW_PATH: Path = (
    Path(__file__).resolve().parent.parent
    / "workflow"
    / "source"
    / "文生图相机视角.json"
)


def _load_source_ui() -> dict[str, Any]:
    """Load the committed source UI workflow from disk."""
    if not SOURCE_WORKFLOW_PATH.is_file():
        raise FileNotFoundError(
            f"source UI workflow missing: {SOURCE_WORKFLOW_PATH}"
        )
    with SOURCE_WORKFLOW_PATH.open("r", encoding="utf-8") as f:
        ui = json.load(f)
    if not isinstance(ui, dict) or "nodes" not in ui or "groups" not in ui:
        raise ValueError(
            f"source UI workflow is not a UI-format workflow: {SOURCE_WORKFLOW_PATH}"
        )
    return ui


def _load_groups(stage: str) -> dict[str, Any]:
    """Load the per-stage groups.json (title -> node id list).

    Source UI workflow JSON does not embed member node ids per group; the
    hand-curated ``workflow/<stage>/groups.json`` is the source of truth
    for the title -> id mapping.
    """
    if stage not in (STAGES.T2I, STAGES.I2I):
        raise ValueError(f"unsupported camera stage: {stage}")
    groups_path = (
        Path(__file__).resolve().parent.parent
        / "workflow"
        / stage
        / "groups.json"
    )
    if not groups_path.is_file():
        raise FileNotFoundError(f"groups asset missing: {groups_path}")
    with groups_path.open("r", encoding="utf-8") as f:
        groups = json.load(f)
    if not isinstance(groups, dict) or "g1" not in groups or "g2" not in groups:
        raise ValueError(f"groups asset is invalid: {groups_path}")
    return groups


def compute_enabled_groups(
    stage: str,
    user_g1: list[str] | None,
    user_g2: list[str] | None,
) -> tuple[set[str], set[str]]:
    """Compute the final enabled G1/G2 titles for this run.

    Union: defaults + user + stage-mandatory. User cannot disable
    defaults (per spec).
    """
    final_g1: set[str] = set(user_g1 or []) | set(DEFAULT_ENABLED_G1)
    final_g2: set[str] = set(user_g2 or []) | set(DEFAULT_ENABLED_G2)
    for mandatory in MANDATORY_GROUPS_BY_STAGE.get(stage, []):
        final_g1.add(mandatory)
    return final_g1, final_g2


def _apply_modes_to_ui(
    ui: dict[str, Any],
    enabled_g1: set[str],
    enabled_g2: set[str],
    groups_meta: dict[str, Any],
) -> dict[str, Any]:
    """Set ``mode=0`` for enabled G1/G2 nodes, ``mode=4`` for the rest.

    Mutates the UI dict in place; returns it for chaining.
    """
    g1_groups = groups_meta.get("g1", {})
    g2_groups = groups_meta.get("g2", {})

    enable_nodes: set[int] = set()
    bypass_nodes: set[int] = set()

    for title, members in g1_groups.items():
        if not isinstance(members, list):
            continue
        if title in enabled_g1:
            enable_nodes.update(members)
        else:
            bypass_nodes.update(members)
    for title, members in g2_groups.items():
        if not isinstance(members, list):
            continue
        if title in enabled_g2:
            enable_nodes.update(members)
        else:
            bypass_nodes.update(members)

    for node in ui.get("nodes", []):
        if not isinstance(node, dict):
            continue
        nid = node.get("id")
        if nid in enable_nodes:
            node["mode"] = 0
        elif nid in bypass_nodes:
            node["mode"] = 4
    return ui


def prepare_temporary_workflow(
    mcp: McpClient,
    *,
    stage: str = STAGES.T2I,
    user_g1: list[str] | None = None,
    user_g2: list[str] | None = None,
) -> dict[str, Any]:
    """Build an API graph for the run via temp file + MCP strip.

    Steps:
    1.  Load source UI workflow from disk.
    2.  Compute enabled G1/G2 titles (DEFAULT + user + stage-mandatory).
    3.  Apply ``mode`` field to nodes in an in-memory copy.
    4.  Write the copy to a unique ``temp_*.json`` file in the system
        temp dir.
    5.  Upload to ComfyUI via MCP ``save_workflow``.
    6.  ``get_workflow(filename, format="api")`` returns the API graph.
    7.  Local temp file is always deleted.

    The returned dict has no ``mode`` fields (strip removed them) and
    is ready for the patcher's tunables step.
    """
    ui = _load_source_ui()
    groups_meta = _load_groups(stage)
    enabled_g1, enabled_g2 = compute_enabled_groups(stage, user_g1, user_g2)
    _apply_modes_to_ui(ui, enabled_g1, enabled_g2, groups_meta)

    fd, temp_path = tempfile.mkstemp(prefix="temp_", suffix=".json")
    os.close(fd)
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(ui, f, ensure_ascii=False)

        temp_filename = os.path.basename(temp_path)
        mcp.save_workflow(temp_filename, ui)
        # get_workflow(format="api") returns the API JSON dict; strip_workflow
        # via subprocess MCP returns only a markdown summary, so we use
        # get_workflow instead. Both code paths (subprocess MCP and host-injected
        # MCP) return the same 42-node dict.
        api_graph = mcp.get_workflow(filename=temp_filename, format="api")
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    return api_graph