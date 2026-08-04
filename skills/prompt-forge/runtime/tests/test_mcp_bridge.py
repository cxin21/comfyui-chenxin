from __future__ import annotations

import copy

import pytest

from runtime.mcp_bridge import McpBridge, McpBridgeError
from runtime.workflow_discovery import reread_workflow_evidence


class RecordingInvoker:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, tool_name, arguments):
        self.calls.append((tool_name, copy.deepcopy(arguments)))
        response = self.responses[tool_name]
        return copy.deepcopy(response(arguments) if callable(response) else response)


def _responses():
    ui = {"nodes": [{"id": 1, "type": "SaveImage"}], "groups": [], "links": []}
    graph = {"1": {"class_type": "SaveImage", "inputs": {}}}
    return {
        "host.get": lambda arguments: ui if arguments["format"] == "ui" else graph,
        "host.strip": graph,
        "host.validate": {"errors": [], "warnings": []},
        "host.runtime": {"runtime": "local", "errors": [], "warnings": []},
    }


def test_bridge_adapts_host_tool_names_and_records_workflow_receipt():
    invoker = RecordingInvoker(_responses())
    bridge = McpBridge(
        invoker,
        tool_names={
            "get_workflow": "host.get",
            "strip_workflow": "host.strip",
            "validate_workflow": "host.validate",
            "check_workflow_runtime": "host.runtime",
        },
        host_id="codex",
        host_version="test",
    )

    evidence = reread_workflow_evidence(
        bridge.workflow_tools(),
        "camera.json",
        profile={},
    )

    assert evidence["api_graph"] == {"1": {"class_type": "SaveImage", "inputs": {}}}
    assert [name for name, _ in invoker.calls] == [
        "host.get",
        "host.get",
        "host.strip",
    ]
    receipt = bridge.receipt()
    assert receipt["host"] == {"id": "codex", "version": "test"}
    assert len(receipt["calls"]) == 3
    assert receipt["calls"][0]["logical_tool"] == "get_workflow"
    assert receipt["calls"][0]["actual_tool"] == receipt["calls"][1]["actual_tool"]
    assert receipt["calls"][0]["response_hash"] != receipt["calls"][1]["response_hash"]


def test_bridge_fails_before_host_call_when_required_tool_is_missing():
    invoker = RecordingInvoker(_responses())
    bridge = McpBridge(
        invoker,
        tool_names={"get_workflow": "host.get"},
    )

    with pytest.raises(McpBridgeError, match="strip_workflow"):
        bridge.require_workflow_tools()
    assert invoker.calls == []


def test_bridge_rejects_non_json_host_responses():
    invoker = RecordingInvoker({"host.get": object()})
    bridge = McpBridge(invoker, tool_names={"get_workflow": "host.get"})

    with pytest.raises(McpBridgeError, match="JSON-compatible"):
        bridge.call("get_workflow", {"filename": "camera.json", "format": "ui"})


def test_bridge_maps_host_failures_without_fabricating_receipts():
    def fail(_arguments):
        raise TimeoutError("tool timed out")

    invoker = RecordingInvoker({"host.get": fail})
    bridge = McpBridge(invoker, tool_names={"get_workflow": "host.get"})

    with pytest.raises(McpBridgeError, match="get_workflow"):
        bridge.call("get_workflow", {"filename": "camera.json", "format": "ui"})
    assert bridge.receipt()["calls"] == []


def test_bridge_blocks_side_effects_by_default():
    invoker = RecordingInvoker({"host.enqueue": {"prompt_id": "p1"}})
    bridge = McpBridge(invoker, tool_names={"enqueue_workflow": "host.enqueue"})

    with pytest.raises(McpBridgeError, match="side effect"):
        bridge.call("enqueue_workflow", {"prompt": {}}, side_effect=True)
    assert invoker.calls == []


def test_bridge_side_effects_require_explicit_runtime_enablement():
    invoker = RecordingInvoker({"host.enqueue": {"prompt_id": "p1"}})
    bridge = McpBridge(
        invoker,
        tool_names={"enqueue_workflow": "host.enqueue"},
        allow_side_effects=True,
    )

    assert bridge.call("enqueue_workflow", {"prompt": {}}, side_effect=True) == {
        "prompt_id": "p1"
    }
    assert bridge.receipt()["calls"][0]["side_effect"] is True
