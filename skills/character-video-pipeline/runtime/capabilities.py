"""Build and validate short-lived, read-only ComfyUI capability reports."""

from datetime import datetime, timedelta, timezone

from .comfy_api import CapabilityError
from .workflow_discovery import discover_workflow_candidates


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


def build_capability_report(
    api,
    adapter: dict,
    now: datetime,
    *,
    workflow_tools: dict | None = None,
    workflow_specs: list[dict] | tuple[dict, ...] | None = None,
) -> dict:
    """Collect live ComfyUI state and explicit workflow-candidate evidence.

    ``workflow_tools`` is an optional, negotiated local adapter boundary.  A
    report without it still lists every configured candidate as unavailable;
    it never silently reports an empty candidate set as success.
    """
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
    try:
        workflow_candidates = discover_workflow_candidates(
            saved_workflows=workflows,
            workflow_tools=workflow_tools,
            workflow_specs=workflow_specs,
            now=now,
        )
    except (TypeError, ValueError) as exc:
        raise CapabilityError(f"workflow candidate discovery failed: {exc}") from exc

    reason_codes = _capability_reason_codes(adapter_metadata, workflow_candidates)
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
        "workflow_candidates": workflow_candidates,
        "reason_codes": reason_codes,
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


def _capability_reason_codes(adapter: dict, candidates: list[dict]) -> list[str]:
    """Summarize known capability gaps using stable machine-readable codes."""
    codes: set[str] = set()
    tools = set(adapter.get("tools", [])) if isinstance(adapter, dict) else set()
    if not adapter.get("board_profiles") and not adapter.get("board_profile_support") and not (
        {"get_board_profile", "validate_board_profile"} <= tools
    ):
        codes.add("missing_board_profile_support")
    if any(
        isinstance(candidate, dict)
        and "unresolved_grouped_flux_buses" in candidate.get("reason_codes", [])
        for candidate in candidates
    ):
        codes.add("unresolved_grouped_flux_buses")
    if any(
        isinstance(candidate, dict)
        and (
            "invalid_orientation_evidence" in candidate.get("reason_codes", [])
            or any(
                isinstance(item, dict) and item.get("verified") is False
                for item in (candidate.get("orientation_evidence") or {}).values()
            )
        )
        for candidate in candidates
    ):
        codes.add("invalid_orientation_evidence")
    if adapter.get("orientation_evidence") is not None and (
        not isinstance(adapter.get("orientation_evidence"), dict)
        or any(
            isinstance(item, dict) and item.get("verified") is not True
            for item in adapter["orientation_evidence"].values()
        )
    ):
        codes.add("invalid_orientation_evidence")
    if not adapter.get("scene_prop_upload") and not ({"upload_scene", "upload_prop"} <= tools):
        codes.add("missing_scene_prop_upload")
    if not adapter.get("ltx_output_verification") and "verify_ltx_output" not in tools:
        codes.add("unavailable_ltx_output_verification")
    return sorted(codes)
