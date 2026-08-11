"""Small public interface for the deep Prompt Forge module.

The module accepts an already authored model-native prompt. It never invents
creative prose. Its implementation resolves the exact profile, audits the
prompt, and returns an immutable artifact for a downstream consumer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PromptForgeError(ValueError):
    """The prompt cannot satisfy the selected exact profile."""


@dataclass(frozen=True)
class ForgeRequest:
    profile_id: str
    operation: str
    positive: str
    negative: str | None = None
    duration: float | None = None
    reference_count: int = 0
    regional: dict[str, str] = field(default_factory=dict)
    constraints: tuple[dict[str, Any], ...] = ()
    assumptions: tuple[str, ...] = ()
    asset_bindings: tuple[dict[str, Any], ...] = ()
    workflow_sha256: str | None = None
    adapter_manifest_sha256: str | None = None


@dataclass(frozen=True)
class PromptArtifact:
    artifact_version: int
    profile_id: str
    operation: str
    positive: str
    negative: str | None
    regional: dict[str, str]
    asset_bindings: tuple[dict[str, Any], ...]
    constraints: tuple[dict[str, Any], ...]
    assumptions: tuple[str, ...]
    workflow_sha256: str | None
    adapter_manifest_sha256: str | None
    lint: dict[str, Any]
    review: dict[str, Any]
    provenance: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_version": self.artifact_version,
            "profile_id": self.profile_id,
            "operation": self.operation,
            "prompt": {
                "positive": self.positive,
                "negative": self.negative,
                "regional": dict(self.regional),
            },
            "asset_bindings": [dict(item) for item in self.asset_bindings],
            "constraints": [dict(item) for item in self.constraints],
            "assumptions": list(self.assumptions),
            "workflow_sha256": self.workflow_sha256,
            "adapter_manifest_sha256": self.adapter_manifest_sha256,
            "lint": dict(self.lint),
            "review": dict(self.review),
            "provenance": [dict(item) for item in self.provenance],
        }
