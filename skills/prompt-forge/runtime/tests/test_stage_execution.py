from __future__ import annotations

import copy
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import runtime.stage_execution as stage_execution
from runtime.artifacts import accept_stage3_reference
from runtime.contracts import content_hash
from runtime.stages import build_shot_plan, build_video_plan
from runtime.workflow_profile import structure_fingerprint


FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 8, 3, 1, 0, tzinfo=timezone.utc)


def _valid_png_bytes():
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )


def _camera_profile(*, production=False):
    profile = json.loads(
        (Path(__file__).parents[1] / "profiles" / "camera-anima.json").read_text(encoding="utf-8")
    )
    profile["workflow_fingerprint"] = structure_fingerprint(_shot_ui())
    return profile


def _yusu_profile():
    return json.loads(
        (Path(__file__).parents[1] / "profiles" / "ltx-yusu-director.json").read_text(encoding="utf-8")
    )


def _capability_report():
    return {
        "schema_version": "1.0",
        "comfyui": {"url": "http://127.0.0.1:8188", "reachable": True},
        "adapter": {"runtime_classification": "local", "tools": []},
        "queue": {"running": 0, "pending": 0},
        "generated_at": NOW.isoformat().replace("+00:00", "Z"),
        "valid_until": (NOW + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
    }


def _shot_build():
    return {
        "target": "image",
        "dialect": "tag",
        "prompt": "score_9, the_swordswoman, sword",
        "negative_prompt": "lowres",
        "recipe_control_tokens": ["score_9"],
        "validated_tags": ["the_swordswoman", "sword"],
        "rejected_tags": [],
        "locked_facts": ["the_swordswoman"],
        "ready_to_execute": True,
        "execution": {"requested": True, "performed": False},
    }


def _shot_plan(report):
    prompt_build = _shot_build()
    return build_shot_plan(
        "b" * 64,
        content_hash(prompt_build),
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "left_45",
            "accepted": True,
            "content_hash": "a" * 64,
        },
        "left_45",
        True,
        shot_prompt_build=prompt_build,
        identity_facts=["the_swordswoman"],
        g1_proof={"vae_encode_node_id": 59, "sampler_node_id": 27, "traversed_node_ids": [27, 75, 59]},
        profile_hash=content_hash(_camera_profile()),
        capability_report_hash=content_hash(report),
        workflow_fingerprint=structure_fingerprint(_shot_ui()),
    )


def _shot_graph():
    return json.loads((FIXTURES / "camera-img2img-api-minimal.json").read_text(encoding="utf-8"))


def _accepted_reference():
    return accept_stage3_reference(
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "left_45",
            "accepted": False,
            "reference_eligible": True,
            "semantic_conflict": False,
            "hash_verified": True,
            "content_hash": "a" * 64,
        },
        "user:test",
        "2026-08-03T00:30:00Z",
    )


def _shot_ui():
    return json.loads((FIXTURES / "camera-img2img-ui-minimal.json").read_text(encoding="utf-8"))


def _video_build():
    return {
        "ready_to_execute": True,
        "target": "video",
        "dialect": "video-timeline",
        "prompt": "The subject moves as the camera dollies in.",
        "negative_prompt": "",
    }


def _video_graph():
    graph = json.loads((FIXTURES / "yusu-api-minimal.json").read_text(encoding="utf-8"))
    profile = _yusu_profile()
    for node_id, node in profile.get("immutable_node_inputs", {}).items():
        graph[node_id] = copy.deepcopy(node)
    graph["174"]["inputs"].update(profile["director_immutable_inputs"])
    return graph


def _video_plan(graph):
    return build_video_plan(
        {"artifact_type": "ShotImage", "accepted": True, "content_hash": "d" * 64},
        _video_build(),
        content_hash(graph),
        content_hash(_yusu_profile()),
        True,
        workflow_fingerprint=_yusu_profile()["workflow_fingerprint"],
    )


