import copy
import concurrent.futures
import hashlib
import threading
import io
import json
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from runtime.contracts import canonical_json, content_hash
from runtime.execution import (
    ExecutionError,
    _validate_multiview_profile,
    approve_execution_draft,
    build_approval_consumption,
    build_execution_draft,
    build_multiview_run_record,
    submit_multiview,
    build_run_record,
    load_pending_bundle,
    write_pending_bundle,
    validate_multiview_mcp_preflight,
)
import runtime.execution as execution_module
import runtime.multiview_evidence as multiview_evidence
import runtime.runtime_cli as runtime_cli


PROFILE_PATH = Path(__file__).parents[1] / "profiles" / "flux2-klein-multiview.json"
V2_PROFILE_PATH = Path(__file__).parents[1] / "profiles" / "flux2-klein-multiview-flat-v2.json"
API_PATH = Path(__file__).parent / "fixtures" / "flux-api-minimal.json"
CAMERA_API_PATH = Path(__file__).parent / "fixtures" / "camera-api-minimal.json"
CAMERA_UI_PATH = Path(__file__).parent / "fixtures" / "camera-ui-minimal.json"
CAMERA_FINGERPRINT = "96aac5b2fc5e565eadf4b9aba8d7c59016d327589fc40153be737b6187f27011"
FINGERPRINT = "fff6236efa6727ac6584d61f640a63f9602b2d07a545d216b96a870a681e6faf"
POSE_IDS = [368, 151, 152, 154, 360, 364, 148, 149, 147, 373, 150, 367]


def _v1_profile():
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _profile():
    return _v2_promotion_evidence()[0]


def _api_graph():
    return json.loads(API_PATH.read_text(encoding="utf-8"))


def test_v2_profile_is_pinned_without_replacing_v1():
    v1 = _v1_profile()
    v2 = json.loads(V2_PROFILE_PATH.read_text(encoding="utf-8"))

    multiview_evidence.validate_profile(v1, "flux2-klein-multiview-v1")
    multiview_evidence.validate_profile(v2, "flux2-klein-multiview-flat-v2")
    assert v2["workflow_fingerprint"] == multiview_evidence.FINGERPRINT
    assert v2["source_api_graph_hash"] == multiview_evidence.SOURCE_API_GRAPH_HASH
    assert v2["promotion_receipt_hash"] == multiview_evidence.PROMOTION_RECEIPT_HASH


def test_live_promotion_receipt_hash_binds_fresh_run_and_normalization():
    receipt = {
        "schema_version": "2.0",
        "receipt_type": "comfyui-mcp-multiview-promotion",
        "source_run": {
            "prompt_id": "f47e75ef-cd40-4bf5-9b77-90f538a605d9",
            "output_png_sha256": "fe455f8a06c0ca9b1d9c8a3c83c22edc40c9fc8948f240db370f0e502b0e23ce",
            "embedded_api_graph_hash": "4607fec84e41b91ecbbb292136b488ebb0ddee3ab9773b3654393554f83e084e",
            "embedded_ui_fingerprint": None,
            "embedded_ui_metadata": "absent",
        },
        "flat_workflow": {
            "workflow_id": "prompt-forge-flat-v2",
            "workflow_name": "PromptForge-Flux2-Klein-multiview-flat-v2.json",
            "ui_fingerprint": "9dc2b01e2aea0b051113b187b134d007f452df6c83cfcbbd8d325eaa4c29e4da",
            "source_api_graph_hash": "450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36",
        },
        "normalization": {
            "policy": "drop-meta-empty-switch-text-integral-float-v1",
            "source_embedded_api_graph_hash": "4607fec84e41b91ecbbb292136b488ebb0ddee3ab9773b3654393554f83e084e",
            "promoted_api_graph_hash": "450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36",
            "normalized_graph_hash": "4414f9ebe1867e17bf66da0b1a9136f05587ac197c2d0e7ee46ef57d098caa73",
            "difference_count": 31,
            "allowed_difference_kinds": ["metadata", "empty-widget", "integral-float"],
        },
        "response_digests": {
            "ui": "af1dfd15758445c9c5afda012fefb318b7149ecf964fc1768e58b0db91646bff",
            "api": "450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36",
            "strip": "450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36",
            "validate": "460769002518875e39704cdad38a6c343138240f8c513f2b73befeb1063af01b",
            "runtime": "f5ae16dd60e9390ae70780baf72fe5717f4f3378eeab102cb56e98ab4ce678f9",
        },
        "orchestrator": {"name": "prompt-forge", "trust_model": "trusted-local-orchestrator"},
    }

    assert content_hash(receipt) == multiview_evidence.PROMOTION_RECEIPT_HASH


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


def _mcp_receipt(api_graph=None):
    graph = _api_graph() if api_graph is None else api_graph
    actual_ui_workflow = {"id": "test-flux-ui", **_ui_workflow()}
    validation = {"valid": True, "errors": [], "warnings": []}
    runtime = {
        "runtime": "local",
        "usesApiNodes": False,
        "apiNodes": [],
        "remoteNodes": [],
        "unknownNodes": [],
    }
    receipt = {
        "schema_version": "1.0",
        "receipt_type": "comfyui-mcp-ui-to-api",
        "adapter": {
            "name": "comfyui-mcp",
            "version": "0.49.0",
            "tools": {
                "load": "get_workflow",
                "convert": "get_workflow",
                "strip": "strip_workflow",
                "validate": "validate_workflow",
                "runtime": "check_workflow_runtime",
            },
        },
        "saved_workflow": {
            "workflow_id": "test-flux-ui",
            "workflow_name": _v1_profile()["workflow_name"],
            "ui_fingerprint": FINGERPRINT,
        },
        "conversion": {
            "source_ui_fingerprint": FINGERPRINT,
            "api_graph_hash": content_hash(graph),
        },
        "validation": validation,
        "runtime": runtime,
        "orchestrator": {"name": "prompt-forge", "trust_model": "trusted-local-orchestrator"},
        "invocations": {
            "load": {"name": "get_workflow", "arguments": {"workflow_id": "test-flux-ui", "format": "ui"}, "response_digest": content_hash(actual_ui_workflow)},
            "convert": {"name": "get_workflow", "arguments": {"workflow_id": "test-flux-ui", "format": "api"}, "response_digest": content_hash(graph)},
            "strip": {"name": "strip_workflow", "arguments": {"workflow_id": "test-flux-ui"}, "response_digest": content_hash(graph)},
            "validate": {"name": "validate_workflow", "arguments": {"workflow": graph}, "response_digest": content_hash(validation)},
            "runtime": {"name": "check_workflow_runtime", "arguments": {"workflow": graph}, "response_digest": content_hash(runtime)},
        },
    }
    return receipt


