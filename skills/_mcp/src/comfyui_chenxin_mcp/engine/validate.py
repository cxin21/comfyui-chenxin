"""Declarative dependency rule validator.

Checks group-config dependencies via Rule objects (data, not procedural code).
Also validates envelope shape (draft.positive/negative non-empty).
"""
from __future__ import annotations

from typing import Any

from .skill_data import SkillData, Rule


def validate_config(skill_data: SkillData, stage: str, config: Any) -> dict[str, Any]:
    """Validate a config dict against the skill's dependency rules + envelope shape.

    Returns {"ok": bool, "errors": list[str], "stage": str, "skill": str}.
    """
    if not isinstance(config, dict):
        return {"ok": False, "errors": ["config must be an object"], "stage": stage, "skill": skill_data.name}

    errors: list[str] = []

    # Envelope shape: draft must have non-empty positive/negative.
    draft = config.get("draft")
    if not isinstance(draft, dict):
        errors.append("config.draft must be an object (prompt-forge envelope)")
    else:
        for key in ("positive", "negative"):
            val = draft.get(key)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"config.draft.{key} must be a non-empty string")

    # Declarative dependency rules.
    groups = config.get("groups") or {}
    g1 = list(groups.get("g1", [])) if isinstance(groups, dict) else []
    g2 = list(groups.get("g2", [])) if isinstance(groups, dict) else []
    all_groups = g1 + g2

    for rule in skill_data.dependency_rules:
        errors.extend(_check_rule(rule, stage, config, all_groups))

    if errors:
        return {"ok": False, "errors": errors, "stage": stage, "skill": skill_data.name}
    return {"ok": True, "errors": [], "stage": stage, "skill": skill_data.name}


def _check_rule(rule: Rule, stage: str, config: dict, all_groups: list[str]) -> list[str]:
    """Check a single Rule. Returns list of error strings (empty if ok)."""
    cond_type, _, cond_val = rule.condition.partition(":")
    impl_type, _, impl_val = rule.implies.partition(":")

    errors: list[str] = []

    cond_met = _is_condition_met(cond_type, cond_val, stage, config, all_groups)
    if cond_met:
        errors.extend(_check_implies(impl_type, impl_val, config, all_groups))

    if rule.direction == "bidirectional":
        impl_met = _is_condition_met(impl_type, impl_val, stage, config, all_groups)
        if impl_met:
            errors.extend(_check_implies(cond_type, cond_val, config, all_groups))

    return errors


def _is_condition_met(cond_type: str, cond_val: str, stage: str, config: dict, all_groups: list[str]) -> bool:
    if cond_type == "config":
        return config.get(cond_val) is not None
    if cond_type == "group":
        return cond_val in all_groups
    if cond_type == "stage":
        return stage == cond_val
    return False


def _check_implies(impl_type: str, impl_val: str, config: dict, all_groups: list[str]) -> list[str]:
    if impl_type == "config":
        if config.get(impl_val) is None:
            return [f"config.{impl_val} is required (dependency rule)"]
    elif impl_type == "group":
        if impl_val not in all_groups:
            return [f"group '{impl_val}' must be enabled (dependency rule)"]
    # group_auto: informational, not a validation error.
    return []