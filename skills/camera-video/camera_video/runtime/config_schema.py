"""Strict public configuration for the three MiniMax H3 video scenes."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


STAGES = ("t2v-video", "i2v-video", "multi-i2v-video")
IMAGE_FIELDS = {
    "i2v-video": ("reference_image_1",),
    "multi-i2v-video": ("reference_image_1", "reference_image_2", "reference_image_3"),
}
ALLOWED_FIELDS = {
    "prompt",
    "duration",
    "reference_image_1",
    "reference_image_2",
    "reference_image_3",
}


@dataclass(frozen=True)
class RunConfig:
    evidence: dict[str, Any]
    draft: dict[str, Any]
    dialect_id: str
    prompt: str
    duration: float
    reference_image_1: str | None = None
    reference_image_2: str | None = None
    reference_image_3: str | None = None
    groups: None = None
    lora: None = None

    @classmethod
    def from_envelope(cls, envelope: dict[str, Any], **tunables: Any) -> "RunConfig":
        if not isinstance(envelope.get("evidence"), dict):
            raise TypeError("envelope.evidence must be an object")
        if envelope.get("draft") not in (None, {}):
            raise ValueError("camera-video does not accept envelope.draft; use config.prompt")
        if envelope.get("dialect_id") not in (None, "minimax_h3"):
            raise ValueError("camera-video uses the fixed minimax_h3 dialect")
        unknown = sorted(set(tunables) - ALLOWED_FIELDS)
        if unknown:
            raise TypeError(f"unsupported camera-video config field(s): {unknown}")
        prompt = tunables.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        duration = tunables.get("duration")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise TypeError("duration must be a number")
        duration = float(duration)
        if not isfinite(duration) or not 2.0 <= duration <= 15.0:
            raise ValueError("duration must be between 2 and 15 seconds")
        return cls(
            evidence=dict(envelope.get("evidence") or {}),
            draft={},
            dialect_id="minimax_h3",
            prompt=prompt,
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
        for field in ALLOWED_FIELDS - required - {"prompt", "duration"}:
            if getattr(self, field) is not None:
                raise ValueError(f"{field} is not allowed for {stage}")
