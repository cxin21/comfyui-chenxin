"""Shared execution engine - one run_skill for all skills.

Replaces t2i_camera.run_t2i + i2i_camera.run_i2i (80+ lines of duplicated code).
Flow: prompt-forge gate -> upload images -> health -> prepare -> apply -> validate -> enqueue -> wait -> download.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from .skill_data import SkillData


def run_skill(
    *,
    mcp,
    skill_data: SkillData,
    stage: str,
    config,
    output_dir: Path,
    timeout: float = 600.0,
    poll_interval: float = 3.0,
) -> tuple[dict[str, Any], int]:
    """Execute a skill stage. Returns (payload, exit_code).

    Generic flow:
    1. prompt-forge gate (compile_envelope)
    2. upload stage_images (reference, controlnet)
    3. health check (ComfyUI queue idle)
    4. prepare temp workflow (copy source + patch groups + upload)
    5. apply run config (write tunables to graph)
    6. validate + check runtime
    7. enqueue + wait + download
    """
    started = time.monotonic()
    run_dir = output_dir / "runs" / f"{stage.replace('/', '-')}_{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: prompt-forge gate.
        from runtime.prompt_forge_bridge import compile_envelope
        package = compile_envelope(config.evidence, config.draft, skill_data.dialect_id)

        # Step 2: upload stage_images.
        patch_config = config
        for spec in skill_data.stage_images.get(stage, ()):
            val = getattr(config, spec.config_key, None)
            if spec.required and not val:
                raise ValueError(f"{spec.config_key} is required for {stage}")
            if val:
                upload_result = mcp.upload_image(val)
                uploaded = None
                if isinstance(upload_result, dict):
                    uploaded = upload_result.get("name")
                    subfolder = upload_result.get("subfolder", "")
                    if subfolder and uploaded:
                        uploaded = f"{subfolder}/{uploaded}"
                if not uploaded:
                    raise RuntimeError(f"{spec.config_key} upload failed: {upload_result}")
                patch_config = replace(patch_config, **{spec.config_key: uploaded})

        # Step 3: health check.
        health = mcp.health()
        if isinstance(health, dict) and isinstance(health.get("queue"), dict):
            q = health["queue"]
            if len(q.get("running", [])) or len(q.get("pending", [])):
                raise RuntimeError(f"ComfyUI queue not idle (running={len(q.get('running', []))}, pending={len(q.get('pending', []))})")

        # Step 4: prepare temp workflow.
        graph = skill_data.prepare_fn(
            mcp,
            stage=stage,
            user_g1=list(patch_config.groups.g1) if patch_config.groups else None,
            user_g2=list(patch_config.groups.g2) if patch_config.groups else None,
        )

        # Step 5: apply run config.
        skill_data.apply_fn(
            graph,
            stage=stage,
            config=patch_config,
            mcp_list_loras=mcp.list_loras if patch_config.lora else None,
        )

        # Step 6: validate + check runtime.
        validation = mcp.validate_workflow(graph)
        if isinstance(validation, dict) and validation.get("error_count", 0) > 0:
            raise RuntimeError(f"workflow validation failed: {validation}")

        runtime_check = mcp.check_runtime(graph)
        if isinstance(runtime_check, dict) and runtime_check.get("runtime") != "local":
            raise RuntimeError(f"workflow uses non-local runtime: {runtime_check}")

        # Step 7: enqueue + wait + download.
        result = mcp.enqueue(graph)
        prompt_id = None
        if isinstance(result, dict):
            prompt_id = result.get("prompt_id") or result.get("promptId")
        if not prompt_id:
            raise RuntimeError(f"enqueue did not return prompt_id: {result}")

        entry = _wait_for_completion(mcp, prompt_id, timeout, poll_interval)
        artifact = _download_artifact(mcp, entry, output_dir, skill_data.output_type)

    except Exception as exc:
        from runtime.attempt_state import record_attempt
        record_attempt({"stage": stage, "status": "failed", "error": str(exc)})
        return {"accepted": False, "stage": stage, "error": str(exc)}, 1

    duration_ms = int((time.monotonic() - started) * 1000)
    run_record = {
        "schema_version": "2.0",
        "stage": stage,
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

    from runtime.attempt_state import record_attempt
    record_attempt({"stage": stage, "status": "success", "prompt_id": prompt_id,
                     "artifact": artifact.get("path")})

    payload: dict[str, Any] = {
        "accepted": True,
        "stage": stage,
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "run_record_path": str(run_dir / "run-record.json"),
        "prompt_forge_warnings": package.get("warnings", []),
    }
    return payload, 0


def _wait_for_completion(mcp, prompt_id: str, timeout: float, poll: float) -> dict:
    """Poll get_history until success or failure."""
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


def _parse_history(history, prompt_id: str) -> tuple[dict | None, str | None, str]:
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
        return None, None, ""
    return None, None, ""


def _download_artifact(mcp, entry: dict, output_dir: Path, output_type: str) -> dict:
    """Download the first output artifact (image or video)."""
    outputs = entry.get("outputs", {})
    artifact_info = None
    for node_id, out in outputs.items():
        if isinstance(out, dict) and isinstance(out.get(output_type), list) and out[output_type]:
            artifact_info = out[output_type][0]
            break
    if not artifact_info:
        raise RuntimeError(f"no output {output_type} in history entry")

    filename = artifact_info["filename"]
    subfolder = artifact_info.get("subfolder", "")
    image_type = artifact_info.get("type", "output")
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
            if isinstance(block, dict) and block.get("type") in ("image", "video"):
                b64 = block.get("data")
                if isinstance(b64, str):
                    data = base64.b64decode(b64)
                    break

    if data is None:
        raise RuntimeError(f"artifact download returned no data for {filename}")

    out_path = output_dir / filename
    out_path.write_bytes(data)
    return {
        "filename": filename,
        "subfolder": subfolder,
        "path": str(out_path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
