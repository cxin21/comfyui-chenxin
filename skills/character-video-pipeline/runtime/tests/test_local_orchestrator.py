import copy
import json
from pathlib import Path

import pytest

from runtime.contracts import content_hash
from runtime.execution import ExecutionError, validate_stage_handoff
from runtime.stage_execution import StageExecutionError
from runtime.mcp_bridge import McpBridge
from runtime.local_orchestrator import (
    _fixed_camera_source_graph,
    submit_character_base_via_local_rest,
    submit_stage_via_local_rest,
    validate_trusted_stage_profile,
    validate_trusted_video_evidence,
)


def _submission(root):
    graph = {"1": {"class_type": "SaveImage", "inputs": {}}}
    request = {
        "prompt": graph,
        "client_id": "local-stage-request",
        "extra_data": {
            "prompt_forge_stage": "shot-image",
            "prompt_forge_execution_plan_hash": "a" * 64,
            "prompt_forge_consumption_id": "b" * 64,
            "prompt_forge_enqueue_request_id": "local-stage-request",
            "prompt_forge_workflow_fingerprint": "c" * 64,
        },
    }
    value = {
        "schema_version": "1.0",
        "stage": "shot-image",
        "submission_type": "prompt-forge-stage-enqueue",
        "execution_plan_hash": "a" * 64,
        "draft_hash": "d" * 64,
        "approval_id": "e" * 64,
        "consumption_id": "b" * 64,
        "consumption_root": str(root.resolve()),
        "enqueue_request_id": "local-stage-request",
        "source_api_graph_hash": "f" * 64,
        "executable_api_graph_hash": content_hash(graph),
        "workflow_fingerprint": "c" * 64,
        "api_graph": graph,
        "request": request,
    }
    value["submission_hash"] = content_hash(value)
    return value


class _FakeApi:
    def __init__(self, queue_running=0):
        self.base_url = "http://127.0.0.1:8188"
        self.queue_running = queue_running

    def system_stats(self):
        return {"system": {"comfyui_version": "test"}, "devices": [{"name": "GPU"}]}

    def queue(self):
        return {"queue_running": ["busy"] * self.queue_running, "queue_pending": []}

    def object_info(self):
        return {}

    def saved_workflows(self):
        return []

    def history(self, prompt_id):
        return {prompt_id: {"status": {"status_str": "success", "completed": True}}}


class _FakeSubmitter:
    calls = []

    def __init__(self, base_url, timeout):
        self.base_url = base_url
        self.timeout = timeout

    def submit(self, request):
        self.calls.append(copy.deepcopy(request))
        return {"prompt_id": "local-prompt-1", "node_errors": {}}


def _payload(tmp_path):
    return {
        "approved_plan": {"stage": "shot-image"},
        "source_api_graph": {},
        "consumption": {},
        "consumption_path": str(tmp_path / "consumed.json"),
        "profile": {},
        "capability_report": {},
    }


def test_production_submission_accepts_host_neutral_mcp_bridge(monkeypatch, tmp_path):
    bridge = McpBridge(
        lambda _tool, _arguments: {},
        tool_names={
            "get_workflow": "codex.get_workflow",
            "strip_workflow": "codex.strip_workflow",
            "validate_workflow": "codex.validate_workflow",
            "check_workflow_runtime": "codex.check_workflow_runtime",
        },
        host_id="codex",
        host_version="test",
    )
    captured = {}

    monkeypatch.setattr(
        "runtime.local_orchestrator.validate_trusted_stage_profile",
        lambda *_args, **_kwargs: {"stage": "shot-image"},
    )

    def capture_refresh(_graph, _profile, workflow_tools, _plan):
        captured["workflow_tools"] = workflow_tools
        raise StageExecutionError("stop after bridge binding")

    monkeypatch.setattr("runtime.local_orchestrator._refresh_workflow_before_submission", capture_refresh)

    with pytest.raises(StageExecutionError, match="stop after bridge binding"):
        submit_stage_via_local_rest(
            {"stage": "shot-image", "production_eligible": True},
            {},
            {},
            tmp_path / "consumed.json",
            profile={},
            capability_report={},
            mcp_bridge=bridge,
        )

    assert set(captured["workflow_tools"]) == {
        "get_workflow",
        "strip_workflow",
        "validate_workflow",
        "check_workflow_runtime",
    }


