"""Schema dispatch - calls the skill's own describe_fn."""
from __future__ import annotations

from .skill_data import SkillData


def describe_config(skill_data: SkillData, stage: str) -> dict:
    """Dispatch to the skill's describe_fn. Validates stage first.

    Returns whatever the skill's describe_fn returns (typically
    {stage, slots, groups, ...}).
    """
    if stage not in skill_data.stages:
        raise ValueError(
            f"unknown stage {stage!r} for skill {skill_data.name!r}; "
            f"available: {skill_data.stages}"
        )
    return skill_data.describe_fn(stage)