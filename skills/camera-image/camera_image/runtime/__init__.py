"""Character video pipeline runtime - camera image generation.

Public API:
- source_workflow.prepare_temporary_workflow                  -- source UI -> API strip
- graph_patcher.apply_run_config / describe_config            -- tunables
- graph_patcher.NODE_FIELD_MAP                                -- single source
- config_schema                                               -- dataclasses + constants
    RunConfig, SamplingConfig, ImageSizeConfig, GroupsConfig, CameraConfig
    STAGES, GROUPS, MANDATORY_GROUPS_BY_STAGE, WORKFLOW_CONVENTIONS
    REFERENCE_IMAGE_NODE, CONTROLNET_IMAGE_NODE, I2I_NODES
    DEFAULT_ENABLED_G1, DEFAULT_ENABLED_G2
- lora_resolver.parse_lora_inventory / filter_anima_loras /
  default_lora_plan / render_stack_text / build_lora_patch   -- LoRA discovery
- camera_mapper.map_camera / validate_camera_extra /
  CAMERA_EXTRA_FIELDS                                         -- camera coords

Single entry-point rule (2026-08-07): all prompt text destined for ComfyUI
must come through the engine's prompt_forge.compile_envelope. Execution is
handled via the MCP server tools: list_skills, describe_config, validate_config,
and run_skill. RunConfig is the only config object accepted (no
backwards-compat kwargs).

The prompt-forge gate is strict: there is no silent fallback. If prompt-forge
rejects a draft or marks it not-ready, the run aborts loud.

Workflow assembly (2026-08-08): the source UI workflow at
``camera_image/runtime/workflow_assets/camera-anima.json`` is the single
source of truth. Every run strips a fresh copy via MCP after applying
G1/G2 mode changes.
"""

from .camera_mapper import CAMERA_EXTRA_FIELDS, map_camera, validate_camera_extra
from .config_schema import (
    DEFAULT_ENABLED_G1,
    DEFAULT_ENABLED_G2,
    GROUPS,
    I2I_NODES,
    MANDATORY_GROUPS_BY_STAGE,
    REFERENCE_IMAGE_NODE,
    CONTROLNET_IMAGE_NODE,
    STAGES,
    WORKFLOW_CONVENTIONS,
    CameraConfig,
    GroupsConfig,
    ImageSizeConfig,
    RunConfig,
    SamplingConfig,
)
from .graph_patcher import NODE_FIELD_MAP, apply_run_config, describe_config
from .lora_resolver import (
    build_lora_patch,
    default_lora_plan,
    filter_anima_loras,
    parse_lora_inventory,
    render_stack_text,
)
from .source_workflow import (
    SOURCE_WORKFLOW_PATH,
    compute_enabled_groups,
    prepare_temporary_workflow,
)

__all__ = [
    "CAMERA_EXTRA_FIELDS",
    "CONTROLNET_IMAGE_NODE",
    "CameraConfig",
    "DEFAULT_ENABLED_G1",
    "DEFAULT_ENABLED_G2",
    "GROUPS",
    "GroupsConfig",
    "I2I_NODES",
    "ImageSizeConfig",
    "MANDATORY_GROUPS_BY_STAGE",
    "NODE_FIELD_MAP",
    "REFERENCE_IMAGE_NODE",
    "RunConfig",
    "SOURCE_WORKFLOW_PATH",
    "STAGES",
    "SamplingConfig",
    "WORKFLOW_CONVENTIONS",
    "apply_run_config",
    "build_lora_patch",
    "compute_enabled_groups",
    "default_lora_plan",
    "describe_config",
    "filter_anima_loras",
    "map_camera",
    "parse_lora_inventory",
    "prepare_temporary_workflow",
    "render_stack_text",
    "validate_camera_extra",
]