def _controlled_mcp_tools():
    graph = _api_graph()
    ui_workflow = {"id": "prompt-forge-flat-v2", **_ui_workflow()}
    validation = {"valid": True, "errors": [], "warnings": []}
    runtime = {
        "runtime": "local",
        "usesApiNodes": False,
        "apiNodes": [],
        "remoteNodes": [],
        "unknownNodes": [],
    }
    calls = []

    def get_workflow(arguments):
        calls.append(("get_workflow", copy.deepcopy(arguments)))
        return copy.deepcopy(ui_workflow if arguments["format"] == "ui" else graph)

    def strip_workflow(arguments):
        calls.append(("strip_workflow", copy.deepcopy(arguments)))
        return copy.deepcopy(graph)

    def validate_workflow(arguments):
        calls.append(("validate_workflow", copy.deepcopy(arguments)))
        return copy.deepcopy(validation)

    def check_workflow_runtime(arguments):
        calls.append(("check_workflow_runtime", copy.deepcopy(arguments)))
        return copy.deepcopy(runtime)

    return {
        "get_workflow": get_workflow,
        "strip_workflow": strip_workflow,
        "validate_workflow": validate_workflow,
        "check_workflow_runtime": check_workflow_runtime,
    }, calls


def _v2_promotion_evidence():
    graph = _api_graph()
    ui_workflow = {"id": "prompt-forge-flat-v2", **_ui_workflow()}
    validation = {"valid": True, "errors": [], "warnings": []}
    runtime = {
        "runtime": "local",
        "usesApiNodes": False,
        "apiNodes": [],
        "remoteNodes": [],
        "unknownNodes": [],
    }
    receipt = {
        "schema_version": "2.0",
        "receipt_type": "comfyui-mcp-multiview-promotion",
        "source_run": {
            "prompt_id": "test-prompt-id",
            "output_png_sha256": "1" * 64,
            "embedded_api_graph_hash": "2" * 64,
            "embedded_ui_fingerprint": None,
            "embedded_ui_metadata": "absent",
        },
        "flat_workflow": {
            "workflow_id": "prompt-forge-flat-v2",
            "workflow_name": "PromptForge-Flux2-Klein-multiview-flat-v2.json",
            "ui_fingerprint": "4" * 64,
            "source_api_graph_hash": content_hash(graph),
        },
        "normalization": {
            "policy": "drop-meta-empty-switch-text-integral-float-v1",
            "source_embedded_api_graph_hash": "2" * 64,
            "promoted_api_graph_hash": content_hash(graph),
            "normalized_graph_hash": "5" * 64,
            "difference_count": 31,
            "allowed_difference_kinds": ["metadata", "empty-widget", "integral-float"],
        },
        "response_digests": {
            "ui": content_hash(ui_workflow),
            "api": content_hash(graph),
            "strip": content_hash(graph),
            "validate": content_hash(validation),
            "runtime": content_hash(runtime),
        },
        "orchestrator": {
            "name": "prompt-forge",
            "trust_model": "trusted-local-orchestrator",
        },
    }
    profile = _v1_profile()
    profile.update(
        schema_version="2.0",
        profile_id="flux2-klein-multiview-flat-v2",
        workflow_id="prompt-forge-flat-v2",
        workflow_name="PromptForge-Flux2-Klein-multiview-flat-v2.json",
        workflow_fingerprint="4" * 64,
        source_api_graph_hash=content_hash(graph),
        promotion_receipt_hash=content_hash(receipt),
    )
    return profile, receipt, ui_workflow, graph, validation, runtime


def _trust_v2_test_evidence(monkeypatch, profile):
    monkeypatch.setattr(multiview_evidence, "FINGERPRINT", profile["workflow_fingerprint"])
    monkeypatch.setattr(
        multiview_evidence, "SOURCE_API_GRAPH_HASH", profile["source_api_graph_hash"]
    )
    monkeypatch.setattr(multiview_evidence, "PROFILE_DIGEST_V2", content_hash(profile))
    monkeypatch.setattr(
        multiview_evidence, "PROMOTION_RECEIPT_HASH", profile["promotion_receipt_hash"]
    )
    monkeypatch.setattr(execution_module, "_MULTIVIEW_FINGERPRINT", profile["workflow_fingerprint"])
    monkeypatch.setattr(
        execution_module, "_MULTIVIEW_SOURCE_API_GRAPH_HASH", profile["source_api_graph_hash"]
    )
    monkeypatch.setattr(
        execution_module,
        "_MULTIVIEW_PROMOTION_RECEIPT_HASH",
        profile["promotion_receipt_hash"],
    )
    monkeypatch.setattr(
        execution_module, "structure_fingerprint", lambda workflow: profile["workflow_fingerprint"]
    )
    monkeypatch.setattr(
        multiview_evidence,
        "structure_fingerprint",
        lambda workflow: profile["workflow_fingerprint"],
    )


