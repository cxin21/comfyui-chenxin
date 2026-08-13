"""Task-specific dynamic token budgets and allocation policies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from math import ceil, floor, isfinite
from pathlib import Path
from typing import Any, Mapping

from .contracts import Complexity


_KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge"
_ANIMA_POLICY = _KNOWLEDGE_ROOT / "anima" / "budget-policy.json"
_REFERENCES_ROOT = Path(__file__).resolve().parent.parent / "references"
_H3_POLICY = _REFERENCES_ROOT / "dialects" / "minimax-h3" / "budget-policy.json"


class BudgetPolicyError(ValueError):
    """An input or bundled allocation policy violates the approved design."""


@dataclass(frozen=True)
class FieldAllocation:
    name: str
    recommended_min_share: float
    recommended_max_share: float
    hard_max_share: float
    budget_target: int

    @property
    def minimum_tokens(self) -> int:
        return floor(self.budget_target * self.recommended_min_share)

    @property
    def recommended_max_tokens(self) -> int:
        return ceil(self.budget_target * self.recommended_max_share)

    @property
    def hard_max_tokens(self) -> int:
        return ceil(self.budget_target * self.hard_max_share)


@dataclass(frozen=True)
class AllocationPolicy:
    fields: tuple[FieldAllocation, ...]
    borrowing_order: tuple[str, ...] = ()
    non_lendable_buckets: frozenset[str] = frozenset()

    def field(self, name: str) -> FieldAllocation:
        for allocation in self.fields:
            if allocation.name == name:
                return allocation
        raise BudgetPolicyError(f"unknown allocation field: {name}")


@dataclass(frozen=True)
class BudgetWindow(AllocationPolicy):
    target: int = 0
    soft_limit: int = 0
    quality_limit: int = 0
    hard_limit: int = 0
    per_shot: AllocationPolicy | None = None


@dataclass(frozen=True)
class AnimaBudgetPlan:
    positive: BudgetWindow
    negative: BudgetWindow


@dataclass(frozen=True)
class H3BudgetPlan:
    text: BudgetWindow
    max_shots: int


def plan_anima_budget(
    complexity: Complexity,
    exclusion_groups: int,
) -> AnimaBudgetPlan:
    """Plan Anima positive and negative budgets from scene complexity."""
    values = {
        "subjects": complexity.subjects,
        "explicit_relations": complexity.explicit_relations,
        "complex_actions": complexity.complex_actions,
        "environment_clusters": complexity.environment_clusters,
        "scene_descriptions": complexity.scene_descriptions,
    }
    for name, value in values.items():
        _require_non_negative_integer(name, value)
    _require_non_negative_integer("exclusion_groups", exclusion_groups)

    policy = _load_policy(_ANIMA_POLICY)
    formula = _mapping(policy, "formula")
    positive_raw = (
        _integer(formula, "positive_base")
        + _integer(formula, "per_additional_subject")
        * max(0, complexity.subjects - 1)
        + _integer(formula, "per_explicit_relation")
        * complexity.explicit_relations
        + _integer(formula, "per_complex_action") * complexity.complex_actions
        + _integer(formula, "per_environment_cluster")
        * complexity.environment_clusters
        + _integer(formula, "per_scene_description")
        * complexity.scene_descriptions
    )
    positive_target = _clamp(
        positive_raw,
        _integer(formula, "positive_min"),
        _integer(formula, "positive_max"),
    )
    negative_target = _clamp(
        _integer(formula, "negative_base")
        + _integer(formula, "per_exclusion_group") * exclusion_groups,
        _integer(formula, "negative_min"),
        _integer(formula, "negative_max"),
    )
    limits = _mapping(policy, "limits")
    return AnimaBudgetPlan(
        positive=_budget_window(
            target=positive_target,
            limits=limits,
            quality_cap_key="positive_quality_cap",
            fields=_list(policy, "positive_fields"),
            borrowing_order=_string_tuple(policy, "positive_borrowing_order"),
            non_lendable=_string_frozenset(
                policy,
                "positive_non_lendable_buckets",
            ),
        ),
        negative=_budget_window(
            target=negative_target,
            limits=limits,
            quality_cap_key="negative_quality_cap",
            fields=_list(policy, "negative_fields"),
            borrowing_order=_string_tuple(policy, "negative_borrowing_order"),
            non_lendable=_string_frozenset(
                policy,
                "negative_non_lendable_buckets",
            ),
        ),
    )


def plan_h3_t2va_budget(
    duration_seconds: float,
    shot_count: int,
    dialogue_tokens: int,
) -> H3BudgetPlan:
    """Plan MiniMax-H3 text-to-video-with-audio text budget."""
    policy = _mapping(_load_policy(_H3_POLICY), "t2va")
    formula = _mapping(policy, "formula")
    max_shots = _validate_h3_inputs(
        duration_seconds,
        shot_count,
        dialogue_tokens,
        formula,
    )
    raw = (
        _integer(formula, "base")
        + _number(formula, "per_duration_second") * duration_seconds
        + _integer(formula, "per_additional_shot") * max(0, shot_count - 1)
        + dialogue_tokens
    )
    target = _clamp_ceil(
        raw,
        _integer(formula, "target_min"),
        _integer(formula, "target_max"),
    )
    per_shot = _allocation_policy(
        _list(policy, "per_shot_fields"),
        target,
    )
    return H3BudgetPlan(
        text=_budget_window(
            target=target,
            limits=_mapping(policy, "limits"),
            quality_cap_key="quality_cap",
            fields=_list(policy, "fields"),
            borrowing_order=_string_tuple(policy, "borrowing_order"),
            non_lendable=_string_frozenset(policy, "non_lendable_buckets"),
            per_shot=per_shot,
        ),
        max_shots=max_shots,
    )


def plan_h3_ref2va_budget(
    duration_seconds: float,
    shot_count: int,
    reference_count: int,
    dialogue_tokens: int,
) -> H3BudgetPlan:
    """Plan MiniMax-H3 reference-to-video-with-audio text budget."""
    _require_positive_integer("reference_count", reference_count)
    policy = _mapping(_load_policy(_H3_POLICY), "ref2va")
    formula = _mapping(policy, "formula")
    max_shots = _validate_h3_inputs(
        duration_seconds,
        shot_count,
        dialogue_tokens,
        formula,
    )
    raw = (
        _integer(formula, "base")
        + _integer(formula, "per_reference") * reference_count
        + _number(formula, "per_duration_second") * duration_seconds
        + _integer(formula, "per_additional_shot") * max(0, shot_count - 1)
        + dialogue_tokens
    )
    target = _clamp_ceil(
        raw,
        _integer(formula, "target_min"),
        _integer(formula, "target_max"),
    )
    return H3BudgetPlan(
        text=_budget_window(
            target=target,
            limits=_mapping(policy, "limits"),
            quality_cap_key="quality_cap",
            fields=_list(policy, "fields"),
            borrowing_order=_string_tuple(policy, "borrowing_order"),
            non_lendable=_string_frozenset(policy, "non_lendable_buckets"),
        ),
        max_shots=max_shots,
    )


def utility_density(
    priority: float,
    adherence_risk: float,
    source_confidence: float,
    non_redundancy: float,
    token_cost: int,
) -> float:
    """Return the approved marginal-information utility per exact token."""
    _require_positive_integer("token_cost", token_cost)
    factors = {
        "priority": priority,
        "adherence_risk": adherence_risk,
        "source_confidence": source_confidence,
        "non_redundancy": non_redundancy,
    }
    for name, value in factors.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BudgetPolicyError(f"{name} must be numeric")
        if not isfinite(float(value)) or value < 0:
            raise BudgetPolicyError(f"{name} must be non-negative and finite")
    if source_confidence > 1:
        raise BudgetPolicyError("source_confidence must be <= 1")
    if non_redundancy > 1:
        raise BudgetPolicyError("non_redundancy must be <= 1")
    return (
        priority
        * adherence_risk
        * source_confidence
        * non_redundancy
        / token_cost
    )


def _validate_h3_inputs(
    duration_seconds: float,
    shot_count: int,
    dialogue_tokens: int,
    formula: Mapping[str, Any],
) -> int:
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not isfinite(float(duration_seconds))
        or duration_seconds < _number(formula, "duration_min")
        or duration_seconds > _number(formula, "duration_max")
    ):
        raise BudgetPolicyError(
            "duration_seconds must be finite and within the approved bounds"
        )
    _require_positive_integer("shot_count", shot_count)
    _require_non_negative_integer("dialogue_tokens", dialogue_tokens)
    max_shots = 1 + floor(
        (duration_seconds - 1)
        / _integer(formula, "seconds_per_additional_shot")
    )
    if shot_count > max_shots:
        raise BudgetPolicyError(
            f"shot_count {shot_count} exceeds max_shots {max_shots}"
        )
    return max_shots


def _budget_window(
    *,
    target: int,
    limits: Mapping[str, Any],
    quality_cap_key: str,
    fields: list[Any],
    borrowing_order: tuple[str, ...],
    non_lendable: frozenset[str],
    per_shot: AllocationPolicy | None = None,
) -> BudgetWindow:
    soft_multiplier = _number(limits, "soft_multiplier")
    quality_multiplier = _number(limits, "quality_multiplier")
    policy = _allocation_policy(
        fields,
        target,
        borrowing_order=borrowing_order,
        non_lendable=non_lendable,
    )
    return BudgetWindow(
        fields=policy.fields,
        borrowing_order=policy.borrowing_order,
        non_lendable_buckets=policy.non_lendable_buckets,
        target=target,
        soft_limit=ceil(target * soft_multiplier),
        quality_limit=min(
            _integer(limits, quality_cap_key),
            ceil(target * quality_multiplier),
        ),
        hard_limit=_integer(limits, "hard_limit"),
        per_shot=per_shot,
    )


def _allocation_policy(
    fields: list[Any],
    target: int,
    *,
    borrowing_order: tuple[str, ...] = (),
    non_lendable: frozenset[str] = frozenset(),
) -> AllocationPolicy:
    allocations: list[FieldAllocation] = []
    names: set[str] = set()
    for raw in fields:
        if not isinstance(raw, dict):
            raise BudgetPolicyError("field allocation must be an object")
        name = raw.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise BudgetPolicyError("field allocation names must be non-empty and unique")
        names.add(name)
        minimum = _share(raw, "recommended_min_share")
        recommended_max = _share(raw, "recommended_max_share")
        hard_max = _share(raw, "hard_max_share")
        if not minimum <= recommended_max <= hard_max:
            raise BudgetPolicyError(f"invalid share ordering for field {name}")
        allocations.append(
            FieldAllocation(
                name=name,
                recommended_min_share=minimum,
                recommended_max_share=recommended_max,
                hard_max_share=hard_max,
                budget_target=target,
            )
        )
    unknown_borrowers = set(borrowing_order) - names
    if unknown_borrowers:
        raise BudgetPolicyError(
            f"borrowing order references unknown fields: {sorted(unknown_borrowers)}"
        )
    return AllocationPolicy(tuple(allocations), borrowing_order, non_lendable)


@lru_cache(maxsize=3)
def _load_policy(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BudgetPolicyError(f"cannot load bundled budget policy: {path}") from exc
    if not isinstance(payload, dict):
        raise BudgetPolicyError(f"budget policy must be an object: {path}")
    forbidden = {"model", "models", "profile", "profiles", "registry", "selector"}
    if forbidden.intersection(_all_keys(payload)):
        raise BudgetPolicyError("budget policies cannot contain model selection keys")
    return payload


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        result = {str(key) for key in value}
        for child in value.values():
            result.update(_all_keys(child))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(_all_keys(child))
        return result
    return set()


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise BudgetPolicyError(f"policy field {key} must be an object")
    return value


def _list(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise BudgetPolicyError(f"policy field {key} must be an array")
    return value


def _string_tuple(payload: Mapping[str, Any], key: str) -> tuple[str, ...]:
    values = _list(payload, key)
    if not all(isinstance(value, str) and value for value in values):
        raise BudgetPolicyError(f"policy field {key} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise BudgetPolicyError(f"policy field {key} must not contain duplicates")
    return tuple(values)


def _string_frozenset(payload: Mapping[str, Any], key: str) -> frozenset[str]:
    return frozenset(_string_tuple(payload, key))


def _number(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
    ):
        raise BudgetPolicyError(f"policy field {key} must be a finite number")
    return float(value)


def _integer(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BudgetPolicyError(f"policy field {key} must be an integer")
    return value


def _share(payload: Mapping[str, Any], key: str) -> float:
    value = _number(payload, key)
    if value < 0 or value > 1:
        raise BudgetPolicyError(f"policy field {key} must be between 0 and 1")
    return value


def _require_non_negative_integer(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BudgetPolicyError(f"{name} must be a non-negative integer")


def _require_positive_integer(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BudgetPolicyError(f"{name} must be a positive integer")


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))


def _clamp_ceil(value: float, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, ceil(value)))
