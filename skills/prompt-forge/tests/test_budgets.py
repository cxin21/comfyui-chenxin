from __future__ import annotations

from math import ceil

import pytest

from prompt_forge.budgets import (
    BudgetPolicyError,
    plan_anima_budget,
    plan_h3_ref2va_budget,
    plan_h3_t2va_budget,
    utility_density,
)
from prompt_forge.contracts import Complexity


def complexity(
    subjects: int = 1,
    relations: int = 0,
    actions: int = 0,
    environments: int = 0,
    bridges: int = 0,
) -> Complexity:
    return Complexity(subjects, relations, actions, environments, bridges)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (complexity(0), 128),
        (complexity(1), 128),
        (complexity(2), 176),
        (complexity(1, 1, 1, 1, 1), 272),
        (complexity(20, 20, 20, 20, 20), 512),
    ],
)
def test_anima_positive_formula_and_clamps(
    value: Complexity,
    expected: int,
) -> None:
    assert plan_anima_budget(value, exclusion_groups=0).positive.target == expected


@pytest.mark.parametrize(
    ("groups", "expected"),
    [(0, 32), (1, 40), (8, 96), (100, 96)],
)
def test_anima_negative_formula_and_clamps(groups: int, expected: int) -> None:
    assert plan_anima_budget(complexity(), exclusion_groups=groups).negative.target == expected


@pytest.mark.parametrize(
    ("duration", "shots", "dialogue", "expected"),
    [
        (2.0, 1, 0, 180),
        (4.0, 2, 0, 290),
        (4.01, 2, 3, 294),
        (15.0, 5, 200, 900),
    ],
)
def test_h3_t2va_formula_and_integer_rounding(
    duration: float,
    shots: int,
    dialogue: int,
    expected: int,
) -> None:
    assert plan_h3_t2va_budget(duration, shots, dialogue).text.target == expected


@pytest.mark.parametrize(
    ("duration", "shots", "refs", "dialogue", "expected"),
    [
        (2.0, 1, 1, 0, 650),
        (4.0, 2, 2, 0, 776),
        (4.01, 2, 2, 3, 780),
        (15.0, 5, 5, 500, 1600),
    ],
)
def test_h3_ref2va_formula_and_integer_rounding(
    duration: float,
    shots: int,
    refs: int,
    dialogue: int,
    expected: int,
) -> None:
    assert plan_h3_ref2va_budget(duration, shots, refs, dialogue).text.target == expected


def test_limits_use_exact_multipliers_and_caps() -> None:
    anima = plan_anima_budget(complexity(2), exclusion_groups=1)
    assert (anima.positive.soft_limit, anima.positive.quality_limit) == (
        ceil(176 * 1.25),
        ceil(176 * 1.60),
    )
    assert (anima.negative.soft_limit, anima.negative.quality_limit) == (50, 64)

    anima_capped = plan_anima_budget(complexity(20, 20, 20, 20, 20), 100)
    assert (anima_capped.positive.soft_limit, anima_capped.positive.quality_limit) == (
        640,
        768,
    )
    assert (anima_capped.negative.soft_limit, anima_capped.negative.quality_limit) == (
        120,
        128,
    )

    t2va = plan_h3_t2va_budget(15, 5, 200).text
    assert (t2va.soft_limit, t2va.quality_limit) == (1125, 1200)
    ref2va = plan_h3_ref2va_budget(15, 5, 5, 500).text
    assert (ref2va.soft_limit, ref2va.quality_limit) == (2000, 2400)


@pytest.mark.parametrize("duration", [1.99, 15.01, float("nan"), float("inf")])
def test_h3_duration_bounds_are_strict(duration: float) -> None:
    with pytest.raises(BudgetPolicyError, match="duration_seconds"):
        plan_h3_t2va_budget(duration, 1, 0)


@pytest.mark.parametrize(
    "value",
    [
        complexity(-1),
        complexity(1, -1),
        complexity(1, 0, -1),
        complexity(1, 0, 0, -1),
        complexity(1, 0, 0, 0, -1),
    ],
)
def test_anima_rejects_negative_complexity(value: Complexity) -> None:
    with pytest.raises(BudgetPolicyError, match="non-negative"):
        plan_anima_budget(value, 0)


def test_h3_shot_density_and_integer_inputs_are_strict() -> None:
    assert plan_h3_t2va_budget(2, 1, 0).max_shots == 1
    assert plan_h3_t2va_budget(4, 2, 0).max_shots == 2
    assert plan_h3_t2va_budget(15, 5, 0).max_shots == 5
    with pytest.raises(BudgetPolicyError, match="shot_count"):
        plan_h3_t2va_budget(3, 2, 0)
    with pytest.raises(BudgetPolicyError, match="dialogue_tokens"):
        plan_h3_t2va_budget(4, 1, -1)
    with pytest.raises(BudgetPolicyError, match="reference_count"):
        plan_h3_ref2va_budget(4, 1, 0, 0)
    with pytest.raises(BudgetPolicyError):
        plan_h3_ref2va_budget(4, True, 1, 0)  # type: ignore[arg-type]