def test_v2_promotion_receipt_binds_source_and_all_flat_response_digests(monkeypatch):
    profile, receipt, ui_workflow, graph, validation, runtime = _v2_promotion_evidence()
    _trust_v2_test_evidence(monkeypatch, profile)
    monkeypatch.setattr(multiview_evidence, "structure_fingerprint", lambda workflow: "4" * 64)

    validated = multiview_evidence.validate_promotion_receipt(
        promotion_receipt=receipt,
        profile=profile,
        actual_ui_workflow=ui_workflow,
        converted_api_graph=graph,
        stripped_api_graph=graph,
        validation=validation,
        runtime=runtime,
    )

    assert validated == receipt


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("prompt_id", ""),
        ("output_png_sha256", "f" * 64),
        ("embedded_api_graph_hash", "e" * 64),
    ],
)
def test_v2_promotion_receipt_rejects_tampered_historical_provenance(
    monkeypatch, field, value
):
    profile, receipt, ui_workflow, graph, validation, runtime = _v2_promotion_evidence()
    _trust_v2_test_evidence(monkeypatch, profile)
    monkeypatch.setattr(multiview_evidence, "structure_fingerprint", lambda workflow: "4" * 64)
    receipt["source_run"][field] = value

    with pytest.raises(multiview_evidence.MultiviewEvidenceError, match="promotion receipt"):
        multiview_evidence.validate_promotion_receipt(
            promotion_receipt=receipt,
            profile=profile,
            actual_ui_workflow=ui_workflow,
            converted_api_graph=graph,
            stripped_api_graph=graph,
            validation=validation,
            runtime=runtime,
        )


def test_v2_promotion_receipt_rejects_api_graph_outside_profile_pin(monkeypatch):
    profile, receipt, ui_workflow, graph, validation, runtime = _v2_promotion_evidence()
    _trust_v2_test_evidence(monkeypatch, profile)
    monkeypatch.setattr(multiview_evidence, "structure_fingerprint", lambda workflow: "4" * 64)
    graph = copy.deepcopy(graph)
    graph["111"]["inputs"]["image"] = "drifted.png"

    with pytest.raises(multiview_evidence.MultiviewEvidenceError, match="profile pin"):
        multiview_evidence.validate_promotion_receipt(
            promotion_receipt=receipt,
            profile=profile,
            actual_ui_workflow=ui_workflow,
            converted_api_graph=graph,
            stripped_api_graph=graph,
            validation=validation,
            runtime=runtime,
        )


def test_controlled_mcp_builder_calls_exact_tools_before_production_draft(tmp_path, monkeypatch):
    record, artifact, stage1_graph, stage1_history, consumption, consumption_path = _stage1_chain(tmp_path)
    monkeypatch.setattr(execution_module, "structure_fingerprint", lambda workflow: FINGERPRINT)
    monkeypatch.setattr(multiview_evidence, "structure_fingerprint", lambda workflow: FINGERPRINT)
    tools, calls = _controlled_mcp_tools()
    profile, promotion_receipt, _, _, _, _ = _v2_promotion_evidence()
    _trust_v2_test_evidence(monkeypatch, profile)

    draft = execution_module.build_multiview_draft_with_mcp(
        stage1_record=record,
        base_artifact=artifact,
        stage1_api_graph=stage1_graph,
        stage1_history=stage1_history,
        stage1_approval_consumption=consumption,
        stage1_consumption_path=str(consumption_path.resolve()),
        workflow_profile_id=profile["profile_id"],
        workflow_fingerprint=profile["workflow_fingerprint"],
        workflow_id=profile["workflow_id"],
        capability_report=_capability_report(),
        profile=profile,
        promotion_receipt=promotion_receipt,
        upload_receipt=_upload_receipt(tmp_path, artifact),
        mcp_tools=tools,
    )

    graph = _api_graph()
    assert calls == [
        ("get_workflow", {"filename": profile["workflow_name"], "format": "ui"}),
        ("get_workflow", {"filename": profile["workflow_name"], "format": "api"}),
        ("strip_workflow", {"filename": profile["workflow_name"], "format": "api"}),
        ("validate_workflow", {"workflow": graph}),
        ("check_workflow_runtime", {"graph": graph}),
    ]
    assert draft["plan_state"] == "draft"
    assert draft["saved_workflow_id"] == profile["workflow_id"]
    assert draft["promotion_receipt_hash"] == profile["promotion_receipt_hash"]


def test_production_builder_rejects_legacy_v1_profile_before_mcp_calls():
    tools, calls = _controlled_mcp_tools()

    with pytest.raises(ExecutionError, match="flat v2 profile"):
        execution_module.build_multiview_draft_with_mcp(
            stage1_record={},
            base_artifact={},
            stage1_api_graph={},
            stage1_history={},
            stage1_approval_consumption={},
            stage1_consumption_path="unused",
            workflow_profile_id="flux2-klein-multiview-v1",
            workflow_fingerprint=FINGERPRINT,
            workflow_id="test-flux-ui",
            capability_report=_capability_report(),
            profile=_v1_profile(),
            promotion_receipt={},
            upload_receipt={},
            mcp_tools=tools,
        )

    assert calls == []


def test_mcp_preflight_rejects_mix_and_match_api_graph(monkeypatch):
    monkeypatch.setattr(multiview_evidence, "structure_fingerprint", lambda workflow: FINGERPRINT)
    receipt = _mcp_receipt()
    other_graph = _api_graph()
    other_graph["111"]["inputs"]["image"] = "other.png"

    with pytest.raises(ExecutionError, match="API graph hash"):
        validate_multiview_mcp_preflight(
            conversion_receipt=receipt,
            capability_report=_capability_report(),
            profile=_v1_profile(),
            actual_ui_workflow={"id": "test-flux-ui", **_ui_workflow()},
            api_graph=other_graph,
        )


def test_mcp_preflight_rejects_remote_api_node_even_when_receipt_claims_local(monkeypatch):
    monkeypatch.setattr(multiview_evidence, "structure_fingerprint", lambda workflow: FINGERPRINT)
    graph = _api_graph()
    graph["900"] = {"class_type": "RemoteApiNode", "inputs": {}}

    with pytest.raises(ExecutionError, match="remote/API nodes"):
        validate_multiview_mcp_preflight(
            conversion_receipt=_mcp_receipt(graph),
            capability_report=_capability_report(),
            profile=_v1_profile(),
            actual_ui_workflow={"id": "test-flux-ui", **_ui_workflow()},
            api_graph=graph,
        )


def test_flux_profile_digest_rejects_output_map_tamper():
    profile = _v1_profile()
    profile["output_nodes"]["524"]["view_label"] = "attacker_view"

    with pytest.raises(ExecutionError, match="trusted"):
        _validate_multiview_profile(profile, "flux2-klein-multiview-v1")


