"""Stdlib-only HTTP client for direct ComfyUI API access.

The transport deliberately avoids :mod:`requests`, MCP, Node and ``npx``. Every
call goes through :func:`urllib.request.urlopen` so the camera Skills can
hand-roll deterministic tests by monkey-patching that single entry point.
"""

from __future__ import annotations

import json
import mimetypes
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .errors import (
    ComfyUIConnectionError,
    ComfyUIInvalidResponseError,
    ComfyUITimeoutError,
)
from .protocol import Artifact, UploadedFile


DEFAULT_TIMEOUT_SECONDS = 30.0
JSON_CONTENT_TYPE = "application/json"


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _build_request(
    base_url: str,
    path: str,
    *,
    method: str,
    headers: dict[str, str],
    data: bytes | None = None,
) -> urllib.request.Request:
    url = f"{base_url}{path}"
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in headers.items():
        request.add_header(key, value)
    return request


def _decode_json(response: Any) -> Any:
    body = response.read()
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComfyUIInvalidResponseError(f"ComfyUI returned non-JSON payload: {exc}") from exc


def _open(
    request: urllib.request.Request,
    *,
    timeout: float | None,
    decode_json: bool = True,
) -> Any:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if decode_json:
                return _decode_json(response)
            return response.read()
    except urllib.error.HTTPError as error:
        raise
    except urllib.error.URLError as error:
        raise ComfyUIConnectionError(str(error)) from error


def _multipart_body(field_name: str, file_path: Path) -> tuple[bytes, str]:
    """Build a ``multipart/form-data`` body for one file upload."""
    boundary = uuid.uuid4().hex
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{file_path.name}"\r\n'
        f"Content-Type: {content_type}\r\n"
        "\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + file_bytes + tail, f"multipart/form-data; boundary={boundary}"


class ComfyUIClient:
    """Thin synchronous wrapper around the ComfyUI HTTP API."""

    def __init__(self, base_url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._base_url = _normalize_base_url(base_url)
        self._timeout = timeout

    def health(self) -> dict[str, Any]:
        request = _build_request(
            self._base_url,
            "/system_stats",
            method="GET",
            headers={"Accept": JSON_CONTENT_TYPE},
        )
        data = _open(request, timeout=self._timeout, decode_json=True)
        if not isinstance(data, dict):
            raise ComfyUIInvalidResponseError("system_stats response must be a JSON object")
        return data

    def upload_image(self, file_path: Path) -> UploadedFile:
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        body, content_type = _multipart_body("image", file_path)
        request = _build_request(
            self._base_url,
            "/upload/image",
            method="POST",
            headers={
                "Accept": JSON_CONTENT_TYPE,
                "Content-Type": content_type,
            },
            data=body,
        )
        data = _open(request, timeout=self._timeout, decode_json=True)
        if not isinstance(data, dict):
            raise ComfyUIInvalidResponseError("upload response must be a JSON object")
        return UploadedFile.from_payload(data)

    def enqueue(self, workflow: dict[str, Any]) -> str:
        if not isinstance(workflow, dict):
            raise ValueError("workflow must be a JSON object")
        body = json.dumps({"prompt": workflow}).encode("utf-8")
        request = _build_request(
            self._base_url,
            "/prompt",
            method="POST",
            headers={
                "Accept": JSON_CONTENT_TYPE,
                "Content-Type": JSON_CONTENT_TYPE,
            },
            data=body,
        )
        data = _open(request, timeout=self._timeout, decode_json=True)
        if not isinstance(data, dict):
            raise ComfyUIInvalidResponseError("prompt response must be a JSON object")
        prompt_id = data.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyUIInvalidResponseError("prompt response missing 'prompt_id'")
        return prompt_id

    def history(self, prompt_id: str) -> dict[str, Any]:
        if not prompt_id:
            raise ValueError("prompt_id is required")
        request = _build_request(
            self._base_url,
            f"/history/{quote(prompt_id, safe='')}",
            method="GET",
            headers={"Accept": JSON_CONTENT_TYPE},
        )
        try:
            data = _open(request, timeout=self._timeout, decode_json=True)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return {}
            raise ComfyUIInvalidResponseError(
                f"history returned HTTP {error.code}: {error.reason}"
            ) from error
        if not isinstance(data, dict):
            raise ComfyUIInvalidResponseError("history response must be a JSON object")
        return data

    def get_artifact(self, filename: str, subfolder: str, artifact_type: str) -> Artifact:
        if not filename:
            raise ValueError("filename is required")
        query = (
            f"filename={quote(filename, safe='')}"
            f"&subfolder={quote(subfolder, safe='')}"
            f"&type={quote(artifact_type, safe='')}"
        )
        request = _build_request(
            self._base_url,
            f"/view?{query}",
            method="GET",
            headers={"Accept": "*/*"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                data = response.read()
        except urllib.error.URLError as error:
            raise ComfyUIConnectionError(str(error)) from error
        if not isinstance(data, bytes):
            raise ComfyUIInvalidResponseError("artifact response must be bytes")
        return Artifact(
            filename=filename,
            subfolder=subfolder,
            artifact_type=artifact_type,
            bytes=data,
        )

    def wait_for_success(
        self,
        prompt_id: str,
        *,
        timeout: float,
        poll_interval: float = 2.0,
    ) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        deadline = time.monotonic() + timeout
        while True:
            history = self.history(prompt_id)
            record = history.get(prompt_id)
            if record is not None:
                return record
            if time.monotonic() >= deadline:
                raise ComfyUITimeoutError(
                    f"prompt {prompt_id!r} did not complete within {timeout}s"
                )
            time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
