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
from .engine.prompt_forge import (
    author_anima,
    author_h3_t2va,
    author_h3_ref2va,
    validate_prompt_artifact,
)
from .engine import build_log


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


# ----- Authoring request coercion -----
# These map a plain JSON request (caller writes dict, no Python needed) to
# the typed dataclasses in prompt_forge.contracts. Field-by-field checks
# surface a clear error path so the LLM can fix the input shape on the
# first try instead of writing a build script and patching source.
from .engine.prompt_forge import (
    PROMPT_FORGE_ROOT as _PROMPT_FORGE_ROOT_FOR_CONTRACTS,
)
import importlib
import sys as _sys
if str(_PROMPT_FORGE_ROOT_FOR_CONTRACTS) not in _sys.path:
    _sys.path.insert(0, str(_PROMPT_FORGE_ROOT_FOR_CONTRACTS))
_pf_contracts = importlib.import_module("prompt_forge.contracts")


def _coerce_facts(payload: object) -> tuple:
    items = payload or ()
    if not isinstance(items, (list, tuple)):
        raise TypeError(
            f"facts must be a list, got {type(items).__name__}"
        )
    out = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise TypeError(
                f"facts[{index}] must be an object, got {type(item).__name__}"
            )
        for required in ("fact_id", "value", "origin", "owner", "dimension"):
            if required not in item:
                raise ValueError(
                    f"facts[{index}] missing required field {required!r}"
                )
        out.append(_pf_contracts.Fact(
            fact_id=str(item["fact_id"]).strip(),
            value=str(item["value"]).strip(),
            origin=item["origin"],
            locked=bool(item.get("locked", False)),
            owner=str(item["owner"]).strip(),
            dimension=str(item["dimension"]).strip(),
        ))
    return tuple(out)


def _coerce_segments(
    payload: object, field: str, default_fact_ids: tuple = ()
) -> tuple:
    items = payload or ()
    if not isinstance(items, (list, tuple)):
        raise TypeError(
            f"{field} must be a list, got {type(items).__name__}"
        )
    # Anima segment.field must be one of the canonical categories in
    # _FIELD_RANK; we default positive_segments to 'subject_anchor' so
    # LLM callers don't have to memorize the field vocabulary. Callers
    # may pass `field` explicitly to override.
    if field == "positive_segments":
        default_field = "subject_anchor"
    else:
        default_field = "general"
    out = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise TypeError(
                f"{field}[{index}] must be an object, got {type(item).__name__}"
            )
        text = str(item.get("text", "")).strip()
        if not text:
            raise ValueError(f"{field}[{index}].text must be non-empty")
        # fact_ids must be non-empty (validate_segments hard-gates this).
        # If the caller omitted it, default to the entire request fact set
        # so the segment references something auditable.
        raw_fact_ids = item.get("fact_ids")
        if raw_fact_ids is None or len(raw_fact_ids) == 0:
            fact_ids = default_fact_ids
        else:
            fact_ids = tuple(str(x) for x in raw_fact_ids)
        out.append(_pf_contracts.AuthoredSegment(
            segment_id=str(item.get("segment_id", f"{field}-{index}")).strip(),
            field=str(item.get("field", default_field)).strip(),
            text=text,
            fact_ids=fact_ids,
            # Defaults must be positive + finite (validate_weights hard-gate).
            priority=float(item.get("priority", 1.0)),
            adherence_risk=float(item.get("adherence_risk", 0.5)),
            source_confidence=float(item.get("source_confidence", 0.9)),
        ))
    return tuple(out)


def _coerce_complexity(payload: object) -> _pf_contracts.Complexity:
    if not isinstance(payload, dict):
        raise TypeError(
            f"complexity must be an object, got {type(payload).__name__}"
        )
    for required in (
        "subjects", "explicit_relations", "complex_actions",
        "environment_clusters", "natural_language_bridges",
    ):
        if required not in payload:
            raise ValueError(f"complexity missing required field {required!r}")
    return _pf_contracts.Complexity(
        subjects=int(payload["subjects"]),
        explicit_relations=int(payload["explicit_relations"]),
        complex_actions=int(payload["complex_actions"]),
        environment_clusters=int(payload["environment_clusters"]),
        natural_language_bridges=int(payload["natural_language_bridges"]),
    )


def _coerce_references(payload: object) -> tuple:
    items = payload or ()
    if not isinstance(items, (list, tuple)):
        raise TypeError(
            f"references must be a list, got {type(items).__name__}"
        )
    out = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise TypeError(
                f"references[{index}] must be an object, got {type(item).__name__}"
            )
        for required in ("reference_id", "owner", "resized_width", "resized_height"):
            if required not in item:
                raise ValueError(
                    f"references[{index}] missing required field {required!r}"
                )
        out.append(_pf_contracts.H3ReferenceImage(
            reference_id=str(item["reference_id"]).strip(),
            owner=str(item["owner"]).strip(),
            resized_width=int(item["resized_width"]),
            resized_height=int(item["resized_height"]),
        ))
    return tuple(out)


