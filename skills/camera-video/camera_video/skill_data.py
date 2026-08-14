"""SkillData bridge for the fixed MiniMax H3 video workflows."""

from __future__ import annotations

from comfyui_chenxin_mcp.engine.skill_data import ImageSpec, SkillData

from .runtime.config_schema import STAGES, RunConfig
from .runtime.assets import scene_spec
from .runtime.graph_patcher import describe_config
from .runtime.source_workflow import prepare_workflow


def validate_envelope(envelope: dict) -> list[str]:
    """Validate the video envelope boundary before config construction."""
    if set(envelope) - {"prompt"}:
        return [f"envelope may contain only prompt, got {sorted(set(envelope))}"]
    if "prompt" not in envelope:
        return ["envelope must contain exactly prompt"]
    prompt = envelope["prompt"]
    if not isinstance(prompt, dict):
        return ["envelope.prompt must be an object"]
    if set(prompt) != {"text"}:
        return ["envelope.prompt must contain text"]
    if not isinstance(prompt["text"], str):
        return ["envelope.prompt.text must be a string"]
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
        envelope_validate_fn=validate_envelope,
    )


