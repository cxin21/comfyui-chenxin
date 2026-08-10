"""SkillData bridge for the fixed Flux2-Klein multiview workflow."""

from __future__ import annotations

from comfyui_chenxin_mcp.engine.skill_data import ImageSpec, SkillData

from .runtime.config_schema import RunConfig, STAGE
from .runtime.graph_patcher import describe_config
from .runtime.source_workflow import prepare_workflow


def get_skill_data() -> SkillData:
    return SkillData(
        name="camera-multiview",
        stages=(STAGE,),
        source_workflow_path=(
            "camera_multiview/runtime/workflow_assets/"
            "Flux2-Klein人物一键多视图工作流.json"
        ),
        groups_dir_pattern="",
        field_map={
            "full_body_image": (111, "image"),
            "face_image": (667, "image"),
        },
        dependency_rules=(),
        stage_images={
            STAGE: (
                ImageSpec("full_body_image", required=True),
                ImageSpec("face_image", required=True),
            )
        },
        output_type="images",
        artifact_mode="all",
        describe_fn=describe_config,
        prepare_fn=prepare_workflow,
        build_config_fn=RunConfig.from_envelope,
        dialect_id="anima",
    )
