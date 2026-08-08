"""comfyui-chenxin-mcp stdio server entrypoint.

Boots: protocol server + entry-point discovery + 4 unified tools.
No hardcoded skill names. Skills declare themselves via Python entry-points.
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

from .protocol import Server
from .registry import discover_skills
from .engine.describe import describe_config
from .engine.validate import validate_config
from .engine.execute import run_skill
from .engine.skill_data import SkillData


def _spawn_mcp():
    """Spawn comfyui-mcp subprocess for ComfyUI communication."""
    from .engine.mcp_client import McpClient
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx not found on PATH")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
    return McpClient.from_subprocess(
        npx, ["-y", "comfyui-mcp@0.49.8", "--full", "--comfyui-url", comfy_url],
        timeout=600.0,
    )


def _find_skill(skills: list[SkillData], name: str) -> SkillData:
    for sd in skills:
        if sd.name == name:
            return sd
    raise ValueError(f"unknown skill: {name!r}; installed: {[s.name for s in skills]}")


def main() -> None:
    server = Server(name="comfyui-chenxin-mcp", version="0.2.0")
    skills = discover_skills()

    @server.tool(
        name="list_skills",
        description="List installed camera skills and their stages.",
        input_schema={"type": "object", "additionalProperties": False},
    )
    async def list_tools() -> dict:
        return {
            "skills": [
                {"name": sd.name, "stages": list(sd.stages), "output_type": sd.output_type}
                for sd in skills
            ]
        }

    @server.tool(
        name="describe_config",
        description="Return the full schema (defaults, groups, enums, dependencies) for a skill stage.",
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "stage": {"type": "string"},
            },
            "required": ["skill", "stage"],
            "additionalProperties": False,
        },
    )
    async def describe(skill: str, stage: str) -> dict:
        sd = _find_skill(skills, skill)
        return describe_config(sd, stage)

    @server.tool(
        name="validate_config",
        description="Validate a config dict before running a skill.",
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "stage": {"type": "string"},
                "config": {"type": "object"},
            },
            "required": ["skill", "stage", "config"],
            "additionalProperties": False,
        },
    )
    async def validate(skill: str, stage: str, config: dict) -> dict:
        sd = _find_skill(skills, skill)
        return validate_config(sd, stage, config)

    @server.tool(
        name="run_skill",
        description="Run a skill stage (e.g. t2i-camera generation).",
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "stage": {"type": "string"},
                "envelope": {"type": "object"},
                "config": {"type": "object"},
                "output_dir": {"type": "string", "default": "outputs"},
            },
            "required": ["skill", "stage", "envelope", "config"],
            "additionalProperties": False,
        },
    )
    async def run(skill: str, stage: str, envelope: dict, config: dict,
                  output_dir: str = "outputs") -> dict:
        sd = _find_skill(skills, skill)
        run_config = sd.build_config_fn(envelope, **config)
        with _spawn_mcp() as mcp:
            payload, code = run_skill(
                mcp=mcp, skill_data=sd, stage=stage, config=run_config,
                output_dir=Path(output_dir),
            )
        return {"exit_code": code, "payload": payload}

    asyncio.run(server.serve_stdio())


if __name__ == "__main__":
    main()
