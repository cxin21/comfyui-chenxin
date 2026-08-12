"""Declarative dependency rule validator.

Public MCP-tool shape: validate_config takes the SAME inputs as run_skill
(envelope + config dicts), so callers can pre-flight a config without
needing a separate shape. The engine never raises on validation failure —
it returns {"ok": False, "errors": [...]}.

Layered contract:
  - MCP tool layer (server.py:validate) — public; accepts envelope + config dicts.
  - engine.validate_config        — internal; same shape, single source of truth.
  - engine.execute.run_skill      — internal; takes a RunConfig dataclass.
                                  The MCP server builds it via SkillData.build_config_fn.
"""
from __future__ import annotations

from typing import Any

from .skill_data import SkillData, Rule


def validate_config(
    skill_data: SkillData,
    stage: str,
    envelope: Any,
    config: Any,
) -> dict[str, Any]:
    """Validate envelope shape + declarative dependency rules.

    Same input shape as the `run_skill` tool (minus `output_dir`). Returns
    ``{"ok": bool, "errors": list[str], "stage": str, "skill": str}``.

    Never raises on validation failure — bad input is a normal outcome.
    """
    if not isinstance(envelope, dict):
        return {
            "ok": False,
            "errors": ["envelope must be an object"],
            "stage": stage,
            "skill": skill_data.name,
        }
    if not isinstance(config, dict):
        return {
            "ok": False,
            "errors": ["config must be an object"],
            "stage": stage,
            "skill": skill_data.name,
        }

    errors: list[str] = []

    if skill_data.envelope_validate_fn is not None:
        errors.extend(skill_data.envelope_validate_fn(envelope))
    else:
        if set(envelope) != {"prompt_artifact"}:
            errors.append("envelope must contain exactly prompt_artifact")
        elif not isinstance(envelope["prompt_artifact"], dict):
            errors.append("envelope.prompt_artifact must be an object")

    try:
        built = skill_data.build_config_fn(envelope, **config)
        validate_stage = getattr(built, "validate_stage", None)
        if callable(validate_stage):
            validate_stage(stage)
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))

    # Declarative dependency rules (config-only — envelope fields never trigger rules).
    groups = config.get("groups") or {}
    if isinstance(groups, dict):
        g1 = list(groups.get("g1") or [])
        g2 = list(groups.get("g2") or [])
    else:
        g1, g2 = [], []
    all_groups = g1 + g2

    # Reflect the engine's stage auto-append behaviour: any stage:i2i-camera
    # (etc.) -> group_auto:<title> rule auto-enables that group at run time.
    # The validator must mirror that, otherwise rule: 加载图片 <-> reference_image
    # false-fails when the user provides reference_image for an i2i stage
    # without remembering to also add 加载图片 to groups.g1.
    for rule in skill_data.dependency_rules:
        if rule.direction == "forward" and rule.condition == f"stage:{stage}":
            impl_type, _, impl_val = rule.implies.partition(":")
            if impl_type == "group_auto" and impl_val not in all_groups:
                all_groups = list(all_groups) + [impl_val]

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


def _is_condition_met(
    cond_type: str,
    cond_val: str,
    stage: str,
    config: dict,
    all_groups: list[str],
) -> bool:
    if cond_type == "config":
        return config.get(cond_val) is not None
    if cond_type == "group":
        return cond_val in all_groups
    if cond_type == "stage":
        return stage == cond_val
    return False


def _check_implies(
    impl_type: str,
    impl_val: str,
    config: dict,
    all_groups: list[str],
) -> list[str]:
    if impl_type == "config":
        if config.get(impl_val) is None:
            return [f"config.{impl_val} is required (dependency rule)"]
    elif impl_type == "group":
        if impl_val not in all_groups:
            return [f"group '{impl_val}' must be enabled (dependency rule)"]
    # group_auto: informational, not a validation error.
    return []
