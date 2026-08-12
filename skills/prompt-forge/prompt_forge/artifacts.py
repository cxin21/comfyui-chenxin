"""Canonical immutable PromptArtifact construction and hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .contracts import ArtifactStatus, Fact, TaskKind


@dataclass(frozen=True)
class PromptArtifact:
    artifact_version: int
    status: ArtifactStatus
    task: TaskKind
    model: str
    prompt: Mapping[str, str] | None
    facts: tuple[Fact, ...]
    trace: Mapping[str, tuple[str, ...]]
    token_report: Mapping[str, Any]
    audit: Mapping[str, Any]
    compression: tuple[Any, ...]
    conflict: Mapping[str, Any] | None
    sacrificed_facts: tuple[str, ...]
    token_count_verified: bool
    knowledge_manifest_sha256: str
    artifact_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_version": self.artifact_version,
            "status": self.status,
            "task": self.task,
            "model": self.model,
            "prompt": _jsonable(self.prompt),
            "facts": [_jsonable(fact) for fact in self.facts],
            "trace": _jsonable(self.trace),
            "token_report": _jsonable(self.token_report),
            "audit": _jsonable(self.audit),
            "compression": [_jsonable(item) for item in self.compression],
            "conflict": _jsonable(self.conflict),
            "sacrificed_facts": list(self.sacrificed_facts),
            "token_count_verified": self.token_count_verified,
            "knowledge_manifest_sha256": self.knowledge_manifest_sha256,
            "artifact_sha256": self.artifact_sha256,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


def create_prompt_artifact(
    *,
    status: ArtifactStatus,
    task: TaskKind,
    model: str,
    prompt: Mapping[str, str] | None,
    facts: tuple[Fact, ...],
    trace: Mapping[str, tuple[str, ...]],
    token_report: Mapping[str, Any],
    audit: Mapping[str, Any],
    compression: tuple[Any, ...],
    conflict: Mapping[str, Any] | None,
    token_count_verified: bool,
    knowledge_manifest_sha256: str,
) -> PromptArtifact:
    if status == "production_ready" and prompt is None:
        raise ValueError("production_ready artifacts require an executable prompt")
    if status != "production_ready" and prompt is not None:
        raise ValueError("rejected or conflicting artifacts cannot expose a prompt")
    if len(knowledge_manifest_sha256) != 64:
        raise ValueError("knowledge_manifest_sha256 must be a SHA-256 hex digest")
    base = {
        "artifact_version": 1,
        "status": status,
        "task": task,
        "model": model,
        "prompt": _jsonable(prompt),
        "facts": [_jsonable(fact) for fact in facts],
        "trace": _jsonable(trace),
        "token_report": _jsonable(token_report),
        "audit": _jsonable(audit),
        "compression": [_jsonable(item) for item in compression],
        "conflict": _jsonable(conflict),
        "sacrificed_facts": [],
        "token_count_verified": token_count_verified,
        "knowledge_manifest_sha256": knowledge_manifest_sha256,
    }
    digest = hashlib.sha256(
        json.dumps(
            base,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return PromptArtifact(
        artifact_version=1,
        status=status,
        task=task,
        model=model,
        prompt=_freeze_mapping(prompt),
        facts=facts,
        trace=MappingProxyType({key: tuple(value) for key, value in sorted(trace.items())}),
        token_report=_freeze_mapping(token_report) or MappingProxyType({}),
        audit=_freeze_mapping(audit) or MappingProxyType({}),
        compression=tuple(compression),
        conflict=_freeze_mapping(conflict),
        sacrificed_facts=(),
        token_count_verified=token_count_verified,
        knowledge_manifest_sha256=knowledge_manifest_sha256,
        artifact_sha256=digest,
    )


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if value is None:
        return None
    return MappingProxyType({key: _freeze(item) for key, item in value.items()})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list | set | frozenset):
        return [_jsonable(item) for item in value]
    raise TypeError(f"value is not artifact-serializable: {type(value).__name__}")
