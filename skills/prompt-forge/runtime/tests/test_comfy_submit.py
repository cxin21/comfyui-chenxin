import json

import pytest

from runtime.comfy_submit import ComfyPromptSubmitter, SubmissionError


class _Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        return self.payload


def _request():
    return {
        "prompt": {"1": {"class_type": "LoadImage", "inputs": {"image": "角色.png"}}},
        "client_id": "stage-3-local",
        "extra_data": {
            "prompt_forge_stage": "shot-image",
            "extra_pnginfo": {"workflow": {"id": "camera-ui", "nodes": []}},
        },
    }


def test_submit_posts_utf8_and_preserves_ui_provenance(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return _Response({"prompt_id": "prompt-1", "node_errors": {}})

    monkeypatch.setattr("runtime.comfy_submit.urllib.request.urlopen", fake_urlopen)
    response = ComfyPromptSubmitter().submit(_request())

    assert response["prompt_id"] == "prompt-1"
    request, timeout = calls[0]
    assert timeout == 30.0
    assert request.get_full_url() == "http://127.0.0.1:8188/prompt"
    assert request.data.decode("utf-8")
    decoded = json.loads(request.data.decode("utf-8"))
    assert decoded["prompt"]["1"]["inputs"]["image"] == "角色.png"
    assert decoded["extra_data"]["extra_pnginfo"]["workflow"]["id"] == "camera-ui"


@pytest.mark.parametrize("url", ["https://example.com", "http://192.168.1.20:8188"])
def test_submit_rejects_non_loopback_url(url):
    with pytest.raises(SubmissionError, match="loopback"):
        ComfyPromptSubmitter(url)


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True])
def test_submit_rejects_invalid_timeout(timeout):
    with pytest.raises(SubmissionError, match="timeout"):
        ComfyPromptSubmitter(timeout=timeout)


def test_submit_rejects_malformed_ui_provenance(monkeypatch):
    request = _request()
    request["extra_data"]["extra_pnginfo"] = {"workflow": "not-an-object"}
    with pytest.raises(SubmissionError, match="workflow"):
        ComfyPromptSubmitter().submit(request)


def test_submit_rejects_unsuccessful_comfy_response(monkeypatch):
    def fake_urlopen(request, timeout):
        return _Response({"prompt_id": "prompt-1", "node_errors": {"3": "bad node"}})

    monkeypatch.setattr("runtime.comfy_submit.urllib.request.urlopen", fake_urlopen)
    with pytest.raises(SubmissionError, match="node errors"):
        ComfyPromptSubmitter().submit(_request())
