"""Test configuration - isolates side-effect state from real home dir."""
import os
import pytest


@pytest.fixture(autouse=True)
def _isolate_state_dir(tmp_path, monkeypatch):
    """Redirect attempt_state writes to a temp dir during tests."""
    monkeypatch.setenv("COMFYUI_CHENXIN_STATE_DIR", str(tmp_path / "state"))
