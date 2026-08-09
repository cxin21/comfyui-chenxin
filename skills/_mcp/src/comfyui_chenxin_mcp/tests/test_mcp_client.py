"""McpClient tests - verify direct HTTP /history/<id> bypass."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from comfyui_chenxin_mcp.engine.mcp_client import McpClient, McpClientError


def _client(call_tool=None, comfyui_url: str = "http://127.0.0.1:8188") -> McpClient:
    """Build a McpClient without spawning a subprocess."""
    return McpClient(call_tool or MagicMock(), comfyui_url=comfyui_url)


def test_from_subprocess_stores_comfyui_url():
    """``comfyui_url`` parameter is preserved as ``_comfyui_url`` (no trailing slash)."""
    client = _client(comfyui_url="http://example.com:9000/")
    assert client._comfyui_url == "http://example.com:9000"


def test_get_history_raw_calls_comfyui_history_endpoint():
    """``get_history_raw`` hits ComfyUI's HTTP API directly."""
    client = _client()
    payload = {"abc": {"status": {"status_str": "success"}, "outputs": {}}}
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps(payload).encode("utf-8")
    fake_resp.__enter__ = lambda s: s
    fake_resp.__exit__ = lambda *a: False

    with patch("urllib.request.urlopen", return_value=fake_resp) as mock_urlopen:
        result = client.get_history_raw("abc")

    mock_urlopen.assert_called_once()
    called_url = mock_urlopen.call_args[0][0]
    assert called_url == "http://127.0.0.1:8188/history/abc"
    assert result == payload


def test_get_history_raw_returns_empty_on_404():
    """A 404 (prompt not yet in history) yields an empty dict so the poll loop keeps waiting."""
    from urllib.error import HTTPError

    client = _client()
    err = HTTPError(url="http://127.0.0.1:8188/history/missing", code=404, msg="Not Found",
                    hdrs={}, fp=None)
    with patch("urllib.request.urlopen", side_effect=err):
        assert client.get_history_raw("missing") == {}


def test_get_history_raw_reraises_non_404_http_errors():
    """500-class errors must surface so we don't silently wait forever."""
    from urllib.error import HTTPError

    client = _client()
    err = HTTPError(url="http://127.0.0.1:8188/history/broken", code=500,
                    msg="Server Error", hdrs={}, fp=None)
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(HTTPError):
            client.get_history_raw("broken")


def test_mcp_client_exposes_strict_workflow_gates():
    client = _client()
    assert hasattr(client, "strip_workflow")
    assert hasattr(client, "validate_workflow")
    assert hasattr(client, "check_runtime")
    assert hasattr(client, "enqueue")
    assert not hasattr(client, "save_workflow")
    assert not hasattr(client, "get_workflow")
