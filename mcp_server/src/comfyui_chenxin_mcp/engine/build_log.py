"""Server-side BuildLog registry for Prompt Forge authoring audits.

A BuildLog is the full audit trail (facts, trace, token report, audit,
compression, conflict, sha256) produced by the prompt_forge author
pipeline. It lives here, server-side, keyed by a random 32-character
ref id. Camera skills do not consume it directly — they consume the
extracted `prompt` dict passed back from compile_prompt_artifact. Inspect
BuildLogs via `get_build_audit(ref_id)` (full) or
`get_build_metadata(ref_id)` (summary).

The server-side store replaces the earlier "pass the full 14-field
artifact dict across turns" pattern that forced the LLM to carry the
entire certificate as a payload. Per the first-principles re-design:
the LLM carries a 16-character ref id; the audit lives where it
belongs (server-side, on demand).
"""
from __future__ import annotations

import secrets
from typing import Any


_BUILDS: dict[str, dict[str, Any]] = {}


def _new_ref_id() -> str:
    return secrets.token_hex(16)


def register(
    *,
    artifact_version: int,
    task: str,
    model: str,
    prompt: dict[str, str],
    facts: tuple,
    trace: dict,
    token_report: dict,
    audit: dict,
    compression: tuple,
    conflict: Any,
    sacrificed_facts: tuple,
    token_count_verified: bool,
    knowledge_manifest_sha256: str,
    artifact_sha256: str,
    status: str,
) -> str:
    ref_id = _new_ref_id()
    _BUILDS[ref_id] = {
        "ref_id": ref_id,
        "artifact_version": artifact_version,
        "task": task,
        "model": model,
        "prompt": prompt,
        "facts": facts,
        "trace": trace,
        "token_report": token_report,
        "audit": audit,
        "compression": compression,
        "conflict": conflict,
        "sacrificed_facts": sacrificed_facts,
        "token_count_verified": token_count_verified,
        "knowledge_manifest_sha256": knowledge_manifest_sha256,
        "artifact_sha256": artifact_sha256,
        "status": status,
    }
    return ref_id


def get(ref_id: str) -> dict[str, Any] | None:
    return _BUILDS.get(ref_id)


def metadata(ref_id: str) -> dict[str, Any] | None:
    log = _BUILDS.get(ref_id)
    if log is None:
        return None
    token_count = 0
    report = log.get("token_report")
    if isinstance(report, dict):
        actual = report.get("actual")
        if isinstance(actual, (int, float)):
            token_count = int(actual)
    return {
        "ref_id": log["ref_id"],
        "task": log["task"],
        "status": log["status"],
        "sha256_prefix": log["artifact_sha256"][:12],
        "token_count": token_count,
        "token_count_verified": log["token_count_verified"],
        "fact_count": len(log.get("facts") or ()),
        "compression_count": len(log.get("compression") or ()),
        "has_conflict": log.get("conflict") is not None,
    }


def delete(ref_id: str) -> bool:
    return _BUILDS.pop(ref_id, None) is not None


def size() -> int:
    return len(_BUILDS)
