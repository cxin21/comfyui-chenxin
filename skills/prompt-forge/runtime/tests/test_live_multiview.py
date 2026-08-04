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

from runtime.contracts import content_hash
from runtime.execution import ExecutionError, _bind_multiview_view_plan, validate_multiview_mcp_preflight


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


def test_stage2_view_binding_hashes_switches_outputs_and_orientation_evidence():
    profile = {
        "schema_version": "1.0", "profile_id": "flux2-klein-view-selection-v1",
        "base_profile_id": "flux2-klein-multiview-flat-v2", "workflow_id": "prompt-forge-flat-v2",
        "workflow_name": "PromptForge-Flux2-Klein-multiview-flat-v2.json",
        "workflow_fingerprint": "9dc2b01e2aea0b051113b187b134d007f452df6c83cfcbbd8d325eaa4c29e4da",
        "source_api_graph_hash": "450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36",
        "slots": {"base_image_primary": {"id": 111, "type": "LoadImage"}, "base_image_secondary": {"id": 667, "type": "LoadImage"}},
        "view_plan": {"switches": {"731": {"input": "boolean", "type": "ImpactBoolean"}}, "prompt_slots": {}, "seed_slots": {}, "dimension_slots": {}},
        "immutable_roles": {"pose_references": [368, 151, 152, 154, 360, 364, 148, 149, 147, 373, 150, 367]},
        "output_nodes": {"663": {"artifact_type": "CharacterAngleView", "view_label": "front"}, "609": {"artifact_type": "CharacterAngleView", "view_label": "rear"}},
    }
    view_plan = {"views": ["front", "rear"], "switches": {"731": True}, "orientation_evidence": {"front": {"source": "profile-output-map", "verified": True}, "rear": {"source": "profile-output-map", "verified": True}}}
    binding = _bind_multiview_view_plan(view_plan, profile)
    assert binding["view_plan_hash"] == content_hash(view_plan)
    assert binding["requested_views"] == ["front", "rear"]
    assert binding["output_map"] == {"609": {"artifact_type": "CharacterAngleView", "view_label": "rear"}, "663": {"artifact_type": "CharacterAngleView", "view_label": "front"}}
    assert binding["switch_patch"] == {"731": True}
    assert binding["orientation_evidence"] == view_plan["orientation_evidence"]


def test_stage2_view_binding_rejects_grouped_flux_profile():
    with pytest.raises(ExecutionError, match="flat-v2|flat v2"):
        _bind_multiview_view_plan({"views": ["front"]}, {"profile_id": "flux2-klein-view-selection-v1", "base_profile_id": "flux2-klein-multiview-v1", "workflow_id": "grouped-reference-only", "workflow_name": "Flux2-Klein人物一键多视图工作流.json"})


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
