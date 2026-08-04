"""Explicit local REST orchestration after plan approval and consumption.

This module is the small, auditable bridge between the pure runtime contracts
and a local ComfyUI HTTP server.  It does not approve plans or infer graphs:
callers must provide the approved plan, canonical consumption evidence and
the profile/capability evidence needed to reconstruct the exact submission.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from pathlib import Path

from .capabilities import build_capability_report
from .comfy_api import ComfyApi
from .comfy_submit import ComfyPromptSubmitter
from .stage_execution import (
    StageExecutionError,
    build_stage_submission,
    submit_stage,
)
from .execution import build_character_base_submission, submit_character_base


_REST_ADAPTER = {
    "name": "prompt-forge-rest",
    "version": "1.0",
    "tools": [],
    "runtime_classification": "local",
}


def _validate_timeout(timeout: object) -> float:
    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise StageExecutionError("local orchestrator timeout must be a positive finite number")
    return float(timeout)


def _require_idle(report: dict) -> None:
    try:
        queue = report["queue"]
        running = queue["running"]
        pending = queue["pending"]
    except (KeyError, TypeError) as exc:
        raise StageExecutionError("live CapabilityReport queue evidence is incomplete") from exc
    if running or pending:
        raise StageExecutionError("local ComfyUI queue is not idle; no stage was submitted")


def submit_stage_via_local_rest(
    approved_plan: dict,
    source_api_graph: dict,
    consumption: dict,
    consumption_path: str | Path,
    *,
    profile: dict,
    capability_report: dict,
    base_url: str = "http://127.0.0.1:8188",
    timeout: float = 30.0,
    ui_workflow: dict | None = None,
    reference_image_name: str | None = None,
    reference_artifact: dict | None = None,
    image_ref: dict | None = None,
) -> dict:
    """Build, guard and enqueue one consumed Stage 3/4 submission.

    A fresh read-only report guards the queue immediately before POST.  The
    approved/frozen report is still passed to ``build_stage_submission`` and
    remains part of the plan hash; the fresh report cannot rewrite that plan.
    ``submit_stage`` then owns the exclusive intent/receipt sentinel.
    """
    timeout_value = _validate_timeout(timeout)
    api = ComfyApi(base_url=base_url, timeout=timeout_value)
    frozen_url = capability_report.get("comfyui", {}).get("url") if isinstance(capability_report, dict) else None
    if isinstance(frozen_url, str) and frozen_url.rstrip("/") != api.base_url:
        raise StageExecutionError("live ComfyUI URL does not match the approved CapabilityReport")
    live_report = build_capability_report(api, _REST_ADAPTER, datetime.now(timezone.utc))
    _require_idle(live_report)

    optional = {
        key: value
        for key, value in {
            "ui_workflow": ui_workflow,
            "reference_image_name": reference_image_name,
            "reference_artifact": reference_artifact,
            "image_ref": image_ref,
        }.items()
        if value is not None
    }
    submission = build_stage_submission(
        approved_plan,
        source_api_graph,
        consumption,
        consumption_path,
        profile=profile,
        capability_report=capability_report,
        **optional,
    )
    root = Path(submission["consumption_root"]).resolve()
    receipt_path = root / f'{submission["consumption_id"]}.stage-enqueue-receipt.json'
    submitter = ComfyPromptSubmitter(base_url=api.base_url, timeout=timeout_value)
    receipt = submit_stage(submission, submitter.submit, receipt_path=receipt_path)
    history = api.history(receipt["prompt_id"])
    return {
        "submission": submission,
        "receipt": receipt,
        "receipt_path": str(receipt_path.resolve()),
        "history": history,
        "live_capability_report": live_report,
    }


def submit_character_base_via_local_rest(
    approved_plan: dict,
    prompt_build: dict,
    source_api_graph: dict,
    consumption: dict,
    consumption_path: str | Path,
    *,
    base_url: str = "http://127.0.0.1:8188",
    timeout: float = 30.0,
    ui_workflow: dict | None = None,
) -> dict:
    """Build and enqueue the consumed Stage 1 camera text-to-image graph.

    The REST client remains transport-only. Approval, exact graph rebuilding,
    and the exclusive receipt are owned by ``submit_character_base``.
    """
    timeout_value = _validate_timeout(timeout)
    api = ComfyApi(base_url=base_url, timeout=timeout_value)
    live_report = build_capability_report(api, _REST_ADAPTER, datetime.now(timezone.utc))
    _require_idle(live_report)
    submission = build_character_base_submission(
        approved_plan=approved_plan,
        prompt_build=prompt_build,
        source_api_graph=source_api_graph,
        approval_consumption=consumption,
        consumption_path=consumption_path,
        ui_workflow=ui_workflow,
    )
    submitter = ComfyPromptSubmitter(base_url=api.base_url, timeout=timeout_value)
    result = submit_character_base(
        approved_plan=approved_plan,
        prompt_build=prompt_build,
        source_api_graph=source_api_graph,
        approval_consumption=consumption,
        consumption_path=consumption_path,
        enqueue_workflow=submitter.submit,
        receipt_root=consumption["consumption_root"],
        ui_workflow=ui_workflow,
    )
    prompt_id = result["enqueue_receipt"]["prompt_id"]
    history = api.history(prompt_id)
    return {
        "submission": submission,
        **result,
        "history": history,
        "live_capability_report": live_report,
    }


def wait_for_stage_history(
    api: ComfyApi,
    prompt_id: str,
    *,
    timeout: float = 3600.0,
    poll_interval: float = 2.0,
) -> dict:
    """Poll one local history entry until ComfyUI reports a terminal result."""
    timeout_value = _validate_timeout(timeout)
    interval = _validate_timeout(poll_interval)
    if interval > 60:
        raise StageExecutionError("history poll interval must not exceed 60 seconds")
    deadline = time.monotonic() + timeout_value
    while True:
        history = api.history(prompt_id)
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        status = entry.get("status") if isinstance(entry, dict) else None
        if isinstance(status, dict) and status.get("completed") is True:
            return history
        if isinstance(status, dict) and status.get("status_str") in {"error", "failed"}:
            raise StageExecutionError(f"ComfyUI stage {prompt_id} failed")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise StageExecutionError(f"timed out waiting for ComfyUI stage {prompt_id}")
        time.sleep(min(interval, remaining))
