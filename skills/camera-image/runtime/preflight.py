"""Pre-flight gate for character-video-pipeline.

Runs cheap, deterministic checks before any prompt authoring or file writes.
Designed so a host agent can call it as Step 0 of any production flow and
report remediation to the user when a blocker is present.

The runtime never performs UI-to-API conversion and does not depend on a
specific MCP SDK, so checks that need a host are reported as expected tool
names rather than auto-verified. The host agent must independently verify
that the required MCP tools are negotiated in its own session.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .comfy_api import CapabilityError, ComfyApi
from .workflow_discovery import REQUIRED_WORKFLOW_TOOLS


EXPECTED_HOST_MCP_TOOLS = frozenset(
    REQUIRED_WORKFLOW_TOOLS | {"list_local_models"}
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_plugin_version(plugin_json: Path) -> str:
    try:
        raw = json.loads(plugin_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown"
    version = raw.get("version") if isinstance(raw, dict) else None
    return str(version) if isinstance(version, str) and version else "unknown"


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_version(runtime_root: Path) -> dict[str, Any]:
    plugin_json = runtime_root / ".codex-plugin" / "plugin.json"
    if not plugin_json.is_file():
        return {
            "id": "version_stamp",
            "status": "warn",
            "detail": f"plugin.json not found at {plugin_json}",
            "remediation": "reinstall the plugin via scripts/install.ps1",
        }
    version = _read_plugin_version(plugin_json)
    return {
        "id": "version_stamp",
        "status": "ok",
        "detail": f"plugin version: {version}",
        "value": version,
    }


def _check_comfyui_reachable(comfy_url: str, timeout: float) -> dict[str, Any]:
    try:
        api = ComfyApi(comfy_url, timeout=timeout)
        stats = api.system_stats()
        version = stats.get("system", {}).get("comfyui_version", "")
        return {
            "id": "comfyui_reachable",
            "status": "ok",
            "detail": f"GET {comfy_url}/system_stats -> 200 (comfyui {version})",
            "value": {"comfyui_version": version, "url": comfy_url},
        }
    except CapabilityError as exc:
        return {
            "id": "comfyui_reachable",
            "status": "fail",
            "detail": str(exc),
            "remediation": (
                f"start ComfyUI on {comfy_url} and re-run preflight; the production pipeline"
                " cannot reach the live ComfyUI REST surface."
            ),
        }


def _check_fixed_assets(runtime_root: Path) -> dict[str, Any]:
    profiles_dir = runtime_root / "profiles"
    workflows_dir = runtime_root / "workflow_assets"
    if not profiles_dir.is_dir() or not workflows_dir.is_dir():
        return {
            "id": "fixed_assets_integrity",
            "status": "fail",
            "detail": (
                f"missing bundled asset dir under {runtime_root}: profiles={profiles_dir.is_dir()}"
                f" workflow_assets={workflows_dir.is_dir()}"
            ),
            "remediation": "reinstall the plugin (the cache is incomplete).",
        }
    missing: list[str] = []
    if not (workflows_dir / "manifest.json").is_file():
        missing.append("workflow_assets/manifest.json is missing")
    if not (workflows_dir / "camera-anima.json").is_file():
        missing.append("workflow_assets/camera-anima.json is missing")
    profiles_files = sorted(profiles_dir.glob("*.json"))
    if not profiles_files:
        missing.append("profiles/*.json is missing")
    if missing:
        return {
            "id": "fixed_assets_integrity",
            "status": "fail",
            "detail": "; ".join(missing),
            "remediation": (
                "reinstall the plugin (bundled assets are corrupt or incomplete);"
                " if the issue persists, copy the assets from the repo's skills/"
                "character-video-pipeline/runtime/{profiles,workflow_assets}."
            ),
            "value": {"profiles": [pf.name for pf in profiles_files]},
        }
    return {
        "id": "fixed_assets_integrity",
        "status": "ok",
        "detail": f"verified {len(profiles_files)} profile(s) and workflow_assets/ contents",
        "value": {"profiles_dir": str(profiles_dir), "workflows_dir": str(workflows_dir)},
    }


def _check_host_mcp_tools() -> dict[str, Any]:
    return {
        "id": "host_mcp_tools",
        "status": "informational",
        "detail": (
            "host agent must verify the following MCP tools are negotiated in this session"
            " before invoking the runtime: " + ", ".join(sorted(EXPECTED_HOST_MCP_TOOLS))
        ),
        "expected_tools": sorted(EXPECTED_HOST_MCP_TOOLS),
        "remediation": (
            "if any tool is missing, confirm Codex's [mcp_servers.comfyui-mcp] block in"
            " ~/.codex/config.toml launches the server; restart Codex if needed. See"
            " docs/TROUBLESHOOTING.md#mcp-工具不可用."
        ),
    }


def run_preflight(
    *,
    runtime_root: Path,
    comfy_url: str = "http://127.0.0.1:8188",
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Run the deterministic pre-flight checks. Returns a JSON-safe dict."""
    checks = [
        _check_version(runtime_root),
        _check_comfyui_reachable(comfy_url, timeout),
        _check_fixed_assets(runtime_root),
        _check_host_mcp_tools(),
    ]
    blockers = [c["id"] for c in checks if c.get("status") == "fail"]
    return {
        "schema_version": "1.0",
        "ok": not blockers,
        "generated_at": _utc_now(),
        "runtime_version": next(
            (c.get("value") for c in checks if c.get("id") == "version_stamp"),
            "unknown",
        ),
        "checks": checks,
        "blockers": blockers,
    }


def emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="character-video-pipeline-preflight")
    parser.add_argument("--runtime-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    payload = run_preflight(
        runtime_root=args.runtime_root,
        comfy_url=args.comfy_url,
        timeout=args.timeout,
    )
    emit(payload)
    sys.exit(0 if payload["ok"] else 1)
