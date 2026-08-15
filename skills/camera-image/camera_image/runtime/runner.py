"""camera-image end-to-end runner.

Composes:

1.  Loading the fixed UI workflow asset (no MCP),
2.  Applying the supplied ``RunConfig`` to it,
3.  Converting the patched UI graph to API format locally,
4.  Using :mod:`comfyui_http.ComfyUIClient` to upload inputs, enqueue the
    prompt, wait for completion, and download any image artifacts.

No ``comfyui_chenxin-mcp`` symbol is referenced at runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from comfyui_http import Artifact, ComfyUIClient, UploadedFile

from .config_schema import STAGES, RunConfig
from .contracts import validate_api_graph
from .graph_patcher import apply_run_config
from .lora_resolver import (
    DEFAULT_LORA_STACK_TEXT,
    build_lora_patch,
    parse_lora_inventory,
)
from .source_workflow import _load_groups, _load_source_ui, compute_enabled_groups
from .ui_to_api import strip_workflow


@dataclass(frozen=True)
class RunResult:
    """Bundle of facts about a single ``camera-image run`` invocation."""

    prompt_id: str
    api_graph_sha256: str
    artifacts: tuple[Artifact, ...]
    upload_summary: tuple[UploadedFile, ...]
    lora_stack: str


def _hash_graph(graph: dict[str, Any]) -> str:
    import hashlib

    encoded = json.dumps(graph, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _apply_modes_to_ui(
    ui: dict[str, Any],
    enabled_g1: set[str],
    enabled_g2: set[str],
    groups_meta: dict[str, Any],
) -> None:
    node_ids = {
        str(node.get("id"))
        for node in ui.get("nodes", [])
        if isinstance(node, dict) and node.get("id") is not None
    }
    enable_nodes: set[str] = set()
    bypass_nodes: set[str] = set()
    for title, members in groups_meta.get("g1", {}).items():
        if not isinstance(members, list):
            continue
        target = enable_nodes if title in enabled_g1 else bypass_nodes
        for member in members:
            if str(member) in node_ids:
                target.add(str(member))
    for title, members in groups_meta.get("g2", {}).items():
        if not isinstance(members, list):
            continue
        target = enable_nodes if title in enabled_g2 else bypass_nodes
        for member in members:
            if str(member) in node_ids:
                target.add(str(member))
    for node in ui.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id"))
        if node_id in enable_nodes:
            node["mode"] = 0
        elif node_id in bypass_nodes:
            node["mode"] = 4


def _build_api_graph(*, stage: str, config: RunConfig) -> dict[str, Any]:
    ui = _load_source_ui()
    apply_run_config(ui, stage=stage, config=config)
    groups_meta = _load_groups(stage)
    enabled_g1, enabled_g2 = compute_enabled_groups(stage, getattr(config, "groups", None))
    _apply_modes_to_ui(ui, enabled_g1, enabled_g2, groups_meta)
    api_graph = strip_workflow(ui)
    validate_api_graph(api_graph)
    return api_graph


def _resolve_lora_stack(config: RunConfig, inventory: list[str] | None) -> str:
    selections = getattr(config, "lora", None)
    if not selections:
        return DEFAULT_LORA_STACK_TEXT
    return build_lora_patch(selections, inventory or [])


def _upload_inputs(
    client: ComfyUIClient,
    config: RunConfig,
    stage: str,
) -> list[UploadedFile]:
    paths: list[Path] = []
    inputs: list[tuple[str, Path]] = []
    for field_name in ("reference_image", "controlnet_image"):
        path = getattr(config, field_name, None)
        if path is not None:
            inputs.append((field_name, Path(path)))
            paths.append(Path(path))
    if stage == STAGES.I2I and not any(name == "reference_image" for name, _ in inputs):
        raise ValueError("i2i-camera stage requires a 'reference_image' in config")
    return [client.upload_image(path) for path in paths]


def _download_artifacts(client: ComfyUIClient, config: RunConfig) -> tuple[Artifact, ...]:
    artifacts: list[Artifact] = []
    declared = getattr(config, "artifacts", None) or []
    for entry in declared:
        artifact = client.get_artifact(
            filename=entry["filename"],
            subfolder=entry.get("subfolder", ""),
            artifact_type=entry.get("type", "output"),
        )
        artifacts.append(artifact)
    return tuple(artifacts)


def run(
    client: ComfyUIClient,
    *,
    stage: str,
    config: RunConfig,
    inventory: list[str] | None = None,
    timeout: float = 1800.0,
    poll_interval: float = 2.0,
) -> RunResult:
    """End-to-end ``run`` against the supplied client."""
    if stage not in (STAGES.T2I, STAGES.I2I):
        raise ValueError(f"unsupported stage: {stage}")
    api_graph = _build_api_graph(stage=stage, config=config)
    api_graph_sha256 = _hash_graph(api_graph)
    uploads = _upload_inputs(client, config, stage)
    lora_stack = _resolve_lora_stack(config, inventory)
    prompt_id = client.enqueue(api_graph)
    client.wait_for_success(prompt_id, timeout=timeout, poll_interval=poll_interval)
    artifacts = _download_artifacts(client, config)
    return RunResult(
        prompt_id=prompt_id,
        api_graph_sha256=api_graph_sha256,
        artifacts=artifacts,
        upload_summary=tuple(uploads),
        lora_stack=lora_stack,
    )


def inventory_from_path(path: Path) -> list[str]:
    """Load a LoRA inventory from a JSON file produced by the operator."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return parse_lora_inventory(raw)