def test_production_submission_rejects_two_mcp_authorities(tmp_path):
    bridge = McpBridge(lambda _tool, _arguments: {}, tool_names={"get_workflow": "host.get"})
    with pytest.raises(StageExecutionError, match="workflow_tools or mcp_bridge"):
        submit_stage_via_local_rest(
            {"stage": "shot-image"},
            {},
            {},
            tmp_path / "consumed.json",
            profile={},
            capability_report={},
            workflow_tools={"get_workflow": lambda _arguments: {}},
            mcp_bridge=bridge,
        )


def test_submit_stage_via_local_rest_guards_queue_and_returns_history(monkeypatch, tmp_path):
    root = tmp_path.resolve()
    (root / ("b" * 64 + ".stage-enqueue-receipt.json")).unlink(missing_ok=True)
    submission = _submission(root)
    monkeypatch.setattr("runtime.local_orchestrator.ComfyApi", lambda base_url, timeout: _FakeApi())
    monkeypatch.setattr("runtime.local_orchestrator.ComfyPromptSubmitter", _FakeSubmitter)
    monkeypatch.setattr("runtime.local_orchestrator.build_stage_submission", lambda *args, **kwargs: submission)
    _FakeSubmitter.calls = []

    with pytest.raises(StageExecutionError, match="trusted stage profile"):
        submit_stage_via_local_rest(**_payload(tmp_path), base_url="http://127.0.0.1:8188")
    assert _FakeSubmitter.calls == []


def test_submit_stage_via_local_rest_fails_before_post_when_queue_is_busy(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runtime.local_orchestrator.ComfyApi", lambda base_url, timeout: _FakeApi(queue_running=1)
    )
    monkeypatch.setattr("runtime.local_orchestrator.ComfyPromptSubmitter", _FakeSubmitter)
    _FakeSubmitter.calls = []

    with pytest.raises(StageExecutionError, match="trusted stage profile"):
        submit_stage_via_local_rest(**_payload(tmp_path), base_url="http://127.0.0.1:8188")

    assert _FakeSubmitter.calls == []


def test_handoff_rejects_cross_story_lineage_and_acceptance_before_any_enqueue(monkeypatch, tmp_path):
    plan = {
        "stage": "shot-image",
        "reference_hash": "a" * 64,
        "task_context_hash": "b" * 64,
        "source_story_hash": "c" * 64,
        "art_bible_hash": "d" * 64,
        "lineage_id": "lineage-1",
        "reference_view": "right_45",
        "desired_view": "right_45",
        "reference_selection": {
            "selected_view": "right_45",
            "desired_view": "right_45",
        },
        "orientation_proof": {
            "schema_version": "1.0",
            "expected_view": "right_45",
            "observed_view": "right_45",
            "source": "manual-review",
            "verified": True,
        },
    }
    reference = {
        "artifact_type": "CharacterAngleView",
        "view_label": "right_45",
        "accepted": True,
        "reference_eligible": True,
        "semantic_conflict": False,
        "hash_verified": True,
        "content_hash": "a" * 64,
        "task_context_hash": "b" * 64,
        "source_story_hash": "9" * 64,
        "art_bible_hash": "d" * 64,
        "lineage_id": "lineage-1",
        "orientation_proof": {
            "schema_version": "1.0",
            "expected_view": "right_45",
            "observed_view": "right_45",
            "source": "manual-review",
            "verified": True,
        },
    }
    api_calls = []
    monkeypatch.setattr(
        "runtime.local_orchestrator.ComfyApi",
        lambda *args, **kwargs: api_calls.append((args, kwargs)),
    )
    _FakeSubmitter.calls = []

    with pytest.raises((ExecutionError, StageExecutionError), match="trusted stage profile|source_story_hash"):
        submit_stage_via_local_rest(
            plan,
            {},
            {},
            tmp_path / "consumed.json",
            profile={},
            capability_report={},
            reference_artifact=reference,
        )

    assert api_calls == []
    assert _FakeSubmitter.calls == []


