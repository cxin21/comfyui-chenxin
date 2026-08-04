import copy

import pytest

from runtime.contracts import content_hash
from runtime.execution import ExecutionError, validate_stage_handoff
from runtime.stage_execution import StageExecutionError
from runtime.local_orchestrator import (
    submit_character_base_via_local_rest,
    submit_stage_via_local_rest,
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


def test_submit_stage_via_local_rest_guards_queue_and_returns_history(monkeypatch, tmp_path):
    root = tmp_path.resolve()
    (root / ("b" * 64 + ".stage-enqueue-receipt.json")).unlink(missing_ok=True)
    submission = _submission(root)
    monkeypatch.setattr("runtime.local_orchestrator.ComfyApi", lambda base_url, timeout: _FakeApi())
    monkeypatch.setattr("runtime.local_orchestrator.ComfyPromptSubmitter", _FakeSubmitter)
    monkeypatch.setattr("runtime.local_orchestrator.build_stage_submission", lambda *args, **kwargs: submission)
    _FakeSubmitter.calls = []

    result = submit_stage_via_local_rest(**_payload(tmp_path), base_url="http://127.0.0.1:8188")

    assert result["receipt"]["prompt_id"] == "local-prompt-1"
    assert result["history"]["local-prompt-1"]["status"]["completed"] is True
    assert len(_FakeSubmitter.calls) == 1


def test_submit_stage_via_local_rest_fails_before_post_when_queue_is_busy(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runtime.local_orchestrator.ComfyApi", lambda base_url, timeout: _FakeApi(queue_running=1)
    )
    monkeypatch.setattr("runtime.local_orchestrator.ComfyPromptSubmitter", _FakeSubmitter)
    _FakeSubmitter.calls = []

    with pytest.raises(StageExecutionError, match="queue is not idle"):
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

    with pytest.raises((ExecutionError, StageExecutionError), match="source_story_hash"):
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

    with pytest.raises(StageExecutionError, match="explicit directional orientation evidence"):
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
    result = submit_character_base_via_local_rest(
        {"stage": "character-base"},
        {"prompt": "p"},
        {},
        {"consumption_root": str(tmp_path.resolve())},
        tmp_path / "consumed.json",
    )

    assert result["submission"] == submission
    assert result["enqueue_receipt"] == receipt
    assert result["history"]["base-prompt-1"]["status"]["completed"] is True
