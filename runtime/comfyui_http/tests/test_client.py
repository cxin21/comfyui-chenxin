"""Contract tests for :mod:`comfyui_http.client`.

The transport is implemented on top of :mod:`urllib.request`. Tests monkey-
patch :func:`urllib.request.urlopen` so they run without a live ComfyUI
instance and without binding sockets.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from comfyui_http.client import ComfyUIClient
from comfyui_http.errors import (
    ComfyUIConnectionError,
    ComfyUIInvalidResponseError,
    ComfyUITimeoutError,
)


class _FakeResponse:
    """Minimal stand-in for the ``HTTPResponse`` object ``urlopen`` returns."""

    def __init__(self, *, payload: bytes, status: int = 200, headers: dict[str, str] | None = None):
        self._payload = payload
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


def _install_urlopen_stub(monkeypatch: pytest.MonkeyPatch, responder: Any, captured: dict[str, Any] | None = None) -> None:
    """Replace :func:`urllib.request.urlopen` with ``responder(req, timeout)``."""

    def _stub(req: Any, timeout: float | None = None) -> Any:
        if captured is not None:
            captured["req"] = req
            captured["timeout"] = timeout
            try:
                captured["url"] = req.full_url
                captured["method"] = req.get_method()
            except Exception:
                pass
        return responder(req, timeout)

    monkeypatch.setattr(urllib.request, "urlopen", _stub)


def test_health_parses_system_stats_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    payload = json.dumps({"system": {"comfyui_version": "0.3.0"}}).encode("utf-8")

    def _responder(req: Any, timeout: float | None = None) -> _FakeResponse:
        return _FakeResponse(payload=payload)

    _install_urlopen_stub(monkeypatch, _responder, captured=captured)
    client = ComfyUIClient("http://127.0.0.1:8188/")
    stats = client.health()
    assert stats["system"]["comfyui_version"] == "0.3.0"
    assert captured["url"] == "http://127.0.0.1:8188/system_stats"


def test_health_raises_invalid_response_on_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_urlopen_stub(
        monkeypatch,
        lambda req, timeout: _FakeResponse(payload=b"<html>oops</html>"),
    )
    client = ComfyUIClient("http://127.0.0.1:8188")
    with pytest.raises(ComfyUIInvalidResponseError):
        client.health()


def test_upload_image_posts_multipart_and_parses_response(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image_path = tmp_path / "subject.png"
    image_path.write_bytes(b"\x89PNG\r\nfake")
    captured: dict[str, Any] = {}

    def _responder(req: Any, timeout: float | None = None) -> _FakeResponse:
        try:
            captured["content_type"] = req.get_header("Content-type") or ""
        except Exception:
            captured["content_type"] = ""
        captured["body_len"] = len(req.data or b"")
        return _FakeResponse(payload=json.dumps({"name": "subject.png", "type": "input"}).encode())

    _install_urlopen_stub(monkeypatch, _responder, captured=captured)
    client = ComfyUIClient("http://127.0.0.1:8188")
    result = client.upload_image(image_path)
    assert result.name == "subject.png"
    assert result.file_type == "input"
    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:8188/upload/image"
    assert "multipart/form-data" in captured["content_type"]
    assert captured["body_len"] > 0


def test_enqueue_posts_workflow_and_returns_prompt_id(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    workflow = {"3": {"class_type": "KSampler", "inputs": {"seed": 7}}}

    def _responder(req: Any, timeout: float | None = None) -> _FakeResponse:
        captured["body"] = json.loads((req.data or b"").decode("utf-8"))
        return _FakeResponse(payload=json.dumps({"prompt_id": "ab12cd"}).encode())

    _install_urlopen_stub(monkeypatch, _responder, captured=captured)
    client = ComfyUIClient("http://127.0.0.1:8188")
    prompt_id = client.enqueue(workflow)
    assert prompt_id == "ab12cd"
    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:8188/prompt"
    assert captured["body"]["prompt"] == workflow


def test_history_returns_empty_dict_when_prompt_not_yet_known(monkeypatch: pytest.MonkeyPatch) -> None:
    def _responder(req: Any, timeout: float | None = None) -> Any:
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b'{"error":"not found"}'))

    _install_urlopen_stub(monkeypatch, _responder)
    client = ComfyUIClient("http://127.0.0.1:8188")
    assert client.history("missing-prompt") == {}


def test_history_returns_parsed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    history_payload = {
        "ab12cd": {
            "outputs": {"9": {"images": [{"filename": "out.png"}]}},
            "status": {"completed": True},
        }
    }
    _install_urlopen_stub(
        monkeypatch,
        lambda req, timeout: _FakeResponse(payload=json.dumps(history_payload).encode()),
    )
    client = ComfyUIClient("http://127.0.0.1:8188")
    history = client.history("ab12cd")
    assert "ab12cd" in history
    assert history["ab12cd"]["status"]["completed"] is True


def test_get_artifact_returns_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    png_bytes = b"\x89PNG\r\nfake-image-bytes"
    captured: dict[str, Any] = {}

    def _responder(req: Any, timeout: float | None = None) -> _FakeResponse:
        return _FakeResponse(payload=png_bytes, headers={"Content-Type": "image/png"})

    _install_urlopen_stub(monkeypatch, _responder, captured=captured)
    client = ComfyUIClient("http://127.0.0.1:8188")
    artifact = client.get_artifact("out.png", "subjects/blue", "output")
    assert artifact.bytes == png_bytes
    assert artifact.sha256
    assert "filename=out.png" in captured["url"]
    assert "type=output" in captured["url"]


def test_connection_error_translates_urlerror(monkeypatch: pytest.MonkeyPatch) -> None:
    def _responder(req: Any, timeout: float | None = None) -> Any:
        raise urllib.error.URLError("connection refused")

    _install_urlopen_stub(monkeypatch, _responder)
    client = ComfyUIClient("http://127.0.0.1:8188")
    with pytest.raises(ComfyUIConnectionError):
        client.health()


def test_wait_for_success_returns_when_history_present(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            _FakeResponse(payload=b"{}"),
            _FakeResponse(
                payload=json.dumps(
                    {"ab12cd": {"outputs": {"9": {"images": []}}, "status": {"completed": True}}}
                ).encode()
            ),
        ]
    )

    def _responder(req: Any, timeout: float | None = None) -> _FakeResponse:
        return next(responses)

    captured_polls: list[float] = []
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda secs: captured_polls.append(secs))
    _install_urlopen_stub(monkeypatch, _responder)

    client = ComfyUIClient("http://127.0.0.1:8188")
    record = client.wait_for_success("ab12cd", timeout=5.0, poll_interval=0.5)
    assert record["status"]["completed"] is True
    assert captured_polls


def test_wait_for_success_raises_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _responder(req: Any, timeout: float | None = None) -> Any:
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b"{}"))

    _install_urlopen_stub(monkeypatch, _responder)
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda secs: None)

    client = ComfyUIClient("http://127.0.0.1:8188")
    with pytest.raises(ComfyUITimeoutError):
        client.wait_for_success("ab12cd", timeout=0.2, poll_interval=0.05)