def test_invalid_handoff_is_rejected_before_fresh_workflow_read(monkeypatch, tmp_path):
    """A bad handoff must not trigger any MCP/workflow observation."""
    import runtime.local_orchestrator as orchestrator

    plan = {
        "stage": "shot-image",
        "reference_hash": "a" * 64,
    }
    workflow_reads = []
    monkeypatch.setattr(
        orchestrator,
        "validate_trusted_stage_profile",
        lambda *_args, **_kwargs: {"stage": "shot-image"},
    )
    monkeypatch.setattr(
        orchestrator,
        "reread_workflow_evidence",
        lambda *_args, **_kwargs: workflow_reads.append(True),
    )

    with pytest.raises(StageExecutionError, match="stage handoff validation failed"):
        submit_stage_via_local_rest(
            plan,
            {},
            {},
            tmp_path / "consumed.json",
            profile={},
            capability_report={},
            reference_artifact=None,
            workflow_tools={"get_workflow": lambda _args: None},
        )

    assert workflow_reads == []


def test_handoff_rejects_side_unknown_with_fake_orientation_source_before_any_enqueue(
    monkeypatch, tmp_path
):
    plan = {
        "stage": "shot-image",
        "reference_hash": "a" * 64,
        "task_context_hash": "b" * 64,
        "source_story_hash": "c" * 64,
        "art_bible_hash": "d" * 64,
        "lineage_id": "lineage-1",
        "reference_view": "side_unknown",
        "desired_view": "right",
        "reference_selection": {
            "selected_view": "right",
            "desired_view": "right",
        },
        "orientation_proof": {
            "schema_version": "1.0",
            "expected_view": "right",
            "observed_view": "right",
            "source": "manual-review",
            "verified": True,
        },
    }
    reference = {
        "artifact_type": "CharacterAngleView",
        "view_label": "side_unknown",
        "accepted": True,
        "reference_eligible": True,
        "semantic_conflict": False,
        "hash_verified": True,
        "content_hash": "a" * 64,
        "task_context_hash": "b" * 64,
        "source_story_hash": "c" * 64,
        "art_bible_hash": "d" * 64,
        "lineage_id": "lineage-1",
        "orientation_proof": {
            "schema_version": "1.0",
            "expected_view": "right",
            "observed_view": "right",
            "source": "fake",
            "verified": True,
        },
    }
    api_calls = []
    monkeypatch.setattr(
        "runtime.local_orchestrator.ComfyApi",
        lambda *args, **kwargs: api_calls.append((args, kwargs)),
    )
    _FakeSubmitter.calls = []

    with pytest.raises(StageExecutionError, match="trusted stage profile|explicit directional orientation evidence"):
        submit_stage_via_local_rest(
            plan,
            {},
            {},
            tmp_path / "consumed.json",
            profile={},
            capability_report={},
            reference_artifact=reference,
        )

    assert api_calls == []
    assert _FakeSubmitter.calls == []


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("accepted", False, "accepted"),
        ("lineage_id", "lineage-2", "lineage_id"),
        ("artifact_type", "CharacterBaseImage", "artifact_type"),
    ],
)
def test_validate_stage_handoff_rejects_single_field_drift(field, value, message):
    plan = {
        "stage": "shot-image",
        "reference_hash": "a" * 64,
        "task_context_hash": "b" * 64,
        "source_story_hash": "c" * 64,
        "art_bible_hash": "d" * 64,
        "lineage_id": "lineage-1",
        "reference_view": "right_45",
        "desired_view": "right_45",
        "reference_selection": {
            "selected_view": "right_45",
            "desired_view": "right_45",
        },
        "orientation_proof": {
            "schema_version": "1.0",
            "expected_view": "right_45",
            "observed_view": "right_45",
            "source": "manual-review",
            "verified": True,
        },
    }
    reference = {
        "artifact_type": "CharacterAngleView",
        "view_label": "right_45",
        "accepted": True,
        "reference_eligible": True,
        "semantic_conflict": False,
        "hash_verified": True,
        "content_hash": "a" * 64,
        "task_context_hash": "b" * 64,
        "source_story_hash": "c" * 64,
        "art_bible_hash": "d" * 64,
        "lineage_id": "lineage-1",
        "orientation_proof": {
            "schema_version": "1.0",
            "expected_view": "right_45",
            "observed_view": "right_45",
            "source": "manual-review",
            "verified": True,
        },
    }
    reference[field] = value

    with pytest.raises(ExecutionError, match=message):
        validate_stage_handoff(plan, reference)


