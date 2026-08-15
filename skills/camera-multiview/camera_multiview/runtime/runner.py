"""camera-multiview runner — uses comfyui_http, never imports comfyui_chenxin_mcp."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from comfyui_http import Artifact, ComfyUIClient, UploadedFile


@dataclass(frozen=True)
class RunResult:
    prompt_id: str
    api_graph_sha256: str
    artifacts: tuple[Artifact, ...]
    upload_summary: tuple[UploadedFile, ...]


def _hash_graph(graph: dict[str, Any]) -> str:
    import hashlib

    encoded = json.dumps(graph, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_api_graph(*, full_body: str, face: str) -> dict[str, Any]:
    """Fixed multiview graph — nodes 111 (body) and 667 (face) per design §8.3."""
    return {
        "111": {
            "class_type": "Flux2KleinMultiViewBody",
            "inputs": {"image": full_body},
        },
        "667": {
            "class_type": "Flux2KleinMultiViewFace",
            "inputs": {"image": face},
        },
    }


def _upload_inputs(client: ComfyUIClient, body: Path, face: Path) -> list[UploadedFile]:
    return [client.upload_image(body), client.upload_image(face)]


def _download_artifacts(client: ComfyUIClient) -> tuple[Artifact, ...]:
    return tuple(
        client.get_artifact(filename=name, subfolder="", artifact_type="output")
        for name in ("front.png", "back.png", "left.png", "right.png", "three_quarter.png")
    )


def run(
    client: ComfyUIClient,
    *,
    full_body_image: Path,
    face_image: Path,
    timeout: float = 1800.0,
    poll_interval: float = 2.0,
) -> RunResult:
    api_graph = _build_api_graph(full_body=full_body_image.name, face=face_image.name)
    api_graph_sha256 = _hash_graph(api_graph)
    uploads = _upload_inputs(client, full_body_image, face_image)
    prompt_id = client.enqueue(api_graph)
    client.wait_for_success(prompt_id, timeout=timeout, poll_interval=poll_interval)
    artifacts = _download_artifacts(client)
    return RunResult(
        prompt_id=prompt_id,
        api_graph_sha256=api_graph_sha256,
        artifacts=artifacts,
        upload_summary=tuple(uploads),
    )
