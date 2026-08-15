"""Contract tests for the camera-video CLI dispatcher."""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path

import pytest


def _invoke(argv: list[str], stdin_payload: dict | None = None) -> tuple[int, dict, str]:
    from camera_video import cli as cli_module

    stdout, stderr = io.StringIO(), io.StringIO()
    stdin = io.StringIO(json.dumps(stdin_payload)) if stdin_payload is not None else io.StringIO()
    code = cli_module.main(argv, stdin=stdin, stdout=stdout, stderr=stderr)
    parsed = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
    return code, parsed, stderr.getvalue()


def test_package_does_not_import_comfyui_mcp():
    for module in list(sys.modules):
        if module == "comfyui_chenxin_mcp" or module.startswith("comfyui_chenxin_mcp."):
            del sys.modules[module]
        if module == "camera_video" or module.startswith("camera_video."):
            del sys.modules[module]
    importlib.import_module("camera_video")
    assert "comfyui_chenxin_mcp" not in sys.modules


def test_describe_for_t2v_stage():
    code, envelope, _ = _invoke(["describe", "--stage", "t2v-video", "--json"])
    assert code == 0
    assert envelope["ok"] is True
    assert envelope["stage"] == "t2v-video"


def test_assets_verify_passes_for_bundled_asset():
    code, envelope, _ = _invoke(["assets", "verify", "--stage", "t2v-video", "--json"])
    assert code == 0
    assert envelope["ok"] is True
    assert envelope["result"]["verified"] is True


def test_validate_runs_locally(tmp_path: Path):
    (tmp_path / "env.json").write_text(json.dumps({"prompt": {"text": "subject"}}), encoding="utf-8")
    (tmp_path / "cfg.json").write_text(json.dumps({"duration": 4.0}), encoding="utf-8")
    code, envelope, _ = _invoke(
        [
            "validate",
            "--stage",
            "t2v-video",
            "--envelope",
            str(tmp_path / "env.json"),
            "--config",
            str(tmp_path / "cfg.json"),
            "--json",
        ]
    )
    assert code == 0
    assert envelope["result"]["duration"] == 4.0


def test_run_dispatches_into_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from camera_video import cli as cli_module

    captured: dict = {}

    def fake_pipeline(client, **kwargs):
        captured.update(kwargs)
        from camera_video.runtime.runner import RunResult

        return RunResult(
            prompt_id="vid-fake",
            api_graph_sha256="cafef00d",
            artifacts=(),
            upload_summary=(),
        )

    class FakeClient:
        def __init__(self, base_url, *, timeout=30.0):
            self.base_url = base_url
            self.timeout = timeout

    monkeypatch.setattr(cli_module, "ComfyUIClient", FakeClient)
    monkeypatch.setattr(cli_module, "run_pipeline", fake_pipeline)

    (tmp_path / "env.json").write_text(json.dumps({"prompt": {"text": "subject moves"}}), encoding="utf-8")
    (tmp_path / "cfg.json").write_text(json.dumps({"duration": 4.0}), encoding="utf-8")
    code, envelope, _ = _invoke(
        [
            "run",
            "--stage",
            "t2v-video",
            "--envelope",
            str(tmp_path / "env.json"),
            "--config",
            str(tmp_path / "cfg.json"),
            "--output-dir",
            str(tmp_path / "out"),
            "--json",
        ]
    )
    assert code == 0, envelope
    assert envelope["result"]["prompt_id"] == "vid-fake"
    assert captured["stage"] == "t2v-video"
    assert captured["prompt_text"] == "subject moves"
    assert captured["duration"] == 4.0
