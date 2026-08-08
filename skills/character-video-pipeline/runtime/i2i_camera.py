"""End-to-end image-to-image camera pipeline.

Mandatory entry point for character-video-pipeline i2i-camera. Same prompt
forge gate as t2i_camera; uploads a reference image and (optionally)
controlnet_image, then patches the workflow with img2img activation
(node 21 LoadImage + node 27/59 latent rewire).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from .attempt_state import record_attempt
from .config_schema import RunConfig, STAGES
from .graph_patcher import patch_graph
from .mcp_client import McpClient
from .prompt_forge_bridge import compile_envelope


def run_i2i(
    *,
    mcp: McpClient,
    output_dir: Path,
    config: RunConfig,
    timeout: float = 600.0,
    poll_interval: float = 3.0,
    run_dir: Path | None = None,
) -> tuple[dict[str, Any], int]:
    """Run image-to-image camera generation. Returns (payload, exit_code).

    Caller supplies RunConfig with reference_image (local path, required
    for i2i) and optionally controlnet_image. This function:
    1. Validates prompt-forge envelope
    2. Uploads reference_image and (if provided) controlnet_image
    3. Calls patch_graph with stage=i2i-camera (auto-appends
       "加载图片（G1）" and forces node 27.denoise=0.6)
    4. Validates + submits + polls + downloads via McpClient

    The prompt-forge gate is strict: if prompt-forge rejects the draft or
    marks it not-ready, the run aborts loud. There is no silent fallback.
    """
    started = time.monotonic()
    run_dir = Path(run_dir) if run_dir else output_dir / "runs" / f"i2i-{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)

    if not config.reference_image:
        raise ValueError("RunConfig.reference_image is required for i2i-camera")

    # Step 1: prompt-forge validation gate (strict; raises on reject).
    package = compile_envelope(config.evidence, config.draft, config.dialect_id)

    uploaded_reference: str | None = None
    uploaded_controlnet: str | None = None
    try:
        # Step 2: upload reference_image (required).
        ref_upload = mcp.upload_image(config.reference_image)
        if isinstance(ref_upload, dict):
            uploaded_reference = ref_upload.get("name")
            subfolder = ref_upload.get("subfolder", "")
            if subfolder and uploaded_reference:
                uploaded_reference = f"{subfolder}/{uploaded_reference}"
        if not uploaded_reference:
            raise RuntimeError(f"reference image upload failed: {ref_upload}")

        # Step 3: upload controlnet_image (optional).
        if config.controlnet_image is not None:
            cn_upload = mcp.upload_image(config.controlnet_image)
            if isinstance(cn_upload, dict):
                uploaded_controlnet = cn_upload.get("name")
                subfolder = cn_upload.get("subfolder", "")
                if subfolder and uploaded_controlnet:
                    uploaded_controlnet = f"{subfolder}/{uploaded_controlnet}"
            if not uploaded_controlnet:
                raise RuntimeError(f"controlnet image upload failed: {cn_upload}")

        # Step 4: health + patch + validate + submit + wait + download.
        health = mcp.health()
        if isinstance(health, dict) and isinstance(health.get("queue"), dict):
            q = health["queue"]
            running = len(q.get("running", []))
            pending = len(q.get("pending", []))
            if running or pending:
                raise RuntimeError(f"ComfyUI queue not idle (running={running}, pending={pending})")

        # Build a config copy with post-upload filenames so patch_graph
        # writes the right node inputs.
        patch_config = replace(
            config,
            reference_image=uploaded_reference,
            controlnet_image=uploaded_controlnet,
        )

        graph = patch_graph(
            stage=STAGES.I2I,
            config=patch_config,
            mcp_list_loras=mcp.list_loras if patch_config.lora else None,
        )

        validation = mcp.validate_workflow(graph)
        if isinstance(validation, dict) and validation.get("error_count", 0) > 0:
            raise RuntimeError(f"workflow validation failed: {validation}")

        runtime_check = mcp.check_runtime(graph)
        if isinstance(runtime_check, dict) and runtime_check.get("runtime") != "local":
            raise RuntimeError(f"workflow uses non-local runtime: {runtime_check}")

        result = mcp.enqueue(graph)
        prompt_id = None
        if isinstance(result, dict):
            prompt_id = result.get("prompt_id") or result.get("promptId")
        if not prompt_id:
            raise RuntimeError(f"enqueue did not return prompt_id: {result}")

        entry = _wait_for_completion(mcp, prompt_id, timeout, poll_interval)
        artifact = _download_artifact(mcp, entry, output_dir)

    except Exception as exc:
        record_attempt({"stage": "i2i-camera", "status": "failed", "error": str(exc)})
        return {"accepted": False, "stage": "i2i-camera", "error": str(exc)}, 1

    duration_ms = int((time.monotonic() - started) * 1000)
    run_record = {
        "schema_version": "2.0",
        "stage": "i2i-camera",
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "config": asdict(config),
        "prompt_package_quality": package.get("quality", {}),
    }
    (run_dir / "submitted-graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "run-record.json").write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    record_attempt({
        "stage": "i2i-camera",
        "status": "success",
        "prompt_id": prompt_id,
        "artifact": artifact.get("path"),
    })

    payload: dict[str, Any] = {
        "accepted": True,
        "stage": "i2i-camera",
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "run_record_path": str(run_dir / "run-record.json"),
        "prompt_forge_warnings": package.get("warnings", []),
    }
    return payload, 0


def _wait_for_completion(mcp: McpClient, prompt_id: str, timeout: float, poll: float) -> dict:
    """Poll get_history until the prompt succeeds or fails.

    Supports both response formats:
    - dict (raw ComfyUI /history payload, when JSON-parseable)
    - text (formatted markdown, when get_history returns text)
    """
    import re
    deadline = time.monotonic() + timeout
    while True:
        history = mcp.get_history(prompt_id)
        entry, status_str, error_detail = _parse_history(history, prompt_id)
        if status_str == "success":
            return entry if entry else {"prompt_id": prompt_id, "outputs": {}}
        if status_str == "error":
            raise RuntimeError(f"execution failed: {error_detail}")
        if time.monotonic() >= deadline:
            raise RuntimeError(f"timed out after {timeout:.0f}s")
        time.sleep(poll)


def _parse_history(history: object, prompt_id: str) -> tuple[dict | None, str | None, str]:
    """Extract (entry, status_str, error_detail) from dict or text history.

    Accepts three shapes from McpClient.get_history:
    1. dict keyed by prompt_id (raw ComfyUI /history payload)
    2. dict keyed by a markdown heading like '## Execution: <prompt_id>'
       whose value is a list of text lines — joined into the text path
    3. str — already-formatted markdown
    """
    import re
    if isinstance(history, dict):
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {}) if isinstance(entry, dict) else {}
            status_str = status.get("status_str") if isinstance(status, dict) else None
            error_detail = ""
            if status_str == "error":
                msgs = status.get("messages", []) if isinstance(status, dict) else []
                for m in msgs:
                    if isinstance(m, list) and len(m) == 2 and m[0] == "execution_error":
                        info = m[1] if isinstance(m[1], dict) else {}
                        error_detail = f"node {info.get('node_id')}: {info.get('exception_message')}"
            return entry, status_str, error_detail
        # Fallback: dict whose key carries the prompt_id (e.g. "## Execution: <id>")
        # and whose value is a list of text lines.
        for key, value in history.items():
            if isinstance(key, str) and key.endswith(prompt_id) and isinstance(value, list):
                joined = "\n".join(str(line) for line in value)
                entry, status_str, error_detail = _parse_history_text(joined, prompt_id)
                if status_str is not None:
                    return entry, status_str, error_detail
                return None, None, ""
        return None, None, ""
    if isinstance(history, str):
        return _parse_history_text(history, prompt_id)
    return None, None, ""


def _parse_history_text(text: str, prompt_id: str) -> tuple[dict | None, str | None, str]:
    """Parse the markdown text format used by ComfyUI /history dumps."""
    import re
    if "No history found" in text:
        return None, None, ""
    m = re.search(r"\*\*Status\*\*:\s*(\w+)", text)
    if not m:
        return None, None, ""
    status_str = m.group(1).lower()
    if status_str == "success":
        outputs: dict[str, dict] = {}
        for line_match in re.finditer(
            r"Node\s+(\d+):\s+(\w+)\s+(?:→|->)\s+\*\*([^*]+)\((type=\w+)\)\*\*", text
        ):
            node_id, kind, fname_with_space, type_kv = (
                line_match.group(1),
                line_match.group(2),
                line_match.group(3).strip(),
                line_match.group(4),
            )
            image_type = type_kv.split("=", 1)[1]
            if kind == "images":
                outputs[node_id] = {
                    "images": [{"filename": fname_with_space, "subfolder": "", "type": image_type}]
                }
        return (
            {"prompt_id": prompt_id, "outputs": outputs, "_text": text},
            "success",
            "",
        )
    if status_str == "error":
        node_m = re.search(r"\*\*Failed node\*\*:\s*(\S+)", text)
        exc_m = re.search(r"\*\*Exception\*\*:\s*(.+?)(?:\n|$)", text)
        detail = ""
        if node_m:
            detail = f"node {node_m.group(1)}"
        if exc_m:
            detail = f"{detail}: {exc_m.group(1).strip()}" if detail else exc_m.group(1).strip()
        return None, "error", detail
    return None, None, ""


def _download_artifact(mcp: McpClient, entry: dict, output_dir: Path) -> dict:
    outputs = entry.get("outputs", {})
    image_info = None
    for node_id, out in outputs.items():
        if isinstance(out, dict) and isinstance(out.get("images"), list) and out["images"]:
            image_info = out["images"][0]
            break
    if not image_info:
        raise RuntimeError("no output images in history entry")

    filename = image_info["filename"]
    subfolder = image_info.get("subfolder", "")
    image_type = image_info.get("type", "output")
    raw = mcp.get_image(filename, subfolder, image_type)

    output_dir.mkdir(parents=True, exist_ok=True)
    data: bytes | None = None
    if isinstance(raw, (bytes, bytearray)):
        data = bytes(raw)
    elif isinstance(raw, dict) and "data" in raw:
        import base64
        data = base64.b64decode(raw["data"])
    elif isinstance(raw, list):
        import base64
        for block in raw:
            if isinstance(block, dict) and block.get("type") == "image":
                b64 = block.get("data")
                if isinstance(b64, str):
                    data = base64.b64decode(b64)
                    break

    if data is None:
        return {"filename": filename, "subfolder": subfolder, "bytes": 0, "sha256": ""}

    out_path = output_dir / filename
    out_path.write_bytes(data)
    return {
        "filename": filename,
        "subfolder": subfolder,
        "path": str(out_path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
