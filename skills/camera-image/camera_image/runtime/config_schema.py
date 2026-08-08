"""Configuration schema for character-video-pipeline runs.

Single source of truth for what callers can tune. All fields are optional
(unless marked required); missing fields fall through to workflow.json
static values at patch time.

Mandatory inputs are:
  * RunConfig.draft (must contain keys "positive" and "negative")
  * RunConfig.evidence (CreativeEvidence ledger)
Prompt text MUST pass through the prompt-forge gate before reaching here.

Stage-specific mandatory inputs:
  * RunConfig.reference_image (i2i-camera)
  * RunConfig.controlnet_image (when "ControlNet LLLite（G1）" group enabled)

The schema is node-grouped (sampling spans nodes 50/51, image_size spans
nodes 68/71) so the CLI helper output and the patcher's NODE_FIELD_MAP
can both read a single semantic surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CameraConfig:
    """Maps to node 583 (CameraAngleNode).

    None values mean "use workflow.json static value".
    """
    direction: str | None = None
    elevation: str | None = None
    distance: str | None = None
    roll: float | None = None


@dataclass(frozen=True)
class SamplingConfig:
    """Maps to node 50 (Input Parameters) + node 51 (refine KSampler).

    Two physical KSamplers in workflow.json; we keep their fields distinct
    so callers can tune first-pass and refine independently. None fields
    fall through to static values (40 / 4 / dpmpp_2m / karras / 1.0 / 25 / 0.2).
    """
    steps_first: int | None = None
    cfg: float | None = None
    sampler: str | None = None
    scheduler: str | None = None
    denoise_first: float | None = None
    steps_refine: int | None = None
    denoise_refine: float | None = None


@dataclass(frozen=True)
class ImageSizeConfig:
    """Maps to node 68 (easy int) value + node 71 (easy int) value.

    Workflow.json feeds these ints into EmptyLatentImage (node 86).
    Default static values: 1216 × 832.
    """
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class GroupsConfig:
    """G1/G2 group toggles by title.

    i2i-camera stage: "加载图片（G1）" is auto-appended by patch_graph
    (caller does not pass it). Default workflow.json values for the
    core render path are kept inside patch_graph (DEFAULT_ENABLED_G1/G2)
    and merged with the user's choices.
    """
    g1: list[str] | None = None
    g2: list[str] | None = None


@dataclass(frozen=True)
class RunConfig:
    """Top-level config for patch_graph + run_t2i / run_i2i.

    Mandatory: evidence (dict) + draft (dict, must contain "positive" and "negative").
    All other fields are optional — fall through to workflow.json defaults when None.
    """
    # prompt-forge gate (always required)
    evidence: dict
    draft: dict
    dialect_id: str = "anima"
    # existing tunables
    camera: CameraConfig | None = None
    camera_extra: dict | None = None
    lora: dict | None = None   # supported keys: {"selections": [short,...]}
    groups: GroupsConfig | None = None
    # new tunables
    sampling: SamplingConfig | None = None
    seed: int | None = None
    image_size: ImageSizeConfig | None = None
    # stage-specific
    reference_image: str | None = None   # i2i only: local path (run_i2i uploads via mcp.upload_image)
    controlnet_image: str | None = None # t2i and i2i: local path (run_t2i/run_i2i uploads via mcp.upload_image)
    # region prompts (区域提示词 G1): per-channel text written to nodes 3/4/5.
    # Required (validated by Rule) when 区域提示词（G1） group is enabled.
    red_prompt: str | None = None
    green_prompt: str | None = None
    blue_prompt: str | None = None

    @classmethod
    def from_envelope(cls, envelope: dict, **tunables) -> "RunConfig":
        """Build RunConfig from an envelope dict + tunable kwargs.

        envelope must contain: evidence (dict), draft (dict).
        Optional envelope key: dialect_id (str, default "anima").
        tunables: camera (dict), camera_extra (dict), lora (dict),
                  groups (dict), sampling (dict), seed (int),
                  image_size (dict), reference_image (str), controlnet_image (str),
                  red_prompt (str), green_prompt (str), blue_prompt (str).
        """
        camera = tunables.get("camera")
        if isinstance(camera, dict):
            camera = CameraConfig(**camera)
        sampling = tunables.get("sampling")
        if isinstance(sampling, dict):
            sampling = SamplingConfig(**sampling)
        image_size = tunables.get("image_size")
        if isinstance(image_size, dict):
            image_size = ImageSizeConfig(**image_size)
        groups = tunables.get("groups")
        if isinstance(groups, dict):
            groups = GroupsConfig(**groups)
        return cls(
            evidence=envelope.get("evidence", {}),
            draft=envelope.get("draft", {}),
            dialect_id=envelope.get("dialect_id", "anima"),
            camera=camera,
            camera_extra=tunables.get("camera_extra"),
            lora=tunables.get("lora"),
            groups=groups,
            sampling=sampling,
            seed=tunables.get("seed"),
            image_size=image_size,
            reference_image=tunables.get("reference_image"),
            controlnet_image=tunables.get("controlnet_image"),
            red_prompt=tunables.get("red_prompt"),
            green_prompt=tunables.get("green_prompt"),
            blue_prompt=tunables.get("blue_prompt"),
        )


class STAGES:
    T2I = "t2i-camera"
    I2I = "i2i-camera"


@dataclass(frozen=True)
class GroupTitle:
    LOAD_IMAGE: str = "加载图片（G1）"
    CONTROLNET_LLLITE: str = "ControlNet LLLite（G1）"
    AREA_PROMPT: str = "区域提示词（G1）"


GROUPS = GroupTitle()

MANDATORY_GROUPS_BY_STAGE: dict[str, list[str]] = {
    STAGES.I2I: [GROUPS.LOAD_IMAGE],
}

WORKFLOW_CONVENTIONS: dict[str, dict] = {
    STAGES.I2I: {"denoise_override": {"27": 0.6}},
}

REFERENCE_IMAGE_NODE: dict[str, str] = {STAGES.I2I: "21"}
CONTROLNET_IMAGE_NODE: dict[str, str] = {STAGES.T2I: "129", STAGES.I2I: "129"}

# Core-render-path groups that MUST always be active for any working render.
# Patcher merges these with the user's RunConfig.groups.g1/g2 (user-provided
# groups are added on top — they can enable MORE, never disable these).
DEFAULT_ENABLED_G1: list[str] = [
    "保存图片（G1）",          # node 35 Image Saver
    "第二轮采样器（G1）",      # node 51 KSampler (refine)
    "相机视角生图（G1）",      # nodes 583 CameraAngleNode + 585 CameraExtraConfigNode
]
DEFAULT_ENABLED_G2: list[str] = [
    "图像锐化（G2）",          # node 111 ImageSharpen
    "对比度（G2）",            # node 96  AdjustContrast
]

# i2i nodes — single source for the latent-rewire step (was hardcoded in
# _activate_img2img). Node ids: 21 LoadImage, 57/58/59 VAEEncode chain,
# 86 EmptyLatentImage (t2i source),
# 27 KSampler (first-pass; latent_image is rewired between 86 and 59).
@dataclass(frozen=True)
class I2INodes:
    LOAD_IMAGE: str = "21"
    VAE_ENCODE: str = "59"
    EMPTY_LATENT: str = "86"
    KSAMPLER: str = "27"
    LOAD_IMAGE_CHAIN: tuple[str, ...] = ("21", "57", "58", "59")


I2I_NODES = I2INodes()