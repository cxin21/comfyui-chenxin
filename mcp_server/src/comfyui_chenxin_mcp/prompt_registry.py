"""Discovery and dispatch for model-native prompt authoring skills."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import importlib.metadata


PROMPT_ENTRY_POINT_GROUP = "comfyui_chenxin_mcp.prompt_skills"


@dataclass(frozen=True)
class PromptSkillData:
    """The small bridge contract exposed by an authoring package.

    Prompt packages own request coercion and authoring. The MCP server only
    discovers the package, exposes its description, and serializes the result.
    """

    name: str
    model: str
    stages: tuple[str, ...]
    describe_fn: Callable[[str], dict[str, Any]]
    author_fn: Callable[[str, dict[str, Any]], dict[str, Any]]


def discover_prompt_skills() -> list[PromptSkillData]:
    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        selected = eps.select(group=PROMPT_ENTRY_POINT_GROUP)
    else:
        selected = eps.get(PROMPT_ENTRY_POINT_GROUP, [])
    return [
        _normalize_prompt_skill(ep.name, ep.load()())
        for ep in selected
    ]


def _normalize_prompt_skill(entry_point_name: str, value: Any) -> PromptSkillData:
    if isinstance(value, PromptSkillData):
        return value
    if not isinstance(value, dict):
        raise TypeError(
            f"prompt skill entry point {entry_point_name!r} must return an object"
        )
    required = ("name", "model", "stages", "describe_fn", "author_fn")
    missing = [key for key in required if key not in value]
    if missing:
        raise ValueError(
            f"prompt skill entry point {entry_point_name!r} is missing: {', '.join(missing)}"
        )
    stages = tuple(value["stages"])
    if not stages or any(not isinstance(stage, str) or not stage for stage in stages):
        raise ValueError(f"prompt skill {value['name']!r} must declare non-empty stages")
    return PromptSkillData(
        name=str(value["name"]),
        model=str(value["model"]),
        stages=stages,
        describe_fn=value["describe_fn"],
        author_fn=value["author_fn"],
    )


def find_prompt_skill(skills: list[PromptSkillData], name: str) -> PromptSkillData:
    for skill in skills:
        if skill.name == name:
            return skill
    raise ValueError(
        f"unknown prompt skill: {name!r}; installed: {[skill.name for skill in skills]}"
    )
