"""stdio MCP server for ComfyUI execution and model-native prompt authoring."""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

from .engine.describe import describe_config
from .engine.execute import run_skill
from .engine.skill_data import SkillData
from .engine.validate import validate_config
from .prompt_registry import PromptSkillData, discover_prompt_skills, find_prompt_skill
from .protocol import Server
from .registry import discover_skills

DEFAULT_COMFYUI_MCP_VERSION = "0.49.8"


def _spawn_mcp():
    from .engine.mcp_client import McpClient

    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx not found on PATH")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
    version = os.environ.get("COMFYUI_MCP_VERSION", DEFAULT_COMFYUI_MCP_VERSION)
    return McpClient.from_subprocess(
        npx,
        ["-y", f"comfyui-mcp@{version}", "--full", "--comfyui-url", comfy_url],
        timeout=600.0,
        comfyui_url=comfy_url,
    )


def _find_skill(skills: list[SkillData], name: str) -> SkillData:
    for skill in skills:
        if skill.name == name:
            return skill
    raise ValueError(f"unknown skill: {name!r}; installed: {[s.name for s in skills]}")


def _find_prompt_skill(skills: list[PromptSkillData], name: str) -> PromptSkillData:
    return find_prompt_skill(skills, name)


def main() -> None:
    server = Server(name="comfyui-chenxin-mcp", version="1.0.0")
    skills = discover_skills()
    prompt_skills = discover_prompt_skills()

    @server.tool(
        name="list_skills",
        description="List installed execution and prompt-authoring skills and their stages.",
        input_schema={"type": "object", "additionalProperties": False},
    )
    async def list_tools() -> dict:
        return {
            "skills": [
                {"name": skill.name, "kind": "execution", "stages": list(skill.stages), "output_type": skill.output_type}
                for skill in skills
            ] + [
                {"name": skill.name, "kind": "authoring", "model": skill.model, "stages": list(skill.stages), "output_type": "prompt"}
                for skill in prompt_skills
            ]
        }

    @server.tool(
        name="describe_prompt",
        description=(
            "Return the request and output schema for a model-native prompt authoring stage. "
            "Use before author_prompt when the request shape is unclear."
        ),
        input_schema={
            "type": "object",
            "properties": {"skill": {"type": "string"}, "stage": {"type": "string"}},
            "required": ["skill", "stage"],
            "additionalProperties": False,
        },
    )
    async def describe_prompt(skill: str, stage: str) -> dict:
        return _find_prompt_skill(prompt_skills, skill).describe_fn(stage)

    @server.tool(
        name="author_prompt",
        description=(
            "Author a model-native prompt through an installed prompt skill. "
            "Use skill=anima-prompt-v1, stage=author for Anima positive/negative "
            "prompts, or skill=minimax-h3-prompt, stage=t2va/ref2va for MiniMax-H3. "
            "The result contains a prompt object ready for the matching camera skill."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string", "description": "Prompt skill name from list_skills."},
                "stage": {"type": "string", "description": "Stage declared by the selected prompt skill."},
                "request": {"type": "object"},
            },
            "required": ["skill", "stage", "request"],
            "additionalProperties": False,
        },
    )
    async def author_prompt(skill: str, stage: str, request: dict) -> dict:
        prompt_skill = _find_prompt_skill(prompt_skills, skill)
        if stage not in prompt_skill.stages:
            raise ValueError(
                f"unknown stage {stage!r} for prompt skill {skill!r}; "
                f"available: {prompt_skill.stages}"
            )
        return prompt_skill.author_fn(stage, request)

    @server.tool(
        name="describe_config",
        description="Return the complete schema for a skill stage.",
        input_schema={
            "type": "object",
            "properties": {"skill": {"type": "string"}, "stage": {"type": "string"}},
            "required": ["skill", "stage"],
            "additionalProperties": False,
        },
    )
    async def describe(skill: str, stage: str) -> dict:
        return describe_config(_find_skill(skills, skill), stage)

    @server.tool(
        name="validate_config",
        description=(
            "Validate a direct model-native prompt envelope and camera runtime config "
            "without spending GPU time. Use before run_skill."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "stage": {"type": "string"},
                "envelope": {"type": "object"},
                "config": {"type": "object"},
            },
            "required": ["skill", "stage", "envelope", "config"],
            "additionalProperties": False,
        },
    )
    async def validate(skill: str, stage: str, envelope: dict, config: dict) -> dict:
        return validate_config(_find_skill(skills, skill), stage, envelope, config)

    @server.tool(
        name="run_skill",
        description=(
            "Execute one ComfyUI skill stage. The caller supplies the direct prompt "
            "shape required by that camera skill. Use author_prompt first when a "
            "prompt-authoring skill is needed."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "stage": {"type": "string"},
                "envelope": {"type": "object"},
                "config": {"type": "object"},
                "output_dir": {"type": "string", "default": "outputs"},
                "timeout": {"type": "number", "default": 1800.0},
            },
            "required": ["skill", "stage", "envelope", "config"],
            "additionalProperties": False,
        },
    )
    async def run(
        skill: str,
        stage: str,
        envelope: dict,
        config: dict,
        output_dir: str = "outputs",
        timeout: float = 1800.0,
    ) -> dict:
        skill_data = _find_skill(skills, skill)
        preflight = validate_config(skill_data, stage, envelope, config)
        if not preflight.get("ok"):
            return {
                "exit_code": 1,
                "payload": {
                    "accepted": False,
                    "stage": stage,
                    "error_category": "input",
                    "error": "validate_config rejected the inputs",
                    "preflight_errors": preflight.get("errors", []),
                },
            }
        try:
            run_config = skill_data.build_config_fn(envelope, **config)
            with _spawn_mcp() as mcp:
                payload, code = run_skill(
                    mcp=mcp,
                    skill_data=skill_data,
                    stage=stage,
                    config=run_config,
                    output_dir=Path(output_dir),
                    timeout=timeout,
                )
        except (ValueError, TypeError, KeyError) as exc:
            return {"exit_code": 1, "payload": _error_payload(stage, "input", exc)}
        except Exception as exc:
            return {"exit_code": 1, "payload": _error_payload(stage, _classify_error(exc), exc)}
        if not payload.get("accepted", False):
            payload["error_category"] = _classify_error(RuntimeError(payload.get("error", "")))
        return {"exit_code": code, "payload": payload}

    asyncio.run(server.serve_stdio())


def _error_payload(stage: str, category: str, exc: BaseException) -> dict:
    return {
        "accepted": False,
        "stage": stage,
        "error_category": category,
        "error": f"{type(exc).__name__}: {exc}",
        "error_type": type(exc).__name__,
    }


def _classify_error(exc: BaseException) -> str:
    message = str(exc)
    if "prompt" in message and "rejected" in message:
        return "input"
    if any(token in message for token in ("ComfyUI", "queue not idle", "enqueue", "execution failed", "workflow")):
        return "comfyui_runtime"
    return "engine_build"


if __name__ == "__main__":
    main()
