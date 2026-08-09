"""Runtime source UI workflow -> API workflow pipeline.

Single source of truth: the bundled fixed UI asset ``camera-anima.json``.
Per-stage ``groups.json`` (committed mapping of group titles to node id
lists) drives which G1/G2 groups are enabled for the run.

Every run performs:
1.  Load the fixed UI workflow asset and verify its digest/fingerprint.
2.  (Optional) Apply ``RunConfig`` tunables to the UI workflow by
    writing into each node's ``widgets_values`` list (single source of
    truth that ComfyUI's strip step consumes).
3.  Compute enabled G1/G2 titles (DEFAULT + user + stage-mandatory).
4.  Apply ``mode=0`` / ``mode=4`` to nodes in the in-memory copy.
5.  Convert the in-memory UI graph with MCP ``strip_workflow(graph)``.

The returned API dict has no ``mode`` fields (strip removed them) and
carries every tunable baked in (because config was written to the UI
**before** strip).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config_schema import (
    DEFAULT_ENABLED_G1,
    DEFAULT_ENABLED_G2,
    GroupsConfig,
    MANDATORY_GROUPS_BY_STAGE,
    STAGES,
)
from .contracts import validate_api_graph


SOURCE_WORKFLOW_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent
    / "camera_image"
    / "runtime"
    / "workflow_assets"
    / "camera-anima.json"
)


def _load_source_ui() -> dict[str, Any]:
    """Load the committed source UI workflow from disk."""
    from .workflow_assets import load_fixed_workflow

    ui = load_fixed_workflow("camera-anima.json")
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
        Path(__file__).resolve().parent.parent.parent
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
    groups: GroupsConfig | None = None,
) -> tuple[set[str], set[str]]:
    """Compute the final enabled G1/G2 titles for this run.

    Union: defaults + user + stage-mandatory. User cannot disable
    defaults (per spec). Accepts ``GroupsConfig | None`` directly and
    handles every None case internally so callers do not need
    defensive ``list()`` conversions.
    """
    groups_meta = _load_groups(stage)
    known_g1 = set(groups_meta.get("g1", {}))
    known_g2 = set(groups_meta.get("g2", {}))
    user_g1 = list(groups.g1) if groups and groups.g1 else []
    user_g2 = list(groups.g2) if groups and groups.g2 else []
    unknown_g1 = set(user_g1) - known_g1
    unknown_g2 = set(user_g2) - known_g2
    if unknown_g1 or unknown_g2:
        unknown = sorted(unknown_g1 | unknown_g2)
        raise ValueError(f"unknown group title(s) for {stage}: {unknown}")
    final_g1: set[str] = set(user_g1) | set(DEFAULT_ENABLED_G1)
    final_g2: set[str] = set(user_g2) | set(DEFAULT_ENABLED_G2)
    for mandatory in MANDATORY_GROUPS_BY_STAGE.get(stage, []):
        final_g1.add(mandatory)
    missing_g1 = final_g1 - known_g1
    missing_g2 = final_g2 - known_g2
    if missing_g1 or missing_g2:
        missing = sorted(missing_g1 | missing_g2)
        raise ValueError(f"configured default group title(s) missing from {stage}: {missing}")
    return final_g1, final_g2


def _validate_group_metadata(
    ui: dict[str, Any],
    groups_meta: dict[str, Any],
) -> None:
    """Ensure group membership is a valid projection of the fixed UI graph."""
    node_ids = {str(node.get("id")) for node in ui.get("nodes", []) if isinstance(node, dict)}
    for bucket in ("g1", "g2"):
        mapping = groups_meta.get(bucket)
        if not isinstance(mapping, dict):
            raise ValueError(f"groups metadata {bucket!r} must be an object")
        for title, members in mapping.items():
            if not isinstance(title, str) or not title:
                raise ValueError(f"groups metadata {bucket!r} has an invalid title")
            if not isinstance(members, list):
                raise ValueError(f"group {title!r} members must be a list")
            missing = sorted(
                str(member) for member in members if str(member) not in node_ids
            )
            if missing:
                raise ValueError(
                    f"group {title!r} references missing source node(s): {missing}"
                )


def _apply_modes_to_ui(
    ui: dict[str, Any],
    enabled_g1: set[str],
    enabled_g2: set[str],
    groups_meta: dict[str, Any],
) -> dict[str, Any]:
    """Set ``mode=0`` for enabled G1/G2 nodes, ``mode=4`` for the rest.

    Mutates the UI dict in place; returns it for chaining.
    """
    _validate_group_metadata(ui, groups_meta)
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
    mcp: Any,
    *,
    stage: str = STAGES.T2I,
    config: Any = None,
    groups: GroupsConfig | None = None,
    mcp_list_loras: Any = None,
) -> dict[str, Any]:
    """Build an API graph from the fixed UI asset via MCP strip.

    Steps:
    1.  Load the pinned UI workflow asset.
    2.  Apply every config value to the UI widget surface.
    3.  Compute enabled G1/G2 titles and apply node modes.
    4.  Convert the patched UI graph with MCP ``strip_workflow(graph)``.

    The returned dict is the graph produced by the maintained converter.
    No saved-workflow round trip or post-conversion graph mutation is
    allowed: the UI asset and the strip result are the two authorities.

    Accepts ``GroupsConfig | None`` directly; passes it through to
    ``compute_enabled_groups`` which handles every None case.
    """
    ui = _load_source_ui()

    if config is not None:
        # Apply config BEFORE mode toggles: config writes to
        # widgets_values, mode toggles write to mode. Both target the
        # UI dict; ordering is irrelevant functionally but matches the
        # documented flow (config first, then enable groups).
        from .graph_patcher import apply_run_config
        apply_run_config(
            ui,
            stage=stage,
            config=config,
            mcp_list_loras=mcp_list_loras,
        )

    groups_meta = _load_groups(stage)
    _validate_group_metadata(ui, groups_meta)
    enabled_g1, enabled_g2 = compute_enabled_groups(stage, groups)
    _apply_modes_to_ui(ui, enabled_g1, enabled_g2, groups_meta)

    api_graph = mcp.strip_workflow(ui)
    if not isinstance(api_graph, dict) or not api_graph:
        raise ValueError("strip_workflow returned an empty API graph")
    validate_api_graph(api_graph)
    return api_graph
