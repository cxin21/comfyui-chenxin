"""Contract tests for the camera-image CLI dispatcher.

These tests cover the four P1-protocol sub-commands and explicitly assert that
``comfyui_chenxin_mcp`` is no longer importable through the camera-image
package graph.
"""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path

import pytest


def _invoke(argv: list[str], stdin_payload: dict | None = None) -> tuple[int, dict, str]:
    from camera_image import cli as cli_module

    stdout, stderr = io.StringIO(), io.StringIO()
    stdin = (
        io.StringIO(json.dumps(stdin_payload))
        if stdin_payload is not None
        else io.StringIO()
    )
    code = cli_module.main(argv, stdin=stdin, stdout=stdout, stderr=stderr)
    parsed = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
    return code, parsed, stderr.getvalue()


def test_package_does_not_import_comfyui_mcp():
    """Regression: removing the MCP dependency must keep camera-image importable."""
    for module in list(sys.modules):
        if module == "comfyui_chenxin_mcp" or module.startswith("comfyui_chenxin_mcp."):
            del sys.modules[module]
        if module == "camera_image" or module.startswith("camera_image."):
            del sys.modules[module]
    importlib.import_module("camera_image")
    assert "comfyui_chenxin_mcp" not in sys.modules


def test_describe_returns_asset_metadata():
    code, envelope, stderr = _invoke(["describe", "--stage", "t2i-camera", "--json"])
    assert code == 0
    assert stderr == ""
    assert envelope["ok"] is True
    assert envelope["command"] == "describe"
    assert envelope["stage"] == "t2i-camera"
    result = envelope["result"]
    assert result["asset_workflow_name"]
    assert result["asset_fingerprint"]
    assert isinstance(result["field_map"], dict)


def test_validate_runs_locally_without_network(tmp_path: Path):
    envelope_payload = {"prompt": {"positive": "subject", "negative": ""}}
    config_payload = {"camera": {}, "sampling": {}, "image_size": {}}
    envelope_path = tmp_path / "envelope.json"
    config_path = tmp_path / "config.json"
    envelope_path.write_text(json.dumps(envelope_payload), encoding="utf-8")
    config_path.write_text(json.dumps(config_payload), encoding="utf-8")
    code, envelope, stderr = _invoke(
        [
            "validate",
            "--stage",
            "t2i-camera",
            "--envelope",
            str(envelope_path),
            "--config",
            str(config_path),
            "--comfyui-url",
            "http://127.0.0.1:8188",
            "--json",
        ]
    )
    assert code == 0
    assert stderr == ""
    assert envelope["ok"] is True
    assert envelope["result"]["stage"] == "t2i-camera"
    assert "asset_fingerprint" in envelope["result"]


def test_validate_rejects_missing_prompt(tmp_path: Path):
    envelope_path = tmp_path / "envelope.json"
    config_path = tmp_path / "config.json"
    envelope_path.write_text(json.dumps({}), encoding="utf-8")
    config_path.write_text(json.dumps({}), encoding="utf-8")
    code, envelope, _ = _invoke(
        [
            "validate",
            "--stage",
            "t2i-camera",
            "--envelope",
            str(envelope_path),
            "--config",
            str(config_path),
            "--json",
        ]
    )
    assert code == 3
    assert envelope["errors"][0]["code"] == "validation_failed"


def test_assets_verify_passes_for_bundled_asset():
    code, envelope, stderr = _invoke(
        ["assets", "verify", "--stage", "t2i-camera", "--json"]
    )
    assert code == 0
    assert stderr == ""
    assert envelope["ok"] is True
    assert envelope["result"]["verified"] is True
    assert envelope["result"]["asset"] == "camera-anima.json"
    assert envelope["result"]["node_count"] > 0


def test_run_end_to_end_with_fake_transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from camera_image import cli as cli_module
    from camera_image.runtime import runner as runner_module

    class FakeClient:
        def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
            self.base_url = base_url
            self.timeout = timeout

        def upload_image(self, path):
            from comfyui_http import UploadedFile

            return UploadedFile(name=path.name, file_type="input", subfolder="")

        def enqueue(self, workflow):
            self._last_workflow = workflow
            return "fake-prompt-id"

        def wait_for_success(self, prompt_id, *, timeout, poll_interval):
            return {"outputs": {}, "status": {"completed": True}}

        def get_artifact(self, filename, subfolder, artifact_type):
            from comfyui_http import Artifact

            return Artifact(
                filename=filename,
                subfolder=subfolder,
                artifact_type=artifact_type,
                bytes=b"\x89PNG\r\nfake",
            )

    monkeypatch.setattr(cli_module, "ComfyUIClient", FakeClient)

    seen: dict = {}

    def fake_pipeline(client, *, stage, config, inventory, timeout, poll_interval):
        seen["client"] = client
        seen["stage"] = stage
        seen["config"] = config
        seen["inventory"] = inventory
        seen["timeout"] = timeout
        seen["poll_interval"] = poll_interval
        from camera_image.runtime.runner import RunResult

        return RunResult(
            prompt_id="fake-prompt-id",
            api_graph_sha256="deadbeef",
            artifacts=(),
            upload_summary=(),
            lora_stack="",
        )

    monkeypatch.setattr(cli_module, "run_pipeline", fake_pipeline)

    image_path = tmp_path / "subject.png"
    image_path.write_bytes(b"\x89PNG\r\nfake")
    envelope_payload = {"prompt": {"positive": "subject", "negative": ""}}
    config_payload = {
        "camera": {},
        "sampling": {},
        "image_size": {},
        "reference_image": str(image_path),
    }
    envelope_path = tmp_path / "envelope.json"
    config_path = tmp_path / "config.json"
    envelope_path.write_text(json.dumps(envelope_payload), encoding="utf-8")
    config_path.write_text(json.dumps(config_payload), encoding="utf-8")
    output_dir = tmp_path / "out"

    code, envelope, stderr = _invoke(
        [
            "run",
            "--stage",
            "i2i-camera",
            "--envelope",
            str(envelope_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--comfyui-url",
            "http://127.0.0.1:8188",
            "--json",
        ]
    )
    assert code == 0, stderr
    assert envelope["ok"] is True
    assert envelope["command"] == "run"
    assert envelope["stage"] == "i2i-camera"
    assert envelope["result"]["prompt_id"] == "fake-prompt-id"
    assert seen["stage"] == "i2i-camera"
    assert seen["config"].reference_image == str(image_path)
    assert seen["timeout"] == 1800.0
    # Confirm the CLI never touches comfyui_chenxin_mcp through the runner path.
    del sys.modules["camera_image.runtime.runner"]
    importlib.import_module("camera_image.runtime.runner")
    assert "comfyui_chenxin_mcp" not in sys.modules
