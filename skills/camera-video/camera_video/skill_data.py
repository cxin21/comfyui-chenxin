"""SkillData bridge for the fixed MiniMax H3 video workflows."""

from __future__ import annotations

from comfyui_chenxin_mcp.engine.skill_data import ImageSpec, SkillData

from .runtime.config_schema import STAGES, RunConfig
from .runtime.graph_patcher import describe_config
from .runtime.source_workflow import prepare_workflow


def compile_prompt_gate(config) -> dict:
    """Compile the one true camera-video prompt through MiniMax H3 rules."""
    from comfyui_chenxin_mcp.engine.prompt_forge import compile_envelope

    reference_count = sum(
        bool(getattr(config, f"reference_image_{index}", None))
        for index in range(1, 4)
    )
    return compile_envelope(
        config.evidence,
        {
            "global_prompt": config.prompt,
            "duration_seconds": config.duration,
            "reference_count": reference_count,
        },
        "minimax_h3",
    )


def validate_envelope(envelope: dict) -> list[str]:
    """Validate the video envelope boundary before config construction."""
    errors: list[str] = []
    if not isinstance(envelope.get("evidence"), dict):
        errors.append("envelope.evidence must be an object")
    if envelope.get("draft") not in (None, {}):
        errors.append("camera-video does not accept envelope.draft; use config.prompt")
    # dialect_id is auto-coerced to minimax_h3 in config_schema.from_envelope,
    # so any caller-supplied value (including wrong ones like "anima") is
    # silently accepted at this surface.
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
        dialect_id="minimax_h3",
        prompt_gate_fn=compile_prompt_gate,
        envelope_validate_fn=validate_envelope,
    )
