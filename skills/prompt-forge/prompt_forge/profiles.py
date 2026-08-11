"""Exact profile loading and validation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import ForgeRequest, PromptForgeError


PROFILE_ROOT = Path(__file__).resolve().parent.parent / "profiles"


@dataclass(frozen=True)
class Profile:
    profile_id: str
    modality: str
    operations: tuple[str, ...]
    status: str
    workflow_bindings: tuple[dict[str, Any], ...]
    negative_policy: str
    grammar: str
    sources: tuple[dict[str, Any], ...]
    capabilities: dict[str, Any]


def load_profile(profile_id: str) -> Profile:
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise PromptForgeError("profile_id must be a non-empty exact profile id")
    path = PROFILE_ROOT / f"{profile_id}.json"
    if not path.is_file():
        raise PromptForgeError(f"exact prompt profile is not installed: {profile_id}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PromptForgeError(f"prompt profile is invalid: {profile_id}") from exc
    if not isinstance(raw, dict) or raw.get("profile_id") != profile_id:
        raise PromptForgeError(f"prompt profile id mismatch: {profile_id}")
    required = ("modality", "operations", "status", "workflow_bindings", "grammar", "sources")
    missing = [key for key in required if key not in raw]
    if missing:
        raise PromptForgeError(f"prompt profile is incomplete: {profile_id}; missing {missing}")
    return Profile(
        profile_id=profile_id,
        modality=str(raw["modality"]),
        operations=tuple(str(item) for item in raw["operations"]),
        status=str(raw["status"]),
        workflow_bindings=tuple(dict(item) for item in raw["workflow_bindings"]),
        negative_policy=str(raw.get("negative_policy", "unsupported")),
        grammar=str(raw["grammar"]),
        sources=tuple(dict(item) for item in raw["sources"]),
        capabilities=dict(raw.get("capabilities", {})),
    )


def validate_request(profile: Profile, request: ForgeRequest) -> None:
    if request.operation not in profile.operations:
        raise PromptForgeError(
            f"operation {request.operation!r} is not supported by {profile.profile_id}"
        )
    if not request.positive.strip():
        raise PromptForgeError("prompt.positive must be a non-empty authored string")
    if request.reference_count < 0:
        raise PromptForgeError("reference_count must be non-negative")
    if profile.status != "production_verified":
        raise PromptForgeError(
            f"prompt profile is not production_verified: {profile.profile_id} ({profile.status})"
        )
    if profile.negative_policy == "unsupported" and request.negative not in (None, ""):
        raise PromptForgeError(f"{profile.profile_id} does not accept a negative prompt")
    if request.duration is not None and not 2.0 <= float(request.duration) <= 15.0:
        raise PromptForgeError(f"duration must be between 2 and 15 seconds, got {request.duration}")
