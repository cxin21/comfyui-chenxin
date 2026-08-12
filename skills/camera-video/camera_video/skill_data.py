"""SkillData bridge for the fixed MiniMax H3 video workflows."""

from __future__ import annotations

from comfyui_chenxin_mcp.engine.skill_data import ImageSpec, SkillData

from .runtime.config_schema import STAGES, RunConfig
from .runtime.assets import scene_spec
from .runtime.graph_patcher import describe_config
from .runtime.source_workflow import prepare_workflow


def compile_prompt_gate(config) -> dict:
    """Resolve the prompt before workflow use.

    If config.prompt_ref is set, fetch and verify the BuildLog
    server-side. Otherwise trust config.prompt directly.
    """
    from comfyui_chenxin_mcp.engine.prompt_forge import validate_prompt_artifact

    reference_count = sum(
        bool(getattr(config, f"reference_image_{index}", None))
        for index in range(1, 4)
    )
    if config.prompt_ref is not None:
        return validate_prompt_artifact(
            config.prompt_ref,
            expected_task="h3_ref2va" if reference_count else "h3_t2va",
            expected_reference_count=reference_count,
            expected_duration=config.duration,
        )
    # No ref id; trust the caller's prompt directly.
    return dict(config.prompt)


def validate_envelope(envelope: dict) -> list[str]:
    """Validate the video envelope boundary before config construction."""
    if set(envelope) - {"prompt", "prompt_ref"}:
        return [f"envelope may contain only prompt and prompt_ref, got {sorted(set(envelope))}"]
    if "prompt" not in envelope:
        return ["envelope must contain exactly prompt"]
    if not isinstance(envelope["prompt"], dict):
        return ["envelope.prompt must be an object"]
    if "prompt_ref" in envelope and not isinstance(envelope["prompt_ref"], str):
        return ["envelope.prompt_ref must be a string when present"]
    return []


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
