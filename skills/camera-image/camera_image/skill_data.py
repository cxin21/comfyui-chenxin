"""camera-image skill data for the comfyui-chenxin-mcp engine.

Provides SkillData: field map, groups, dependency rules, stage images,
and function pointers to runtime.source_workflow.

prepare_fn (in source_workflow) is the single execution-side entry
point: it loads the UI, applies the RunConfig tunables AND the G1/G2
mode toggles, uploads the fully-patched UI to ComfyUI, and returns
the stripped API graph with every config value baked in.
"""
from __future__ import annotations

from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec
from camera_image.runtime.config_schema import GROUPS, STAGES, RunConfig
from camera_image.runtime.graph_patcher import NODE_FIELD_MAP, describe_config
from camera_image.runtime.source_workflow import prepare_temporary_workflow


def get_skill_data() -> SkillData:
    return SkillData(
        name="camera-image",
        stages=(STAGES.T2I, STAGES.I2I),
        source_workflow_path="workflow/source/文生图相机视角.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map=NODE_FIELD_MAP,
        dependency_rules=(
            Rule(
                condition="config:controlnet_image",
                implies=f"group:{GROUPS.CONTROLNET_LLLITE}",
            ),
            Rule(
                condition=f"stage:{STAGES.I2I}",
                implies=f"group_auto:{GROUPS.LOAD_IMAGE}",
                direction="forward",
            ),
            # 区域提示词（G1） requires 3 text prompts (one per channel).
            # Forward only — text alone does not force the group on.
            Rule(
                condition=f"group:{GROUPS.AREA_PROMPT}",
                implies="config:red_prompt",
                direction="forward",
            ),
            Rule(
                condition=f"group:{GROUPS.AREA_PROMPT}",
                implies="config:green_prompt",
                direction="forward",
            ),
            Rule(
                condition=f"group:{GROUPS.AREA_PROMPT}",
                implies="config:blue_prompt",
                direction="forward",
            ),
        ),
        stage_images={
            STAGES.T2I: (
                ImageSpec("controlnet_image", required=False, requires_group=GROUPS.CONTROLNET_LLLITE),
            ),
            STAGES.I2I: (
                ImageSpec("reference_image", required=True),
                ImageSpec("controlnet_image", required=False, requires_group=GROUPS.CONTROLNET_LLLITE),
            ),
        },
        output_type="images",
        describe_fn=describe_config,
        prepare_fn=prepare_temporary_workflow,
        build_config_fn=RunConfig.from_envelope,
        dialect_id="anima",
    )