@pytest.mark.parametrize(
    ("expected_hash", "artifact_hash"),
    [
        (None, None),
        ("not-a-hash", "not-a-hash"),
        ("a" * 64, None),
        (None, "a" * 64),
    ],
)
def test_validate_stage_handoff_rejects_missing_or_malformed_hashes(
    expected_hash, artifact_hash
):
    plan = {"stage": "shot-image", "reference_hash": expected_hash}
    reference = {
        "artifact_type": "CharacterAngleView",
        "view_label": "right_45",
        "accepted": True,
        "reference_eligible": True,
        "semantic_conflict": False,
        "hash_verified": True,
        "content_hash": artifact_hash,
        "orientation_proof": {
            "schema_version": "1.0",
            "expected_view": "right_45",
            "observed_view": "right_45",
            "source": "manual-review",
            "verified": True,
        },
    }

    with pytest.raises(ExecutionError, match="SHA-256"):
        validate_stage_handoff(plan, reference)


def test_fixed_camera_source_graph_loads_without_workflow_mcp():
    profile = json.loads(
        (Path(__file__).parents[1] / "profiles" / "camera-anima.json").read_text(encoding="utf-8")
    )

    graph = _fixed_camera_source_graph({}, profile)

    assert graph["24"]["class_type"] == "ImpactWildcardProcessor"
    assert graph["35"]["class_type"] == "Image Saver Simple"

def test_submit_character_base_via_local_rest_uses_live_queue_and_transport(monkeypatch, tmp_path):
    submission = {"stage": "character-base", "api_graph": {}}
    receipt = {"prompt_id": "base-prompt-1"}
    monkeypatch.setattr("runtime.local_orchestrator.ComfyApi", lambda base_url, timeout: _FakeApi())
    monkeypatch.setattr("runtime.local_orchestrator.ComfyPromptSubmitter", _FakeSubmitter)
    monkeypatch.setattr(
        "runtime.local_orchestrator.build_character_base_submission",
        lambda **kwargs: submission,
    )
    monkeypatch.setattr(
        "runtime.local_orchestrator.submit_character_base",
        lambda **kwargs: {
            "submission": submission,
            "enqueue_receipt": receipt,
            "enqueue_receipt_path": str(tmp_path / "receipt.json"),
            "submission_intent_path": str(tmp_path / "intent.json"),
        },
    )
    with pytest.raises(StageExecutionError, match="trusted camera profile"):
        submit_character_base_via_local_rest(
            {"stage": "character-base"},
            {"prompt": "p"},
            {},
            {"consumption_root": str(tmp_path.resolve())},
            tmp_path / "consumed.json",
        )


def test_submit_character_base_rejects_forged_plan_before_api(monkeypatch, tmp_path):
    api_calls = []
    monkeypatch.setattr(
        "runtime.local_orchestrator.ComfyApi",
        lambda *args, **kwargs: api_calls.append((args, kwargs)),
    )
    with pytest.raises(StageExecutionError, match="trusted camera profile"):
        submit_character_base_via_local_rest(
            {"stage": "character-base", "execution_approved": True, "profile_hash": "0" * 64},
            {"prompt": "forged"}, {}, {}, tmp_path / "consumed.json", profile={}
        )
    assert api_calls == []


def test_fresh_workflow_ui_drift_is_rejected_even_when_api_graph_is_unchanged():
    import runtime.local_orchestrator as orchestrator

    tools = {
        "get_workflow": lambda args: (
            {"nodes": [], "groups": [], "links": []}
            if args.get("format") == "ui"
            else {}
        ),
        "strip_workflow": lambda _args: {},
        "validate_workflow": lambda _args: {"valid": True, "errors": [], "warnings": []},
        "check_workflow_runtime": lambda _args: {"runtime": "local"},
    }
    with pytest.raises(StageExecutionError, match="fingerprint"):
        orchestrator._refresh_workflow_before_submission(
            {},
            {
                "workflow_name": "camera.json",
                "workflow_fingerprint": "a" * 64,
            },
            tools,
            {"stage": "shot-image", "workflow_fingerprint": "a" * 64},
        )