def ranges(plan: object) -> dict[str, tuple[float, float, float]]:
    fields = getattr(plan, "fields")
    return {
        field.name: (
            field.recommended_min_share,
            field.recommended_max_share,
            field.hard_max_share,
        )
        for field in fields
    }


def test_anima_field_ranges_and_borrowing_policy_are_exact() -> None:
    plan = plan_anima_budget(complexity(), 0).positive
    assert ranges(plan) == {
        "protocol_prefix": (0.06, 0.10, 0.12),
        "count": (0.04, 0.08, 0.10),
        "character": (0.15, 0.22, 0.28),
        "series": (0.03, 0.06, 0.08),
        "artist": (0.08, 0.14, 0.18),
        "appearance": (0.18, 0.24, 0.30),
        "general": (0.25, 0.35, 0.45),
        "environment": (0.10, 0.16, 0.22),
        "scene_description": (0.00, 0.18, 0.25),
    }
    assert plan.borrowing_order == (
        "series",
        "artist",
        "general",
        "environment",
        "appearance",
    )
    assert plan.non_lendable_buckets == frozenset(
        {"subject_identity", "subject_count", "user_locked_facts"}
    )

    negative = plan_anima_budget(complexity(), 0).negative
    assert ranges(negative) == {
        "quality_baseline": (0.35, 0.45, 0.45),
        "anatomy_and_structure": (0.20, 0.30, 0.30),
        "technical_defects": (0.15, 0.25, 0.25),
        "user_exclusions": (0.10, 0.20, 0.20),
    }


def test_h3_t2va_field_and_per_shot_ranges_are_exact() -> None:
    plan = plan_h3_t2va_budget(4, 2, 0).text
    assert ranges(plan) == {
        "fixed_structure_and_labels": (0.03, 0.05, 0.05),
        "integrated_multimodal_description": (0.72, 0.82, 0.82),
        "overall_soundscape": (0.08, 0.12, 0.12),
        "non_diegetic_music": (0.03, 0.08, 0.08),
        "safety_margin": (0.05, 0.05, 0.05),
    }
    assert ranges(plan.per_shot) == {
        "opening_state_and_composition": (0.20, 0.25, 0.25),
        "subject_action_and_state_change": (0.30, 0.40, 0.40),
        "camera_motion": (0.10, 0.15, 0.15),
        "synchronous_sound_and_dialogue": (0.10, 0.20, 0.20),
        "action_result_and_landing": (0.10, 0.15, 0.15),
    }


def test_h3_ref2va_field_ranges_are_exact() -> None:
    plan = plan_h3_ref2va_budget(4, 1, 1, 0).text
    assert ranges(plan) == {
        "subject_definitions": (0.12, 0.18, 0.18),
        "summary": (0.03, 0.05, 0.05),
        "retention_analysis": (0.10, 0.16, 0.16),
        "detailed_description": (0.52, 0.64, 0.64),
        "overall_soundscape": (0.05, 0.08, 0.08),
        "non_diegetic_music": (0.02, 0.05, 0.05),
        "safety_margin": (0.05, 0.05, 0.05),
    }
    assert plan.non_lendable_buckets == frozenset(
        {"subject_identity", "reference_identity", "user_locked_facts"}
    )


def test_field_token_windows_use_floor_for_minimum_and_ceil_for_maximum() -> None:
    field = plan_anima_budget(complexity(), 0).positive.field("protocol_prefix")
    assert (field.minimum_tokens, field.recommended_max_tokens, field.hard_max_tokens) == (
        7,
        13,
        16,
    )


def test_utility_density_is_exact_and_rejects_non_positive_cost() -> None:
    assert utility_density(4.0, 1.5, 0.85, 0.8, 12) == pytest.approx(0.34)
    with pytest.raises(BudgetPolicyError, match="token_cost"):
        utility_density(4, 1.5, 1, 1, 0)
    with pytest.raises(BudgetPolicyError, match="non_redundancy"):
        utility_density(4, 1.5, 1, -0.1, 10)


def test_budget_formulas_are_monotonic() -> None:
    anima_targets = [
        plan_anima_budget(complexity(subjects=count), 0).positive.target
        for count in range(8)
    ]
    t2va_targets = [plan_h3_t2va_budget(duration, 1, 0).text.target for duration in range(2, 16)]
    ref_targets = [plan_h3_ref2va_budget(4, 1, refs, 0).text.target for refs in range(1, 10)]
    assert anima_targets == sorted(anima_targets)
    assert t2va_targets == sorted(t2va_targets)
    assert ref_targets == sorted(ref_targets)
