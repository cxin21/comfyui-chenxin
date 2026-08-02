"""Build and validate short-lived, read-only ComfyUI capability reports."""

from datetime import datetime, timedelta, timezone

from .comfy_api import CapabilityError


REPORT_TTL_SECONDS = 600


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise CapabilityError("capability report clock must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validated_adapter(adapter: dict) -> dict:
    if not isinstance(adapter, dict):
        raise CapabilityError("adapter metadata must be an object")
    classification = adapter.get("runtime_classification")
    if classification != "local":
        raise CapabilityError("adapter runtime_classification must be 'local'")
    tools = adapter.get("tools")
    if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
        raise CapabilityError("adapter tools must be a string list")
    return dict(adapter)


def build_capability_report(api, adapter: dict, now: datetime) -> dict:
    """Collect live, GET-only ComfyUI state into a report valid for ten minutes."""
    adapter_metadata = _validated_adapter(adapter)
    generated_at = _utc_timestamp(now)
    valid_until = _utc_timestamp(now + timedelta(seconds=REPORT_TTL_SECONDS))

    try:
        stats = api.system_stats()
        queue = api.queue()
        object_info = api.object_info()
        workflows = api.saved_workflows()
        system = stats["system"]
        device = stats["devices"][0]
        running = queue["queue_running"]
        pending = queue["queue_pending"]
        if not isinstance(system, dict) or not isinstance(device, dict):
            raise CapabilityError("system and first device must be objects")
    except (KeyError, IndexError, TypeError, CapabilityError) as exc:
        raise CapabilityError(f"invalid ComfyUI capability response: {exc}") from exc

    if not isinstance(object_info, dict):
        raise CapabilityError("object_info response must be an object")
    if not isinstance(workflows, list) or not all(isinstance(item, str) for item in workflows):
        raise CapabilityError("saved workflow response must be a string list")
    if not isinstance(running, list) or not isinstance(pending, list):
        raise CapabilityError("queue response must contain list counts")

    return {
        "schema_version": "1.0",
        "comfyui": {
            "url": getattr(api, "base_url", "http://127.0.0.1:8188"),
            "reachable": True,
            "version": system.get("comfyui_version", ""),
        },
        "hardware": {
            "device": device.get("name", ""),
            "vram_total_bytes": device.get("vram_total", 0),
            "vram_free_bytes": device.get("vram_free", 0),
        },
        "adapter": adapter_metadata,
        "node_type_count": len(object_info),
        "saved_workflows": list(workflows),
        "queue": {"running": len(running), "pending": len(pending)},
        "workflow_candidates": [],
        "generated_at": generated_at,
        "valid_until": valid_until,
    }


def report_is_fresh(report: dict, now: datetime) -> bool:
    """Return whether a report has not yet passed its UTC expiry time."""
    if not isinstance(report, dict):
        return False
    try:
        generated_at = datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00"))
        valid_until = datetime.fromisoformat(report["valid_until"].replace("Z", "+00:00"))
        if generated_at.tzinfo is None or valid_until.tzinfo is None:
            return False
        if now.tzinfo is None:
            return False
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
    if any(
        value.utcoffset() != timedelta(0)
        for value in (generated_at, valid_until, now)
    ):
        return False
    validity_window = valid_until - generated_at
    return (
        timedelta(0) < validity_window <= timedelta(seconds=REPORT_TTL_SECONDS)
        and generated_at <= now < valid_until
    )


def require_adapter_tools(report: dict, required) -> None:
    """Stop before workflow operations when negotiated adapter tools are absent."""
    try:
        available = report["adapter"]["tools"]
    except (KeyError, TypeError) as exc:
        raise CapabilityError("capability report has no adapter tools") from exc
    if not isinstance(available, list) or not all(isinstance(tool, str) for tool in available):
        raise CapabilityError("capability report adapter tools must be a string list")
    missing = sorted(set(required) - set(available))
    if missing:
        raise CapabilityError(f"adapter is missing required tools: {', '.join(missing)}")
