import copy
import hashlib
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from runtime.adapters.flux_multiview import patch_base_images
from runtime.contracts import content_hash
from runtime.execution import (
    ExecutionError,
    approve_execution_draft,
    build_approval_consumption,
    build_multiview_draft,
    build_multiview_run_record,
)
import runtime.execution as execution_module
import runtime.runtime_cli as runtime_cli


PROFILE_PATH = Path(__file__).parents[1] / "profiles" / "flux2-klein-multiview.json"
API_PATH = Path(__file__).parent / "fixtures" / "flux-api-minimal.json"
FINGERPRINT = "fff6236efa6727ac6584d61f640a63f9602b2d07a545d216b96a870a681e6faf"
POSE_IDS = [368, 151, 152, 154, 360, 364, 148, 149, 147, 373, 150, 367]


def _profile():
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _api_graph():
    return json.loads(API_PATH.read_text(encoding="utf-8"))


def _ui_workflow():
    nodes = [
        {"id": 111, "type": "LoadImage"},
        {"id": 667, "type": "LoadImage"},
        *({"id": node_id, "type": "LoadImage"} for node_id in POSE_IDS),
    ]
    return {"nodes": nodes, "groups": [], "links": []}


def _capability_report():
    now = datetime.now(timezone.utc)
    return {
        "schema_version": "1.0",
        "comfyui": {"url": "http://127.0.0.1:8188", "reachable": True},
        "adapter": {
            "name": "comfyui-mcp",
            "version": "0.49.0",
            "runtime_classification": "local",
            "tools": ["get_workflow", "strip_workflow", "validate_workflow"],
        },
        "queue": {"running": 0, "pending": 0},
        "generated_at": (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        "valid_until": (now + timedelta(minutes=9)).isoformat().replace("+00:00", "Z"),
    }


def _stage1_record(filename, digest):
    record = {
        "schema_version": "1.0",
        "terminal_status": "succeeded",
        "history_verified": True,
        "execution_plan": {
            "stage": "character-base",
            "workflow_profile_id": "camera-anima-v1",
        },
        "output_hashes": {filename: digest},
    }
    record["record_hash"] = content_hash(record)
    return record


def _artifact(tmp_path, *, accepted=True, artifact_type="CharacterBaseImage"):
    path = tmp_path / "base.png"
    path.write_bytes(b"real-png-fixture")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    record = _stage1_record(path.name, digest)
    artifact = {
        "schema_version": "1.0",
        "artifact_type": artifact_type,
        "accepted": accepted,
        "content_hash": digest,
        "lineage_id": "lineage-1",
        "source_record_hash": record["record_hash"],
        "artifact_path": str(path.resolve()),
        "artifact_root": str(tmp_path.resolve()),
        "visual_acceptance": {"front_facing": True, "identity_visible": True},
    }
    return record, artifact


def _draft(tmp_path, monkeypatch):
    monkeypatch.setattr(execution_module, "structure_fingerprint", lambda workflow: FINGERPRINT)
    record, artifact = _artifact(tmp_path)
    draft = build_multiview_draft(
        stage1_record=record,
        base_artifact=artifact,
        workflow_profile_id="flux2-klein-multiview-v1",
        workflow_fingerprint=FINGERPRINT,
        capability_report=_capability_report(),
        profile=_profile(),
        actual_ui_workflow=_ui_workflow(),
        api_graph=_api_graph(),
    )
    return record, artifact, draft


def _event(draft, root):
    now = datetime.now(timezone.utc)
    return {
        "decision": "approved",
        "draft_hash": draft["draft_hash"],
        "displayed_at": (now - timedelta(seconds=2)).isoformat().replace("+00:00", "Z"),
        "approved_at": (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "scope": "enqueue-once",
        "consumption_root": str(root.resolve()),
        "actor": "user:test",
        "source": "external-test",
    }


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (lambda artifact: artifact.update(accepted=False), "accepted"),
        (lambda artifact: artifact.update(artifact_type="DiagnosticImage"), "CharacterBaseImage"),
        (lambda artifact: artifact.update(content_hash=""), "SHA-256"),
        (lambda artifact: artifact["visual_acceptance"].update(front_facing=False), "front-facing"),
    ],
)
def test_multiview_draft_rejects_unaccepted_or_ineligible_stage1_artifact(
    tmp_path, monkeypatch, change, match
):
    monkeypatch.setattr(execution_module, "structure_fingerprint", lambda workflow: FINGERPRINT)
    record, artifact = _artifact(tmp_path)
    change(artifact)
    with pytest.raises(ExecutionError, match=match):
        build_multiview_draft(
            stage1_record=record,
            base_artifact=artifact,
            workflow_profile_id="flux2-klein-multiview-v1",
            workflow_fingerprint=FINGERPRINT,
            capability_report=_capability_report(),
            profile=_profile(),
            actual_ui_workflow=_ui_workflow(),
            api_graph=_api_graph(),
        )


