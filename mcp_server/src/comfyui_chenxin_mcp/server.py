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


# Default upstream comfyui-mcp version. Mirrors install.ps1/install.sh and
# .mcp.json; can be overridden by the host via the COMFYUI_MCP_VERSION env var.
DEFAULT_COMFYUI_MCP_VERSION = "0.49.8"


def _spawn_mcp():
    """Spawn comfyui-mcp subprocess for ComfyUI communication."""
    from .engine.mcp_client import McpClient
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx not found on PATH")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
    version = os.environ.get("COMFYUI_MCP_VERSION", DEFAULT_COMFYUI_MCP_VERSION)
    return McpClient.from_subprocess(
        npx, ["-y", f"comfyui-mcp@{version}", "--full", "--comfyui-url", comfy_url],
        timeout=600.0,
        comfyui_url=comfy_url,
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
        description=(
            "Return the full schema (defaults, groups, enums, dependencies) for a skill stage. "
            "CALL THIS FIRST before validate_config or run_skill if any field's shape is unclear."
        ),
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
        description=(
            "Dry-run validation: same envelope + config shape as run_skill, returns "
            "{ok, errors}. Use this BEFORE run_skill to surface field errors without "
            "spending GPU time.\n"
            "Minimum working payload for camera-image / t2i-camera:\n"
            "  envelope = {\n"
            "    \"dialect_id\": \"anima\",\n"
            "    \"draft\": {\"positive\": \"1girl ...\", \"negative\": \"\"},\n"
            "    \"evidence\": {}  // optional; omit keys you don't need\n"
            "  }\n"
            "  config = {\"image_size\": [1200, 800]}"
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
        sd = _find_skill(skills, skill)
        return validate_config(sd, stage, envelope, config)

    @server.tool(
        name="run_skill",
        description=(
            "Execute one skill stage end-to-end (e.g. t2i-camera image generation). "
            "Pre-flight: validate_config is run first; on validation failure the run is "
            "aborted before any GPU time is spent and the response carries the full error list.\n"
            "On runtime failure, payload.error_category is one of:\n"
            "  prompt_forge_input   — fix envelope/draft/evidence fields\n"
            "  engine_build         — server-side bug, file an issue\n"
            "  comfyui_runtime      — ComfyUI rejected the workflow, check model/queue/connection\n"
            "  unknown              — unclassified; treat as engine_build\n"
            "Minimum working payload for camera-image / t2i-camera:\n"
            "  envelope = {\"dialect_id\": \"anima\", \"draft\": {\"positive\": \"1girl ...\", \"negative\": \"\"}, \"evidence\": {}}\n"
            "  config = {\"image_size\": [1200, 800]}\n"
            "For full schema call describe_config(skill=\"camera-image\", stage=\"t2i-camera\")."
        ),
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

        # Pre-flight: surface validation errors before any GPU work.
        preflight = validate_config(sd, stage, envelope, config)
        if not preflight.get("ok"):
            return {
                "exit_code": 1,
                "payload": {
                    "accepted": False,
                    "stage": stage,
                    "error_category": "prompt_forge_input",
                    "error": "validate_config rejected the inputs; fix errors and retry",
                    "preflight_errors": preflight.get("errors", []),
                },
            }

        try:
            run_config = sd.build_config_fn(envelope, **config)
        except (ValueError, TypeError, KeyError) as exc:
            return {
                "exit_code": 1,
                "payload": {
                    "accepted": False,
                    "stage": stage,
                    "error_category": "engine_build",
                    "error": f"{type(exc).__name__}: {exc}",
                    "error_type": type(exc).__name__,
                },
            }

        try:
            with _spawn_mcp() as mcp:
                payload, code = run_skill(
                    mcp=mcp, skill_data=sd, stage=stage, config=run_config,
                    output_dir=Path(output_dir),
                )
        except Exception as exc:
            # Defensive: if spawn_mcp itself fails, classify it.
            payload = {
                "accepted": False,
                "stage": stage,
                "error_category": _classify_error(exc),
                "error": f"{type(exc).__name__}: {exc}",
                "error_type": type(exc).__name__,
            }
            return {"exit_code": 1, "payload": payload}

        # run_skill() always returns a payload; enrich failure payloads with
        # an error_category so callers can route the fix.
        if not payload.get("accepted", False):
            inner = RuntimeError(payload.get("error", ""))
            payload["error_category"] = _classify_error(inner)
        return {"exit_code": code, "payload": payload}

    asyncio.run(server.serve_stdio())


def _classify_error(exc: BaseException) -> str:
    """Map an engine-side exception to a coarse error_category the caller can act on."""
    msg = str(exc)
    if "prompt-forge rejected" in msg:
        return "prompt_forge_input"
    if isinstance(exc, (AttributeError, KeyError, TypeError)):
        return "engine_build"
    if isinstance(exc, (RuntimeError, ValueError)):
        if any(token in msg for token in (
            "ComfyUI", "queue not idle", "enqueue", "execution failed",
            "validate_workflow", "workflow validation", "no output", "timed out",
            "workflow uses non-local runtime",
        )):
            return "comfyui_runtime"
        if isinstance(exc, ValueError):
            return "engine_build"
    return "engine_build"


if __name__ == "__main__":
    main()
