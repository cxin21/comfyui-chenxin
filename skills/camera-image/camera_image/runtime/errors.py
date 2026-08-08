"""Structured, JSON-safe faults emitted by the Prompt Forge runtime."""

from __future__ import annotations

import json


FAULT_CATEGORIES = frozenset(
    {
        "CAPABILITY_ERROR",
        "WORKFLOW_ERROR",
        "RESOURCE_ERROR",
        "POLICY_ERROR",
        "EXECUTION_ERROR",
    }
)


class FaultError(ValueError):
    """Raised when a runtime fault does not meet the stable fault contract."""


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FaultError(f"{name} must be a non-empty string")
    return value


def make_fault(
    category: str,
    stage: str,
    message: str,
    retry_safe: bool,
    next_action: str,
    evidence: dict,
    *,
    remediation: str | None = None,
) -> dict:
    """Create one validated fault that can be serialized as strict JSON."""
    if not isinstance(category, str) or category not in FAULT_CATEGORIES:
        raise FaultError("category must be one of the five supported categories")
    _require_text("stage", stage)
    _require_text("message", message)
    if not isinstance(retry_safe, bool):
        raise FaultError("retry_safe must be a boolean")
    _require_text("next_action", next_action)
    if not isinstance(evidence, dict):
        raise FaultError("evidence must be a dictionary")

    fault = {
        "schema_version": "1.0",
        "category": category,
        "stage": stage,
        "message": message,
        "retry_safe": retry_safe,
        "next_action": next_action,
        "remediation": remediation if isinstance(remediation, str) and remediation.strip() else next_action,
        "evidence": evidence,
    }
    try:
        return json.loads(json.dumps(fault, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FaultError("evidence must be JSON-safe") from exc
