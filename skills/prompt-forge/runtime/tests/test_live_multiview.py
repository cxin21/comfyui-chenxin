"""Opt-in Experiment C safety gate for the Flux multi-view workflow.

The camera normalization bridge is not applicable to Flux conversion. This
test therefore keeps Flux conversion/preflight evidence independent, never
treats a pending draft as a successful experiment, and never uploads or
enqueues from test code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.execution import ExecutionError, validate_multiview_mcp_preflight


LIVE = os.environ.get("PROMPT_FORGE_LIVE") == "1"
LIVE_MARK = pytest.mark.skipif(not LIVE, reason="set PROMPT_FORGE_LIVE=1 explicitly")
_REQUIRED_KEYS = frozenset(
    ("conversion_receipt", "capability_report", "profile", "ui_workflow", "api_graph")
)


def _load_production_preflight(path_value: str) -> dict:
    """Parse and validate the exact evidence consumed by the runtime boundary."""
    try:
        payload = json.loads(Path(path_value).resolve(strict=True).read_text(encoding="utf-8"))
    except (OSError, RuntimeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionError("Experiment C MCP preflight file is unreadable") from exc
    if not isinstance(payload, dict) or set(payload) != _REQUIRED_KEYS:
        raise ExecutionError("Experiment C MCP preflight schema is invalid")
    validate_multiview_mcp_preflight(
        conversion_receipt=payload["conversion_receipt"],
        capability_report=payload["capability_report"],
        profile=payload["profile"],
        actual_ui_workflow=payload["ui_workflow"],
        api_graph=payload["api_graph"],
    )
    return payload


def test_invalid_live_preflight_raises_typed_runtime_error(tmp_path):
    path = tmp_path / "invalid-preflight.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ExecutionError, match="preflight schema"):
        _load_production_preflight(str(path))


def test_runtime_preflight_rejects_invalid_evidence_under_python_optimized():
    code = """
from runtime.execution import ExecutionError, validate_multiview_mcp_preflight
try:
    validate_multiview_mcp_preflight(
        conversion_receipt={}, capability_report={}, profile={}, actual_ui_workflow={}, api_graph={}
    )
except ExecutionError:
    raise SystemExit(0)
raise SystemExit(1)
"""
    env = os.environ.copy()
    skill_root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (skill_root, env.get("PYTHONPATH")) if value
    )
    result = subprocess.run([sys.executable, "-O", "-c", code], check=False, env=env)
    assert result.returncode == 0


@LIVE_MARK
def test_live_multiview_experiment_c_stops_before_upload_or_enqueue():
    preflight_path = os.environ.get("PROMPT_FORGE_MCP_PREFLIGHT_FILE")
    if not preflight_path:
        pytest.skip("no real zero-error comfyui-mcp conversion receipt is available")
    _load_production_preflight(preflight_path)
    pytest.fail(
        "Experiment C remains intentionally blocked: this gate validates MCP evidence only; "
        "it performs no upload or enqueue without an externally approved production run."
    )