def test_stage1_source_rejects_minimal_self_hashed_record(tmp_path, monkeypatch):
    monkeypatch.setattr(execution_module, "structure_fingerprint", lambda workflow: FINGERPRINT)
    record, artifact = _minimal_artifact(tmp_path)
    profile, promotion_receipt, _, _, _, _ = _v2_promotion_evidence()
    _trust_v2_test_evidence(monkeypatch, profile)

    with pytest.raises(ExecutionError, match="complete Stage 1 RunRecord"):
        execution_module.build_multiview_draft_with_mcp(
            stage1_record=record,
            base_artifact=artifact,
            stage1_api_graph={},
            stage1_history={},
            stage1_approval_consumption={},
            stage1_consumption_path=str(tmp_path.resolve()),
            workflow_profile_id=profile["profile_id"],
            workflow_fingerprint=profile["workflow_fingerprint"],
            workflow_id=profile["workflow_id"],
            capability_report=_capability_report(),
            profile=profile,
            promotion_receipt=promotion_receipt,
            upload_receipt={},
            mcp_tools=_controlled_mcp_tools()[0],
        )


def test_stage1_source_rejects_non_png_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(execution_module, "structure_fingerprint", lambda workflow: FINGERPRINT)
    record, artifact = _minimal_artifact(tmp_path)
    profile, promotion_receipt, _, _, _, _ = _v2_promotion_evidence()
    _trust_v2_test_evidence(monkeypatch, profile)
    record.update(
        {
            "task_context_hash": "1" * 64,
            "prompt_build_hash": "2" * 64,
            "prompt_build": {},
            "source_api_graph_hash": "3" * 64,
            "executable_api_graph_hash": "4" * 64,
            "execution_plan_hash": content_hash(record["execution_plan"]),
            "prompt_id": "stage1-prompt",
            "history_status": {"status_str": "success", "completed": True},
                "history_outputs": [
                    {"node_id": "900", "filename": "base.png", "subfolder": "", "type": "output"}
                ],
                "artifact_descriptor": {"node_id": "900", "filename": "base.png", "subfolder": "", "type": "output"},
                "artifact_hashes_verified": False,
            "input_hashes": {},
        }
    )
    record.pop("record_hash")
    record["record_hash"] = content_hash(record)
    artifact["source_record_hash"] = record["record_hash"]

    with pytest.raises(ExecutionError, match="PNG"):
        execution_module.build_multiview_draft_with_mcp(
            stage1_record=record,
            base_artifact=artifact,
            stage1_api_graph={},
            stage1_history={},
            stage1_approval_consumption={},
            stage1_consumption_path=str(tmp_path.resolve()),
            workflow_profile_id=profile["profile_id"],
            workflow_fingerprint=profile["workflow_fingerprint"],
            workflow_id=profile["workflow_id"],
            capability_report=_capability_report(),
            profile=profile,
            promotion_receipt=promotion_receipt,
            upload_receipt={},
            mcp_tools=_controlled_mcp_tools()[0],
        )


def _minimal_stage1_record(filename, digest):
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


def _minimal_artifact(tmp_path, *, accepted=True, artifact_type="CharacterBaseImage"):
    path = tmp_path / "base.png"
    path.write_bytes(b"real-png-fixture")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    record = _minimal_stage1_record(path.name, digest)
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


