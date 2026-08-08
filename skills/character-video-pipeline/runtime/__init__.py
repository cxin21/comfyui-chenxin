"""Character video pipeline runtime - camera image generation.

Public API:
- prompt_forge_bridge.compile_envelope                        -- prompt-forge gate
- t2i_camera.run_t2i                                          -- text-to-image
- i2i_camera.run_i2i                                          -- image-to-image
- graph_patcher.patch_graph / describe_config                 -- workflow patch
- graph_patcher.NODE_FIELD_MAP                                 -- single source
- config_schema                                               -- dataclasses + constants
    RunConfig, SamplingConfig, ImageSizeConfig, GroupsConfig, CameraConfig
    STAGES, GROUPS, MANDATORY_GROUPS_BY_STAGE, WORKFLOW_CONVENTIONS
    REFERENCE_IMAGE_NODE, CONTROLNET_IMAGE_NODE, I2I_NODES
    DEFAULT_ENABLED_G1, DEFAULT_ENABLED_G2
- lora_resolver.parse_lora_inventory / filter_anima_loras /
  default_lora_plan / render_stack_text / build_lora_patch   -- LoRA discovery
- camera_mapper.map_camera / validate_camera_extra /
  CAMERA_EXTRA_FIELDS                                         -- camera coords
- group_controller.apply_group_modes / MODE_ACTIVE / MODE_BYPASS -- group control
- workflow_loader.load_workflow / load_groups / list_group_titles
- mcp_client.McpClient / McpClient.from_subprocess            -- MCP bridge
- attempt_state.record_attempt                                -- attempt log

Single entry-point rule (2026-08-07): all prompt text destined for ComfyUI
must come through prompt_forge_bridge.compile_envelope. run_t2i and run_i2i
are the only functions that produce images, and they enforce the gate as
their first step. RunConfig is the only config object they accept (no
backwards-compat kwargs).

The prompt-forge gate is strict: there is no silent fallback. If prompt-forge
rejects a draft or marks it not-ready, the run aborts loud.
"""

from .attempt_state import record_attempt
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
from .graph_patcher import NODE_FIELD_MAP, describe_config, patch_graph
from .group_controller import MODE_ACTIVE, MODE_BYPASS, apply_group_modes
from .lora_resolver import (
    build_lora_patch,
    default_lora_plan,
    filter_anima_loras,
    parse_lora_inventory,
    render_stack_text,
)
from .mcp_client import McpClient, McpClientError
from .prompt_forge_bridge import compile_envelope
from .workflow_loader import list_group_titles, load_groups, load_workflow

# Functions that produce images (the only paths to call sites in user code).
from .t2i_camera import run_t2i
from .i2i_camera import run_i2i

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
    "MODE_ACTIVE",
    "MODE_BYPASS",
    "McpClient",
    "McpClientError",
    "NODE_FIELD_MAP",
    "REFERENCE_IMAGE_NODE",
    "RunConfig",
    "STAGES",
    "SamplingConfig",
    "WORKFLOW_CONVENTIONS",
    "apply_group_modes",
    "build_lora_patch",
    "compile_envelope",
    "default_lora_plan",
    "describe_config",
    "filter_anima_loras",
    "list_group_titles",
    "load_groups",
    "load_workflow",
    "map_camera",
    "parse_lora_inventory",
    "patch_graph",
    "record_attempt",
    "render_stack_text",
    "run_i2i",
    "run_t2i",
    "validate_camera_extra",
]
