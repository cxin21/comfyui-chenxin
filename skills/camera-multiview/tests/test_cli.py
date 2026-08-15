"""Contract tests for the camera-multiview CLI dispatcher."""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path

import pytest


def _invoke(argv: list[str], stdin_payload: dict | None = None) -> tuple[int, dict, str]:
    from camera_multiview import cli as cli_module

    stdout, stderr = io.StringIO(), io.StringIO()
    stdin = io.StringIO(json.dumps(stdin_payload)) if stdin_payload is not None else io.StringIO()
    code = cli_module.main(argv, stdin=stdin, stdout=stdout, stderr=stderr)
    parsed = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
    return code, parsed, stderr.getvalue()


def test_package_does_not_import_comfyui_mcp():
    for module in list(sys.modules):
        if module == "comfyui_chenxin_mcp" or module.startswith("comfyui_chenxin_mcp."):
            del sys.modules[module]
        if module == "camera_multiview" or module.startswith("camera_multiview."):
            del sys.modules[module]
    importlib.import_module("camera_multiview")
    assert "comfyui_chenxin_mcp" not in sys.modules


def test_describe_for_multiview_stage():
    code, envelope, _ = _invoke(["describe", "--stage", "multiview", "--json"])
    assert code == 0
    assert envelope["ok"] is True
    assert envelope["stage"] == "multiview"
    assert envelope["result"]["fixed_nodes"]["body"] == "111"
    assert envelope["result"]["fixed_nodes"]["face"] == "667"


def test_assets_verify_passes_for_bundled_asset():
    code, envelope, _ = _invoke(["assets", "verify", "--stage", "multiview", "--json"])
    assert code == 0
    assert envelope["ok"] is True
    assert envelope["result"]["verified"] is True


def test_validate_rejects_nonempty_envelope(tmp_path: Path):
    (tmp_path / "env.json").write_text(json.dumps({"unrelated": "key"}), encoding="utf-8")
    (tmp_path / "cfg.json").write_text(
        json.dumps({"full_body_image": "body.png", "face_image": "face.png"}),
        encoding="utf-8",
    )
    code, envelope, _ = _invoke(
        [
            "validate",
            "--stage",
            "multiview",
            "--envelope",
            str(tmp_path / "env.json"),
            "--config",
            str(tmp_path / "cfg.json"),
            "--json",
        ]
    )
    assert code == 3
    assert envelope["errors"][0]["code"] == "validation_failed"


def test_run_dispatches_into_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from camera_multiview import cli as cli_module

    captured: dict = {}

    def fake_pipeline(client, **kwargs):
        captured.update(kwargs)
        from camera_multiview.runtime.runner import RunResult

        return RunResult(
            prompt_id="mv-fake",
            api_graph_sha256="cafef01d",
            artifacts=(),
            upload_summary=(),
        )

    class FakeClient:
        def __init__(self, base_url, *, timeout=30.0):
            self.base_url = base_url
            self.timeout = timeout

    monkeypatch.setattr(cli_module, "ComfyUIClient", FakeClient)
    monkeypatch.setattr(cli_module, "run_pipeline", fake_pipeline)

    body = tmp_path / "body.png"
    face = tmp_path / "face.png"
    body.write_bytes(b"\x89PNG\r\nbody")
    face.write_bytes(b"\x89PNG\r\nface")
    (tmp_path / "env.json").write_text(json.dumps({}), encoding="utf-8")
    (tmp_path / "cfg.json").write_text(
        json.dumps({"full_body_image": str(body), "face_image": str(face)}),
        encoding="utf-8",
    )
    code, envelope, _ = _invoke(
        [
            "run",
            "--stage",
            "multiview",
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
    assert envelope["result"]["prompt_id"] == "mv-fake"
    assert captured["full_body_image"] == body
    assert captured["face_image"] == face