def test_camera_base_profile_uses_trusted_workflow_name_fallback(monkeypatch):
    import runtime.local_orchestrator as orchestrator

    profile = json.loads(
        (Path(__file__).parents[1] / "profiles" / "camera-anima-base.json").read_text(encoding="utf-8")
    )
    observed = {}

    def reread(tools, name, *, profile, normalize):
        observed["name"] = name
        return {"api_graph": {}, "ui_fingerprint": profile["workflow_fingerprint"]}

    monkeypatch.setattr(orchestrator, "reread_workflow_evidence", reread)
    result = orchestrator._refresh_workflow_before_submission(
        {}, profile, {}, {"stage": "character-base"}
    )
    assert result == {}
    assert observed["name"] == "文生图相机视角.json"


def test_submit_stage_rejects_grouped_or_caller_converted_graph_before_api(monkeypatch, tmp_path):
    api_calls = []

    def fail_api(*args, **kwargs):
        api_calls.append((args, kwargs))
        raise AssertionError("ComfyUI API must not be constructed for an untrusted graph")

    monkeypatch.setattr("runtime.local_orchestrator.ComfyApi", fail_api)
    plan = {"stage": "shot-image", "reference_hash": "a" * 64}
    with pytest.raises(StageExecutionError, match="trusted stage profile|conversion|grouped|normalized"):
        submit_stage_via_local_rest(
            plan,
            {"__conversion_receipt__": {"source": "caller"}, "groups": ["virtual-bus"]},
            {},
            tmp_path / "consumed.json",
            profile={},
            capability_report={},
        )
    assert api_calls == []


def test_production_stage_requires_fresh_workflow_tools_before_api(monkeypatch, tmp_path):
    api_calls = []
    monkeypatch.setattr(
        "runtime.local_orchestrator.ComfyApi",
        lambda *args, **kwargs: api_calls.append((args, kwargs)),
    )
    plan = {
        "stage": "video",
        "production_eligible": True,
        "stage_plan": {"stage": "video", "production_eligible": True},
    }
    with pytest.raises(StageExecutionError, match="trusted stage profile|fresh workflow re-read"):
        submit_stage_via_local_rest(
            plan,
            {},
            {},
            tmp_path / "consumed.json",
            profile={},
            capability_report={},
        )
    assert api_calls == []


def test_legacy_stage_plan_is_rejected_before_api_construction(monkeypatch, tmp_path):
    api_calls = []
    monkeypatch.setattr(
        "runtime.local_orchestrator.ComfyApi",
        lambda *args, **kwargs: api_calls.append((args, kwargs)),
    )
    with pytest.raises(StageExecutionError, match="legacy dry-run"):
        submit_stage_via_local_rest(
            {"stage": "video", "plan_mode": "legacy-dry-run"},
            {}, {}, tmp_path / "consumed.json", profile={}, capability_report={}
        )
    assert api_calls == []


def test_trusted_camera_profile_success_path_loads_canonical_json(monkeypatch):
    import runtime.local_orchestrator as orchestrator

    profile = json.loads(
        (Path(__file__).parents[1] / "profiles" / "camera-anima.json").read_text(encoding="utf-8")
    )
    monkeypatch.setattr(
        orchestrator,
        "_stage_plan",
        lambda plan, expected_stage=None: {
            "stage": "shot-image",
            "profile_hash": content_hash(profile),
        },
    )
    validated = validate_trusted_stage_profile(
        {"stage_plan": {"stage": "shot-image"}}, profile
    )
    assert validated["stage"] == "shot-image"


def test_trusted_ltx_profile_success_path_accepts_pinned_graph(monkeypatch):
    import runtime.local_orchestrator as orchestrator

    profile = json.loads(
        (Path(__file__).parents[1] / "profiles" / "ltx-yusu-short.json").read_text(encoding="utf-8")
    )
    graph = {"trusted": {"class_type": "YusuLTXDirector", "inputs": {}}}
    real_hash = orchestrator.content_hash
    monkeypatch.setattr(
        orchestrator,
        "content_hash",
        lambda value: profile["api_graph_hash"] if value is graph else real_hash(value),
    )
    validate_trusted_video_evidence(profile, graph, "ltx-yusu-short-v1")
