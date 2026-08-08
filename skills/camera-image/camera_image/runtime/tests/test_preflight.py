"""Tests for runtime/preflight.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.preflight import (
    EXPECTED_HOST_MCP_TOOLS,
    run_preflight,
)


def _write_plugin_json(runtime_root: Path, version: str) -> None:
    (runtime_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (runtime_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "x", "version": version}), encoding="utf-8"
    )


def test_preflight_json_contract(tmp_path: Path) -> None:
    _write_plugin_json(tmp_path, "0.0.0+test")
    (tmp_path / "profiles").mkdir()
    (tmp_path / "workflow_assets").mkdir()
    (tmp_path / "profiles" / "camera-anima.json").write_text("{}", encoding="utf-8")
    (tmp_path / "workflow_assets" / "camera-anima.json").write_text("{}", encoding="utf-8")

    payload = run_preflight(
        runtime_root=tmp_path,
        comfy_url="http://127.0.0.1:1",  # unreachable port
        timeout=0.5,
    )

    assert payload["schema_version"] == "1.0"
    assert payload["ok"] is False
    assert payload["runtime_version"] == "0.0.0+test"
    check_ids = {c["id"] for c in payload["checks"]}
    assert {"version_stamp", "comfyui_reachable", "fixed_assets_integrity", "host_mcp_tools"} <= check_ids
    comfy = next(c for c in payload["checks"] if c["id"] == "comfyui_reachable")
    assert comfy["status"] == "fail"
    assert "remediation" in comfy
    assert "host_mcp_tools" in {n for n in EXPECTED_HOST_MCP_TOOLS}


def test_preflight_missing_plugin_json(tmp_path: Path) -> None:
    payload = run_preflight(runtime_root=tmp_path, comfy_url="http://127.0.0.1:1", timeout=0.5)
    version = next(c for c in payload["checks"] if c["id"] == "version_stamp")
    assert version["status"] == "warn"
    assert "reinstall" in version["remediation"].lower()


def test_preflight_missing_assets(tmp_path: Path) -> None:
    _write_plugin_json(tmp_path, "0.0.0+test")
    payload = run_preflight(runtime_root=tmp_path, comfy_url="http://127.0.0.1:1", timeout=0.5)
    assets = next(c for c in payload["checks"] if c["id"] == "fixed_assets_integrity")
    assert assets["status"] == "fail"
    assert "remediation" in assets
