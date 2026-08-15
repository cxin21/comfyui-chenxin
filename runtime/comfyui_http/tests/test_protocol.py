"""Contract tests for the protocol dataclasses.

These tests pin the *shape* of records the transport exchanges with ComfyUI
without touching the network, so they run in every environment.
"""

from __future__ import annotations

import hashlib

import pytest

from comfyui_http.protocol import Artifact, HistoryRecord, UploadedFile


def test_uploaded_file_from_payload_minimal():
    record = UploadedFile.from_payload({"name": "clipspace/alpha.png"})
    assert record.name == "clipspace/alpha.png"
    assert record.file_type == "input"
    assert record.subfolder == ""


def test_uploaded_file_from_payload_rejects_non_object():
    with pytest.raises(ValueError):
        UploadedFile.from_payload(["not", "an", "object"])  # type: ignore[arg-type]


def test_uploaded_file_from_payload_requires_name():
    with pytest.raises(ValueError):
        UploadedFile.from_payload({"type": "input"})


def test_history_record_outputs_are_sorted_and_frozen():
    payload = {
        "outputs": {
            "9": {"images": [{"filename": "out.png"}]},
            "3": {"images": [{"filename": "earlier.png"}]},
        },
        "status": {"completed": True},
    }
    record = HistoryRecord.from_payload("prompt-id", payload)
    assert record.prompt_id == "prompt-id"
    assert tuple(node_id for node_id, _ in record.outputs) == ("3", "9")
    assert record.status == {"completed": True}


def test_history_record_rejects_non_object():
    with pytest.raises(ValueError):
        HistoryRecord.from_payload("prompt-id", "string")


def test_artifact_sha256_property_matches_content():
    payload = b"hello comfyui"
    artifact = Artifact(filename="out.png", subfolder="", artifact_type="output", bytes=payload)
    assert artifact.sha256 == hashlib.sha256(payload).hexdigest()
    assert len(artifact.sha256) == 64
