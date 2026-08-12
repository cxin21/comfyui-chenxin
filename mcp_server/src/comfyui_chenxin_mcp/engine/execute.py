"""Shared execution engine - one run_skill for all skills.

Layered contract:
  - MCP tool layer (server.py:run) — public; accepts envelope + config dicts.
  - engine.execute.run_skill     — INTERNAL; takes a RunConfig dataclass.
                                The MCP server builds it via SkillData.build_config_fn.
                                Direct callers (e.g. unit tests) MUST construct
                                a RunConfig themselves.

Flow: optional PromptArtifact gate -> upload images -> health -> prepare -> validate -> enqueue -> wait -> download.
"""
from __future__ import annotations

import hashlib
import json
import sys
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
    output_dir: str | Path,
    timeout: float = 1800.0,
    poll_interval: float = 3.0,
) -> tuple[dict[str, Any], int]:
    """Execute a skill stage. Returns (payload, exit_code).

    Generic flow:
    1. Prompt Forge artifact gate
    2. upload stage_images (reference, controlnet)
    3. health check (ComfyUI queue idle)
    4. prepare temp workflow (apply config + G1/G2 modes to UI, upload,
       return stripped API graph with config baked in)
    5. validate + check runtime
    6. enqueue + wait + download

    `config` is the skill's RunConfig dataclass (the engine's internal
    type). The MCP tool layer is the only public caller; it builds the
    RunConfig via `SkillData.build_config_fn(envelope, **tunables)` so
    hosts can keep using JSON-shape inputs.

    `output_dir` accepts either a string (the JSON-RPC shape hosts send)
    or a Path (idiomatic for direct callers). Coerced internally.

    `timeout` (seconds, default 1800.0) bounds the wait for ComfyUI
    to commit the prompt's terminal status. 1800s (30 min) covers the
    MiniMax H3 i2v-video generation observed at ~12 min plus headroom;
    shorter stages (t2i-camera, i2i-camera) finish in <5 min so the
    default is harmless for them. Callers with known-slow stages may
    raise this; callers wanting fast-fail on stuck queues may lower it.

    Returns ``({"accepted": False, "error": ..., "error_type": ...}, 1)``
    on failure. The error message includes the exception class name so
    callers can distinguish infrastructure failures from validation
    failures without parsing prose.
    """
    output_dir = Path(output_dir)
    started = time.monotonic()
    run_dir = output_dir / "runs" / f"{stage.replace('/', '-')}_{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: validate the model-native prompt for prompt-consuming skills.
        prompt_gate_result = None
        if skill_data.prompt_gate_fn is not None:
            prompt_gate_result = skill_data.prompt_gate_fn(config)

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
        # prepare_fn loads UI, applies config + G1/G2 mode toggles,
        # uploads to ComfyUI, and returns the stripped API graph with
        # every config value baked in (config writes to UI pre-strip;
        # strip lifts widget values into API inputs).
        graph = skill_data.prepare_fn(
            mcp,
            stage=stage,
            config=patch_config,
            groups=patch_config.groups,
            mcp_list_loras=mcp.list_loras if patch_config.lora else None,
        )

        # Step 5: validate the exact API graph before enqueueing it.
        validation = mcp.validate_workflow(graph)
        if not isinstance(validation, dict) or validation.get("valid") is not True:
            raise RuntimeError(f"workflow validation failed: {validation}")

        runtime_check = mcp.check_runtime(graph)
        if not isinstance(runtime_check, dict):
            raise RuntimeError(f"workflow runtime check returned an invalid result: {runtime_check}")
        if runtime_check.get("runtime") not in (None, "local"):
            raise RuntimeError(f"workflow uses non-local runtime: {runtime_check}")

        # Step 6: enqueue + wait + download.
        result = mcp.enqueue(graph)
        if isinstance(result, dict) and result.get("node_errors"):
            raise RuntimeError(f"ComfyUI rejected workflow nodes: {result['node_errors']}")
        prompt_id = None
        if isinstance(result, dict):
            prompt_id = result.get("prompt_id") or result.get("promptId")
        if not prompt_id:
            raise RuntimeError(f"enqueue did not return prompt_id: {result}")

        entry = _wait_for_completion(mcp, prompt_id, timeout, poll_interval)
        if skill_data.artifact_mode == "all":
            artifact = _download_artifacts(mcp, entry, output_dir, skill_data.output_type)
        elif skill_data.artifact_mode == "first":
            artifact = _download_artifact(mcp, entry, output_dir, skill_data.output_type)
        else:
            raise ValueError(f"unsupported artifact mode: {skill_data.artifact_mode}")

    except Exception as exc:
        import traceback as _tb
        # Surface the full traceback to stderr so operators (and tests
        # that drain MCP server stderr) can localise the failure without
        # needing to enable a debug mode. The returned payload still has
        # only the message; the traceback is for diagnosis only.
        sys.stderr.write(f"[engine] run_skill({stage}) failed:\n")
        sys.stderr.write(_tb.format_exc())
        sys.stderr.flush()
        from .state import record_attempt
        record_attempt({"stage": stage, "status": "failed",
                         "error": str(exc),
                         "error_type": type(exc).__name__})
        return {
            "accepted": False,
            "stage": stage,
            "error": f"{type(exc).__name__}: {exc}",
            "error_type": type(exc).__name__,
        }, 1

    duration_ms = int((time.monotonic() - started) * 1000)
    # prompt_gate_fn returns the resolved model-native prompt dict.
    # Record it (plus the optional BuildLog ref id) for reproducibility.
    run_record = {
        "schema_version": "2.0",
        "stage": stage,
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "config": asdict(config),
        "prompt": prompt_gate_result if prompt_gate_result is not None else None,
        "prompt_ref": getattr(config, "prompt_ref", None),
    }
    (run_dir / "submitted-graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "run-record.json").write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    from .state import record_attempt
    record_attempt({"stage": stage, "status": "success", "prompt_id": prompt_id,
                     "artifact": _artifact_state_value(artifact)})

    payload: dict[str, Any] = {
        "accepted": True,
        "stage": stage,
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "run_record_path": str(run_dir / "run-record.json"),
        "prompt": prompt_gate_result if prompt_gate_result is not None else None,
        "prompt_ref": getattr(config, "prompt_ref", None),
    }
    return payload, 0


def _artifact_state_value(artifact: dict[str, Any] | list[dict[str, Any]]) -> str | list[str]:
    """Keep state records compact while supporting one or many artifacts."""
    if isinstance(artifact, dict):
        return str(artifact.get("path", ""))
    return [str(item.get("path", "")) for item in artifact if isinstance(item, dict)]


def _wait_for_completion(mcp, prompt_id: str, timeout: float, poll: float) -> dict:
    """Poll get_history_raw until success or failure.

    Bypasses comfyui-mcp's markdown wrapper by calling ComfyUI's
    ``/history/<prompt_id>`` HTTP endpoint directly via ``mcp.get_history_raw``.
    """
    deadline = time.monotonic() + timeout
    while True:
        history = mcp.get_history_raw(prompt_id)
        entry, status_str, error_detail = _parse_history(history, prompt_id)
        if status_str == "success":
            return entry if entry else {"prompt_id": prompt_id, "outputs": {}}
        if status_str == "error":
            raise RuntimeError(f"execution failed: {error_detail}")
        if time.monotonic() >= deadline:
            raise RuntimeError(f"timed out after {timeout:.0f}s")
        time.sleep(poll)


def _parse_history(history, prompt_id: str) -> tuple[dict | None, str | None, str]:
    """Parse the raw ``GET /history/<id>`` response from ComfyUI.

    The wire format is ``{<prompt_id>: {status, outputs, ...}}`` — empty
    dict means the prompt is not yet committed, so we treat that as
    "still running" by returning ``(None, None, "")``.
    """
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
    candidates = _artifact_candidates(entry, output_type)
    if not candidates:
        raise RuntimeError(f"no output {output_type} in history entry")
    return _download_one_artifact(mcp, candidates[0], output_dir)


def _download_artifacts(mcp, entry: dict, output_dir: Path, output_type: str) -> list[dict]:
    """Download every saved output artifact, preserving history order."""
    candidates = [
        item for item in _artifact_candidates(entry, output_type)
        if item.get("type", "output") == "output"
    ]
    if not candidates:
        raise RuntimeError(f"no saved output {output_type} in history entry")
    return [_download_one_artifact(mcp, item, output_dir) for item in candidates]


def _artifact_candidates(entry: dict, output_type: str) -> list[dict]:
    """Collect artifacts from history without discarding batch outputs."""
    outputs = entry.get("outputs", {})
    candidates: list[dict] = []
    for node_id, out in outputs.items():
        if isinstance(out, dict) and isinstance(out.get(output_type), list) and out[output_type]:
            candidates.extend(
                item for item in out[output_type] if isinstance(item, dict)
            )
    return candidates


def _download_one_artifact(mcp, artifact_info: dict, output_dir: Path) -> dict:
    """Download one history artifact and return its verified file record."""

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
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str) and text.startswith("Saved to: "):
                    saved_path = text.removeprefix("Saved to: ").split(" (", 1)[0]
                    candidate = Path(saved_path)
                    if candidate.is_file():
                        data = candidate.read_bytes()
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