def _coerce_anima_request(payload: dict) -> _pf_contracts.AnimaAuthoringRequest:
    if not isinstance(payload, dict):
        raise TypeError(
            f"anima request must be an object, got {type(payload).__name__}"
        )
    if "facts" not in payload or "positive_segments" not in payload or "complexity" not in payload:
        raise ValueError(
            "anima request requires: facts, positive_segments, complexity"
        )
    facts = _coerce_facts(payload["facts"])
    fact_ids = tuple(fact.fact_id for fact in facts)
    return _pf_contracts.AnimaAuthoringRequest(
        facts=facts,
        positive_segments=_coerce_segments(
            payload["positive_segments"], "positive_segments", default_fact_ids=fact_ids
        ),
        complexity=_coerce_complexity(payload["complexity"]),
        negative_segments=_coerce_segments(
            payload.get("negative_segments"), "negative_segments", default_fact_ids=fact_ids
        ),
        exclusion_groups=int(payload.get("exclusion_groups", 0)),
    )


def _coerce_h3_t2va_request(payload: dict) -> _pf_contracts.H3T2VAAuthoringRequest:
    if not isinstance(payload, dict):
        raise TypeError(
            f"h3_t2va request must be an object, got {type(payload).__name__}"
        )
    for required in ("facts", "duration_seconds", "shot_count", "integrated_multimodal_description"):
        if required not in payload:
            raise ValueError(f"h3_t2va request requires: {required}")
    if not isinstance(payload["integrated_multimodal_description"], (list, tuple)):
        raise TypeError(
            "integrated_multimodal_description must be a list of segment objects"
        )
    facts = _coerce_facts(payload["facts"])
    fact_ids = tuple(fact.fact_id for fact in facts)
    return _pf_contracts.H3T2VAAuthoringRequest(
        facts=facts,
        duration_seconds=float(payload["duration_seconds"]),
        shot_count=int(payload["shot_count"]),
        integrated_multimodal_description=_coerce_segments(
            payload["integrated_multimodal_description"],
            "integrated_multimodal_description",
            default_fact_ids=fact_ids,
        ),
        overall_soundscape=_coerce_segments(
            payload.get("overall_soundscape", []), "overall_soundscape", default_fact_ids=fact_ids
        ),
        non_diegetic_music=_coerce_segments(
            payload.get("non_diegetic_music", []), "non_diegetic_music", default_fact_ids=fact_ids
        ),
    )


