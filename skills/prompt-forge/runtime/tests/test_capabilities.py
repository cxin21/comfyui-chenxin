from datetime import datetime, timedelta, timezone

import pytest

from runtime.capabilities import (
    build_capability_report,
    report_is_fresh,
    require_adapter_tools,
)
from runtime.comfy_api import CapabilityError
from runtime.comfy_api import ComfyApi


class FakeApi:
    def system_stats(self):
        return {
            "system": {"comfyui_version": "0.29.0"},
            "devices": [
                {"name": "RTX 4060", "vram_total": 8585216000, "vram_free": 1000}
            ],
        }

    def queue(self):
        return {"queue_running": [], "queue_pending": []}

    def object_info(self):
        return {"ImpactWildcardProcessor": {}, "CameraAngleNode": {}}

    def saved_workflows(self):
        return ["camera-workflow.json"]


def local_adapter(**overrides):
    adapter = {
        "name": "comfyui-mcp",
        "version": "0.49.0",
        "tools": [],
        "runtime_classification": "local",
    }
    adapter.update(overrides)
    return adapter


def test_report_contains_live_counts_and_expiry():
    now = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
    report = build_capability_report(FakeApi(), local_adapter(), now)

    assert report["hardware"] == {
        "device": "RTX 4060",
        "vram_total_bytes": 8585216000,
        "vram_free_bytes": 1000,
    }
    assert report["node_type_count"] == 2
    assert report["saved_workflows"] == ["camera-workflow.json"]
    assert report["queue"] == {"running": 0, "pending": 0}
    assert report["workflow_candidates"]
    assert all(candidate["status"] == "unavailable" for candidate in report["workflow_candidates"])
    assert report_is_fresh(report, now)


def test_report_can_bind_negotiated_workflow_discovery_callables():
    class WorkflowApi(FakeApi):
        def saved_workflows(self):
            return ["test-workflow.json"]

    ui = {
        "nodes": [
            {"id": 1, "type": "LoadImage", "title": "Guide", "widgets_values": []},
            {"id": 2, "type": "SaveImage", "title": "Output", "widgets_values": []},
        ],
        "groups": [],
        "links": [],
    }
    api_graph = {
        "1": {"class_type": "LoadImage", "inputs": {}},
        "2": {"class_type": "SaveImage", "inputs": {}},
    }
    from runtime.workflow_profile import structure_fingerprint

    profile = {
        "schema_version": "1.0",
        "profile_id": "test-profile-v1",
        "workflow_name": "test-workflow.json",
        "workflow_fingerprint": structure_fingerprint(ui),
        "runtime_classification": "local",
        "slots": {},
    }
    tools = {
        "get_workflow": lambda args: ui if args["format"] == "ui" else api_graph,
        "strip_workflow": lambda _args: api_graph,
        "validate_workflow": lambda _args: {"valid": True, "errors": [], "warnings": []},
        "check_workflow_runtime": lambda _args: {"runtime": "local"},
    }

    report = build_capability_report(
        WorkflowApi(),
        local_adapter(tools=list(tools)),
        datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc),
        workflow_tools=tools,
        workflow_specs=[
            {
                "role": "test-stage",
                "workflow_name": "test-workflow.json",
                "profile": profile,
                "production": True,
            }
        ],
    )

    assert report["workflow_candidates"][0]["status"] == "ready"
    assert report["workflow_candidates"][0]["production_ready"] is True


def test_report_expires_after_600_seconds():
    now = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
    report = build_capability_report(FakeApi(), local_adapter(), now)
    later = datetime(2026, 8, 2, 15, 10, 1, tzinfo=timezone.utc)

    assert not report_is_fresh(report, later)


def test_report_expires_at_exactly_600_seconds():
    now = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
    report = build_capability_report(FakeApi(), local_adapter(), now)

    assert not report_is_fresh(report, now + timedelta(seconds=600))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda report: report.pop("generated_at"),
        lambda report: report.update(generated_at="invalid"),
        lambda report: report.update(generated_at="2026-08-03T00:01:00Z"),
        lambda report: report.update(valid_until="2026-08-03T00:10:01Z"),
        lambda report: report.update(generated_at="2026-08-03T08:00:00+08:00"),
    ],
)
def test_report_rejects_invalid_future_non_utc_or_overlong_validity(mutate):
    now = datetime(2026, 8, 3, tzinfo=timezone.utc)
    report = build_capability_report(FakeApi(), local_adapter(), now)
    mutate(report)
    assert not report_is_fresh(report, now)


def test_report_rejects_naive_current_time():
    now = datetime(2026, 8, 3, tzinfo=timezone.utc)
    report = build_capability_report(FakeApi(), local_adapter(), now)
    assert not report_is_fresh(report, now.replace(tzinfo=None))


@pytest.mark.parametrize(
    "stats",
    [
        {"system": [], "devices": [{"name": "RTX 4060"}]},
        {"system": {"comfyui_version": "0.29.0"}, "devices": [[]]},
    ],
)
def test_malformed_system_or_first_device_raises_capability_error(stats):
    now = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
    api = FakeApi()
    api.system_stats = lambda: stats

    with pytest.raises(CapabilityError, match="invalid ComfyUI capability response"):
        build_capability_report(api, local_adapter(), now)


def test_missing_adapter_tool_is_a_hard_stop():
    now = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
    report = build_capability_report(FakeApi(), local_adapter(tools=["list_workflows"]), now)

    with pytest.raises(CapabilityError, match="validate_workflow"):
        require_adapter_tools(report, ["list_workflows", "validate_workflow"])


@pytest.mark.parametrize("classification", [None, "unknown", "paid", "mixed"])
def test_non_local_adapter_classification_is_a_hard_stop(classification):
    now = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
    adapter = local_adapter()
    if classification is None:
        adapter.pop("runtime_classification")
    else:
        adapter["runtime_classification"] = classification

    with pytest.raises(CapabilityError, match="runtime_classification"):
        build_capability_report(FakeApi(), adapter, now)


def test_saved_workflows_rejects_non_string_list():
    api = ComfyApi()
    api.get_json = lambda path: ["valid.json", 42]

    with pytest.raises(CapabilityError, match="string list"):
        api.saved_workflows()


def test_get_json_wraps_transport_failures(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr("runtime.comfy_api.urllib.request.urlopen", fail)

    with pytest.raises(CapabilityError, match="system_stats"):
        ComfyApi().system_stats()


def test_invalid_base_url_is_a_capability_error():
    with pytest.raises(CapabilityError, match="base_url"):
        ComfyApi(base_url=None)


@pytest.mark.parametrize("base_url", ["https://example.com", "http://192.168.1.8:8188"])
def test_capability_api_rejects_non_loopback_urls(base_url):
    with pytest.raises(CapabilityError, match="loopback"):
        ComfyApi(base_url=base_url)


def test_api_surface_exposes_only_read_operations():
    api = ComfyApi()

    assert not any("enqueue" in name.lower() for name in dir(api))


def test_history_endpoint_is_read_only_and_binds_prompt_id(monkeypatch):
    api = ComfyApi()
    seen = []

    def fake_get(path):
        seen.append(path)
        return {"prompt-1": {"status": {"status_str": "success", "completed": True}}}

    monkeypatch.setattr(api, "get_json", fake_get)
    assert api.history("prompt-1")["prompt-1"]["status"]["completed"] is True
    assert seen == ["/history/prompt-1"]

    with pytest.raises(CapabilityError, match="prompt_id"):
        api.history("bad id")
