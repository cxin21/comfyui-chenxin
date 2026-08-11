"""SkillData bridge for the fixed MiniMax H3 video workflows."""

from __future__ import annotations

from comfyui_chenxin_mcp.engine.skill_data import ImageSpec, SkillData

from .runtime.config_schema import STAGES, RunConfig
from .runtime.assets import scene_spec
from .runtime.graph_patcher import describe_config
from .runtime.source_workflow import prepare_workflow


def compile_prompt_gate(config) -> dict:
    """Lint an authored prompt against the exact local H3 task profile."""
    from comfyui_chenxin_mcp.engine.prompt_forge import forge_prompt

    reference_count = sum(
        bool(getattr(config, f"reference_image_{index}", None))
        for index in range(1, 4)
    )
    expected_profile_id = "minimax-h3.base.ref2va" if reference_count else "minimax-h3.base.t2va"
    if config.profile_id != expected_profile_id:
        raise ValueError(
            f"profile_id {config.profile_id!r} does not match {stage}: "
            f"expected {expected_profile_id!r}"
        )
    operation = "ref2va" if reference_count else "t2va"
    stage = "multi-i2v-video" if reference_count == 3 else "i2v-video" if reference_count == 1 else "t2v-video"
    return forge_prompt(
        prompt=config.prompt,
        evidence=config.evidence,
        profile_id=config.profile_id,
        operation=operation,
        duration=config.duration,
        reference_count=reference_count,
        workflow_sha256=scene_spec(stage)["sha256"],
        asset_bindings=tuple({"input_index": index} for index in range(1, reference_count + 1)),
    )


def validate_envelope(envelope: dict) -> list[str]:
    """Validate the video envelope boundary before config construction."""
    errors: list[str] = []
    if not isinstance(envelope.get("evidence"), dict):
        errors.append("envelope.evidence must be an object")
    if not isinstance(envelope.get("profile_id"), str) or not envelope["profile_id"].strip():
        errors.append("envelope.profile_id must be a non-empty string")
    if "draft" in envelope or "dialect_id" in envelope:
        errors.append("legacy prompt envelope fields are forbidden")
    return errors


def get_skill_data() -> SkillData:
    return SkillData(
        name="camera-video",
        stages=STAGES,
        source_workflow_path="camera_video/runtime/workflow_assets/manifest.json",
        groups_dir_pattern="",
        field_map={},
        dependency_rules=(),
        stage_images={
            "t2v-video": (),
            "i2v-video": (ImageSpec("reference_image_1", required=True),),
            "multi-i2v-video": (
                ImageSpec("reference_image_1", required=True),
                ImageSpec("reference_image_2", required=True),
                ImageSpec("reference_image_3", required=True),
            ),
        },
        output_type="gifs",
        artifact_mode="all",
        describe_fn=describe_config,
        prepare_fn=prepare_workflow,
        build_config_fn=RunConfig.from_envelope,
        prompt_gate_fn=compile_prompt_gate,
        envelope_validate_fn=validate_envelope,
    )