def _coerce_h3_ref2va_request(payload: dict) -> _pf_contracts.H3Ref2VAAuthoringRequest:
    if not isinstance(payload, dict):
        raise TypeError(
            f"h3_ref2va request must be an object, got {type(payload).__name__}"
        )
    for required in (
        "facts", "duration_seconds", "shot_count", "references",
        "subject_definitions", "summary", "retention_analysis",
        "detailed_description",
    ):
        if required not in payload:
            raise ValueError(f"h3_ref2va request requires: {required}")
    for field in ("subject_definitions", "summary", "retention_analysis", "detailed_description"):
        if not isinstance(payload[field], (list, tuple)):
            raise TypeError(
                f"{field} must be a list of segment objects"
            )
    facts = _coerce_facts(payload["facts"])
    fact_ids = tuple(fact.fact_id for fact in facts)
    return _pf_contracts.H3Ref2VAAuthoringRequest(
        facts=facts,
        duration_seconds=float(payload["duration_seconds"]),
        shot_count=int(payload["shot_count"]),
        references=_coerce_references(payload["references"]),
        subject_definitions=_coerce_segments(
            payload["subject_definitions"], "subject_definitions", default_fact_ids=fact_ids
        ),
        summary=_coerce_segments(payload["summary"], "summary", default_fact_ids=fact_ids),
        retention_analysis=_coerce_segments(
            payload["retention_analysis"], "retention_analysis", default_fact_ids=fact_ids
        ),
        detailed_description=_coerce_segments(
            payload["detailed_description"], "detailed_description", default_fact_ids=fact_ids
        ),
        overall_soundscape=_coerce_segments(
            payload.get("overall_soundscape", []), "overall_soundscape", default_fact_ids=fact_ids
        ),
        non_diegetic_music=_coerce_segments(
            payload.get("non_diegetic_music", []), "non_diegetic_music", default_fact_ids=fact_ids
        ),
    )


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

    # ----- Authoring tools: build a verified PromptArtifact -----
    # These close the gap surfaced in session 5ba39012: callers had no
    # way to produce the prompt camera-* consumes without writing a
    # Python build script. Each tool coerces a plain JSON request into
    # the matching typed dataclass and runs author_*(). The full audit
    # trail is stored server-side in the BuildLog registry; the tool
    # returns a slim {ref_id, prompt, metadata} dict. The caller carries
    # the 32-char ref_id (or the prompt dict) and passes it back via
    # envelope={"prompt": <dict>, "prompt_ref": <ref_id>} to run_skill.

    @server.tool(
        name="compile_anima_artifact",
        description=(
            "Build a verified Anima prompt and register its BuildLog.\n"
            "Use when the goal is an Anima still image and the caller can "
            "express it as a list of locked facts + positive/negative "
            "AuthoredSegments + Complexity (subjects / explicit_relations / "
            "complex_actions / environment_clusters / natural_language_bridges).\n"
            "Returns {ref_id, prompt, metadata}. Pass ref_id (and/or the "
            "prompt dict) back to camera-image via envelope={\"prompt\": ..., "
            "\"prompt_ref\": ...}."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "request": {
                    "type": "object",
                    "description": (
                        "AnimaAuthoringRequest fields: facts (list[Fact]), "
                        "positive_segments (list[AuthoredSegment]), complexity "
                        "(Complexity), negative_segments (list[AuthoredSegment], "
                        "optional), exclusion_groups (int, optional, default 0)."
                    ),
                },
            },
            "required": ["request"],
            "additionalProperties": False,
        },
    )
    async def compile_anima(request: dict) -> dict:
        req = _coerce_anima_request(request)
        slim = author_anima(req)  # returns {ref_id, prompt}
        meta = build_log.metadata(slim["ref_id"]) or {}
        return {
            "ref_id": slim["ref_id"],
            "prompt": slim["prompt"],
            "metadata": meta,
        }

    @server.tool(
        name="compile_h3_t2va_artifact",
        description=(
            "Build a verified MiniMax-H3 text-to-video-with-audio prompt.\n"
            "Use for camera-video t2v-video stages (no reference images). "
            "Caller supplies facts + duration_seconds + shot_count + a single "
            "integrated_multimodal_description (with [Shot 1]...[Shot N] "
            "markers and At MM:SS.mmm cut timestamps) + optional "
            "overall_soundscape + non_diegetic_music. Returns "
            "{ref_id, prompt, metadata}."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "request": {
                    "type": "object",
                    "description": (
                        "H3T2VAAuthoringRequest fields: facts, duration_seconds, "
                        "shot_count, integrated_multimodal_description, "
                        "overall_soundscape (optional), non_diegetic_music (optional)."
                    ),
                },
            },
            "required": ["request"],
            "additionalProperties": False,
        },
    )
    async def compile_h3_t2va(request: dict) -> dict:
        req = _coerce_h3_t2va_request(request)
        slim = author_h3_t2va(req)
        meta = build_log.metadata(slim["ref_id"]) or {}
        return {
            "ref_id": slim["ref_id"],
            "prompt": slim["prompt"],
            "metadata": meta,
        }

    @server.tool(
        name="compile_h3_ref2va_artifact",
        description=(
            "Build a verified MiniMax-H3 reference-to-video-with-audio prompt.\n"
            "Use for camera-video i2v-video / multi-i2v-video stages (one or "
            "three reference images). Caller supplies facts + duration_seconds + "
            "shot_count + references (list of {reference_id: 'Picture N', owner, "
            "resized_width, resized_height}) + subject_definitions + summary + "
            "retention_analysis + detailed_description + optional soundscape/music. "
            "All 'Picture N' labels in the text must resolve to ordered references. "
            "Returns {ref_id, prompt, metadata}."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "request": {
                    "type": "object",
                    "description": (
                        "H3Ref2VAAuthoringRequest fields: facts, duration_seconds, "
                        "shot_count, references, subject_definitions, summary, "
                        "retention_analysis, detailed_description, "
                        "overall_soundscape (optional), non_diegetic_music (optional)."
                    ),
                },
            },
            "required": ["request"],
            "additionalProperties": False,
        },
    )
    async def compile_h3_ref2va(request: dict) -> dict:
        req = _coerce_h3_ref2va_request(request)
        slim = author_h3_ref2va(req)
        meta = build_log.metadata(slim["ref_id"]) or {}
        return {
            "ref_id": slim["ref_id"],
            "prompt": slim["prompt"],
            "metadata": meta,
        }
    async def list_tools() -> dict:
        return {
            "skills": [
                {"name": sd.name, "stages": list(sd.stages), "output_type": sd.output_type}
                for sd in skills
            ]
        }

    @server.tool(
        name="get_build_audit",
        description=(
            "Return the full server-side BuildLog (audit trail) for a "
            "compile_*_artifact call by ref id. Includes facts, trace, "
            "token_report, audit, compression, conflict, and sha256. "
            "Use only when the caller needs to inspect the build process; "
            "for runtime execution the prompt ref id is enough."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "ref_id": {
                    "type": "string",
                    "description": "The 32-character ref id returned by a compile_*_artifact call.",
                },
            },
            "required": ["ref_id"],
            "additionalProperties": False,
        },
    )
    async def get_build_audit(ref_id: str) -> dict:
        log = build_log.get(ref_id)
        if log is None:
            raise ValueError(f"unknown BuildLog ref_id: {ref_id!r}")
        return log

    @server.tool(
        name="get_build_metadata",
        description=(
            "Return a small summary of a BuildLog (ref id, task, status, "
            "sha256 prefix, token count, fact count, compression count, "
            "has_conflict). Use this to decide whether a stored build is "
            "production_ready without paying the cost of the full audit log."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "ref_id": {
                    "type": "string",
                    "description": "The 32-character ref id returned by a compile_*_artifact call.",
                },
            },
            "required": ["ref_id"],
            "additionalProperties": False,
        },
    )
    async def get_build_metadata(ref_id: str) -> dict:
        meta = build_log.metadata(ref_id)
        if meta is None:
            raise ValueError(f"unknown BuildLog ref_id: {ref_id!r}")
        return meta

    @server.tool(
        name="delete_prompt_artifact",
        description=(
            "Remove a BuildLog from the server-side registry. Use to free "
            "memory when a build is no longer needed. Returns true if "
            "the ref was present, false otherwise."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "ref_id": {
                    "type": "string",
                    "description": "The 32-character ref id returned by a compile_*_artifact call.",
                },
            },
            "required": ["ref_id"],
            "additionalProperties": False,
        },
    )
    async def delete_prompt_artifact(ref_id: str) -> dict:
        return {"deleted": build_log.delete(ref_id)}

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
            "For camera-image and camera-video, the envelope carries the model-native prompt:\n"
            "  envelope = {\"prompt\": <prompt dict from compile_*_artifact>}\n"
            "  e.g. for anima: envelope = {\"prompt\": {\"positive\": \"...\", \"negative\": \"...\"}}\n"
            "  e.g. for h3_t2va / h3_ref2va: envelope = {\"prompt\": {\"text\": \"...\"}}\n"
            "For camera-multiview, envelope = {}.\n"
            "  config = {\"image_size\": {\"width\": 1200, \"height\": 800}}\n"
            "FORBIDDEN in both envelope and config (these belong to the camera skill, not here):\n"
            "  workflow, node, hash, gpu, execution, mode, runtime, profile, camera,\n"
            "  lens, lora, loras, checkpoint, sampler, seed, steps, cfg, denoise."
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
            "  prompt_forge_input   — fix the prompt_artifact input\n"
            "  engine_build         — server-side bug, file an issue\n"
            "  comfyui_runtime      — ComfyUI rejected the workflow, check model/queue/connection\n"
            "  unknown              — unclassified; treat as engine_build\n"
            "For camera-image/video, envelope = {\"prompt\": <prompt dict from compile_*_artifact>}.\n"
            "For camera-multiview, envelope = {} because its fixed graph has no prompt input.\n"
            "For camera-image, config may contain image_size and runtime tunables.\n"
            "For full schema call describe_config(skill=\"camera-image\", stage=\"t2i-camera\").\n"
            "For camera-video (t2v / i2v / multi-i2v) stages:\n"
            "  envelope = {\"prompt\": {\"text\": \"<the H3 production prompt>\"}}\n"
            "  config = {\"duration\": 8.0, \"reference_image_1\": \"/path/to/img.png\"}\n"
            "  CRITICAL: `duration` is a JSON number (8.0), NOT a string (\"8.0\").\n"
            "FORBIDDEN in both envelope and config (these belong to the camera skill, not here):\n"
            "  workflow, node, hash, gpu, execution, mode, runtime, profile, camera,\n"
            "  lens, lora, loras, checkpoint, sampler, seed, steps, cfg, denoise."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "stage": {"type": "string"},
                "envelope": {"type": "object"},
                "config": {"type": "object"},
                "output_dir": {"type": "string", "default": "outputs"},
                "timeout": {"type": "number", "description": "Polling timeout in seconds for ComfyUI history; default 1800 covers MiniMax H3 i2v-video (~12 min)"},
            },
            "required": ["skill", "stage", "envelope", "config"],
            "additionalProperties": False,
        },
    )
    async def run(skill: str, stage: str, envelope: dict, config: dict,
                  output_dir: str = "outputs", timeout: float = 1800.0) -> dict:
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
                    output_dir=Path(output_dir), timeout=timeout,
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
