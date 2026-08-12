"""Strict public configuration for the three MiniMax H3 video scenes."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


def _truncate_repr(value: Any, limit: int) -> str:
    text = repr(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


STAGES = ("t2v-video", "i2v-video", "multi-i2v-video")
IMAGE_FIELDS = {
    "i2v-video": ("reference_image_1",),
    "multi-i2v-video": ("reference_image_1", "reference_image_2", "reference_image_3"),
}
ALLOWED_FIELDS = {
    "duration",
    "reference_image_1",
    "reference_image_2",
    "reference_image_3",
}


@dataclass(frozen=True)
class RunConfig:
    prompt_artifact: dict[str, Any]
    duration: float
    reference_image_1: str | None = None
    reference_image_2: str | None = None
    reference_image_3: str | None = None
    groups: None = None
    lora: None = None

    @classmethod
    def from_envelope(cls, envelope: dict[str, Any], **tunables: Any) -> "RunConfig":
        if not isinstance(envelope, dict):
            raise TypeError("envelope must be an object")
        unknown_envelope = sorted(set(envelope) - {"prompt_artifact"})
        if unknown_envelope:
            raise TypeError(f"unsupported envelope field(s): {unknown_envelope}")
        prompt_artifact = envelope.get("prompt_artifact")
        if not isinstance(prompt_artifact, dict):
            raise TypeError("envelope.prompt_artifact must be an object")
        unknown = sorted(set(tunables) - ALLOWED_FIELDS)
        if unknown:
            raise TypeError(
                f"unsupported camera-video config field(s): {unknown}; "
                f"valid fields: {sorted(ALLOWED_FIELDS)}"
            )
        duration = tunables.get("duration")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise TypeError(
                f"duration must be a JSON number (got "
                f"{type(duration).__name__}: {_truncate_repr(duration, 60)}); "
                f"use 8.0 not \"8.0\""
            )
        duration = float(duration)
        if not isfinite(duration) or not 2.0 <= duration <= 15.0:
            raise ValueError(
                f"duration must be between 2 and 15 seconds, got {duration}"
            )
        return cls(
            prompt_artifact=dict(prompt_artifact),
            duration=duration,
            reference_image_1=tunables.get("reference_image_1"),
            reference_image_2=tunables.get("reference_image_2"),
            reference_image_3=tunables.get("reference_image_3"),
        )

    def validate_stage(self, stage: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown camera-video stage: {stage!r}")
        required = set(IMAGE_FIELDS.get(stage, ()))
        for field in IMAGE_FIELDS.get(stage, ()):
            if not getattr(self, field):
                raise ValueError(f"{field} is required for {stage}")
        for field in ALLOWED_FIELDS - required - {"duration"}:
            if getattr(self, field) is not None:
                raise ValueError(f"{field} is not allowed for {stage}")
