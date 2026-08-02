from datetime import datetime, timezone

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
    assert report_is_fresh(report, now)


def test_report_expires_after_600_seconds():
    now = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
    report = build_capability_report(FakeApi(), local_adapter(), now)
    later = datetime(2026, 8, 2, 15, 10, 1, tzinfo=timezone.utc)

    assert not report_is_fresh(report, later)


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


def test_api_surface_exposes_only_read_operations():
    api = ComfyApi()

    assert not any("enqueue" in name.lower() for name in dir(api))