def _png_bytes():
    def chunk(kind, data):
        return (
            len(data).to_bytes(4, "big")
            + kind
            + data
            + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")
        )

    ihdr = (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes((8, 6, 0, 0, 0))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\xff")) + chunk(b"IEND", b"")


def _stage1_chain(tmp_path):
    image_path = tmp_path / "base.png"
    image_path.write_bytes(_png_bytes())
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    build = {
        "schema_version": "1.0",
        "target": "image",
        "generation_mode": "text-to-image",
        "model_id": "anima",
        "dialect": "tags",
        "prompt": "score_9, 1girl, solo, from_front, full_body",
        "negative_prompt": "worst quality, low quality, watermark",
        "validated_tags": ["1girl", "solo", "from_front", "full_body"],
        "rejected_tags": [],
        "recipe_control_tokens": ["score_9"],
        "locked_facts": ["1girl"],
        "ready_to_execute": True,
        "execution": {"requested": True, "performed": False},
    }
    camera_profile = {
        "schema_version": "1.0",
        "profile_id": "camera-anima-v1",
        "runtime_classification": "local",
        "workflow_fingerprint": CAMERA_FINGERPRINT,
        "api_normalization": {
            "schema_version": "1.0",
            "literal_inputs": [
                {"node_id": 26, "input_name": "text", "ui_node_id": 26, "widget_index": 1}
            ],
            "output_fallbacks": [
                {"source_node_id": 111, "output_index": 0, "target_node_id": 35, "target_input": "images"},
                {"source_node_id": 111, "output_index": 0, "target_node_id": 490, "target_input": "images"},
            ],
            "remove_nodes": [28, 41, 52, 62, 67, 70, 77],
        },
        "allowed_mutations": [],
        "slots": {
            "positive_prompt": {"id": 24, "type": "ImpactWildcardProcessor", "title": "POSITIVE"},
            "negative_prompt": {"id": 25, "type": "ImpactWildcardProcessor", "title": "NEGATIVE"},
            "camera_angle": {"id": 583, "type": "CameraAngleNode"},
            "camera_extra": {"id": 585, "type": "CameraExtraConfigNode"},
        },
        "img2img": {
            "group_id": 3,
            "node_ids": [21, 58, 57, 59],
            "load_image_node_id": 21,
            "vae_encode_node_id": 59,
            "latent_switch_node_id": 75,
            "sampler_node_id": 27,
            "expected_path_node_ids": [27, 75, 59],
        },
        "expected_outputs": ["image/png"],
    }
    camera_graph = json.loads(CAMERA_API_PATH.read_text(encoding="utf-8"))
    patches = [
        {"slot": "positive_prompt", "input": "wildcard_text", "value": build["prompt"]},
        {"slot": "positive_prompt", "input": "populated_text", "value": build["prompt"]},
        {"slot": "negative_prompt", "input": "wildcard_text", "value": build["negative_prompt"]},
        {"slot": "negative_prompt", "input": "populated_text", "value": build["negative_prompt"]},
    ]
    draft = build_execution_draft(
        "character-base",
        build,
        "camera-anima-v1",
        CAMERA_FINGERPRINT,
        patches,
        capability_report=_capability_report(),
        profile=camera_profile,
        actual_ui_workflow=json.loads(CAMERA_UI_PATH.read_text(encoding="utf-8")),
        api_graph=camera_graph,
    )
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    executable = copy.deepcopy(camera_graph)
    executable["24"]["inputs"].update(wildcard_text=build["prompt"], populated_text=build["prompt"])
    executable["25"]["inputs"].update(wildcard_text=build["negative_prompt"], populated_text=build["negative_prompt"])
    prompt_id = "stage1-prompt"
    history = {
        prompt_id: {
            "prompt": [1, prompt_id, executable],
            "status": {"status_str": "success", "completed": True},
            "outputs": {"900": {"images": [{"filename": image_path.name, "subfolder": "", "type": "output"}]}},
        }
    }
    record = build_run_record(
        _task_context(), build, camera_graph, plan, prompt_id, "succeeded", {},
        {image_path.name: digest}, history=history,
    )
    consumption = build_approval_consumption(plan, "stage1-enqueue-request")
    consumption_path = tmp_path / f'{consumption["approval_id"]}.consumed.json'
    consumption_path.write_text(canonical_json(consumption) + "\n", encoding="utf-8")
    artifact = {
        "schema_version": "1.0",
        "artifact_type": "CharacterBaseImage",
        "accepted": True,
        "content_hash": digest,
        "lineage_id": "lineage-1",
        "source_record_hash": record["record_hash"],
        "artifact_path": str(image_path.resolve()),
        "artifact_root": str(tmp_path.resolve()),
        "visual_acceptance": {"front_facing": True, "identity_visible": True},
    }
    return record, artifact, camera_graph, history, consumption, consumption_path


def _upload_receipt(tmp_path, artifact):
    relative = f'prompt-forge/{artifact["lineage_id"]}/character-base-{artifact["content_hash"]}.png'
    root = tmp_path / "comfy-input"
    server_path = root.joinpath(*relative.split("/"))
    server_path.parent.mkdir(parents=True, exist_ok=True)
    server_path.write_bytes(Path(artifact["artifact_path"]).read_bytes())
    return {
        "schema_version": "1.0",
        "receipt_type": "comfyui-mcp-image-upload",
        "adapter": {"name": "comfyui-mcp", "version": "0.49.0", "tool": "upload_image"},
        "source_artifact_hash": artifact["content_hash"],
        "requested_filename": relative,
        "stored_filename": relative,
        "server_input_root": str(root.resolve()),
        "server_input_path": str(server_path.resolve()),
        "server_content_hash": artifact["content_hash"],
    }


@pytest.mark.parametrize(
    "descriptor",
    [
        {"node_id": "900", "filename": "base.png", "subfolder": "other", "type": "output"},
        {"node_id": "900", "filename": "base.png", "subfolder": "", "type": "temp"},
    ],
)
def test_stage1_artifact_must_match_exact_output_history_descriptor(tmp_path, monkeypatch, descriptor):
    record, artifact, graph, history, consumption, consumption_path = _stage1_chain(tmp_path)
    prompt_id = record["prompt_id"]
    history[prompt_id]["outputs"] = {"900": {"images": [{k: v for k, v in descriptor.items() if k != "node_id"}]}}
    record["history_outputs"] = [descriptor]
    record["artifact_descriptor"] = descriptor
    unsigned = dict(record)
    unsigned.pop("record_hash")
    record["record_hash"] = content_hash(unsigned)
    artifact["source_record_hash"] = record["record_hash"]
    monkeypatch.setattr(execution_module, "structure_fingerprint", lambda workflow: FINGERPRINT)
    monkeypatch.setattr(multiview_evidence, "structure_fingerprint", lambda workflow: FINGERPRINT)
    profile, promotion_receipt, _, _, _, _ = _v2_promotion_evidence()
    _trust_v2_test_evidence(monkeypatch, profile)

    with pytest.raises(ExecutionError, match="history descriptor"):
        execution_module.build_multiview_draft_with_mcp(
            stage1_record=record, base_artifact=artifact, stage1_api_graph=graph,
            stage1_history=history, stage1_approval_consumption=consumption,
            stage1_consumption_path=consumption_path,
            workflow_profile_id=profile["profile_id"],
            workflow_fingerprint=profile["workflow_fingerprint"],
            workflow_id=profile["workflow_id"],
            capability_report=_capability_report(), profile=profile,
            promotion_receipt=promotion_receipt,
            upload_receipt=_upload_receipt(tmp_path, artifact),
            mcp_tools=_controlled_mcp_tools()[0],
        )


def _draft(tmp_path, monkeypatch, *, include_stage1=False):
    record, artifact, stage1_graph, stage1_history, consumption, consumption_path = _stage1_chain(tmp_path)
    monkeypatch.setattr(execution_module, "structure_fingerprint", lambda workflow: FINGERPRINT)
    monkeypatch.setattr(multiview_evidence, "structure_fingerprint", lambda workflow: FINGERPRINT)
    profile, promotion_receipt, _, _, _, _ = _v2_promotion_evidence()
    _trust_v2_test_evidence(monkeypatch, profile)
    draft = execution_module.build_multiview_draft_with_mcp(
        stage1_record=record,
        base_artifact=artifact,
        stage1_api_graph=stage1_graph,
        stage1_history=stage1_history,
        stage1_approval_consumption=consumption,
        stage1_consumption_path=str(consumption_path.resolve()),
        workflow_profile_id=profile["profile_id"],
        workflow_fingerprint=profile["workflow_fingerprint"],
        workflow_id=profile["workflow_id"],
        capability_report=_capability_report(),
        profile=profile,
        promotion_receipt=promotion_receipt,
        upload_receipt=_upload_receipt(tmp_path, artifact),
        mcp_tools=_controlled_mcp_tools()[0],
    )
    if include_stage1:
        return record, artifact, draft, stage1_graph, stage1_history, consumption, consumption_path
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
    record, artifact, stage1_graph, stage1_history, consumption, consumption_path = _stage1_chain(tmp_path)
    monkeypatch.setattr(execution_module, "structure_fingerprint", lambda workflow: FINGERPRINT)
    monkeypatch.setattr(multiview_evidence, "structure_fingerprint", lambda workflow: FINGERPRINT)
    profile, promotion_receipt, _, _, _, _ = _v2_promotion_evidence()
    _trust_v2_test_evidence(monkeypatch, profile)
    change(artifact)
    with pytest.raises(ExecutionError, match=match):
        execution_module.build_multiview_draft_with_mcp(
            stage1_record=record,
            base_artifact=artifact,
            stage1_api_graph=stage1_graph,
            stage1_history=stage1_history,
            stage1_approval_consumption=consumption,
            stage1_consumption_path=str(consumption_path.resolve()),
            workflow_profile_id=profile["profile_id"],
            workflow_fingerprint=profile["workflow_fingerprint"],
            workflow_id=profile["workflow_id"],
            capability_report=_capability_report(),
            profile=profile,
            promotion_receipt=promotion_receipt,
            upload_receipt=_upload_receipt(tmp_path, artifact),
            mcp_tools=_controlled_mcp_tools()[0],
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
    profile, promotion_receipt, _, _, _, _ = _v2_promotion_evidence()
    assert draft["workflow_fingerprint"] == profile["workflow_fingerprint"]
    assert draft["promotion_receipt"] == promotion_receipt
    assert draft["promotion_receipt_hash"] == profile["promotion_receipt_hash"]
    assert draft["preflight"]["promotion"]["receipt_hash"] == profile["promotion_receipt_hash"]
    assert draft["draft_hash"] == content_hash({k: v for k, v in draft.items() if k != "draft_hash"})


def test_generic_approval_and_consumption_accept_stage2_exact_draft(tmp_path, monkeypatch):
    _, _, draft = _draft(tmp_path, monkeypatch)
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    consumption = build_approval_consumption(plan, "stage2-request-1")

    assert plan["stage"] == "character-multiview"
    assert plan["promotion_receipt_hash"] == draft["promotion_receipt_hash"]
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


def test_pending_bundle_requires_exact_draft_frozen_inputs_and_expiry(tmp_path, monkeypatch):
    _, _, draft = _draft(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    path = write_pending_bundle(
        tmp_path,
        draft,
        expires_at=(now + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    )
    now = datetime.now(timezone.utc)
    bundle = load_pending_bundle(path, expected_stage="character-multiview", now=now)

    assert bundle["draft_hash"] == draft["draft_hash"]
    assert bundle["frozen_inputs"]["upload_receipt_hash"] == draft["upload_receipt_hash"]
    assert bundle["frozen_inputs"]["promotion_receipt_hash"] == draft["promotion_receipt_hash"]
    assert bundle["consumption_namespace"] == f"character-multiview:{draft['draft_hash']}"

    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["frozen_inputs"]["uploaded_filename"] = "attacker.png"
    tampered["bundle_hash"] = content_hash({k: v for k, v in tampered.items() if k != "bundle_hash"})
    path.write_text(canonical_json(tampered) + "\n", encoding="utf-8")
    with pytest.raises(ExecutionError, match="frozen inputs"):
        load_pending_bundle(path, expected_stage="character-multiview", now=now)


def test_pending_bundle_rejects_expired_or_cross_stage_resume(tmp_path, monkeypatch):
    _, _, draft = _draft(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    path = write_pending_bundle(
        tmp_path,
        draft,
        expires_at=(now + timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
    )
    with pytest.raises(ExecutionError, match="stage"):
        load_pending_bundle(path, expected_stage="character-base", now=now)
    with pytest.raises(ExecutionError, match="expired"):
        load_pending_bundle(path, expected_stage="character-multiview", now=now + timedelta(seconds=2))


def test_pending_bundle_rejects_future_created_time(tmp_path, monkeypatch):
    _, _, draft = _draft(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    path = write_pending_bundle(
        tmp_path, draft, expires_at=(now + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    )
    bundle = json.loads(path.read_text(encoding="utf-8"))
    bundle["created_at"] = (now + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    bundle["bundle_hash"] = content_hash({k: v for k, v in bundle.items() if k != "bundle_hash"})
    path.write_text(canonical_json(bundle) + "\n", encoding="utf-8")
    with pytest.raises(ExecutionError, match="created"):
        load_pending_bundle(path, expected_stage="character-multiview", now=now)


def test_submit_multiview_calls_trusted_enqueue_and_persists_bound_receipt(tmp_path, monkeypatch):
    _, artifact, draft = _draft(tmp_path, monkeypatch)
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    consumption = build_approval_consumption(plan, "stage2-enqueue-request")
    consumption_path = tmp_path / f'{consumption["approval_id"]}.consumed.json'
    consumption_path.write_text(canonical_json(consumption) + "\n", encoding="utf-8")
    calls = []

    def enqueue_workflow(request):
        calls.append(copy.deepcopy(request))
        response = {"prompt_id": "stage2-prompt", "number": 42, "node_errors": {}}
        return {
            "tool": {"name": "enqueue_workflow", "arguments": request},
            "response": response,
            "response_digest": content_hash(response),
            "orchestrator": {"name": "prompt-forge", "trust_model": "trusted-local-orchestrator"},
        }

    submitted = submit_multiview(
        approved_plan=plan,
        source_api_graph=_api_graph(),
        upload_receipt=_upload_receipt(tmp_path, artifact),
        approval_consumption=consumption,
        consumption_path=consumption_path,
        enqueue_workflow=enqueue_workflow,
    )

    assert calls[0]["client_id"] == consumption["enqueue_request_id"]
    assert calls[0]["extra_data"]["prompt_forge_enqueue_request_id"] == consumption["enqueue_request_id"]
    assert calls[0]["prompt"] == submitted["submission"]["api_graph"]
    assert submitted["enqueue_receipt"]["prompt_id"] == "stage2-prompt"
    assert submitted["enqueue_receipt"]["submitted_graph_hash"] == plan["executable_api_graph_hash"]
    assert Path(submitted["enqueue_receipt_path"]).is_file()


def test_submit_multiview_is_exactly_once_across_concurrent_callers(tmp_path, monkeypatch):
    _, artifact, draft = _draft(tmp_path, monkeypatch)
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    consumption = build_approval_consumption(plan, "stage2-enqueue-request")
    consumption_path = tmp_path / f'{consumption["approval_id"]}.consumed.json'
    consumption_path.write_text(canonical_json(consumption) + "\n", encoding="utf-8")
    started = threading.Event()
    release = threading.Event()
    calls = []

    def enqueue_workflow(request):
        calls.append(copy.deepcopy(request))
        started.set()
        assert release.wait(timeout=5)
        response = {"prompt_id": "stage2-prompt", "node_errors": {}}
        return {
            "tool": {"name": "enqueue_workflow", "arguments": request},
            "response": response,
            "response_digest": content_hash(response),
            "orchestrator": {"name": "prompt-forge-test", "trust_model": "trusted-local-orchestrator"},
        }

    kwargs = {
        "approved_plan": plan,
        "source_api_graph": _api_graph(),
        "upload_receipt": _upload_receipt(tmp_path, artifact),
        "approval_consumption": consumption,
        "consumption_path": consumption_path,
        "enqueue_workflow": enqueue_workflow,
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(submit_multiview, **kwargs)
        assert started.wait(timeout=5)
        with pytest.raises(ExecutionError, match="in progress"):
            submit_multiview(**kwargs)
        release.set()
        first.result(timeout=5)
    completed = submit_multiview(**kwargs)
    assert len(calls) == 1
    assert completed["enqueue_receipt"]["prompt_id"] == "stage2-prompt"


@pytest.mark.parametrize("tamper", ["truncated", "wrong_response", "wrong_graph"])
def test_submit_multiview_recovery_rejects_forged_success_receipt(
    tmp_path, monkeypatch, tamper
):
    _, artifact, draft = _draft(tmp_path, monkeypatch)
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    consumption = build_approval_consumption(plan, "stage2-enqueue-request")
    consumption_path = tmp_path / f'{consumption["approval_id"]}.consumed.json'
    consumption_path.write_text(canonical_json(consumption) + "\n", encoding="utf-8")
    first = _trusted_submission(
        plan, _api_graph(), _upload_receipt(tmp_path, artifact), consumption, consumption_path
    )
    receipt_path = Path(first["enqueue_receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if tamper == "truncated":
        receipt = {"submission_intent_hash": receipt["submission_intent_hash"]}
    elif tamper == "wrong_response":
        receipt["response"]["prompt_id"] = "forged-prompt"
        receipt["receipt_hash"] = content_hash(
            {key: value for key, value in receipt.items() if key != "receipt_hash"}
        )
    else:
        receipt["submitted_graph_hash"] = "0" * 64
        receipt["receipt_hash"] = content_hash(
            {key: value for key, value in receipt.items() if key != "receipt_hash"}
        )
    receipt_path.write_text(canonical_json(receipt) + "\n", encoding="utf-8")
    recovery_calls = []

    with pytest.raises(ExecutionError, match="enqueue receipt"):
        submit_multiview(
            approved_plan=plan,
            source_api_graph=_api_graph(),
            upload_receipt=_upload_receipt(tmp_path, artifact),
            approval_consumption=consumption,
            consumption_path=consumption_path,
            enqueue_workflow=lambda request: recovery_calls.append(request),
        )

    assert recovery_calls == []


def test_submit_multiview_retains_failed_receipt_without_retry(tmp_path, monkeypatch):
    _, artifact, draft = _draft(tmp_path, monkeypatch)
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    consumption = build_approval_consumption(plan, "stage2-enqueue-request")
    consumption_path = tmp_path / f'{consumption["approval_id"]}.consumed.json'
    consumption_path.write_text(canonical_json(consumption) + "\n", encoding="utf-8")
    calls = []

    def enqueue_workflow(request):
        calls.append(copy.deepcopy(request))
        raise RuntimeError("transport lost")

    kwargs = {
        "approved_plan": plan,
        "source_api_graph": _api_graph(),
        "upload_receipt": _upload_receipt(tmp_path, artifact),
        "approval_consumption": consumption,
        "consumption_path": consumption_path,
        "enqueue_workflow": enqueue_workflow,
    }
    with pytest.raises(ExecutionError, match="failed receipt retained"):
        submit_multiview(**kwargs)
    failed = list(tmp_path.glob("*.enqueue-failed.json"))
    assert len(failed) == 1
    assert json.loads(failed[0].read_text(encoding="utf-8"))["status"] == "failed"
    with pytest.raises(ExecutionError, match="failed receipt"):
        submit_multiview(**kwargs)
    assert len(calls) == 1


def _task_context():
    return {
        "schema_version": "1.0",
        "shared_known": {"goal": "build multiview references", "background": [], "acceptance": [], "boundaries": []},
        "user_known_agent_unknown": {"references": [], "aesthetic_preferences": [], "real_world_constraints": []},
        "agent_known_user_unknown": {"capabilities": [], "risks": [], "alternatives": []},
        "shared_unknown": {"hypotheses": [], "experiments": []},
    }


def _trusted_submission(plan, graph, upload_receipt, consumption, consumption_path, prompt_id="stage2-prompt"):
    def enqueue_workflow(request):
        response = {"prompt_id": prompt_id, "number": 42, "node_errors": {}}
        return {
            "tool": {"name": "enqueue_workflow", "arguments": request},
            "response": response,
            "response_digest": content_hash(response),
            "orchestrator": {"name": "prompt-forge-test", "trust_model": "trusted-local-orchestrator"},
        }

    return submit_multiview(
        approved_plan=plan,
        source_api_graph=graph,
        upload_receipt=upload_receipt,
        approval_consumption=consumption,
        consumption_path=consumption_path,
        enqueue_workflow=enqueue_workflow,
    )


def test_multiview_run_record_binds_raw_executable_history_and_artifacts(tmp_path, monkeypatch):
    record, artifact, draft, stage1_graph, stage1_history, stage1_consumption, stage1_consumption_path = _draft(
        tmp_path, monkeypatch, include_stage1=True
    )
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    consumption = build_approval_consumption(plan, "stage2-enqueue-request")
    consumption_path = tmp_path / f'{consumption["approval_id"]}.consumed.json'
    consumption_path.write_text(canonical_json(consumption) + "\n", encoding="utf-8")
    graph = _api_graph()
    submitted = _trusted_submission(
        plan, graph, _upload_receipt(tmp_path, artifact), consumption, consumption_path
    )
    submission = submitted["submission"]
    executable = submission["api_graph"]
    prompt_id = "stage2-prompt"
    output_root = tmp_path / "comfy-output"
    output_root.mkdir()
    (output_root / "front.png").write_bytes(_png_bytes())
    history = {
        prompt_id: {
                "prompt": [1, prompt_id, executable, {"extra_data": {
                    "prompt_forge_enqueue_request_id": consumption["enqueue_request_id"]
                }}],
                "status": {"status_str": "success", "completed": True},
            "outputs": {"524": {"images": [{"filename": "front.png", "subfolder": "", "type": "output"}]}},
        }
    }
    result = build_multiview_run_record(
        _task_context(), record, artifact, graph, plan, _profile(), prompt_id,
        "succeeded",
        stage1_api_graph=stage1_graph,
        stage1_history=stage1_history,
        stage1_approval_consumption=stage1_consumption,
        stage1_consumption_path=stage1_consumption_path,
        approval_consumption=consumption,
        consumption_path=consumption_path,
        submission=submission,
        enqueue_receipt=submitted["enqueue_receipt"],
        enqueue_receipt_path=submitted["enqueue_receipt_path"],
        output_root=output_root,
        history=history,
    )

    assert result["stage"] == "character-multiview"
    assert result["promotion_receipt_hash"] == plan["promotion_receipt_hash"]
    assert result["upstream_record_hash"] == record["record_hash"]
    assert result["source_artifact_hash"] == artifact["content_hash"]
    assert result["raw_history"] == history
    assert result["artifacts"][0]["content_hash"] == hashlib.sha256(_png_bytes()).hexdigest()
    assert result["artifacts"][0]["lineage_id"] == artifact["lineage_id"]
    assert result["artifacts"][0]["hash_verified"] is True
    assert result["approval_consumption_id"] == consumption["consumption_id"]
    assert result["enqueue_request_id"] == consumption["enqueue_request_id"]
    assert result["record_hash"] == content_hash({k: v for k, v in result.items() if k != "record_hash"})


def test_multiview_run_record_rejects_history_for_another_enqueue(tmp_path, monkeypatch):
    record, artifact, draft, stage1_graph, stage1_history, stage1_consumption, stage1_consumption_path = _draft(
        tmp_path, monkeypatch, include_stage1=True
    )
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    consumption = build_approval_consumption(plan, "stage2-enqueue-request")
    consumption_path = tmp_path / f'{consumption["approval_id"]}.consumed.json'
    consumption_path.write_text(canonical_json(consumption) + "\n", encoding="utf-8")
    submitted = _trusted_submission(
        plan, _api_graph(), _upload_receipt(tmp_path, artifact), consumption, consumption_path
    )
    submission = submitted["submission"]
    output_root = tmp_path / "comfy-output"
    output_root.mkdir()
    (output_root / "front.png").write_bytes(_png_bytes())
    prompt_id = "stage2-prompt"
    history = {prompt_id: {
        "prompt": [1, prompt_id, submission["api_graph"], {"extra_data": {
            "prompt_forge_enqueue_request_id": "different-request"
        }}],
        "status": {"status_str": "success", "completed": True},
        "outputs": {"524": {"images": [{"filename": "front.png", "subfolder": "", "type": "output"}]}},
    }}
    with pytest.raises(ExecutionError, match="enqueue request"):
        build_multiview_run_record(
            _task_context(), record, artifact, _api_graph(), plan, _profile(), prompt_id, "succeeded",
            stage1_api_graph=stage1_graph, stage1_history=stage1_history,
            stage1_approval_consumption=stage1_consumption, stage1_consumption_path=stage1_consumption_path,
            approval_consumption=consumption, consumption_path=consumption_path,
            submission=submission, enqueue_receipt=submitted["enqueue_receipt"],
            enqueue_receipt_path=submitted["enqueue_receipt_path"], output_root=output_root, history=history,
        )


def test_stage2_json_cli_cannot_claim_production_conversion_or_submit(tmp_path, monkeypatch, capsys):
    record, artifact, stage1_graph, stage1_history, consumption, consumption_path = _stage1_chain(tmp_path)
    payload = {
        "stage1_record": record,
        "base_artifact": artifact,
        "stage1_api_graph": stage1_graph,
        "stage1_history": stage1_history,
        "stage1_approval_consumption": consumption,
        "stage1_consumption_path": str(consumption_path.resolve()),
        "workflow_profile_id": "flux2-klein-multiview-v1",
        "workflow_fingerprint": FINGERPRINT,
        "capability_report": _capability_report(),
        "profile": _profile(),
        "actual_ui_workflow": {"id": "test-flux-ui", **_ui_workflow()},
        "api_graph": _api_graph(),
        "conversion_receipt": _mcp_receipt(),
        "upload_receipt": _upload_receipt(tmp_path, artifact),
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert runtime_cli.main(["plan-multiview", "--from-stdin"]) == 1
    rejected = json.loads(capsys.readouterr().out)
    assert rejected["accepted"] is False
    assert "trusted local MCP conversion callables" in rejected["error"]

    _, _, draft = _draft(tmp_path, monkeypatch)
    plan = approve_execution_draft(draft, _event(draft, tmp_path), consumption_root=tmp_path)
    consumption = build_approval_consumption(plan, "stage2-enqueue-request")
    consumption_path = tmp_path / f'{consumption["approval_id"]}.consumed.json'
    consumption_path.write_text(canonical_json(consumption) + "\n", encoding="utf-8")
    patch_payload = {
        "approved_plan": plan,
        "source_api_graph": _api_graph(),
        "upload_receipt": _upload_receipt(tmp_path, artifact),
        "approval_consumption": consumption,
        "consumption_path": str(consumption_path.resolve()),
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(patch_payload)))
    assert runtime_cli.main(["patch-flux", "--from-stdin"]) == 2
    assert "trusted local MCP enqueue callable" in capsys.readouterr().err
