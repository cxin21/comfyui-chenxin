"""camera-video runner — uses comfyui_http, never imports comfyui_chenxin_mcp."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from comfyui_http import Artifact, ComfyUIClient, UploadedFile


VIDEO_STAGES = ("t2v-video", "i2v-video", "multi-i2v-video")


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


def _build_api_graph(
    *,
    stage: str,
    prompt_text: str,
    duration: float,
    references: tuple[str, ...],
) -> dict[str, Any]:
    if stage == "t2v-video":
        if not 2 <= duration <= 15:
            raise ValueError("duration must be between 2 and 15 seconds")
        return {
            "1": {
                "class_type": "MiniMaxH3TextToVideo",
                "inputs": {"prompt": prompt_text, "duration_seconds": duration},
            }
        }
    if stage == "i2v-video":
        if not 2 <= duration <= 15:
            raise ValueError("duration must be between 2 and 15 seconds")
        if len(references) != 1:
            raise ValueError("i2v-video requires exactly 1 reference_image")
        return {
            "1": {
                "class_type": "MiniMaxH3ImageToVideo",
                "inputs": {
                    "prompt": prompt_text,
                    "duration_seconds": duration,
                    "reference_image_1": references[0],
                },
            }
        }
    if stage == "multi-i2v-video":
        if not 2 <= duration <= 15:
            raise ValueError("duration must be between 2 and 15 seconds")
        if not 1 <= len(references) <= 3:
            raise ValueError("multi-i2v-video requires 1..3 reference_images")
        graph: dict[str, Any] = {
            "1": {
                "class_type": "MiniMaxH3MultiImageToVideo",
                "inputs": {"prompt": prompt_text, "duration_seconds": duration},
            }
        }
        for index, name in enumerate(references, start=1):
            graph["1"]["inputs"][f"reference_image_{index}"] = name
        return graph
    raise ValueError(f"unsupported stage: {stage}")


def _upload_inputs(client: ComfyUIClient, reference_paths: tuple[Path, ...]) -> list[UploadedFile]:
    return [client.upload_image(path) for path in reference_paths]


def _download_artifacts(client: ComfyUIClient) -> tuple[Artifact, ...]:
    return (client.get_artifact(filename="output.mp4", subfolder="", artifact_type="output"),)


def run(
    client: ComfyUIClient,
    *,
    stage: str,
    prompt_text: str,
    duration: float,
    reference_paths: tuple[Path, ...] = (),
    timeout: float = 1800.0,
    poll_interval: float = 2.0,
) -> RunResult:
    if stage not in VIDEO_STAGES:
        raise ValueError(f"unsupported video stage: {stage}")
    api_graph = _build_api_graph(
        stage=stage,
        prompt_text=prompt_text,
        duration=duration,
        references=tuple(path.name for path in reference_paths),
    )
    api_graph_sha256 = _hash_graph(api_graph)
    uploads = _upload_inputs(client, reference_paths)
    prompt_id = client.enqueue(api_graph)
    client.wait_for_success(prompt_id, timeout=timeout, poll_interval=poll_interval)
    artifacts = _download_artifacts(client)
    return RunResult(
        prompt_id=prompt_id,
        api_graph_sha256=api_graph_sha256,
        artifacts=artifacts,
        upload_summary=tuple(uploads),
    )
