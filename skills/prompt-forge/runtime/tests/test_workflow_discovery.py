from datetime import datetime, timezone
import copy

import pytest

from runtime.workflow_discovery import discover_workflow_candidates
from runtime.workflow_profile import structure_fingerprint


def _ui_workflow():
    return {
        "nodes": [
            {"id": 1, "type": "LoadImage", "title": "Guide", "widgets_values": []},
            {"id": 2, "type": "SaveImage", "title": "Output", "widgets_values": []},
        ],
        "groups": [],
        "links": [],
    }


def _spec(ui, *, production=True):
    profile = {
        "schema_version": "1.0",
        "profile_id": "test-profile-v1",
        "workflow_name": "test-workflow.json",
        "workflow_fingerprint": structure_fingerprint(ui),
        "runtime_classification": "local",
        "slots": {},
    }
    return {
        "role": "test-stage",
        "workflow_name": "test-workflow.json",
        "profile_id": profile["profile_id"],
        "profile": profile,
        "production": production,
    }


def _tools(ui, api):
    calls = []

    def get_workflow(arguments):
        calls.append(("get_workflow", copy.deepcopy(arguments)))
        return copy.deepcopy(ui if arguments["format"] == "ui" else api)

    def strip_workflow(arguments):
        calls.append(("strip_workflow", copy.deepcopy(arguments)))
        return copy.deepcopy(api)

    def validate_workflow(arguments):
        calls.append(("validate_workflow", copy.deepcopy(arguments)))
        return {"valid": True, "errors": [], "warnings": []}

    def check_workflow_runtime(arguments):
        calls.append(("check_workflow_runtime", copy.deepcopy(arguments)))
        return {"runtime": "local", "usesApiNodes": [], "unknownNodes": []}

    return {
        "get_workflow": get_workflow,
        "strip_workflow": strip_workflow,
        "validate_workflow": validate_workflow,
        "check_workflow_runtime": check_workflow_runtime,
    }, calls


def test_discovery_binds_candidate_to_live_ui_and_api_evidence():
    ui = _ui_workflow()
    api = {"1": {"class_type": "LoadImage", "inputs": {}}, "2": {"class_type": "SaveImage", "inputs": {}}}
    tools, calls = _tools(ui, api)

    candidates = discover_workflow_candidates(
        saved_workflows=["test-workflow.json"],
        workflow_tools=tools,
        workflow_specs=[_spec(ui)],
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["status"] == "ready"
    assert candidate["production"] is True
    assert candidate["workflow_fingerprint"] == structure_fingerprint(ui)
    assert candidate["api_graph_hash"]
    assert candidate["reasons"] == []
    assert [name for name, _ in calls] == [
        "get_workflow",
        "get_workflow",
        "strip_workflow",
        "validate_workflow",
        "check_workflow_runtime",
    ]


def test_discovery_reports_missing_saved_workflow_without_calling_tools():
    ui = _ui_workflow()
    api = {"1": {"class_type": "LoadImage", "inputs": {}}}
    tools, calls = _tools(ui, api)

    candidates = discover_workflow_candidates(
        saved_workflows=[],
        workflow_tools=tools,
        workflow_specs=[_spec(ui)],
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert candidates[0]["status"] == "unavailable"
    assert candidates[0]["reason_codes"] == ["workflow_not_saved"]
    assert calls == []


def test_discovery_rejects_invalid_runtime_and_keeps_reason_codes():
    ui = _ui_workflow()
    api = {"1": {"class_type": "LoadImage", "inputs": {}}, "2": {"class_type": "SaveImage", "inputs": {}}}
    tools, _ = _tools(ui, api)
    tools["validate_workflow"] = lambda _arguments: {
        "valid": False,
        "errors": [{"message": "missing model"}],
        "warnings": [],
    }
    tools["check_workflow_runtime"] = lambda _arguments: {
        "runtime": "mixed",
        "usesApiNodes": ["PaidNode"],
        "unknownNodes": [],
    }

    candidates = discover_workflow_candidates(
        saved_workflows=["test-workflow.json"],
        workflow_tools=tools,
        workflow_specs=[_spec(ui)],
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert candidates[0]["status"] == "rejected"
    assert candidates[0]["reason_codes"] == ["workflow_invalid", "runtime_not_local"]


def test_discovery_never_claims_ready_without_negotiated_callables():
    ui = _ui_workflow()
    candidates = discover_workflow_candidates(
        saved_workflows=["test-workflow.json"],
        workflow_tools=None,
        workflow_specs=[_spec(ui)],
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert candidates[0]["status"] == "unavailable"
    assert candidates[0]["reason_codes"] == ["mcp_tools_unavailable"]


@pytest.mark.parametrize("missing", ["get_workflow", "strip_workflow", "validate_workflow", "check_workflow_runtime"])
def test_discovery_rejects_partial_tool_negotiation(missing):
    ui = _ui_workflow()
    api = {"1": {"class_type": "LoadImage", "inputs": {}}}
    tools, _ = _tools(ui, api)
    tools.pop(missing)

    candidates = discover_workflow_candidates(
        saved_workflows=["test-workflow.json"],
        workflow_tools=tools,
        workflow_specs=[_spec(ui)],
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert candidates[0]["status"] == "unavailable"
    assert candidates[0]["reason_codes"] == ["mcp_tools_unavailable"]
