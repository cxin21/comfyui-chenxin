"""MCP entry-point for camera-image skill.

Binds t2i-camera / i2i-camera tools onto the comfyui-chenxin-mcp server.
Discovered via setuptools entry-points; no changes needed in
comfyui-chenxin-mcp when this skill is added/removed.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from camera_image.runtime.config_schema import RunConfig
from camera_image.runtime.graph_patcher import describe_config
from camera_image.runtime.lora_resolver import (
    default_lora_plan,
    filter_anima_loras,
    parse_lora_inventory,
    render_stack_text,
)
from camera_image.runtime.mcp_client import McpClient
from comfyui_chenxin_mcp.protocol import Server
from comfyui_chenxin_mcp.registry import SkillRegistration


def _spawn_mcp() -> McpClient:
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx not found on PATH; install Node.js or set CHENXIN_MCP_CMD/ARGS")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
    return McpClient.from_subprocess(
        npx, ["-y", "comfyui-mcp@0.49.8", "--full", "--comfyui-url", comfy_url],
        timeout=600.0,
    )


def validate_config(skill: str, stage: str, config: dict[str, Any]) -> dict[str, Any]:
    """Validate a RunConfig dict before run_t2i_camera / run_i2i_camera.

    The runtime's graph_patcher exposes ``describe_config`` for shape
    introspection but does not yet ship a ``validate_config`` callable. The
    MCP layer therefore implements a thin local validator that checks
    prompt-forge gate presence and stage-specific reference_image
    requirements. Richer validation lands with the runtime tools in Task 4.
    """
    if not isinstance(config, dict):
        return {"ok": False, "stage": stage, "skill": skill, "error": "config must be an object"}
    errors: list[str] = []
    draft = config.get("draft")
    if not isinstance(draft, dict):
        errors.append("config.draft must be an object (prompt-forge envelope)")
    else:
        for key in ("positive", "negative"):
            if not isinstance(draft.get(key), str) or not draft[key].strip():
                errors.append(f"config.draft.{key} must be a non-empty string")
    if stage == "i2i-camera" and not config.get("reference_image"):
        errors.append("config.reference_image is required for i2i-camera")
    if errors:
        return {"ok": False, "stage": stage, "skill": skill, "errors": errors}
    return {"ok": True, "stage": stage, "skill": skill}


def register(mcp: Server) -> None:
    @mcp.tool(
        name="describe_camera_config",
        description="Return the full schema (defaults, groups, enums) for a camera stage.",
        input_schema={
            "type": "object",
            "properties": {"stage": {"type": "string", "enum": ["t2i-camera", "i2i-camera"]}},
            "additionalProperties": False,
        },
    )
    async def describe(stage: str = "t2i-camera") -> dict:
        return describe_config(stage)

    @mcp.tool(
        name="validate_camera_config",
        description="Validate a RunConfig dict before run_t2i_camera / run_i2i_camera.",
        input_schema={
            "type": "object",
            "properties": {
                "stage": {"type": "string", "enum": ["t2i-camera", "i2i-camera"]},
                "config": {"type": "object"},
            },
            "required": ["stage", "config"],
            "additionalProperties": False,
        },
    )
    async def validate(stage: str, config: dict) -> dict:
        return validate_config("camera-image", stage, config)

    @mcp.tool(
        name="list_camera_loras",
        description="List available Anima LoRA short names.",
        input_schema={"type": "object", "additionalProperties": False},
    )
    async def list_loras() -> dict:
        with _spawn_mcp() as mcp:
            inventory = parse_lora_inventory(mcp.list_loras())
        anima = filter_anima_loras(inventory)
        return {
            "anima_loras": anima,
            "default_stack_text": render_stack_text(default_lora_plan()),
        }

    @mcp.tool(
        name="run_t2i_camera",
        description="Run t2i-camera generation.",
        input_schema={
            "type": "object",
            "properties": {
                "envelope": {"type": "object"},
                "stage": {"type": "string", "enum": ["t2i-camera"]},
                "camera": {"type": "object"},
                "camera_extra": {"type": "object"},
                "lora": {"type": "object"},
                "groups": {"type": "object"},
                "sampling": {"type": "object"},
                "seed": {"type": "integer"},
                "image_size": {"type": "object"},
                "controlnet_image": {"type": "string"},
                "output_dir": {"type": "string", "default": "outputs"},
            },
            "required": ["envelope"],
            "additionalProperties": False,
        },
    )
    async def run_t2i_tool(envelope: dict, stage: str = "t2i-camera", **kwargs) -> dict:
        from camera_image.runtime.runtime_cli import _kwargs_to_run_config

        cli_args = {"envelope_json": json.dumps(envelope, ensure_ascii=False)}
        for k, v in kwargs.items():
            if k == "output_dir":
                continue
            cli_args[k] = v
        config = _kwargs_to_run_config(**cli_args)
        from camera_image.runtime.t2i_camera import run_t2i

        with _spawn_mcp() as mcp:
            payload, code = run_t2i(
                mcp=mcp,
                output_dir=Path(kwargs.get("output_dir", "outputs")),
                config=config,
                timeout=600.0,
            )
        return {"exit_code": code, "payload": payload}

    @mcp.tool(
        name="run_i2i_camera",
        description="Run i2i-camera generation.",
        input_schema={
            "type": "object",
            "properties": {
                "envelope": {"type": "object"},
                "reference": {"type": "string"},
                "stage": {"type": "string", "enum": ["i2i-camera"]},
                "camera": {"type": "object"},
                "lora": {"type": "object"},
                "groups": {"type": "object"},
                "sampling": {"type": "object"},
                "seed": {"type": "integer"},
                "image_size": {"type": "object"},
                "controlnet_image": {"type": "string"},
                "output_dir": {"type": "string", "default": "outputs"},
            },
            "required": ["envelope", "reference"],
            "additionalProperties": False,
        },
    )
    async def run_i2i_tool(envelope: dict, reference: str, stage: str = "i2i-camera", **kwargs) -> dict:
        from camera_image.runtime.runtime_cli import _kwargs_to_run_config

        cli_args = {"envelope_json": json.dumps(envelope, ensure_ascii=False), "reference": reference}
        for k, v in kwargs.items():
            if k == "output_dir":
                continue
            cli_args[k] = v
        config = _kwargs_to_run_config(**cli_args)
        from camera_image.runtime.i2i_camera import run_i2i

        with _spawn_mcp() as mcp:
            payload, code = run_i2i(
                mcp=mcp,
                output_dir=Path(kwargs.get("output_dir", "outputs")),
                config=config,
                timeout=600.0,
            )
        return {"exit_code": code, "payload": payload}


SKILL_INFO = SkillRegistration(
    name="camera-image",
    label="Camera Image (Anima t2i/i2i)",
    description="Anima camera workflow: t2i-camera and i2i-camera. Prompt-forge gate is mandatory; all tunables flow through RunConfig.",
    stages=("t2i-camera", "i2i-camera"),
    register_fn=register,
)

# Attach the metadata to the entry-point callable so registry.discover()
# can look it up via ``getattr(register_fn, "SKILL_INFO", None)``.
register.SKILL_INFO = SKILL_INFO