def test_multiview_draft_binds_stage1_and_exact_dual_patch(tmp_path, monkeypatch):
    record, artifact, draft = _draft(tmp_path, monkeypatch)

    expected_name = f'prompt-forge/{artifact["lineage_id"]}/character-base-{artifact["content_hash"]}.png'
    assert draft["stage"] == "character-multiview"
    assert draft["plan_state"] == "draft"
    assert draft["execution_approved"] is False
    assert draft["upstream_record_hash"] == record["record_hash"]
    assert draft["source_artifact_hash"] == artifact["content_hash"]
    assert draft["lineage_id"] == artifact["lineage_id"]
    assert draft["uploaded_filename"] == expected_name
    assert draft["patches"] == [
        {"slot": "base_image_primary", "input": "image", "value": expected_name, "source_hash": artifact["content_hash"]},
        {"slot": "base_image_secondary", "input": "image", "value": expected_name, "source_hash": artifact["content_hash"]},
    ]
    assert {item["node_id"] for item in draft["immutable_inputs"]} == set(POSE_IDS)
    assert draft["workflow_fingerprint"] == FINGERPRINT
    assert draft["draft_hash"] == content_hash({k: v for k, v in draft.items() if k != "draft_hash"})


def test_generic_approval_and_consumption_accept_stage2_exact_draft(tmp_path, monkeypatch):
    _, _, draft = _draft(tmp_path, monkeypatch)
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    consumption = build_approval_consumption(plan, "stage2-request-1")

    assert plan["stage"] == "character-multiview"
    assert plan["approval_event"]["draft_hash"] == draft["draft_hash"]
    assert consumption["draft_hash"] == draft["draft_hash"]
    assert consumption["enqueue_request_id"] == "stage2-request-1"


def test_generic_approval_rejects_self_hashed_stage2_draft_with_unbound_upload(tmp_path, monkeypatch):
    _, _, draft = _draft(tmp_path, monkeypatch)
    draft["uploaded_filename"] = "attacker.png"
    unsigned = dict(draft)
    unsigned.pop("draft_hash")
    draft["draft_hash"] = content_hash(unsigned)

    with pytest.raises(ExecutionError, match="uploaded filename"):
        approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)


def _task_context():
    return {
        "schema_version": "1.0",
        "shared_known": {"goal": "build multiview references", "background": [], "acceptance": [], "boundaries": []},
        "user_known_agent_unknown": {"references": [], "aesthetic_preferences": [], "real_world_constraints": []},
        "agent_known_user_unknown": {"capabilities": [], "risks": [], "alternatives": []},
        "shared_unknown": {"hypotheses": [], "experiments": []},
    }


def test_multiview_run_record_binds_raw_executable_history_and_artifacts(tmp_path, monkeypatch):
    record, artifact, draft = _draft(tmp_path, monkeypatch)
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    graph = _api_graph()
    executable = patch_base_images(graph, draft["uploaded_filename"], {"base_image_primary": 111, "base_image_secondary": 667})
    prompt_id = "stage2-prompt"
    history = {
        prompt_id: {
            "prompt": [1, prompt_id, executable],
            "status": {"status_str": "success", "completed": True},
            "outputs": {"524": {"images": [{"filename": "front.png", "subfolder": "", "type": "output"}]}},
        }
    }
    output_hash = "9" * 64
    result = build_multiview_run_record(
        _task_context(), record, artifact, graph, plan, _profile(), prompt_id,
        "succeeded", {"front.png": output_hash}, history=history,
    )

    assert result["stage"] == "character-multiview"
    assert result["upstream_record_hash"] == record["record_hash"]
    assert result["source_artifact_hash"] == artifact["content_hash"]
    assert result["raw_history"] == history
    assert result["artifacts"][0]["content_hash"] == output_hash
    assert result["artifacts"][0]["lineage_id"] == artifact["lineage_id"]
    assert result["record_hash"] == content_hash({k: v for k, v in result.items() if k != "record_hash"})


def test_stage2_cli_plans_and_patches_without_approval_boolean(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(execution_module, "structure_fingerprint", lambda workflow: FINGERPRINT)
    monkeypatch.setattr(runtime_cli, "build_multiview_draft", build_multiview_draft)
    record, artifact = _artifact(tmp_path)
    payload = {
        "stage1_record": record,
        "base_artifact": artifact,
        "workflow_profile_id": "flux2-klein-multiview-v1",
        "workflow_fingerprint": FINGERPRINT,
        "capability_report": _capability_report(),
        "profile": _profile(),
        "actual_ui_workflow": _ui_workflow(),
        "api_graph": _api_graph(),
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert runtime_cli.main(["plan-multiview", "--from-stdin"]) == 0
    draft = json.loads(capsys.readouterr().out)
    assert draft["execution_approved"] is False

    patch_payload = {"api_graph": _api_graph(), "image_name": draft["uploaded_filename"], "slots": {"base_image_primary": 111, "base_image_secondary": 667}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(patch_payload)))
    assert runtime_cli.main(["patch-flux", "--from-stdin"]) == 0
    patched = json.loads(capsys.readouterr().out)
    assert patched["111"]["inputs"]["image"] == patched["667"]["inputs"]["image"]