def _event(draft, root):
    return {
        "decision": "approved",
        "draft_hash": draft["draft_hash"],
        "displayed_at": (NOW - timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
        "approved_at": (NOW - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "scope": "enqueue-once",
        "consumption_root": str(root.resolve()),
        "actor": "user:test",
        "source": "test-fixture",
    }


@pytest.fixture(autouse=True)
def trusted_clock(monkeypatch):
    monkeypatch.setattr(stage_execution, "_utc_now", lambda: NOW)


def test_shot_execution_draft_rebinds_graph_and_g1_without_mutating_sources():
    report = _capability_report()
    plan = _shot_plan(report)
    graph = _shot_graph()
    ui = _shot_ui()
    before = copy.deepcopy((plan, graph, ui))
    draft = stage_execution.build_stage_execution_draft(
        plan,
        graph,
        _camera_profile(),
        report,
        ui_workflow=ui,
        image_name="runs/lineage/ref.png",
        reference_artifact=_accepted_reference(),
    )
    assert (plan, graph, ui) == before
    assert draft["stage"] == "shot-image"
    assert draft["execution_approved"] is False
    assert draft["source_api_graph_hash"] == content_hash(graph)
    assert draft["executable_api_graph_hash"] != draft["source_api_graph_hash"]
    assert draft["g1_path_proof"]["traversed_node_ids"] == [27, 75, 59]
    unsigned = dict(draft)
    unsigned.pop("draft_hash")
    assert draft["draft_hash"] == content_hash(unsigned)


def test_shot_execution_draft_rejects_profile_fingerprint_drift():
    report = _capability_report()
    plan = _shot_plan(report)
    graph = _shot_graph()
    ui = _shot_ui()
    profile = _camera_profile()
    profile["workflow_fingerprint"] = "0" * 64
    plan["profile_hash"] = content_hash(profile)
    plan["plan_hash"] = content_hash({key: value for key, value in plan.items() if key != "plan_hash"})
    with pytest.raises(stage_execution.StageExecutionError, match="verified camera profile"):
        stage_execution.build_stage_execution_draft(
            plan,
            graph,
            profile,
            report,
            ui_workflow=ui,
            image_name="runs/lineage/ref.png",
            reference_artifact=_accepted_reference(),
        )


def test_shot_execution_draft_rejects_profile_path_contract_drift():
    report = _capability_report()
    plan = _shot_plan(report)
    graph = _shot_graph()
    ui = _shot_ui()
    profile = _camera_profile()
    profile["img2img"]["expected_path_node_ids"] = [27, 59]
    plan["profile_hash"] = content_hash(profile)
    plan["plan_hash"] = content_hash({key: value for key, value in plan.items() if key != "plan_hash"})
    with pytest.raises(stage_execution.StageExecutionError, match="pinned camera normalization profile"):
        stage_execution.build_stage_execution_draft(
            plan,
            graph,
            profile,
            report,
            ui_workflow=ui,
            image_name="runs/lineage/ref.png",
            reference_artifact=_accepted_reference(),
        )


def test_shot_execution_draft_rejects_unormalized_camera_source_graph():
    report = _capability_report()
    graph = _shot_graph()
    graph.update(
        {
            "26": {"class_type": "Lora Loader (LoraManager)", "inputs": {"model": ["22", 0]}},
            "35": {"class_type": "Image Saver Simple", "inputs": {"metadata": ["89", 0]}},
            "490": {"class_type": "PreviewImage", "inputs": {}},
            "76": {"class_type": "VAEDecode", "inputs": {"samples": ["51", 0], "vae": ["48", 0]}},
            "96": {"class_type": "AdjustContrast", "inputs": {"images": ["76", 0]}},
            "111": {"class_type": "ImageSharpen", "inputs": {"image": ["96", 0]}},
            **{
                str(node_id): {"class_type": "Optional", "inputs": {}}
                for node_id in (28, 41, 52, 62, 67, 70, 77)
            },
        }
    )
    ui = _shot_ui()
    profile = _camera_profile(production=True)
    plan = _shot_plan(report)
    plan["profile_hash"] = content_hash(profile)
    plan["workflow_fingerprint"] = structure_fingerprint(ui)
    plan["plan_hash"] = content_hash({key: value for key, value in plan.items() if key != "plan_hash"})
    with pytest.raises(stage_execution.StageExecutionError, match="normalize-camera"):
        stage_execution.build_stage_execution_draft(
            plan,
            graph,
            profile,
            report,
            ui_workflow=ui,
            image_name="runs/lineage/ref.png",
            reference_artifact=_accepted_reference(),
        )


def test_stage_draft_rejects_stale_or_busy_capability():
    report = _capability_report()
    report["queue"]["running"] = 1
    with pytest.raises(stage_execution.StageExecutionError, match="one ComfyUI job"):
        stage_execution.build_stage_execution_draft(
            _shot_plan(report), _shot_graph(), _camera_profile(), report,
            ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=_accepted_reference(),
        )


def test_stage_draft_rejects_non_utc_reference_acceptance_even_with_valid_hash():
    report = _capability_report()
    reference = _accepted_reference()
    reference["acceptance"]["accepted_at"] = "2026-08-03T01:30:00+01:00"
    unsigned = dict(reference["acceptance"])
    unsigned.pop("acceptance_id")
    reference["acceptance"]["acceptance_id"] = content_hash(unsigned)
    reference["acceptance_id"] = reference["acceptance"]["acceptance_id"]
    with pytest.raises(stage_execution.StageExecutionError, match="must be UTC"):
        stage_execution.build_stage_execution_draft(
            _shot_plan(report), _shot_graph(), _camera_profile(), report,
            ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=reference,
        )


def test_stage_draft_rechecks_reference_eligibility_after_acceptance():
    report = _capability_report()
    reference = _accepted_reference()
    reference["semantic_conflict"] = True
    with pytest.raises(stage_execution.StageExecutionError, match="not Stage 3 eligible"):
        stage_execution.build_stage_execution_draft(
            _shot_plan(report), _shot_graph(), _camera_profile(), report,
            ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=reference,
        )


def test_stage_approval_is_bound_to_exact_displayed_draft_and_consumption_root(tmp_path):
    report = _capability_report()
    draft = stage_execution.build_stage_execution_draft(
        _shot_plan(report), _shot_graph(), _camera_profile(), report,
        ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=_accepted_reference(),
    )
    approved = stage_execution.approve_stage_execution_draft(draft, _event(draft, tmp_path), tmp_path)
    assert approved["plan_state"] == "approved"
    assert approved["approval_id"] == content_hash(approved["approval_event"])
    assert approved["execution_plan_hash"]
    with pytest.raises(stage_execution.StageExecutionError, match="draft_hash"):
        bad = _event(draft, tmp_path)
        bad["draft_hash"] = "0" * 64
        stage_execution.approve_stage_execution_draft(draft, bad, tmp_path)


def test_stage_consumption_and_submission_require_canonical_evidence(tmp_path):
    report = _capability_report()
    draft = stage_execution.build_stage_execution_draft(
        _shot_plan(report), _shot_graph(), _camera_profile(), report,
        ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=_accepted_reference(),
    )
    approved = stage_execution.approve_stage_execution_draft(draft, _event(draft, tmp_path), tmp_path)
    consumption = stage_execution.build_stage_consumption(approved, "shot-request-1")
    path = stage_execution.write_stage_consumption(tmp_path, consumption)
    submission = stage_execution.build_stage_submission(
        approved,
        _shot_graph(),
        consumption,
        path,
        profile=_camera_profile(),
        capability_report=report,
        ui_workflow=_shot_ui(),
        reference_image_name="ref.png",
        reference_artifact=_accepted_reference(),
    )
    assert submission["api_graph"]["21"]["inputs"]["image"] == "ref.png"
    assert submission["stage"] == "shot-image"
    assert submission["request"]["client_id"] == "shot-request-1"
    assert submission["request"]["extra_data"]["extra_pnginfo"]["workflow"] == _shot_ui()
    with pytest.raises(stage_execution.StageExecutionError, match="missing"):
        stage_execution.build_stage_submission(
            approved, _shot_graph(), consumption, path.with_name("wrong.json"),
            profile=_camera_profile(), capability_report=report, reference_image_name="ref.png",
            ui_workflow=_shot_ui(),
            reference_artifact=_accepted_reference(),
        )


def test_stage_submission_rejects_tampered_ui_provenance(tmp_path):
    report = _capability_report()
    draft = stage_execution.build_stage_execution_draft(
        _shot_plan(report), _shot_graph(), _camera_profile(), report,
        ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=_accepted_reference(),
    )
    approved = stage_execution.approve_stage_execution_draft(draft, _event(draft, tmp_path), tmp_path)
    consumption = stage_execution.build_stage_consumption(approved, "shot-request-provenance")
    path = stage_execution.write_stage_consumption(tmp_path, consumption)
    submission = stage_execution.build_stage_submission(
        approved,
        _shot_graph(),
        consumption,
        path,
        profile=_camera_profile(),
        capability_report=report,
        ui_workflow=_shot_ui(),
        reference_image_name="ref.png",
        reference_artifact=_accepted_reference(),
    )
    tampered = copy.deepcopy(submission)
    tampered["request"]["extra_data"]["extra_pnginfo"]["workflow"]["nodes"][0]["title"] = "tampered"
    with pytest.raises(stage_execution.StageExecutionError, match="UI provenance fingerprint"):
        stage_execution._validate_submission_request(tampered)


def test_video_submission_patches_yusu_timeline_and_preserves_workflow_negative(tmp_path):
    graph = _video_graph()
    plan = _video_plan(graph)
    shot_hash = plan["source_shot_hash"]
    image_ref = {"artifact_type": "ShotImage", "accepted": True, "content_hash": shot_hash, "imageFile": "shots/shot.png", "imageB64": "/api/view?filename=shot.png"}
    report = _capability_report()
    plan["capability_report_hash"] = content_hash(report)
    plan["plan_hash"] = content_hash({key: value for key, value in plan.items() if key != "plan_hash"})
    draft = stage_execution.build_stage_execution_draft(
        plan, graph, _yusu_profile(), report, image_ref=image_ref,
    )
    approved = stage_execution.approve_stage_execution_draft(draft, _event(draft, tmp_path), tmp_path)
    consumption = stage_execution.build_stage_consumption(approved, "video-request-1")
    path = stage_execution.write_stage_consumption(tmp_path, consumption)
    submission = stage_execution.build_stage_submission(
        approved, graph, consumption, path, profile=_yusu_profile(), capability_report=report, image_ref=image_ref,
    )
    timeline = json.loads(submission["api_graph"]["174"]["inputs"]["timeline_data"])
    assert timeline["segments"][0]["imageFile"] == "shots/shot.png"
    assert submission["api_graph"]["195"] == graph["195"]


def test_video_execution_rejects_wrong_ltx_profile():
    graph = _video_graph()
    plan = _video_plan(graph)
    image_ref = {
        "artifact_type": "ShotImage",
        "accepted": True,
        "content_hash": plan["source_shot_hash"],
        "imageFile": "shots/shot.png",
        "imageB64": "/api/view?filename=shot.png",
    }
    report = _capability_report()
    plan["capability_report_hash"] = content_hash(report)
    profile = _yusu_profile()
    # The final assignment below intentionally invalidates the profile.
    profile["workflow_name"] = "wrong-ltx-mojibake.json"
    plan["profile_hash"] = content_hash(profile)
    plan["plan_hash"] = content_hash({key: value for key, value in plan.items() if key != "plan_hash"})
    with pytest.raises(stage_execution.StageExecutionError, match="exact local LTX"):
        stage_execution.build_stage_execution_draft(
            plan, graph, profile, report, image_ref=image_ref,
        )


def test_video_execution_rejects_unpinned_ltx_contract():
    graph = _video_graph()
    plan = _video_plan(graph)
    image_ref = {
        "artifact_type": "ShotImage",
        "accepted": True,
        "content_hash": plan["source_shot_hash"],
        "imageFile": "shots/shot.png",
        "imageB64": "/api/view?filename=shot.png",
    }
    report = _capability_report()
    profile = _yusu_profile()
    profile["immutable_node_inputs"].pop("175")
    plan["profile_hash"] = content_hash(profile)
    plan["capability_report_hash"] = content_hash(report)
    plan["plan_hash"] = content_hash({key: value for key, value in plan.items() if key != "plan_hash"})
    with pytest.raises(stage_execution.StageExecutionError, match="trusted LTX"):
        stage_execution.build_stage_execution_draft(
            plan, graph, profile, report, image_ref=image_ref,
        )


def test_video_execution_rejects_profile_fingerprint_drift():
    graph = _video_graph()
    plan = _video_plan(graph)
    plan["workflow_fingerprint"] = "0" * 64
    image_ref = {
        "artifact_type": "ShotImage",
        "accepted": True,
        "content_hash": plan["source_shot_hash"],
        "imageFile": "shots/shot.png",
        "imageB64": "/api/view?filename=shot.png",
    }
    report = _capability_report()
    plan["capability_report_hash"] = content_hash(report)
    plan["plan_hash"] = content_hash({key: value for key, value in plan.items() if key != "plan_hash"})
    with pytest.raises(stage_execution.StageExecutionError, match="workflow fingerprint"):
        stage_execution.build_stage_execution_draft(
            plan, graph, _yusu_profile(), report, image_ref=image_ref,
        )


def test_video_execution_rejects_ltx_sampler_drift():
    graph = _video_graph()
    graph["128"]["inputs"]["sampler_name"] = "ddim"
    plan = _video_plan(graph)
    image_ref = {
        "artifact_type": "ShotImage",
        "accepted": True,
        "content_hash": plan["source_shot_hash"],
        "imageFile": "shots/shot.png",
        "imageB64": "/api/view?filename=shot.png",
    }
    report = _capability_report()
    plan["capability_report_hash"] = content_hash(report)
    plan["plan_hash"] = content_hash({key: value for key, value in plan.items() if key != "plan_hash"})
    with pytest.raises(stage_execution.StageExecutionError, match="immutable node 128"):
        stage_execution.build_stage_execution_draft(
            plan, graph, _yusu_profile(), report, image_ref=image_ref,
        )


def test_submit_stage_uses_injected_callable_once_and_writes_receipt(tmp_path):
    report = _capability_report()
    draft = stage_execution.build_stage_execution_draft(
        _shot_plan(report), _shot_graph(), _camera_profile(), report,
        ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=_accepted_reference(),
    )
    approved = stage_execution.approve_stage_execution_draft(draft, _event(draft, tmp_path), tmp_path)
    consumption = stage_execution.build_stage_consumption(approved, "shot-request-2")
    consumption_path = stage_execution.write_stage_consumption(tmp_path, consumption)
    submission = stage_execution.build_stage_submission(
        approved, _shot_graph(), consumption, consumption_path,
        profile=_camera_profile(), capability_report=report, reference_image_name="ref.png",
        ui_workflow=_shot_ui(),
        reference_artifact=_accepted_reference(),
    )
    calls = []

    def enqueue(request):
        calls.append(request)
        return {"prompt_id": "prompt-1", "node_errors": {}}

    receipt_path = tmp_path / f"{consumption['consumption_id']}.stage-enqueue-receipt.json"
    receipt = stage_execution.submit_stage(submission, enqueue, receipt_path=receipt_path)
    assert len(calls) == 1
    assert receipt["status"] == "succeeded"
    retained = stage_execution.submit_stage(submission, enqueue, receipt_path=receipt_path)
    assert retained["prompt_id"] == "prompt-1"
    assert len(calls) == 1
    with pytest.raises(stage_execution.StageExecutionError, match="canonical"):
        stage_execution.submit_stage(submission, enqueue, receipt_path=tmp_path / "other.json")
    tampered = copy.deepcopy(submission)
    tampered["request"]["client_id"] = "different-request"
    tampered["submission_hash"] = content_hash(
        {key: value for key, value in tampered.items() if key != "submission_hash"}
    )
    with pytest.raises(stage_execution.StageExecutionError, match="client_id"):
        stage_execution.submit_stage(tampered, enqueue, receipt_path=receipt_path)
    assert len(calls) == 1


def test_stage_receipt_rejects_rehashed_identity_mismatch(tmp_path):
    report = _capability_report()
    draft = stage_execution.build_stage_execution_draft(
        _shot_plan(report), _shot_graph(), _camera_profile(), report,
        ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=_accepted_reference(),
    )
    approved = stage_execution.approve_stage_execution_draft(draft, _event(draft, tmp_path), tmp_path)
    consumption = stage_execution.build_stage_consumption(approved, "receipt-check")
    # The private validator is exercised directly to keep this test side-effect free.
    submission = {
        "schema_version": "1.0",
        "stage": "shot-image",
        "submission_type": "prompt-forge-stage-enqueue",
        "execution_plan_hash": approved["execution_plan_hash"],
        "draft_hash": approved["draft_hash"],
        "approval_id": approved["approval_id"],
        "consumption_id": consumption["consumption_id"],
        "consumption_root": consumption["consumption_root"],
        "enqueue_request_id": "receipt-check",
        "source_api_graph_hash": "a" * 64,
        "executable_api_graph_hash": "b" * 64,
        "api_graph": {},
        "request": {},
    }
    submission["submission_hash"] = content_hash(submission)
    response = {"prompt_id": "prompt-receipt", "node_errors": {}}
    receipt = {
        "schema_version": "1.0",
        "receipt_type": "prompt-forge-stage-enqueue",
        "stage": "video",
        "status": "succeeded",
        "execution_plan_hash": submission["execution_plan_hash"],
        "consumption_id": submission["consumption_id"],
        "submission_hash": submission["submission_hash"],
        "prompt_id": response["prompt_id"],
        "enqueue_request_id": submission["enqueue_request_id"],
        "submitted_graph_hash": submission["executable_api_graph_hash"],
        "request": {},
        "response": response,
        "response_digest": content_hash(response),
        "orchestrator": {"name": "prompt-forge", "trust_model": "trusted-local-orchestrator"},
    }
    receipt["receipt_hash"] = content_hash(receipt)
    with pytest.raises(stage_execution.StageExecutionError, match="succeeded enqueue receipt"):
        stage_execution._validate_stage_receipt(submission, receipt)


def test_stage_run_record_binds_receipt_history_and_png_bytes(tmp_path):
    report = _capability_report()
    source_graph = _shot_graph()
    draft = stage_execution.build_stage_execution_draft(
        _shot_plan(report), source_graph, _camera_profile(), report,
        ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=_accepted_reference(),
    )
    approved = stage_execution.approve_stage_execution_draft(draft, _event(draft, tmp_path), tmp_path)
    consumption = stage_execution.build_stage_consumption(approved, "shot-request-3")
    consumption_path = stage_execution.write_stage_consumption(tmp_path, consumption)
    submission = stage_execution.build_stage_submission(
        approved, source_graph, consumption, consumption_path,
        profile=_camera_profile(), capability_report=report, reference_image_name="ref.png",
        ui_workflow=_shot_ui(),
        reference_artifact=_accepted_reference(),
    )
    receipt = stage_execution.submit_stage(
        submission,
        lambda request: {"prompt_id": "prompt-3", "node_errors": {}},
        receipt_path=tmp_path / f"{consumption['consumption_id']}.stage-enqueue-receipt.json",
    )
    image_path = tmp_path / "shot.png"
    image_path.write_bytes(_valid_png_bytes())
    image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
    history = {
        "prompt-3": {
            "prompt": [
                "queue",
                "prompt-3",
                submission["api_graph"],
                {"extra_data": {"prompt_forge_enqueue_request_id": submission["enqueue_request_id"]}},
            ],
            "status": {"status_str": "success", "completed": True},
        }
    }
    record = stage_execution.build_stage_run_record(
        approved, submission, receipt,
        {
            "artifact_type": "ShotImage",
            "accepted": True,
            "content_hash": image_hash,
            "artifact_path": str(image_path.resolve()),
            "source_reference_hash": "a" * 64,
        },
        history=history,
    )
    assert record["terminal_status"] == "succeeded"
    assert record["artifact"]["content_hash"] == image_hash
    assert record["record_hash"]
    assert record["history_hash"] == content_hash(history)
    assert record["execution_plan"] == approved
    assert record["stage_plan"] == approved["stage_plan"]
    assert record["lineage"]["reference_hash"] == approved["stage_plan"]["reference_hash"]
    image_path.write_bytes(b"tampered")
    with pytest.raises(stage_execution.StageExecutionError, match="bytes"):
        stage_execution.build_stage_run_record(
            approved, submission, receipt,
            record["artifact"], history=history,
        )


def test_stage_run_record_requires_raw_history_for_success(tmp_path):
    report = _capability_report()
    source_graph = _shot_graph()
    draft = stage_execution.build_stage_execution_draft(
        _shot_plan(report), source_graph, _camera_profile(), report,
        ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=_accepted_reference(),
    )
    approved = stage_execution.approve_stage_execution_draft(draft, _event(draft, tmp_path), tmp_path)
    consumption = stage_execution.build_stage_consumption(approved, "history-required")
    consumption_path = stage_execution.write_stage_consumption(tmp_path, consumption)
    submission = stage_execution.build_stage_submission(
        approved, source_graph, consumption, consumption_path,
        profile=_camera_profile(), capability_report=report, reference_image_name="ref.png",
        ui_workflow=_shot_ui(), reference_artifact=_accepted_reference(),
    )
    receipt = stage_execution.submit_stage(
        submission,
        lambda request: {"prompt_id": "prompt-history-required", "node_errors": {}},
        receipt_path=tmp_path / f"{consumption['consumption_id']}.stage-enqueue-receipt.json",
    )
    image_path = tmp_path / "shot-history-required.png"
    image_path.write_bytes(_valid_png_bytes())
    image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
    artifact = {
        "artifact_type": "ShotImage",
        "accepted": True,
        "content_hash": image_hash,
        "artifact_path": str(image_path.resolve()),
        "source_reference_hash": "a" * 64,
    }
    with pytest.raises(stage_execution.StageExecutionError, match="raw ComfyUI history"):
        stage_execution.build_stage_run_record(approved, submission, receipt, artifact)


def test_stage_run_record_rejects_artifact_outside_declared_output_root(tmp_path):
    report = _capability_report()
    source_graph = _shot_graph()
    draft = stage_execution.build_stage_execution_draft(
        _shot_plan(report), source_graph, _camera_profile(), report,
        ui_workflow=_shot_ui(), image_name="ref.png", reference_artifact=_accepted_reference(),
    )
    approved = stage_execution.approve_stage_execution_draft(draft, _event(draft, tmp_path), tmp_path)
    consumption = stage_execution.build_stage_consumption(approved, "root-boundary")
    consumption_path = stage_execution.write_stage_consumption(tmp_path, consumption)
    submission = stage_execution.build_stage_submission(
        approved, source_graph, consumption, consumption_path,
        profile=_camera_profile(), capability_report=report, reference_image_name="ref.png",
        ui_workflow=_shot_ui(), reference_artifact=_accepted_reference(),
    )
    receipt = stage_execution.submit_stage(
        submission,
        lambda request: {"prompt_id": "prompt-root-boundary", "node_errors": {}},
        receipt_path=tmp_path / f'{consumption["consumption_id"]}.stage-enqueue-receipt.json',
    )
    image_path = tmp_path / "outside.png"
    image_path.write_bytes(_valid_png_bytes())
    image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
    history = {
        "prompt-root-boundary": {
            "prompt": [
                "queue",
                "prompt-root-boundary",
                submission["api_graph"],
                {"extra_data": {"prompt_forge_enqueue_request_id": submission["enqueue_request_id"]}},
            ],
            "status": {"status_str": "success", "completed": True},
        }
    }
    artifact = {
        "artifact_type": "ShotImage",
        "accepted": True,
        "content_hash": image_hash,
        "artifact_path": str(image_path.resolve()),
        "source_reference_hash": "a" * 64,
    }
    with pytest.raises(stage_execution.StageExecutionError, match="output root"):
        stage_execution.build_stage_run_record(
            approved, submission, receipt, artifact, history=history, artifact_root=tmp_path / "output",
        )
