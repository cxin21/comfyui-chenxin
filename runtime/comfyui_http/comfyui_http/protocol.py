"""Typed records the neutral HTTP transport returns and accepts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UploadedFile:
    """The payload returned by ``POST /upload/image``."""

    name: str
    file_type: str
    subfolder: str

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "UploadedFile":
        if not isinstance(payload, dict):
            raise ValueError("upload payload must be a JSON object")
        name = payload.get("name")
        file_type = payload.get("type", "input")
        subfolder = payload.get("subfolder", "")
        if not isinstance(name, str) or not name:
            raise ValueError("upload payload missing 'name'")
        if not isinstance(file_type, str):
            raise ValueError("upload payload 'type' must be a string")
        if not isinstance(subfolder, str):
            raise ValueError("upload payload 'subfolder' must be a string")
        return cls(name=name, file_type=file_type, subfolder=subfolder)


@dataclass(frozen=True)
class HistoryRecord:
    """The shell returned by ``GET /history/{prompt_id}`` for one prompt."""

    prompt_id: str
    outputs: tuple[tuple[str, dict[str, object]], ...]
    status: dict[str, object]

    @classmethod
    def from_payload(cls, prompt_id: str, payload: object) -> "HistoryRecord":
        if not isinstance(payload, dict):
            raise ValueError("history record must be a JSON object")
        outputs_raw = payload.get("outputs", {})
        status_raw = payload.get("status", {})
        if not isinstance(outputs_raw, dict):
            raise ValueError("'outputs' must be a JSON object")
        if not isinstance(status_raw, dict):
            raise ValueError("'status' must be a JSON object")
        outputs = tuple(sorted(outputs_raw.items()))
        return cls(prompt_id=prompt_id, outputs=outputs, status=status_raw)


@dataclass(frozen=True)
class Artifact:
    """A binary asset downloaded from ``GET /view``."""

    filename: str
    subfolder: str
    artifact_type: str
    bytes: bytes

    @property
    def sha256(self) -> str:
        import hashlib

        return hashlib.sha256(self.bytes).hexdigest()
