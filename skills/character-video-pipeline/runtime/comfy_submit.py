"""Local-only ComfyUI prompt submission with UTF-8 and UI provenance support.

The discovery client intentionally remains GET-only.  This module is a
transport-only adapter: callers must pass ``ComfyPromptSubmitter().submit``
into ``stage_execution.submit_stage`` after plan approval and consumption.
Calling ``submit`` directly does not establish approval or idempotency and is
therefore not a complete Prompt Forge execution.
"""

from __future__ import annotations

import json
import math
import re
from urllib.parse import urlsplit
import urllib.error
import urllib.request


class SubmissionError(RuntimeError):
    """Raised when a local ComfyUI prompt cannot be submitted safely."""


_PROMPT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _local_base_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise SubmissionError("ComfyUI submission base_url must be a non-empty string")
    normalized = base_url.rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise SubmissionError("ComfyUI submission is restricted to a local loopback URL")
    return normalized


def _request_payload(request: object) -> dict:
    if not isinstance(request, dict) or set(request) != {"prompt", "client_id", "extra_data"}:
        raise SubmissionError("ComfyUI prompt request schema is invalid")
    if not isinstance(request.get("prompt"), dict):
        raise SubmissionError("ComfyUI prompt request graph is invalid")
    if not isinstance(request.get("client_id"), str) or not request["client_id"].strip():
        raise SubmissionError("ComfyUI prompt request client_id is invalid")
    extra = request.get("extra_data")
    if not isinstance(extra, dict):
        raise SubmissionError("ComfyUI prompt request extra_data is invalid")
    pnginfo = extra.get("extra_pnginfo")
    if pnginfo is not None and (
        not isinstance(pnginfo, dict)
        or not isinstance(pnginfo.get("workflow"), dict)
    ):
        raise SubmissionError("ComfyUI extra_pnginfo.workflow must be a UI workflow object")
    return request


class ComfyPromptSubmitter:
    """Submit one already-validated request to a local ComfyUI server.

    This class deliberately does not own plan, approval, or retry state.  Use
    it only as the injected enqueue callable for ``submit_stage``.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 30.0):
        self.base_url = _local_base_url(base_url)
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise SubmissionError("ComfyUI submission timeout must be a positive finite number")
        self.timeout = timeout

    def submit(self, request: dict) -> dict:
        payload = _request_payload(request)
        try:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            http_request = urllib.request.Request(
                self.base_url + "/prompt",
                data=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json; charset=utf-8",
                },
                method="POST",
            )
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                result = json.load(response)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise SubmissionError(f"ComfyUI POST /prompt failed: {exc}") from exc
        if not isinstance(result, dict):
            raise SubmissionError("ComfyUI POST /prompt response must be an object")
        prompt_id = result.get("prompt_id")
        if not isinstance(prompt_id, str) or not _PROMPT_ID_RE.fullmatch(prompt_id):
            raise SubmissionError("ComfyUI POST /prompt response prompt_id is invalid")
        if result.get("node_errors") not in ({}, None):
            raise SubmissionError("ComfyUI POST /prompt response contains node errors")
        return result
