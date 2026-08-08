"""Runtime source UI workflow -> API workflow pipeline.

Single source of truth: ``workflow/source/文生图相机视角.json`` (UI workflow).
Per-stage ``groups.json`` (committed mapping of group titles to node id
lists) drives which G1/G2 groups are enabled for the run.

Every run performs:
1.  Load source UI workflow from disk.
2.  (Optional) Apply ``RunConfig`` tunables to the UI workflow by
    writing into each node's ``widgets_values`` list (single source of
    truth that ComfyUI's strip step consumes).
3.  Compute enabled G1/G2 titles (DEFAULT + user + stage-mandatory).
4.  Apply ``mode=0`` / ``mode=4`` to nodes in the in-memory copy.
5.  Write the copy to a unique ``temp_*.json`` file in the system temp
    dir.
6.  Hand the file to the ComfyUI server via MCP ``save_workflow``.
7.  ``get_workflow(filename, format="api")`` returns the API graph.
8.  Local temp file is deleted.

The returned API dict has no ``mode`` fields (strip removed them) and
carries every tunable baked in (because config was written to the UI
**before** strip).
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
    GroupsConfig,
    MANDATORY_GROUPS_BY_STAGE,
    STAGES,
)


SOURCE_WORKFLOW_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent
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
    user_g1 = list(groups.g1) if groups and groups.g1 else []
    user_g2 = list(groups.g2) if groups and groups.g2 else []
    final_g1: set[str] = set(user_g1) | set(DEFAULT_ENABLED_G1)
    final_g2: set[str] = set(user_g2) | set(DEFAULT_ENABLED_G2)
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
    mcp: Any,
    *,
    stage: str = STAGES.T2I,
    config: Any = None,
    groups: GroupsConfig | None = None,
    mcp_list_loras: Any = None,
) -> dict[str, Any]:
    """Build an API graph for the run via temp file + MCP strip.

    Steps:
    1.  Load source UI workflow from disk.
    2.  If ``config`` is provided, apply tunables (sampling, camera,
        LoRA, prompts, image_size, seed, controlnet image, reference
        image) to the UI workflow's ``widgets_values`` so the strip
        step propagates them to the final API graph. Runs **before**
        mode toggles so config and mode write to disjoint keys
        (config -> widgets_values, mode -> mode).
    3.  Compute enabled G1/G2 titles (DEFAULT + user + stage-mandatory).
    4.  Apply ``mode`` field to nodes in an in-memory copy.
    5.  Write the copy to a unique ``temp_*.json`` file in the system
        temp dir.
    6.  Upload to ComfyUI via MCP ``save_workflow``.
    7.  ``get_workflow(filename, format="api")`` returns the API graph.
    8.  Local temp file is always deleted.

    The returned dict carries every tunable baked in (config was
    applied to UI pre-strip) and has no ``mode`` fields (strip removed
    them).

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
    enabled_g1, enabled_g2 = compute_enabled_groups(stage, groups)
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

    # i2i latent-rewire activation + per-stage WORKFLOW_CONVENTIONS run
    # HERE — after the strip, on the API graph. Doing them on the UI
    # graph (pre-strip) KeyErrors because UI nodes live in
    # graph["nodes"], not keyed by id.
    #
    # 1. Apply per-stage denoise_override (e.g. i2i denoise=0.6 on node 27).
    # 2. For i2i: rewire KSampler latent from EmptyLatentImage to
    #    VAEEncode of the uploaded reference_image.
    from .config_schema import WORKFLOW_CONVENTIONS
    if stage in WORKFLOW_CONVENTIONS:
        for nid, value in WORKFLOW_CONVENTIONS[stage].get("denoise_override", {}).items():
            api_graph[nid]["inputs"]["denoise"] = value

    if stage == STAGES.I2I:
        if config is None or not getattr(config, "reference_image", None):
            raise ValueError("reference_image is required for i2i-camera")
        from .graph_patcher import _activate_img2img
        _activate_img2img(api_graph, config.reference_image)

    # Belt-and-braces: ensure node 26's text input is present post-strip.
    # ComfyUI's server-side strip occasionally drops the ``text`` widget on
    # the Lora Loader (LoraManager) because of the custom AUTOCOMPLETE_TEXT_LORAS
    # type declaration. We resolve the stack text from the resolver (same
    # logic as the pre-strip patcher; falls back to DEFAULT_LORA_STACK_TEXT
    # when config.lora is None) and write it directly into the API dict so
    # the run never fails on "Required input is missing (text)".
    from .graph_patcher import _ensure_lora_text, build_lora_patch
    lora_patch = build_lora_patch(
        run_config_lora=getattr(config, "lora", None) if config is not None else None,
        mcp_list_loras=getattr(mcp, "list_loras", None) if hasattr(mcp, "list_loras") else None,
    )
    _ensure_lora_text(api_graph, lora_patch["node_26"]["text"])

    return api_graph