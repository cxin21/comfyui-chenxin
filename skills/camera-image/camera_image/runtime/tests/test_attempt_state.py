"""Tests for runtime/attempt_state.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime import attempt_state


def test_record_and_read_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(attempt_state.STATE_DIR_ENV, str(tmp_path))
    assert attempt_state.read_last_attempt() is None
    path = attempt_state.record_attempt({"outcome": "blocked", "reason_code": "x"})
    assert path == tmp_path / attempt_state.STATE_FILE_NAME
    last = attempt_state.read_last_attempt()
    assert last is not None
    assert last["outcome"] == "blocked"
    assert last["reason_code"] == "x"
    assert "recorded_at" in last


def test_malformed_lines_are_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(attempt_state.STATE_DIR_ENV, str(tmp_path))
    attempt_state.ensure_state_dir().write_text(
        "not-json\n" + json.dumps({"outcome": "ok", "value": 1}) + "\n",
        encoding="utf-8",
    )
    last = attempt_state.read_last_attempt()
    assert last == {"outcome": "ok", "value": 1, "recorded_at": last["recorded_at"]}


def test_record_rejects_non_dict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(attempt_state.STATE_DIR_ENV, str(tmp_path))
    with pytest.raises(TypeError):
        attempt_state.record_attempt("nope")  # type: ignore[arg-type]
