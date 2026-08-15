"""camera-image skill data for the comfyui-chenxin-mcp engine.

Provides SkillData: field map, groups, dependency rules, stage images,
and function pointers to runtime.source_workflow.

prepare_fn (in source_workflow) is the single execution-side entry
point: it loads the UI, applies the RunConfig tunables AND the G1/G2
mode toggles, uploads the fully-patched UI to ComfyUI, and returns
the stripped API graph with every config value baked in.
"""
from __future__ import annotations

from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec  # noqa: F401  (legacy re-export shim; canonical types live in .runtime.types)
from camera_image.runtime.config_schema import GROUPS, STAGES, RunConfig
from camera_image.runtime.graph_patcher import NODE_FIELD_MAP, describe_config
from camera_image.runtime.source_workflow import prepare_temporary_workflow


def validate_envelope(envelope: dict) -> list[str]:
    if set(envelope) - {"prompt"}:
        return [f"envelope may contain only prompt, got {sorted(set(envelope))}"]
    if "prompt" not in envelope:
        return ["envelope must contain exactly prompt"]
    prompt = envelope["prompt"]
    if not isinstance(prompt, dict):
        return ["envelope.prompt must be an object"]
    if set(prompt) != {"positive", "negative"}:
        return ["envelope.prompt must contain positive and negative"]
    if any(not isinstance(value, str) for value in prompt.values()):
        return ["envelope.prompt fields must be strings"]
    return []


def get_skill_data() -> SkillData:
    return SkillData(
        name="camera-image",
        stages=(STAGES.T2I, STAGES.I2I),
        source_workflow_path="camera_image/runtime/workflow_assets/camera-anima.json",
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
            # 鍔犺浇鍥剧墖锛圙1锛?<-> reference_image (bidirectional)
            Rule(
                condition=f"group:{GROUPS.LOAD_IMAGE}",
                implies="config:reference_image",
            ),
            # 鍖哄煙鎻愮ず璇嶏紙G1锛?-> 3 images (forward)
            Rule(
                condition=f"group:{GROUPS.AREA_PROMPT}",
                implies="config:red_image",
                direction="forward",
            ),
            Rule(
                condition=f"group:{GROUPS.AREA_PROMPT}",
                implies="config:green_image",
                direction="forward",
            ),
            Rule(
                condition=f"group:{GROUPS.AREA_PROMPT}",
                implies="config:blue_image",
                direction="forward",
            ),
            # 鍖哄煙鎻愮ず璇嶏紙G1锛?-> 3 text prompts (forward)
            # 娣诲姞绛惧悕锛圙1锛?<-> signature_image (bidirectional)
            Rule(
                condition=f"group:{GROUPS.ADD_SIGNATURE}",
                implies="config:signature_image",
            ),
        ),
        stage_images={
            STAGES.T2I: (
                ImageSpec("controlnet_image", required=False, requires_group=GROUPS.CONTROLNET_LLLITE),
                ImageSpec("reference_image", required=False, requires_group=GROUPS.LOAD_IMAGE),
                ImageSpec("red_image", required=False, requires_group=GROUPS.AREA_PROMPT),
                ImageSpec("green_image", required=False, requires_group=GROUPS.AREA_PROMPT),
                ImageSpec("blue_image", required=False, requires_group=GROUPS.AREA_PROMPT),
                ImageSpec("signature_image", required=False, requires_group=GROUPS.ADD_SIGNATURE),
            ),
            STAGES.I2I: (
                ImageSpec("reference_image", required=True),
                ImageSpec("controlnet_image", required=False, requires_group=GROUPS.CONTROLNET_LLLITE),
                ImageSpec("red_image", required=False, requires_group=GROUPS.AREA_PROMPT),
                ImageSpec("green_image", required=False, requires_group=GROUPS.AREA_PROMPT),
                ImageSpec("blue_image", required=False, requires_group=GROUPS.AREA_PROMPT),
                ImageSpec("signature_image", required=False, requires_group=GROUPS.ADD_SIGNATURE),
            ),
        },
        output_type="images",
        describe_fn=describe_config,
        prepare_fn=prepare_temporary_workflow,
        build_config_fn=RunConfig.from_envelope,
        envelope_validate_fn=validate_envelope,
    )


