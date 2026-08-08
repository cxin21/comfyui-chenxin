"""Single-entry orchestration for character-base stage.

The runtime never depends on a host SDK and does not own submission.  This
orchestrator chains the deterministic runtime checks and returns an
assembled execution draft plus manifest hints; the host agent then drives
approval, submission, and verification using the existing
approve-plan / consume-approval / record subcommands.

Layered this way because the approval boundary must be crossed by a human
and the submission boundary must be driven by the host's MCP bridge.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

from .capabilities import build_capability_report
from .comfy_api import CapabilityError, ComfyApi
from .execution import ExecutionError, build_execution_draft
from .preflight import run_preflight


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_package(package_path: Path) -> dict[str, Any]:
    raw = package_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("PromptPackage must be a JSON object")
    return data


def run_character_base(
    *,
    package_path: Path,
    run_dir: Path,
    comfy_url: str = "http://127.0.0.1:8188",
) -> tuple[dict[str, Any], int]:
    """Return (payload, exit_code) for the character-base stage."""
    run_dir.mkdir(parents=True, exist_ok=True)
    preflight = run_preflight(
        runtime_root=Path(__file__).resolve().parent,
        comfy_url=comfy_url,
    )
    if not preflight["ok"]:
        return (
            {
                "accepted": False,
                "stage": "character-base",
                "phase": "preflight",
                "preflight": preflight,
                "remediation": (
                    "preflight reported blockers; fix the listed checks and re-run."
                    " See docs/TROUBLESHOOTING.md for repair commands."
                ),
            },
            1,
        )

    try:
        package = _read_package(package_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return (
            {
                "accepted": False,
                "stage": "character-base",
                "phase": "load_package",
                "error": str(exc),
                "remediation": (
                    "pass a valid PromptPackage JSON produced by prompt-forge;"
                    " the file must contain dialect_id, evidence, positive, negative."
                ),
            },
            2,
        )

    try:
        api = ComfyApi(comfy_url)
        capability_report = build_capability_report(api, adapter={"runtime_classification": "local", "tools": []}, now=_now())
    except (CapabilityError, Exception) as exc:
        return (
            {
                "accepted": False,
                "stage": "character-base",
                "phase": "capability_report",
                "error": str(exc),
                "remediation": "verify ComfyUI is reachable at the configured URL.",
            },
            2,
        )

    profile_id = package.get("profile_id") or "camera-anima-v1"
    prompt_build = package.get("prompt_build") or {
        "dialect_id": package.get("dialect_id"),
        "positive": package.get("positive"),
        "negative": package.get("negative"),
        "evidence": package.get("evidence", {}),
        "continuity_locks": package.get("continuity_locks", {}),
    }

    try:
        draft = build_execution_draft(
            stage="character-base",
            prompt_build=prompt_build,
            profile_id=profile_id,
            fingerprint=None,
            patches={},
            capability_report=capability_report,
            profile=None,
            actual_ui_workflow=None,
            api_graph=None,
        )
    except ExecutionError as exc:
        return (
            {
                "accepted": False,
                "stage": "character-base",
                "phase": "compile_draft",
                "error": str(exc),
                "remediation": (
                    "if the error mentions workflow_candidate_unavailable, the production"
                    " preconditions (MCP negotiation, fixed asset integrity) are not met."
                    " Run runtime preflight and resolve blockers first."
                ),
                "capability_report_digest": capability_report.get("reason_codes"),
            },
            2,
        )

    artifact_path = run_dir / "draft.json"
    artifact_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return (
        {
            "accepted": True,
            "stage": "character-base",
            "phase": "awaiting_approval",
            "next_step": (
                "host agent must obtain user approval, then call"
                " approve-plan -> consume-approval -> record with the resulting draft."
            ),
            "preflight_version": preflight.get("runtime_version"),
            "capability_report_digest": copy.deepcopy(capability_report.get("reason_codes")),
            "draft_path": str(artifact_path),
            "draft": copy.deepcopy(draft),
            "manifest_hint": {
                "expected_history_keys": ["prompt_id"],
                "expected_artifact_keys": ["filename", "content_hash"],
            },
            "recorded_at": _utc_now(),
        },
        0,
    )


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
