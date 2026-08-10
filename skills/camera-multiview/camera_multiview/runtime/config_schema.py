"""The intentionally small public configuration surface for multiview."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


STAGE = "multiview"


@dataclass(frozen=True)
class RunConfig:
    """Only the two user-uploaded reference images are configurable."""

    evidence: dict
    draft: dict
    dialect_id: str = "anima"
    full_body_image: str | None = None
    face_image: str | None = None
    # The shared execution engine passes these attributes to every skill.
    groups: None = None
    lora: None = None

    @classmethod
    def from_envelope(cls, envelope: dict[str, Any] | None, **tunables: Any) -> "RunConfig":
        allowed = {"full_body_image", "face_image"}
        unknown = sorted(set(tunables) - allowed)
        if unknown:
            raise TypeError(f"unsupported multiview config field(s): {unknown}")
        envelope = envelope if isinstance(envelope, dict) else {}
        return cls(
            evidence=envelope.get("evidence", {}),
            draft=envelope.get(
                "draft",
                {
                    "positive": "fixed Flux2-Klein multiview workflow, cinematic lighting, anime style",
                    "negative": "fixed",
                    "tags": ["solo"],
                    "structure": [
                        {"name": "subject", "text": "fixed Flux2-Klein multiview workflow"},
                        {"name": "action_or_pose", "text": "multiview"},
                        {"name": "scene", "text": "cinematic"},
                        {"name": "lighting", "text": "cinematic lighting"},
                        {"name": "style", "text": "anime style"},
                    ],
                },
            ),
            dialect_id=envelope.get("dialect_id", "anima"),
            full_body_image=tunables.get("full_body_image"),
            face_image=tunables.get("face_image"),
        )
