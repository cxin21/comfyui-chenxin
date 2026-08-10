"""Prepare a fixed API graph without UI conversion or runtime graph repair."""

from __future__ import annotations

from typing import Any

from .assets import load_fixed_workflow
from .config_schema import RunConfig
from .contracts import validate_api_graph
from .graph_patcher import apply_run_config


def prepare_workflow(
    mcp,
    *,
    stage: str,
    config: RunConfig,
    groups=None,
    mcp_list_loras=None,
    **_: Any,
) -> dict[str, Any]:
    """Load, patch, and validate one fixed video API graph."""
    graph = load_fixed_workflow(stage)
    patched = apply_run_config(graph, stage, config)
    validate_api_graph(patched, stage)
    return patched
