"""Small, deterministic helper boundary for the fixed Anima camera workflow.

The complete workflow is an install-time asset. Runtime callers read and patch
only the declared camera Config Surface, then compile that surface through the
trusted UI-to-API normalizer.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from .config_surface import build_stage_config, validate_stage_config
from .contracts import content_hash
from .stage_config_surface import (
    StageSurfaceError,
    compile_fixed_camera_api_plan,
    read_fixed_ui_stage_config,
)
from .workflow_assets import load_fixed_api_workflow, load_fixed_workflow


class CameraConfigHelperError(ValueError):
    """Raised when the fixed camera helper contract cannot be satisfied."""


_CAMERA_STAGES = frozenset(("character-base", "shot-image"))
_ASSET = "camera-anima.json"


def _profile() -> dict:
    path = Path(__file__).with_name("profiles") / "camera-anima.json"
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CameraConfigHelperError("fixed camera profile is unreadable") from exc
    if not isinstance(profile, dict) or profile.get("fixed_workflow_asset") != _ASSET:
        raise CameraConfigHelperError("fixed camera profile is not bound to camera-anima.json")
    return profile


def load_fixed_camera_bundle(stage: str = "character-base") -> dict:
    """Load the fixed UI/API pair and its profile for a camera stage."""
    if stage not in _CAMERA_STAGES:
        raise CameraConfigHelperError(f"unsupported fixed camera stage: {stage}")
    try:
        profile = _profile()
        ui_workflow = load_fixed_workflow(_ASSET)
        api_graph = load_fixed_api_workflow(_ASSET, stage=stage)
        config = read_fixed_ui_stage_config(stage, ui_workflow)
    except (StageSurfaceError, KeyError, TypeError) as exc:
        raise CameraConfigHelperError(f"fixed camera asset is invalid: {exc}") from exc
    return {
        "workflow_asset": _ASSET,
        "workflow_fingerprint": profile["workflow_fingerprint"],
        "profile": profile,
        "ui_workflow": ui_workflow,
        "api_graph": api_graph,
        "config": config,
    }


def read_fixed_camera_config(bundle: dict | None = None, *, stage: str | None = None) -> dict:
    """Return only declared config values, never sampler or other internals."""
    safe_bundle = bundle if bundle is not None else load_fixed_camera_bundle(stage)
    if not isinstance(safe_bundle, dict) or safe_bundle.get("workflow_asset") != _ASSET:
        raise CameraConfigHelperError("camera bundle is invalid")
    bundle_stage = safe_bundle.get("config", {}).get("stage")
    requested_stage = stage or bundle_stage
    if requested_stage not in _CAMERA_STAGES or bundle_stage != requested_stage:
        raise CameraConfigHelperError("camera bundle stage does not match the requested stage")
    return copy.deepcopy(safe_bundle["config"])


def build_fixed_camera_config(
    *,
    stage: str,
    prompts: dict,
    camera: dict,
    camera_extra: dict,
    groups: dict,
    lora_plan: dict,
    reference_image: str | None = None,
) -> dict:
    """Build the canonical semantic config accepted by the camera helper."""
    if stage not in _CAMERA_STAGES:
        raise CameraConfigHelperError(f"unsupported fixed camera stage: {stage}")
    try:
        plan_input = copy.deepcopy(lora_plan)
        plan_input.pop("stack_text", None)
        return build_stage_config(
            stage=stage,
            prompts=prompts,
            camera=camera,
            camera_extra=camera_extra,
            groups=groups,
            lora_plan=plan_input,
            reference_image=reference_image,
        )
    except (ValueError, TypeError) as exc:
        raise CameraConfigHelperError(f"camera config is invalid: {exc}") from exc


def compile_fixed_camera_config(
    bundle: dict,
    stage_config: dict,
    *,
    image_name: str | None = None,
    prompt_build: dict | None = None,
) -> dict:
    """Patch the declared surface and return UI/API graphs plus provenance."""
    if not isinstance(bundle, dict) or bundle.get("workflow_asset") != _ASSET:
        raise CameraConfigHelperError("camera bundle is invalid")
    safe_config = validate_stage_config(stage_config)
    stage = safe_config["stage"]
    if stage not in _CAMERA_STAGES:
        raise CameraConfigHelperError(f"unsupported fixed camera stage: {stage}")
    try:
        result = compile_fixed_camera_api_plan(
            stage,
            copy.deepcopy(bundle["api_graph"]),
            copy.deepcopy(bundle["ui_workflow"]),
            safe_config,
            copy.deepcopy(bundle["profile"]),
            image_name=image_name,
            prompt_build=prompt_build,
        )
    except (StageSurfaceError, KeyError, TypeError, ValueError) as exc:
        raise CameraConfigHelperError(f"camera config compilation failed: {exc}") from exc
    return {
        **result,
        "config_hash": safe_config["config_hash"],
        "api_graph_hash": content_hash(result["api_graph"]),
        "ui_workflow_hash": content_hash(result["ui_workflow"]),
    }







