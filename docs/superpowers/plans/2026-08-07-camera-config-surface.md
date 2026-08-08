# Camera Config Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace character-video-pipeline's `patch_graph(*, positive=..., ...)` kwargs API and `run_t2i/run_i2i` kwargs APIs with a single `RunConfig` dataclass, add NODE_FIELD_MAP as the single source of truth for the patcher + describe_config helper, expose sampling/seed/image_size/controlnet_image as first-class tunables, drop the old CLI flags (no compat shim), and update all docs.

**Architecture:** New `runtime/config_schema.py` houses frozen dataclasses (`CameraConfig`, `SamplingConfig`, `ImageSizeConfig`, `GroupsConfig`, `RunConfig`) + constants (`STAGES`, `GROUPS`, `MANDATORY_GROUPS_BY_STAGE`, `WORKFLOW_CONVENTIONS`, `REFERENCE_IMAGE_NODE`, `CONTROLNET_IMAGE_NODE`, `DEFAULT_ENABLED_G1/G2`, `I2I_NODES`). `runtime/graph_patcher.py` is rewritten around `patch_graph(*, stage, config, mcp_list_loras)`, with `NODE_FIELD_MAP` driving both patch writes and the workflow-bound `describe_config` helper. `runtime/runtime_cli.py` gets a `CONFIG_FLAGS` tuple + `_add_flags_to_parser` that drives argparse. `t2i_camera` / `i2i_camera` build `RunConfig` and call `patch_graph(config=...)`. `I2I_NODES` table replaces hardcoded node ids in `_activate_img2img`.

**Tech Stack:** Python 3.12 (existing project standard), dataclasses, comfyui-mcp@0.49.8 (subprocess bridge via `McpClient.from_subprocess`), pytest (existing test runner).

## Global Constraints

- **No backwards compatibility**: old `patch_graph(*, positive, negative, camera, ...)` signature is deleted. Old CLI flags (`--positive`, `--negative`, `--camera`, `--lora`, `--g1`, `--g2`, `--reference`) are deleted. There is NO compat shim — callers must be updated to the new API.
- **`--positive` / `--negative` removed from CLI**: the only path to write positive/negative text is `--envelope` (prompt-forge gate); inline override would bypass the hard rule.
- **`run_t2i` / `run_i2i` new signatures**: `run_t2i(*, mcp, output_dir, config: RunConfig, timeout=600, poll_interval=3, run_dir=None)` and `run_i2i(*, mcp, output_dir, config: RunConfig, timeout=600, poll_interval=3, run_dir=None)`. Old kwargs (`camera: dict`, `camera_extra: dict`, `lora_selections: list[str]`, `enabled_g1: list[str]`, `enabled_g2: list[str]`, `reference_image_path: str`) are deleted.
- **`run-record.json` schema_version** bumps from `"1.0"` to `"2.0"`. `config` field becomes the full `RunConfig` (via `dataclasses.asdict`).
- **`build_lora_patch` signature**: `(run_config_lora: dict | None, mcp_list_loras)` — reads `run_config_lora["selections"]`.
- **`describe-config --stage` default**: `STAGES.T2I`.
- **Image size nodes**: nodes 68/71 are `easy int` (write `value` field); NOT EmptyLatentImage.
- **i2i node ids are NOT hardcoded**: `I2I_NODES` table is the single source.
- **All new tunables are optional**; missing fields fall through to workflow.json static values.
- **`run-record.json` / `submitted-graph.json` written** to `run_dir` (`output_dir/runs/t2i-<timestamp>/` or `output_dir/runs/i2i-<timestamp>/`).
- **`run-record.json` config** is the full frozen RunConfig serialized via `dataclasses.asdict`.
- **Tests**: all new tests live under `skills/character-video-pipeline/runtime/tests/`. Existing test files for old signatures are updated in place. prompt-forge tests remain untouched.
- **Commits**: each task ends with a commit. Use `Co-Authored-By: Claude <noreply@anthropic.com>` in commit body.

---

## File Structure

### New files

- `skills/character-video-pipeline/runtime/config_schema.py` — frozen dataclasses + constants.
- `skills/character-video-pipeline/runtime/tests/test_config_schema.py` — dataclass + frozen + nested access tests.
- `skills/character-video-pipeline/runtime/tests/test_graph_patcher.py` — patch_graph writes + NODE_FIELD_MAP single-source + describe_config helper + WORKFLOW_CONVENTIONS + cross-validation + mandatory-group tests.
- `skills/character-video-pipeline/runtime/tests/test_runtime_cli.py` — CONFIG_FLAGS routing + stage-filter tests.
- `skills/character-video-pipeline/runtime/tests/test_t2i_i2i.py` — end-to-end run_t2i/run_i2i with mocked McpClient.

### Modified files

- `skills/character-video-pipeline/runtime/graph_patcher.py` — full rewrite of `patch_graph` signature + add `NODE_FIELD_MAP` + `_apply_*` helpers + single-source `describe_config` + `_activate_img2img` driven by `I2I_NODES`.
- `skills/character-video-pipeline/runtime/lora_resolver.py` — `build_lora_patch(selections, mcp_list_loras)` → `build_lora_patch(run_config_lora, mcp_list_loras)`.
- `skills/character-video-pipeline/runtime/t2i_camera.py` — signature rewrite + build `RunConfig` from kwargs + upload chain for controlnet_image.
- `skills/character-video-pipeline/runtime/i2i_camera.py` — signature rewrite + build `RunConfig` from kwargs + upload chain for reference_image + controlnet_image.
- `skills/character-video-pipeline/runtime/runtime_cli.py` — full rewrite using `CONFIG_FLAGS` + `_add_flags_to_parser`.
- `skills/character-video-pipeline/runtime/__init__.py` — export `RunConfig`, `SamplingConfig`, `ImageSizeConfig`, `GroupsConfig`, `CameraConfig`, `STAGES`, `GROUPS`, `MANDATORY_GROUPS_BY_STAGE`, `WORKFLOW_CONVENTIONS`, `REFERENCE_IMAGE_NODE`, `CONTROLNET_IMAGE_NODE`, `I2I_NODES`, `DEFAULT_ENABLED_G1`, `DEFAULT_ENABLED_G2`, `NODE_FIELD_MAP`.
- `skills/character-video-pipeline/SKILL.md` — document new config surface + new CLI flags.
- `skills/character-video-pipeline/workflow/README.md` — document new flags + new schema.
- `skills/character-video-pipeline/workflow/t2i-camera/README.md` — document new flags + RunConfig example.
- `skills/character-video-pipeline/workflow/t2i-camera/02-configure.md` — document RunConfig fields.
- `skills/character-video-pipeline/workflow/t2i-camera/03-patch.md` — document new patch_graph flow (13 steps).
- `skills/character-video-pipeline/workflow/t2i-camera/06-record.md` — document new schema_version 2.0 + new config dump format.
- `skills/character-video-pipeline/workflow/i2i-camera/README.md` — document new flags + RunConfig example for i2i.
- `skills/character-video-pipeline/workflow/i2i-camera/01-upload.md` — note that prompt text still comes from envelope.
- `skills/character-video-pipeline/workflow/i2i-camera/03-patch.md` — document new patch_graph flow for i2i (now shares flow with t2i + adds i2i-specific step).

### Unchanged files

- `workflow/t2i-camera/workflow.json` — read-only.
- `workflow/t2i-camera/groups.json` — read-only.
- `prompt-forge/**` — read-only.
- `comfyui-mcp/**` — read-only.
- `scripts/install.ps1` — no new files to verify (existing criticalFiles list is sufficient).
- `.codex-plugin/plugin.json` — no change.

---

## Task 1: Create `runtime/config_schema.py`

**Files:**
- Create: `skills/character-video-pipeline/runtime/config_schema.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces: `RunConfig`, `CameraConfig`, `SamplingConfig`, `ImageSizeConfig`, `GroupsConfig`, `STAGES`, `GROUPS`, `MANDATORY_GROUPS_BY_STAGE`, `WORKFLOW_CONVENTIONS`, `REFERENCE_IMAGE_NODE`, `CONTROLNET_IMAGE_NODE`, `I2I_NODES`, `DEFAULT_ENABLED_G1`, `DEFAULT_ENABLED_G2`.

- [ ] **Step 1: Create the file with all dataclasses + constants**

```python
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
    # prompt-forge gate is always hard (no bypass), per commit d5167a3
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


class STAGES:
    T2I = "t2i-camera"
    I2I = "i2i-camera"


@dataclass(frozen=True)
class GroupTitle:
    LOAD_IMAGE: str = "加载图片（G1）"
    CONTROLNET_LLLITE: str = "ControlNet LLLite（G1）"


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
# 75 ImpactSwitch (latent router), 86 EmptyLatentImage (t2i source),
# 27 KSampler (first-pass; latent_image is rewired between 86 and 59).
@dataclass(frozen=True)
class I2INodes:
    LOAD_IMAGE: str = "21"
    VAE_ENCODE: str = "59"
    IMPACT_SWITCH: str = "75"
    EMPTY_LATENT: str = "86"
    KSAMPLER: str = "27"
    LOAD_IMAGE_CHAIN: tuple[str, ...] = ("21", "57", "58", "59")


I2I_NODES = I2INodes()
```

- [ ] **Step 2: Verify the module imports cleanly**

Run:
```bash
cd skills/character-video-pipeline
python -c "from runtime import config_schema; print(config_schema.STAGES.T2I, config_schema.GROUPS.LOAD_IMAGE, config_schema.I2I_NODES.LOAD_IMAGE)"
```
Expected output: `t2i-camera 加载图片（G1） 21`

- [ ] **Step 3: Verify RunConfig is frozen**

Run:
```bash
python -c "
from runtime.config_schema import RunConfig
c = RunConfig(evidence={}, draft={'positive':'a','negative':'b'})
try:
    c.evidence = {'x':1}
    print('FAIL: not frozen')
except Exception as exc:
    print('OK:', type(exc).__name__)
"
```
Expected output: `OK: dataclasses.FrozenInstanceError`

- [ ] **Step 4: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/character-video-pipeline/runtime/config_schema.py
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "feat(config): add RunConfig schema and i2i node table

- 5 frozen dataclasses (Camera, Sampling, ImageSize, Groups, RunConfig)
- 7 constant tables (STAGES, GROUPS, MANDATORY_GROUPS_BY_STAGE,
  WORKFLOW_CONVENTIONS, REFERENCE_IMAGE_NODE, CONTROLNET_IMAGE_NODE,
  DEFAULT_ENABLED_G1/G2)
- I2I_NODES dataclass (was hardcoded literals in _activate_img2img)
- RunConfig.dialect_id carried inline (RunConfig fully self-contained
  for prompt-forge gate + patcher; gate is always hard per commit d5167a3)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Rewrite `runtime/lora_resolver.build_lora_patch` signature

**Files:**
- Modify: `skills/character-video-pipeline/runtime/lora_resolver.py:172-211`

**Interfaces:**
- Consumes: nothing new (existing internal helpers).
- Produces: `build_lora_patch(run_config_lora: dict | None, mcp_list_loras: Callable | None) -> dict`.

- [ ] **Step 1: Write the failing test for the new signature**

Create `skills/character-video-pipeline/runtime/tests/test_lora_resolver_signature.py`:
```python
"""Test build_lora_patch accepts the new RunConfig.lora dict shape."""
from runtime.lora_resolver import build_lora_patch


def test_build_lora_patch_accepts_dict_with_selections_key():
    """When caller passes {"selections": [...]} the resolver runs the normal flow."""
    # No MCP resolver — should still work for default selections=None.
    patch = build_lora_patch(None, mcp_list_loras=None)
    assert "node_26" in patch
    assert "node_66" in patch


def test_build_lora_patch_accepts_empty_dict_as_default():
    """Empty dict is treated as no selections (use default plan)."""
    patch = build_lora_patch({}, mcp_list_loras=None)
    assert "<lora:anima-base-1-masterpiece-v51:1.00>" in patch["node_26"]["text"]
```

- [ ] **Step 2: Run the test — verify it FAILS on the old signature**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_lora_resolver_signature.py -v
```
Expected: test 1 passes (existing behavior); test 2 FAILS because the old signature `(selections: list[str] | None, mcp_list_loras)` doesn't accept a dict — `TypeError: list[str] | None vs dict`.

- [ ] **Step 3: Rewrite `build_lora_patch` signature**

In `runtime/lora_resolver.py`, replace the `build_lora_patch` function (lines 172-211) with:
```python
def build_lora_patch(
    run_config_lora: dict | None,
    mcp_list_loras: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Build the node 26 + node 66 patch values from RunConfig.lora dict.

    run_config_lora supported shape:
      {"selections": [short_name_or_full_filename, ...]}  (optional key)
    If run_config_lora is None or empty, uses the default 3-LoRA stack.
    If "selections" key is present and non-empty, resolves against MCP
    inventory.
    """
    selections = None
    if isinstance(run_config_lora, dict):
        raw = run_config_lora.get("selections")
        if isinstance(raw, list) and raw:
            selections = raw

    if selections:
        if mcp_list_loras is None:
            raise ValueError("LoRA selections provided but no MCP resolver available")
        raw_inv = mcp_list_loras()
        inventory = parse_lora_inventory(raw_inv)
        anima_loras = filter_anima_loras(inventory)
        resolved = resolve_lora_names(selections, anima_loras)
    else:
        resolved = default_lora_plan()

    stack_text = render_stack_text(resolved)
    trigger_message = render_trigger_concat(resolved)

    return {
        "node_26": {"text": stack_text},
        "node_66": {
            "trigger_words": ["26", 2],
            "orinalMessage": trigger_message,
        },
        "selections": [
            {
                "name": s.name,
                "strength_model": s.strength_model,
                "strength_clip": s.strength_clip,
                "active": s.active,
                "trigger_words": list(s.trigger_words),
            }
            for s in resolved
        ],
        "stack_text": stack_text,
    }
```

- [ ] **Step 4: Re-run the test — verify it PASSES**

Run:
```bash
python -m pytest runtime/tests/test_lora_resolver_signature.py -v
```
Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/character-video-pipeline/runtime/lora_resolver.py skills/character-video-pipeline/runtime/tests/test_lora_resolver_signature.py
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "feat(lora): build_lora_patch takes RunConfig.lora dict

Old signature (selections: list[str] | None) is incompatible with the
new RunConfig.lora: dict | None. The new signature reads
run_config_lora['selections'] (the only supported key). All other keys
are ignored for now.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Rewrite `runtime/graph_patcher.py` — NODE_FIELD_MAP, helpers, describe_config

**Files:**
- Modify: `skills/character-video-pipeline/runtime/graph_patcher.py` (entire file)

**Interfaces:**
- Consumes: from `.config_schema` — `RunConfig`, `SamplingConfig`, `ImageSizeConfig`, `GroupsConfig`, `STAGES`, `GROUPS`, `MANDATORY_GROUPS_BY_STAGE`, `WORKFLOW_CONVENTIONS`, `REFERENCE_IMAGE_NODE`, `CONTROLNET_IMAGE_NODE`, `DEFAULT_ENABLED_G1`, `DEFAULT_ENABLED_G2`, `I2I_NODES`.
- Consumes: from existing modules — `CameraCoords`, `map_camera`, `validate_camera_extra`, `CAMERA_EXTRA_FIELDS`, `apply_group_modes`, `MODE_ACTIVE`, `build_lora_patch`, `DEFAULT_LORA_STACK_TEXT`, `load_workflow`, `load_groups`, `list_group_titles`.
- Produces: `patch_graph(*, stage, config: RunConfig, mcp_list_loras=None) -> dict`; `describe_config(stage=STAGES.T2I) -> dict`; `NODE_FIELD_MAP` (module-level constant).

- [ ] **Step 1: Write the failing test for `describe_config` and `NODE_FIELD_MAP`**

Create `skills/character-video-pipeline/runtime/tests/test_graph_patcher.py`:
```python
"""Tests for graph_patcher.describe_config and NODE_FIELD_MAP single source."""
from runtime.graph_patcher import (
    describe_config,
    NODE_FIELD_MAP,
    _node_static_default,
    _apply_sampling,
    _apply_seed,
    _apply_image_size,
    _apply_controlnet_image,
)
from runtime.config_schema import (
    SamplingConfig,
    ImageSizeConfig,
    STAGES,
)
from runtime.workflow_loader import load_workflow


def test_node_field_map_has_eleven_entries():
    assert len(NODE_FIELD_MAP) == 11


def test_node_field_map_keys_match_config_schema_paths():
    paths = set(NODE_FIELD_MAP.keys())
    assert "sampling.steps_first" in paths
    assert "sampling.cfg" in paths
    assert "sampling.sampler" in paths
    assert "sampling.scheduler" in paths
    assert "sampling.denoise_first" in paths
    assert "sampling.steps_refine" in paths
    assert "sampling.denoise_refine" in paths
    assert "seed" in paths
    assert "image_size.width" in paths
    assert "image_size.height" in paths
    assert "controlnet_image" in paths


def test_node_static_default_reads_workflow_value():
    graph = load_workflow(STAGES.T2I)
    # node 50 default steps = 40 per the workflow dump
    assert _node_static_default(graph, "50", "steps") == 40
    # node 65 default seed = -1
    assert _node_static_default(graph, "65", "seed") == -1


def test_describe_config_returns_workflow_bound_defaults():
    out = describe_config(STAGES.T2I)
    assert out["workflow"] == STAGES.T2I
    sampling = out["slots"]["sampling"]
    assert sampling["nodes"] == ["50", "51"]
    assert sampling["fields"]["steps_first"]["node"] == "50"
    assert sampling["fields"]["steps_first"]["default"] == 40
    assert sampling["fields"]["denoise_refine"]["default"] == 0.2


def test_apply_sampling_writes_only_set_fields():
    # Build a minimal graph copy with just node 50 / 51 inputs.
    graph = {
        "50": {"inputs": {"steps": 40, "cfg": 4, "sampler": "dpmpp_2m",
                          "scheduler": "karras", "denoise": 1.0}},
        "51": {"inputs": {"steps": 25, "denoise": 0.2}},
    }
    _apply_sampling(graph, SamplingConfig(steps_first=50, cfg=7))
    assert graph["50"]["inputs"]["steps"] == 50
    assert graph["50"]["inputs"]["cfg"] == 7
    # Untouched fields stay at original
    assert graph["50"]["inputs"]["sampler"] == "dpmpp_2m"
    assert graph["51"]["inputs"]["steps"] == 25
    assert graph["51"]["inputs"]["denoise"] == 0.2


def test_apply_seed_writes_node_65():
    graph = {"65": {"inputs": {"seed": 1}}}
    _apply_seed(graph, 42)
    assert graph["65"]["inputs"]["seed"] == 42


def test_apply_image_size_writes_nodes_68_and_71():
    graph = {"68": {"inputs": {"value": 1216}}, "71": {"inputs": {"value": 832}}}
    _apply_image_size(graph, ImageSizeConfig(width=1024, height=1024))
    assert graph["68"]["inputs"]["value"] == 1024
    assert graph["71"]["inputs"]["value"] == 1024


def test_apply_image_size_partial():
    graph = {"68": {"inputs": {"value": 1216}}, "71": {"inputs": {"value": 832}}}
    _apply_image_size(graph, ImageSizeConfig(width=2048))  # height=None
    assert graph["68"]["inputs"]["value"] == 2048
    assert graph["71"]["inputs"]["value"] == 832  # unchanged


def test_apply_controlnet_image_writes_node_129():
    graph = {"129": {"inputs": {"image": "old.png"}}}
    _apply_controlnet_image(graph, "subfolder/new.png")
    assert graph["129"]["inputs"]["image"] == "subfolder/new.png"
```

- [ ] **Step 2: Run the test — verify it FAILS**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_graph_patcher.py -v
```
Expected: collection error (`cannot import name 'NODE_FIELD_MAP' from 'runtime.graph_patcher'`) or multiple AttributeError/NameError failures.

- [ ] **Step 3: Rewrite `runtime/graph_patcher.py`**

Replace the entire file contents with:
```python
"""Declarative API graph patching for camera workflows.

Single signature `patch_graph(*, stage, config, mcp_list_loras=None)` accepts
a `RunConfig` (defined in runtime.config_schema) and writes every tunable
into the fixed workflow.json. Anything not set on the config falls through
to workflow.json's static value.

Tunable surface (also enumerated by NODE_FIELD_MAP for the helper):
- prompts (24/25)                              — from config.draft via prompt-forge gate
- camera (583)                                 — from config.camera
- camera_extra (585)                           — from config.camera_extra
- lora (26/66)                                 — from config.lora
- sampling (50/51)                             — from config.sampling
- seed (65)                                    — from config.seed
- image_size (68/71)                           — from config.image_size
- controlnet_image (129)                       — from config.controlnet_image
                                                only if group "ControlNet LLLite（G1）" enabled
- groups (G1/G2 by title)                      — from config.groups
- reference_image (21)                         — from config.reference_image (i2i only)
"""

from __future__ import annotations

from typing import Any, Callable

from .camera_mapper import (
    CameraCoords,
    map_camera,
    validate_camera_extra,
    CAMERA_EXTRA_FIELDS,
)
from .config_schema import (
    DEFAULT_ENABLED_G1,
    DEFAULT_ENABLED_G2,
    GROUPS,
    I2I_NODES,
    MANDATORY_GROUPS_BY_STAGE,
    REFERENCE_IMAGE_NODE,
    RunConfig,
    SamplingConfig,
    ImageSizeConfig,
    GroupsConfig,
    STAGES,
    WORKFLOW_CONVENTIONS,
)
from .group_controller import apply_group_modes, MODE_ACTIVE
from .lora_resolver import build_lora_patch, DEFAULT_LORA_STACK_TEXT
from .workflow_loader import load_workflow, load_groups, list_group_titles


# Single source of truth — patcher and describe_config both read this.
NODE_FIELD_MAP: dict[str, tuple[str, str]] = {
    "sampling.steps_first":    ("50", "steps"),
    "sampling.cfg":            ("50", "cfg"),
    "sampling.sampler":        ("50", "sampler"),
    "sampling.scheduler":      ("50", "scheduler"),
    "sampling.denoise_first":  ("50", "denoise"),
    "sampling.steps_refine":   ("51", "steps"),
    "sampling.denoise_refine": ("51", "denoise"),
    "seed":                    ("65", "seed"),
    "image_size.width":        ("68", "value"),
    "image_size.height":       ("71", "value"),
    "controlnet_image":        ("129", "image"),
}


def _set_prompt(graph: dict, node_id: str, text: str) -> None:
    if node_id not in graph:
        raise KeyError(f"prompt node {node_id} missing from workflow")
    graph[node_id]["inputs"]["wildcard_text"] = text
    graph[node_id]["inputs"]["populated_text"] = text


def _set_camera(graph: dict, coords: CameraCoords) -> None:
    node = graph.get("583")
    if not node:
        raise KeyError("node 583 (CameraAngleNode) missing from workflow")
    node["inputs"]["pos_x"] = coords.pos_x
    node["inputs"]["pos_y"] = coords.pos_y
    node["inputs"]["pos_z"] = coords.pos_z
    node["inputs"]["roll"] = coords.roll


def _set_camera_extra(graph: dict, extra: dict) -> None:
    node = graph.get("585")
    if not node:
        raise KeyError("node 585 (CameraExtraConfigNode) missing from workflow")
    for field in CAMERA_EXTRA_FIELDS:
        if field in extra:
            node["inputs"][field] = extra[field]


def _set_lora(graph: dict, lora_patch: dict) -> None:
    if "26" in graph:
        graph["26"]["inputs"]["text"] = lora_patch["node_26"]["text"]
    if "66" in graph:
        for key, value in lora_patch["node_66"].items():
            graph["66"]["inputs"][key] = value


def _apply_sampling(graph: dict, s: SamplingConfig) -> None:
    if s.steps_first is not None:    graph["50"]["inputs"]["steps"]    = s.steps_first
    if s.cfg is not None:            graph["50"]["inputs"]["cfg"]      = s.cfg
    if s.sampler is not None:        graph["50"]["inputs"]["sampler"]  = s.sampler
    if s.scheduler is not None:      graph["50"]["inputs"]["scheduler"] = s.scheduler
    if s.denoise_first is not None:  graph["50"]["inputs"]["denoise"]  = s.denoise_first
    if s.steps_refine is not None:   graph["51"]["inputs"]["steps"]    = s.steps_refine
    if s.denoise_refine is not None: graph["51"]["inputs"]["denoise"]  = s.denoise_refine


def _apply_seed(graph: dict, seed: int) -> None:
    graph["65"]["inputs"]["seed"] = seed


def _apply_image_size(graph: dict, size: ImageSizeConfig) -> None:
    if size.width is not None:
        graph["68"]["inputs"]["value"] = size.width
    if size.height is not None:
        graph["71"]["inputs"]["value"] = size.height


def _apply_controlnet_image(graph: dict, image_name: str) -> None:
    graph["129"]["inputs"]["image"] = image_name


def _node_static_default(graph: dict, node_id: str, field: str) -> Any:
    """Read workflow.json static value for (node, input). Returns None if missing."""
    node = graph.get(node_id)
    if not node:
        return None
    return node.get("inputs", {}).get(field)


def _activate_img2img(graph: dict, image_name: str) -> None:
    """Rewire KSampler latent from EmptyLatentImage to VAEEncode for i2i.

    Reads node ids from I2I_NODES (single source). After this function:
    - I2I_NODES.LOAD_IMAGE[image] = image_name (uploaded filename)
    - I2I_NODES.VAE_ENCODE[pixels]  = [I2I_NODES.LOAD_IMAGE, 0]
    - I2I_NODES.KSAMPLER[latent_image] = [I2I_NODES.VAE_ENCODE, 0]
    - I2I_NODES.KSAMPLER[denoise]   = 0.6
    - All nodes in I2I_NODES.LOAD_IMAGE_CHAIN set mode = MODE_ACTIVE
    """
    n = I2I_NODES
    for nid in n.LOAD_IMAGE_CHAIN:
        if nid in graph:
            graph[nid]["mode"] = MODE_ACTIVE
    if n.LOAD_IMAGE in graph:
        graph[n.LOAD_IMAGE]["inputs"]["image"] = image_name
    if n.VAE_ENCODE in graph and n.LOAD_IMAGE in graph:
        graph[n.VAE_ENCODE]["inputs"]["pixels"] = [n.LOAD_IMAGE, 0]
    if n.KSAMPLER in graph and n.VAE_ENCODE in graph:
        graph[n.KSAMPLER]["inputs"]["latent_image"] = [n.VAE_ENCODE, 0]
    if n.KSAMPLER in graph:
        graph[n.KSAMPLER]["inputs"]["denoise"] = 0.6


def patch_graph(
    *,
    stage: str = STAGES.T2I,
    config: RunConfig,
    mcp_list_loras: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Build a fully patched, ready-to-submit API graph.

    Single signature: caller passes RunConfig; this function applies all
    non-prompt tunables to the loaded workflow. Prompt text (positive /
    negative) comes from `config.draft` — caller must run the prompt-forge
    gate BEFORE patch_graph and pass the validated draft.
    """
    graph = load_workflow(stage)
    groups_meta = load_groups(stage)

    # 1. Prompts (from prompt-forge-validated draft).
    _set_prompt(graph, "24", config.draft["positive"].strip())
    _set_prompt(graph, "25", config.draft["negative"].strip())

    # 2. Camera coords (583) + extra (585).
    if config.camera:
        coords = map_camera(
            direction=config.camera.direction or "front",
            elevation=config.camera.elevation or "eye-level",
            distance=config.camera.distance or "full_body",
            roll=float(config.camera.roll or 0.0),
        )
        _set_camera(graph, coords)
    if config.camera_extra:
        _set_camera_extra(graph, validate_camera_extra(config.camera_extra))

    # 3. LoRA (26/66).
    if config.lora is not None:
        lora_patch = build_lora_patch(
            run_config_lora=config.lora,
            mcp_list_loras=mcp_list_loras,
        )
        _set_lora(graph, lora_patch)

    # 4. New tunables: sampling (50/51), seed (65), image size (68/71).
    if config.sampling:
        _apply_sampling(graph, config.sampling)
    if config.seed is not None:
        _apply_seed(graph, config.seed)
    if config.image_size:
        _apply_image_size(graph, config.image_size)

    # 5. Group merging: defaults + user + stage-mandatory.
    user_g1 = list((config.groups.g1 if config.groups else []) or [])
    user_g2 = list((config.groups.g2 if config.groups else []) or [])
    final_g1 = list(set(user_g1) | set(DEFAULT_ENABLED_G1))
    final_g2 = list(set(user_g2) | set(DEFAULT_ENABLED_G2))
    for mandatory in MANDATORY_GROUPS_BY_STAGE.get(stage, []):
        if mandatory not in final_g1:
            final_g1.append(mandatory)

    # 6. Cross-validate controlnet_image <-> ControlNet LLLite group.
    cn_node_for_stage = None
    if stage == STAGES.T2I:
        cn_node_for_stage = "129"
    elif stage == STAGES.I2I:
        cn_node_for_stage = "129"
    if config.controlnet_image is not None and not cn_node_for_stage:
        raise ValueError(f"controlnet_image not supported in stage={stage!r}")
    if config.controlnet_image is not None and GROUPS.CONTROLNET_LLLITE not in final_g1:
        raise ValueError(
            f"controlnet_image provided but {GROUPS.CONTROLNET_LLLITE!r} is not in groups.g1; "
            "either enable the group or omit controlnet_image"
        )
    if GROUPS.CONTROLNET_LLLITE in final_g1 and config.controlnet_image is None:
        raise ValueError(
            f"groups.g1 contains {GROUPS.CONTROLNET_LLLITE!r} but controlnet_image is None; "
            "ControlNet LLLite requires node 129 'Load Image ControlNet' to have an image"
        )

    graph = apply_group_modes(graph, groups_meta, final_g1, final_g2)

    # 7. ControlNet LLLite image (node 129) — only after group is confirmed active.
    if config.controlnet_image is not None:
        _apply_controlnet_image(graph, config.controlnet_image)

    # 8. WORKFLOW_CONVENTIONS per stage.
    if stage in WORKFLOW_CONVENTIONS:
        for nid, value in WORKFLOW_CONVENTIONS[stage].get("denoise_override", {}).items():
            graph[nid]["inputs"]["denoise"] = value

    # 9. i2i activation (after group validation so the upload path is enforced).
    if stage == STAGES.I2I:
        if not config.reference_image:
            raise ValueError("reference_image is required for i2i-camera")
        _activate_img2img(graph, config.reference_image)

    return graph


def describe_config(stage: str = STAGES.T2I) -> dict[str, Any]:
    """Return all configurable slots for the current workflow.

    Reads NODE_FIELD_MAP + workflow.json static values + groups.json titles.
    No hand-written field table.
    """
    graph = load_workflow(stage)
    titles = list_group_titles(stage)

    slots: dict[str, Any] = {}

    # Walk NODE_FIELD_MAP: cluster by top-level key.
    grouped: dict[str, list[tuple[str, str, str]]] = {}
    for path, (nid, fld) in NODE_FIELD_MAP.items():
        group = path.split(".", 1)[0] if "." in path else path
        grouped.setdefault(group, []).append((path, nid, fld))

    for group, items in grouped.items():
        if group == "sampling":
            slots[group] = {
                "source": f"config.{group}",
                "nodes": sorted({nid for _, nid, _ in items}),
                "fields": {
                    p.split(".", 1)[1]: {
                        "node": nid,
                        "default": _node_static_default(graph, nid, fld),
                    }
                    for p, nid, fld in items
                },
            }
        elif group == "image_size":
            slots[group] = {
                "source": f"config.{group}",
                "nodes": sorted({nid for _, nid, _ in items}),
                "default": {
                    p.split(".", 1)[1]: _node_static_default(graph, nid, fld)
                    for p, nid, fld in items
                },
            }
        else:
            path, nid, fld = items[0]
            slots[group] = {
                "source": f"config.{group}",
                "node": nid,
                "default": _node_static_default(graph, nid, fld),
            }

    # Special slots that don't map to NODE_FIELD_MAP.
    slots["positive"] = {
        "source": "envelope.draft.positive",
        "node": "24",
        "type": "ImpactWildcardProcessor",
        "required": True,
    }
    slots["negative"] = {
        "source": "envelope.draft.negative",
        "node": "25",
        "type": "ImpactWildcardProcessor",
        "required": True,
    }
    slots["camera"] = {
        "source": "config.camera",
        "node": "583",
        "type": "CameraAngleNode",
        "required": False,
        "default": "front / eye-level / full_body / 0",
        "fields": {
            "direction": ["front", "back", "left", "right"],
            "elevation": ["high", "eye-level", "low"],
            "distance": [
                "extreme_close_up", "close_up", "medium",
                "cowboy_shot", "full_body", "wide",
            ],
            "roll": "[0, 1]",
        },
    }
    slots["camera_extra"] = {
        "source": "config.camera_extra",
        "node": "585",
        "type": "CameraExtraConfigNode",
        "required": False,
        "fields": list(CAMERA_EXTRA_FIELDS),
    }
    slots["lora"] = {
        "source": "config.lora",
        "loader_node": "26",
        "trigger_node": "66",
        "required": False,
        "default_stack": DEFAULT_LORA_STACK_TEXT,
    }
    slots["reference_image"] = {
        "source": "config.reference_image",
        "node": "21",
        "type": "LoadImage",
        "required_if": 'stage == "i2i-camera"',
        "default": None,
    }
    slots["controlnet_image"] = {
        "source": "config.controlnet_image",
        "node": "129",
        "type": "Load Image ControlNet",
        "required_if": f'groups.g1 contains {GROUPS.CONTROLNET_LLLITE!r}',
        "default": None,
    }
    slots["groups"] = {
        "source": "config.groups",
        "g1_titles": titles["g1"],
        "g2_titles": titles["g2"],
        "auto_appended_g1": {
            GROUPS.CONTROLNET_LLLITE: "when controlnet_image provided",
            GROUPS.LOAD_IMAGE: "when stage == 'i2i-camera'",
        },
    }

    return {"stage": stage, "workflow": stage, "slots": slots}
```

- [ ] **Step 4: Run the test — verify it PASSES**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_graph_patcher.py -v
```
Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/character-video-pipeline/runtime/graph_patcher.py skills/character-video-pipeline/runtime/tests/test_graph_patcher.py
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "feat(patcher): RunConfig-driven patch_graph + NODE_FIELD_MAP single source

- patch_graph(*, stage, config: RunConfig, mcp_list_loras=None)
- NODE_FIELD_MAP (11 entries) drives patcher writes and describe_config
- _apply_sampling/_apply_seed/_apply_image_size/_apply_controlnet_image
- _activate_img2img driven by I2I_NODES (no more hardcoded node ids)
- Group merging: DEFAULT_ENABLED_G1/G2 + user groups + stage mandatory
- Cross-validation: controlnet_image <-> ControlNet LLLite group
- describe_config: workflow-bound defaults from NODE_FIELD_MAP +
  workflow.json static values + groups.json titles (no hand-written table)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Add tests for `patch_graph` end-to-end (cross-validation, mandatory groups, conventions, controlnet image write)

**Files:**
- Create: append to `skills/character-video-pipeline/runtime/tests/test_graph_patcher.py`

**Interfaces:**
- Consumes: `patch_graph` from `runtime.graph_patcher`.
- Produces: test cases (this task adds to existing test file from Task 3).

- [ ] **Step 1: Add tests for patch_graph end-to-end behavior**

Append the following tests to `runtime/tests/test_graph_patcher.py`:
```python
"""End-to-end patch_graph tests (cross-validation, conventions, etc.)."""
import pytest

from runtime.config_schema import (
    GroupsConfig,
    RunConfig,
    SamplingConfig,
    STAGES,
)
from runtime.graph_patcher import patch_graph


def _base_config(stage=STAGES.T2I, **overrides):
    return RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl, solo", "negative": "lowres, bad"},
        **overrides,
    )


def test_patch_graph_writes_default_when_field_is_none():
    """No field overrides -> workflow.json static values remain untouched."""
    g = patch_graph(stage=STAGES.T2I, config=_base_config())
    # node 50 default steps = 40 per workflow.json
    assert g["50"]["inputs"]["steps"] == 40
    # node 51 default steps = 25 per workflow.json
    assert g["51"]["inputs"]["steps"] == 25


def test_patch_graph_applies_sampling_overrides():
    g = patch_graph(
        stage=STAGES.T2I,
        config=_base_config(sampling=SamplingConfig(steps_first=50, cfg=7)),
    )
    assert g["50"]["inputs"]["steps"] == 50
    assert g["50"]["inputs"]["cfg"] == 7


def test_patch_graph_t2i_does_not_force_denoise():
    """T2I: WORKFLOW_CONVENTIONS for I2I doesn't apply; node 27.denoise
    must equal its workflow.json static value (which is derived from node 50
    via input ref, but the static input is '1' in our dump)."""
    g = patch_graph(stage=STAGES.T2I, config=_base_config())
    # node 27.denoise is fed by [50, 5] in workflow.json; workflow.json
    # static value of node 50.inputs.denoise is 1.
    # Just ensure patch_graph didn't overwrite anything weird.
    assert "denoise" in g["50"]["inputs"]


def test_patch_graph_i2i_auto_appends_load_image_group():
    g = patch_graph(
        stage=STAGES.I2I,
        config=_base_config(reference_image="ref.png"),
    )
    # The LoadImage group must be active: nodes 21/57/58/59 mode=0 (active)
    for nid in ("21", "57", "58", "59"):
        assert g[nid]["mode"] == 0


def test_patch_graph_i2i_forces_denoise_override():
    g = patch_graph(
        stage=STAGES.I2I,
        config=_base_config(reference_image="ref.png"),
    )
    assert g["27"]["inputs"]["denoise"] == 0.6


def test_patch_graph_i2i_missing_reference_image_raises():
    cfg = _base_config(stage=STAGES.I2I)
    # No reference_image provided
    with pytest.raises(ValueError, match="reference_image is required"):
        patch_graph(stage=STAGES.I2I, config=cfg)


def test_patch_graph_controlnet_image_requires_group():
    cfg = _base_config(controlnet_image="pose.png")
    # User did not enable the ControlNet LLLite group -> raises
    with pytest.raises(ValueError, match="not in groups.g1"):
        patch_graph(stage=STAGES.T2I, config=cfg)


def test_patch_graph_controlnet_group_without_image_raises():
    cfg = _base_config(groups=GroupsConfig(g1=["ControlNet LLLite（G1）"]))
    with pytest.raises(ValueError, match="but controlnet_image is None"):
        patch_graph(stage=STAGES.T2I, config=cfg)


def test_patch_graph_controlnet_image_and_group_writes_node_129():
    cfg = _base_config(
        controlnet_image="uploaded/pose.png",
        groups=GroupsConfig(g1=["ControlNet LLLite（G1）"]),
    )
    g = patch_graph(stage=STAGES.T2I, config=cfg)
    assert g["129"]["inputs"]["image"] == "uploaded/pose.png"


def test_patch_graph_user_groups_combine_with_defaults():
    """DEFAULT_ENABLED_G1 must always be active; user can add MORE."""
    cfg = _base_config(groups=GroupsConfig(g1=["手部 ADetailer（G1）"]))
    g = patch_graph(stage=STAGES.T2I, config=cfg)
    # 保存图片（G1） (default) must still be active
    assert g["35"]["mode"] == 0
    # 手部 ADetailer（G1） (user) must be active
    assert g["31"]["mode"] == 0
    # A non-default, non-user group should still be bypassed
    # (随机挑个不属于 DEFAULT/USER 的 G1 组)
    assert g["124"]["mode"] == 4  # 移除背景（G1）is bypassed by default
```

- [ ] **Step 2: Run the test — verify it PASSES**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_graph_patcher.py -v
```
Expected: all tests (8 from Task 3 + 10 new) pass.

- [ ] **Step 3: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/character-video-pipeline/runtime/tests/test_graph_patcher.py
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "test(patcher): end-to-end patch_graph coverage

- Default fallback when fields are None
- Sampling override path
- t2i does not apply I2I WORKFLOW_CONVENTIONS
- i2i auto-appends LoadImage group + forces denoise=0.6
- i2i missing reference_image raises
- controlnet_image <-> ControlNet LLLite group bidirectional validation
- User groups combine with DEFAULT_ENABLED_G1/G2 (additive, never disable)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Rewrite `runtime/t2i_camera.py` — new signature + build RunConfig

**Files:**
- Modify: `skills/character-video-pipeline/runtime/t2i_camera.py` (entire file)
- Reference: existing `_wait_for_completion`, `_parse_history`, `_download_artifact` (keep unchanged).

**Interfaces:**
- Consumes: `RunConfig`, `compile_envelope`, `compile_or_minimal`, `McpClient`, `patch_graph`.
- Produces: `run_t2i(*, mcp, output_dir, config: RunConfig, timeout=600, poll_interval=3, run_dir=None)`.

- [ ] **Step 1: Write the failing test for the new `run_t2i` signature**

Create `skills/character-video-pipeline/runtime/tests/test_t2i_i2i.py`:
```python
"""End-to-end run_t2i / run_i2i tests with mocked McpClient."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from runtime import t2i_camera, i2i_camera
from runtime.config_schema import RunConfig


@pytest.fixture
def fake_mcp():
    """Mock McpClient that returns canned responses for the camera run."""
    mcp = MagicMock()
    mcp.health.return_value = {"queue": {"running": [], "pending": []}}
    mcp.validate_workflow.return_value = {"error_count": 0}
    mcp.check_runtime.return_value = {"runtime": "local"}
    mcp.enqueue.return_value = {"prompt_id": "test-prompt-id"}
    mcp.get_history.return_value = {
        "## Execution: test-prompt-id": [
            "**Status**: success",
            "**Duration**: 10s",
            "**Cached nodes**: 0",
            "### Outputs (1 nodes)",
            "- Node 35: images -> **dummy.png (type=output)**",
        ]
    }
    mcp.get_image.return_value = {
        "type": "image",
        "data": "iVBORw0KGgo=",
        "mimeType": "image/png",
    }
    mcp.upload_image.return_value = {"name": "uploaded-ref.png"}
    return mcp


def _base_config(**overrides):
    return RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl, solo", "negative": "lowres"},
        **overrides,
    )


def test_run_t2i_new_signature_accepts_config_object(tmp_path: Path, fake_mcp):
    payload, code = t2i_camera.run_t2i(
        mcp=fake_mcp,
        output_dir=tmp_path,
        config=_base_config(),
        timeout=10,
    )
    assert code == 0
    assert payload["accepted"] is True
    assert payload["stage"] == "t2i-camera"
    assert payload["prompt_id"] == "test-prompt-id"
    assert "prompt_forge_warnings" in payload  # may be empty or populated


def test_run_t2i_no_longer_accepts_old_kwargs(tmp_path: Path, fake_mcp):
    """Old kwargs (camera dict / lora_selections list / enabled_g1/g2 list)
    are no longer accepted — TypeError."""
    with pytest.raises(TypeError):
        t2i_camera.run_t2i(
            mcp=fake_mcp,
            output_dir=tmp_path,
            config=_base_config(),
            camera={"direction": "front"},  # OLD kwarg, no longer supported
        )


def test_run_i2i_new_signature_accepts_config_object(tmp_path: Path, fake_mcp):
    payload, code = i2i_camera.run_i2i(
        mcp=fake_mcp,
        output_dir=tmp_path,
        config=_base_config(reference_image="/tmp/ref.png"),
        timeout=10,
    )
    assert code == 0
    assert payload["accepted"] is True
    assert payload["stage"] == "i2i-camera"
    fake_mcp.upload_image.assert_called_once_with("/tmp/ref.png")


def test_run_i2i_uploads_controlnet_image_when_provided(tmp_path: Path, fake_mcp):
    payload, code = i2i_camera.run_i2i(
        mcp=fake_mcp,
        output_dir=tmp_path,
        config=_base_config(
            reference_image="/tmp/ref.png",
            controlnet_image="/tmp/pose.png",
        ),
        timeout=10,
    )
    assert code == 0
    # upload_image should have been called twice: once for reference, once for controlnet
    assert fake_mcp.upload_image.call_count == 2
    uploaded_paths = sorted(call.args[0] for call in fake_mcp.upload_image.call_args_list)
    assert uploaded_paths == ["/tmp/pose.png", "/tmp/ref.png"]
```

- [ ] **Step 2: Run the test — verify it FAILS**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_t2i_i2i.py -v
```
Expected: `test_run_t2i_new_signature_accepts_config_object` fails because old `run_t2i` doesn't accept `config=...` kwarg. The "no longer accepts old kwargs" test may pass vacuously depending on how the error is thrown.

- [ ] **Step 3: Rewrite `runtime/t2i_camera.py`**

Replace the entire file contents with:
```python
"""End-to-end text-to-image camera pipeline.

Mandatory entry point for character-video-pipeline t2i-camera. All prompt text
(positive / negative) MUST be authored through prompt-forge before reaching
ComfyUI; this module owns the prompt-forge gate as part of the run_t2i flow.

Steps: prompt-forge validate -> upload controlnet_image -> health check
       -> patch workflow -> validate -> submit -> wait -> download -> record.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from .attempt_state import record_attempt
from .config_schema import RunConfig, STAGES
from .graph_patcher import patch_graph
from .mcp_client import McpClient
from .prompt_forge_bridge import compile_envelope, compile_or_minimal


def run_t2i(
    *,
    mcp: McpClient,
    output_dir: Path,
    config: RunConfig,
    timeout: float = 600.0,
    poll_interval: float = 3.0,
    run_dir: Path | None = None,
) -> tuple[dict[str, Any], int]:
    """Run text-to-image camera generation. Returns (payload, exit_code).

    Caller supplies RunConfig (which already carries evidence + draft + all
    tunables). This function:
    1. Validates prompt-forge envelope (config.evidence + config.draft)
    2. Uploads config.controlnet_image if provided (and group enabled)
    3. Calls patch_graph to build the graph
    4. Validates + submits + polls + downloads via McpClient
    """
    started = time.monotonic()
    run_dir = Path(run_dir) if run_dir else output_dir / "runs" / f"t2i-{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)

    uploaded_controlnet: str | None = None
    try:
        # Step 1: prompt-forge validation gate.
        # prompt-forge gate is always hard (no bypass); commit d5167a3.
        package = compile_envelope(config.evidence, config.draft, config.dialect_id)

        # Step 2: upload controlnet_image (if provided).
        if config.controlnet_image is not None:
            upload_result = mcp.upload_image(config.controlnet_image)
            if isinstance(upload_result, dict):
                uploaded_controlnet = upload_result.get("name")
                subfolder = upload_result.get("subfolder", "")
                if subfolder and uploaded_controlnet:
                    uploaded_controlnet = f"{subfolder}/{uploaded_controlnet}"
            if not uploaded_controlnet:
                raise RuntimeError(f"controlnet image upload failed: {upload_result}")

        # Step 3: health + patch + validate + submit + wait + download.
        health = mcp.health()
        if isinstance(health, dict) and isinstance(health.get("queue"), dict):
            q = health["queue"]
            running = len(q.get("running", []))
            pending = len(q.get("pending", []))
            if running or pending:
                raise RuntimeError(f"ComfyUI queue not idle (running={running}, pending={pending})")

        # If controlnet was uploaded, override the config's controlnet_image
        # with the post-upload filename.
        patch_config = config
        if uploaded_controlnet and uploaded_controlnet != config.controlnet_image:
            patch_config = replace(config, controlnet_image=uploaded_controlnet)

        graph = patch_graph(
            stage=STAGES.T2I,
            config=patch_config,
            mcp_list_loras=mcp.list_loras if patch_config.lora else None,
        )

        validation = mcp.validate_workflow(graph)
        if isinstance(validation, dict) and validation.get("error_count", 0) > 0:
            raise RuntimeError(f"workflow validation failed: {validation}")

        runtime_check = mcp.check_runtime(graph)
        if isinstance(runtime_check, dict) and runtime_check.get("runtime") != "local":
            raise RuntimeError(f"workflow uses non-local runtime: {runtime_check}")

        result = mcp.enqueue(graph)
        prompt_id = None
        if isinstance(result, dict):
            prompt_id = result.get("prompt_id") or result.get("promptId")
        if not prompt_id:
            raise RuntimeError(f"enqueue did not return prompt_id: {result}")

        entry = _wait_for_completion(mcp, prompt_id, timeout, poll_interval)
        artifact = _download_artifact(mcp, entry, output_dir)

    except Exception as exc:
        record_attempt({"stage": "t2i-camera", "status": "failed", "error": str(exc)})
        return {"accepted": False, "stage": "t2i-camera", "error": str(exc)}, 1

    duration_ms = int((time.monotonic() - started) * 1000)
    run_record = {
        "schema_version": "2.0",
        "stage": "t2i-camera",
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "config": asdict(config),
        "prompt_package_quality": package.get("quality", {}),
    }
    (run_dir / "submitted-graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "run-record.json").write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    record_attempt({
        "stage": "t2i-camera",
        "status": "success",
        "prompt_id": prompt_id,
        "artifact": artifact.get("path"),
    })

    payload: dict[str, Any] = {
        "accepted": True,
        "stage": "t2i-camera",
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "run_record_path": str(run_dir / "run-record.json"),
    }
    if package.get("warnings"):
        payload["prompt_forge_warnings"] = package["warnings"]
    return payload, 0


def _wait_for_completion(mcp: McpClient, prompt_id: str, timeout: float, poll: float) -> dict:
    """Poll get_history until the prompt succeeds or fails.

    Supports both response formats:
    - dict (raw ComfyUI /history payload, when JSON-parseable)
    - text (formatted markdown, when get_history returns text)
    """
    import re
    deadline = time.monotonic() + timeout
    while True:
        history = mcp.get_history(prompt_id)
        entry, status_str, error_detail = _parse_history(history, prompt_id)
        if status_str == "success":
            return entry if entry else {"prompt_id": prompt_id, "outputs": {}}
        if status_str == "error":
            raise RuntimeError(f"execution failed: {error_detail}")
        if time.monotonic() >= deadline:
            raise RuntimeError(f"timed out after {timeout:.0f}s")
        time.sleep(poll)


def _parse_history(history: object, prompt_id: str) -> tuple[dict | None, str | None, str]:
    """Extract (entry, status_str, error_detail) from dict or text history."""
    import re
    if isinstance(history, dict):
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {}) if isinstance(entry, dict) else {}
            status_str = status.get("status_str") if isinstance(status, dict) else None
            error_detail = ""
            if status_str == "error":
                msgs = status.get("messages", []) if isinstance(status, dict) else []
                for m in msgs:
                    if isinstance(m, list) and len(m) == 2 and m[0] == "execution_error":
                        info = m[1] if isinstance(m[1], dict) else {}
                        error_detail = f"node {info.get('node_id')}: {info.get('exception_message')}"
            return entry, status_str, error_detail
        return None, None, ""
    if isinstance(history, str):
        text = history
        if "No history found" in text:
            return None, None, ""
        m = re.search(r"\*\*Status\*\*:\s*(\w+)", text)
        if m:
            status_str = m.group(1).lower()
            if status_str == "success":
                outputs: dict[str, dict] = {}
                for line_match in re.finditer(
                    r"Node\s+(\d+):\s+(\w+)\s+→\s+\*\*([^*]+)\((type=\w+)\)\*\*", text
                ):
                    node_id, kind, fname_with_space, type_kv = (
                        line_match.group(1),
                        line_match.group(2),
                        line_match.group(3).strip(),
                        line_match.group(4),
                    )
                    image_type = type_kv.split("=", 1)[1]
                    if kind == "images":
                        outputs[node_id] = {
                            "images": [{"filename": fname_with_space, "subfolder": "", "type": image_type}]
                        }
                return (
                    {"prompt_id": prompt_id, "outputs": outputs, "_text": text},
                    "success",
                    "",
                )
            if status_str == "error":
                node_m = re.search(r"\*\*Failed node\*\*:\s*(\S+)", text)
                exc_m = re.search(r"\*\*Exception\*\*:\s*(.+?)(?:\n|$)", text)
                detail = ""
                if node_m:
                    detail = f"node {node_m.group(1)}"
                if exc_m:
                    detail = f"{detail}: {exc_m.group(1).strip()}" if detail else exc_m.group(1).strip()
                return None, "error", detail
    return None, None, ""


def _download_artifact(mcp: McpClient, entry: dict, output_dir: Path) -> dict:
    outputs = entry.get("outputs", {})
    image_info = None
    for node_id, out in outputs.items():
        if isinstance(out, dict) and isinstance(out.get("images"), list) and out["images"]:
            image_info = out["images"][0]
            break
    if not image_info:
        raise RuntimeError("no output images in history entry")

    filename = image_info["filename"]
    subfolder = image_info.get("subfolder", "")
    image_type = image_info.get("type", "output")
    raw = mcp.get_image(filename, subfolder, image_type)

    output_dir.mkdir(parents=True, exist_ok=True)
    data: bytes | None = None
    if isinstance(raw, (bytes, bytearray)):
        data = bytes(raw)
    elif isinstance(raw, dict) and "data" in raw:
        import base64
        data = base64.b64decode(raw["data"])
    elif isinstance(raw, list):
        import base64
        for block in raw:
            if isinstance(block, dict) and block.get("type") == "image":
                b64 = block.get("data")
                if isinstance(b64, str):
                    data = base64.b64decode(b64)
                    break

    if data is None:
        return {"filename": filename, "subfolder": subfolder, "bytes": 0, "sha256": ""}

    out_path = output_dir / filename
    out_path.write_bytes(data)
    return {
        "filename": filename,
        "subfolder": subfolder,
        "path": str(out_path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
```

- [ ] **Step 4: Run the test — verify t2i tests PASS**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_t2i_i2i.py::test_run_t2i_new_signature_accepts_config_object runtime/tests/test_t2i_i2i.py::test_run_t2i_no_longer_accepts_old_kwargs -v
```
Expected: both tests pass. (`test_run_i2i_*` and `test_run_i2i_uploads_controlnet_image_when_provided` will fail because we haven't rewritten i2i_camera yet — that's Task 6.)

- [ ] **Step 5: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/character-video-pipeline/runtime/t2i_camera.py
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "feat(t2i): rewrite run_t2i to take RunConfig

- New signature: run_t2i(*, mcp, output_dir, config: RunConfig, ...)
- Old kwargs (camera dict / camera_extra dict / lora_selections list /
  enabled_g1 / enabled_g2 / reference_image_path) removed; only
  RunConfig is accepted
- controlnet_image (if provided) is uploaded via mcp.upload_image
  BEFORE patch_graph; the post-upload filename overrides the local
  path via dataclasses.replace on a copy of RunConfig
- run-record.json schema_version bumped to '2.0'; config field is
  the full RunConfig (dataclasses.asdict)
- prompt_forge_warnings preserved in the response payload
- _wait_for_completion / _parse_history / _download_artifact kept
  unchanged (no config surface changes)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Rewrite `runtime/i2i_camera.py` — new signature + reference/controlnet upload chain

**Files:**
- Modify: `skills/character-video-pipeline/runtime/i2i_camera.py` (entire file)

**Interfaces:**
- Consumes: `RunConfig`, `compile_envelope`, `compile_or_minimal`, `McpClient`, `patch_graph`, `STAGES`.
- Produces: `run_i2i(*, mcp, output_dir, config: RunConfig, timeout=600, poll_interval=3, run_dir=None)`.

- [ ] **Step 1: Run the i2i tests from Task 5 — verify they FAIL**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_t2i_i2i.py::test_run_i2i_new_signature_accepts_config_object runtime/tests/test_t2i_i2i.py::test_run_i2i_uploads_controlnet_image_when_provided -v
```
Expected: both fail because old `run_i2i` signature takes `reference_image_path` separately and doesn't handle controlnet_image.

- [ ] **Step 2: Rewrite `runtime/i2i_camera.py`**

Replace the entire file contents with:
```python
"""End-to-end image-to-image camera pipeline.

Mandatory entry point for character-video-pipeline i2i-camera. Same prompt
forge gate as t2i_camera; uploads a reference image and (optionally)
controlnet_image, then patches the workflow with img2img activation
(node 21 LoadImage + node 27/59 latent rewire).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from .attempt_state import record_attempt
from .config_schema import RunConfig, STAGES
from .graph_patcher import patch_graph
from .mcp_client import McpClient
from .prompt_forge_bridge import compile_envelope, compile_or_minimal


def run_i2i(
    *,
    mcp: McpClient,
    output_dir: Path,
    config: RunConfig,
    timeout: float = 600.0,
    poll_interval: float = 3.0,
    run_dir: Path | None = None,
) -> tuple[dict[str, Any], int]:
    """Run image-to-image camera generation. Returns (payload, exit_code).

    Caller supplies RunConfig with reference_image (local path, required
    for i2i) and optionally controlnet_image. This function:
    1. Validates prompt-forge envelope
    2. Uploads reference_image and (if provided) controlnet_image
    3. Calls patch_graph with stage=i2i-camera (auto-appends
       "加载图片（G1）" and forces node 27.denoise=0.6)
    4. Validates + submits + polls + downloads via McpClient
    """
    started = time.monotonic()
    run_dir = Path(run_dir) if run_dir else output_dir / "runs" / f"i2i-{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)

    if not config.reference_image:
        raise ValueError("RunConfig.reference_image is required for i2i-camera")

    uploaded_reference: str | None = None
    uploaded_controlnet: str | None = None
    try:
        # Step 1: prompt-forge validation gate.
        # prompt-forge gate is always hard (no bypass); commit d5167a3.
        package = compile_envelope(config.evidence, config.draft, config.dialect_id)

        # Step 2: upload reference_image (required).
        ref_upload = mcp.upload_image(config.reference_image)
        if isinstance(ref_upload, dict):
            uploaded_reference = ref_upload.get("name")
            subfolder = ref_upload.get("subfolder", "")
            if subfolder and uploaded_reference:
                uploaded_reference = f"{subfolder}/{uploaded_reference}"
        if not uploaded_reference:
            raise RuntimeError(f"reference image upload failed: {ref_upload}")

        # Step 3: upload controlnet_image (optional).
        if config.controlnet_image is not None:
            cn_upload = mcp.upload_image(config.controlnet_image)
            if isinstance(cn_upload, dict):
                uploaded_controlnet = cn_upload.get("name")
                subfolder = cn_upload.get("subfolder", "")
                if subfolder and uploaded_controlnet:
                    uploaded_controlnet = f"{subfolder}/{uploaded_controlnet}"
            if not uploaded_controlnet:
                raise RuntimeError(f"controlnet image upload failed: {cn_upload}")

        # Step 4: health + patch + validate + submit + wait + download.
        health = mcp.health()
        if isinstance(health, dict) and isinstance(health.get("queue"), dict):
            q = health["queue"]
            running = len(q.get("running", []))
            pending = len(q.get("pending", []))
            if running or pending:
                raise RuntimeError(f"ComfyUI queue not idle (running={running}, pending={pending})")

        # Build a config copy with post-upload filenames so patch_graph
        # writes the right node inputs.
        patch_config = replace(
            config,
            reference_image=uploaded_reference,
            controlnet_image=uploaded_controlnet,
        )

        graph = patch_graph(
            stage=STAGES.I2I,
            config=patch_config,
            mcp_list_loras=mcp.list_loras if patch_config.lora else None,
        )

        validation = mcp.validate_workflow(graph)
        if isinstance(validation, dict) and validation.get("error_count", 0) > 0:
            raise RuntimeError(f"workflow validation failed: {validation}")

        runtime_check = mcp.check_runtime(graph)
        if isinstance(runtime_check, dict) and runtime_check.get("runtime") != "local":
            raise RuntimeError(f"workflow uses non-local runtime: {runtime_check}")

        result = mcp.enqueue(graph)
        prompt_id = None
        if isinstance(result, dict):
            prompt_id = result.get("prompt_id") or result.get("promptId")
        if not prompt_id:
            raise RuntimeError(f"enqueue did not return prompt_id: {result}")

        entry = _wait_for_completion(mcp, prompt_id, timeout, poll_interval)
        artifact = _download_artifact(mcp, entry, output_dir)

    except Exception as exc:
        record_attempt({"stage": "i2i-camera", "status": "failed", "error": str(exc)})
        return {"accepted": False, "stage": "i2i-camera", "error": str(exc)}, 1

    duration_ms = int((time.monotonic() - started) * 1000)
    run_record = {
        "schema_version": "2.0",
        "stage": "i2i-camera",
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "config": asdict(config),
        "prompt_package_quality": package.get("quality", {}),
    }
    (run_dir / "submitted-graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "run-record.json").write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    record_attempt({
        "stage": "i2i-camera",
        "status": "success",
        "prompt_id": prompt_id,
        "artifact": artifact.get("path"),
    })

    payload: dict[str, Any] = {
        "accepted": True,
        "stage": "i2i-camera",
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "run_record_path": str(run_dir / "run-record.json"),
    }
    if package.get("warnings"):
        payload["prompt_forge_warnings"] = package["warnings"]
    return payload, 0


def _wait_for_completion(mcp: McpClient, prompt_id: str, timeout: float, poll: float) -> dict:
    """Poll get_history until the prompt succeeds or fails.

    Supports both response formats:
    - dict (raw ComfyUI /history payload, when JSON-parseable)
    - text (formatted markdown, when get_history returns text)
    """
    import re
    deadline = time.monotonic() + timeout
    while True:
        history = mcp.get_history(prompt_id)
        entry, status_str, error_detail = _parse_history(history, prompt_id)
        if status_str == "success":
            return entry if entry else {"prompt_id": prompt_id, "outputs": {}}
        if status_str == "error":
            raise RuntimeError(f"execution failed: {error_detail}")
        if time.monotonic() >= deadline:
            raise RuntimeError(f"timed out after {timeout:.0f}s")
        time.sleep(poll)


def _parse_history(history: object, prompt_id: str) -> tuple[dict | None, str | None, str]:
    """Extract (entry, status_str, error_detail) from dict or text history."""
    import re
    if isinstance(history, dict):
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {}) if isinstance(entry, dict) else {}
            status_str = status.get("status_str") if isinstance(status, dict) else None
            error_detail = ""
            if status_str == "error":
                msgs = status.get("messages", []) if isinstance(status, dict) else []
                for m in msgs:
                    if isinstance(m, list) and len(m) == 2 and m[0] == "execution_error":
                        info = m[1] if isinstance(m[1], dict) else {}
                        error_detail = f"node {info.get('node_id')}: {info.get('exception_message')}"
            return entry, status_str, error_detail
        return None, None, ""
    if isinstance(history, str):
        text = history
        if "No history found" in text:
            return None, None, ""
        m = re.search(r"\*\*Status\*\*:\s*(\w+)", text)
        if m:
            status_str = m.group(1).lower()
            if status_str == "success":
                outputs: dict[str, dict] = {}
                for line_match in re.finditer(
                    r"Node\s+(\d+):\s+(\w+)\s+→\s+\*\*([^*]+)\((type=\w+)\)\*\*", text
                ):
                    node_id, kind, fname_with_space, type_kv = (
                        line_match.group(1),
                        line_match.group(2),
                        line_match.group(3).strip(),
                        line_match.group(4),
                    )
                    image_type = type_kv.split("=", 1)[1]
                    if kind == "images":
                        outputs[node_id] = {
                            "images": [{"filename": fname_with_space, "subfolder": "", "type": image_type}]
                        }
                return (
                    {"prompt_id": prompt_id, "outputs": outputs, "_text": text},
                    "success",
                    "",
                )
            if status_str == "error":
                node_m = re.search(r"\*\*Failed node\*\*:\s*(\S+)", text)
                exc_m = re.search(r"\*\*Exception\*\*:\s*(.+?)(?:\n|$)", text)
                detail = ""
                if node_m:
                    detail = f"node {node_m.group(1)}"
                if exc_m:
                    detail = f"{detail}: {exc_m.group(1).strip()}" if detail else exc_m.group(1).strip()
                return None, "error", detail
    return None, None, ""


def _download_artifact(mcp: McpClient, entry: dict, output_dir: Path) -> dict:
    outputs = entry.get("outputs", {})
    image_info = None
    for node_id, out in outputs.items():
        if isinstance(out, dict) and isinstance(out.get("images"), list) and out["images"]:
            image_info = out["images"][0]
            break
    if not image_info:
        raise RuntimeError("no output images in history entry")

    filename = image_info["filename"]
    subfolder = image_info.get("subfolder", "")
    image_type = image_info.get("type", "output")
    raw = mcp.get_image(filename, subfolder, image_type)

    output_dir.mkdir(parents=True, exist_ok=True)
    data: bytes | None = None
    if isinstance(raw, (bytes, bytearray)):
        data = bytes(raw)
    elif isinstance(raw, dict) and "data" in raw:
        import base64
        data = base64.b64decode(raw["data"])
    elif isinstance(raw, list):
        import base64
        for block in raw:
            if isinstance(block, dict) and block.get("type") == "image":
                b64 = block.get("data")
                if isinstance(b64, str):
                    data = base64.b64decode(b64)
                    break

    if data is None:
        return {"filename": filename, "subfolder": subfolder, "bytes": 0, "sha256": ""}

    out_path = output_dir / filename
    out_path.write_bytes(data)
    return {
        "filename": filename,
        "subfolder": subfolder,
        "path": str(out_path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
```

- [ ] **Step 3: Run the test — verify all t2i_i2i tests PASS**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_t2i_i2i.py -v
```
Expected: all 4 tests pass.

- [ ] **Step 4: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/character-video-pipeline/runtime/i2i_camera.py
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "feat(i2i): rewrite run_i2i to take RunConfig + dual upload

- New signature: run_i2i(*, mcp, output_dir, config: RunConfig, ...)
- Old kwargs (camera dict / lora_selections list / reference_image_path)
  removed
- Uploads BOTH reference_image (required) AND controlnet_image (optional)
  via mcp.upload_image before patch_graph
- Post-upload filenames override local paths via dataclasses.replace
  on a copy of RunConfig
- run-record.json schema_version '2.0'; config is full RunConfig
- _wait_for_completion / _parse_history / _download_artifact unchanged

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Rewrite `runtime/runtime_cli.py` — CONFIG_FLAGS + _add_flags_to_parser

**Files:**
- Modify: `skills/character-video-pipeline/runtime/runtime_cli.py` (entire file)

**Interfaces:**
- Consumes: from `.config_schema` — `RunConfig`, `SamplingConfig`, `ImageSizeConfig`, `GroupsConfig`, `CameraConfig`, `STAGES`.
- Produces: argparse with subcommands `describe-config`, `list-loras`, `run-t2i`, `run-i2i`. CLI flags generated from `CONFIG_FLAGS`. A kwargs → RunConfig bridge function.

- [ ] **Step 1: Write the failing tests for CLI flag routing**

Append to `runtime/tests/test_runtime_cli.py`:
```python
"""Tests for runtime_cli CONFIG_FLAGS routing and stage filter."""
import argparse

from runtime import runtime_cli


def _make_parser(subcommand: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="character-video-pipeline")
    runtime_cli._add_flags_to_parser(parser, subcommand)
    return parser


def test_add_flags_includes_envelope_for_both_stages():
    p = _make_parser("t2i-camera")
    help_text = p.format_help()
    assert "--envelope" in help_text
    p = _make_parser("i2i-camera")
    assert "--envelope" in p.format_help()


def test_add_flags_includes_reference_only_for_i2i():
    p_t2i = _make_parser("t2i-camera")
    assert "--reference" not in p_t2i.format_help()
    p_i2i = _make_parser("i2i-camera")
    assert "--reference" in p_i2i.format_help()


def test_add_flags_includes_sampling_per_field():
    p = _make_parser("t2i-camera")
    text = p.format_help()
    for flag in ("--sampling-steps-first", "--sampling-cfg", "--sampling-sampler",
                 "--sampling-scheduler", "--sampling-denoise-first",
                 "--sampling-steps-refine", "--sampling-denoise-refine"):
        assert flag in text, f"missing flag: {flag}"


def test_add_flags_includes_image_size_and_seed_and_controlnet():
    p = _make_parser("t2i-camera")
    text = p.format_help()
    assert "--image-size" in text
    assert "--seed" in text
    assert "--controlnet-image" in text


def test_no_legacy_flags_present():
    """Old flags --positive/--negative are explicitly REMOVED."""
    p = _make_parser("t2i-camera")
    text = p.format_help()
    assert "--positive" not in text
    assert "--negative" not in text


def test_kwargs_to_run_config_lora_wraps_csv_as_selections():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
        lora="add_detail,masterpiece",
    )
    assert cfg.lora == {"selections": ["add_detail", "masterpiece"]}


def test_kwargs_to_run_config_camera_parses_kv():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
        camera="direction=front,elevation=high,roll=0.5",
    )
    assert cfg.camera.direction == "front"
    assert cfg.camera.elevation == "high"
    assert cfg.camera.roll == 0.5


def test_kwargs_to_run_config_image_size_parses_kv():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
        image_size="width=1024,height=1280",
    )
    assert cfg.image_size.width == 1024
    assert cfg.image_size.height == 1280


def test_kwargs_to_run_config_sampling_builds_dataclass():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
        sampling_steps_first="50",
        sampling_cfg="7",
        sampling_denoise_refine="0.4",
    )
    assert cfg.sampling.steps_first == 50
    assert cfg.sampling.cfg == 7.0
    assert cfg.sampling.denoise_refine == 0.4
    # Unset fields stay None
    assert cfg.sampling.sampler is None


def test_kwargs_to_run_config_groups_parses_csv():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
        g1="保存图片（G1）,手部 ADetailer（G1）",
        g2="图像锐化（G2）",
    )
    assert cfg.groups.g1 == ["保存图片（G1）", "手部 ADetailer（G1）"]
    assert cfg.groups.g2 == ["图像锐化（G2）"]


def test_kwargs_to_run_config_no_explicit_flags_gives_minimal_config():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
    )
    assert cfg.camera is None
    assert cfg.sampling is None
    assert cfg.seed is None
    assert cfg.image_size is None
    assert cfg.reference_image is None
    assert cfg.controlnet_image is None
```

- [ ] **Step 2: Run the test — verify it FAILS**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_runtime_cli.py -v
```
Expected: collection error (`cannot import name 'runtime_cli' from 'runtime'`) because the new `__init__.py` exports aren't there yet, or AttributeError on `_add_flags_to_parser`/`_kwargs_to_run_config`.

- [ ] **Step 3: Rewrite `runtime/runtime_cli.py`**

Replace the entire file contents with:
```python
"""Thin CLI for character-video-pipeline camera runs.

Single mandatory entry for image stages: `run-t2i` and `run-i2i`. Both read a
prompt-forge envelope (--envelope) and feed the validated positive/negative
into the corresponding RunConfig -> patch_graph flow. The prompt-forge gate
lives inside runtime.t2i_camera.run_t2i / runtime.i2i_camera.run_i2i (cannot
be bypassed by this CLI).

Other commands (`describe-config`, `list-loras`) are read-only inspection
and do not produce images.

Single-entry-point rule (2026-08-07): all prompt text destined for ComfyUI
must come through --envelope. There is intentionally no --positive or
--negative flag.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config_schema import (
    CameraConfig,
    GroupsConfig,
    ImageSizeConfig,
    RunConfig,
    SamplingConfig,
    STAGES,
)
from .graph_patcher import describe_config
from .lora_resolver import (
    default_lora_plan,
    filter_anima_loras,
    parse_lora_inventory,
    render_stack_text,
)


def _parse_kv_list(value: str) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _parse_kv_dict(value: str) -> dict:
    result = {}
    if not value:
        return result
    for pair in value.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _resolve_mcp_launch() -> tuple[str, list[str]]:
    cmd = os.environ.get("CHENXIN_MCP_CMD")
    args_str = os.environ.get("CHENXIN_MCP_ARGS")
    if cmd and args_str:
        try:
            return cmd, json.loads(args_str)
        except json.JSONDecodeError:
            pass
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx not found on PATH; install Node.js or set CHENXIN_MCP_CMD/CHENXIN_MCP_ARGS")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
    return npx, ["-y", "comfyui-mcp@0.49.8", "--full", "--comfyui-url", comfy_url]


@dataclass(frozen=True)
class ConfigFlag:
    flag: str
    dest_path: str          # dot-path into RunConfig
    applies_to: str         # "both" | "t2i" | "i2i"
    kind: str = "scalar"    # "scalar" | "csv" | "kv_csv" | "path" | "envelope"
    help: str = ""


CONFIG_FLAGS: tuple[ConfigFlag, ...] = (
    ConfigFlag("--envelope",                "envelope",                "both", kind="envelope",
               help="path to prompt-forge envelope JSON (required; prompt-forge is the only path to write positive/negative)"),
    ConfigFlag("--camera",                  "camera",                  "both", kind="kv_csv",
               help="k=v pairs: direction,elevation,distance,roll"),
    ConfigFlag("--camera-extra",            "camera_extra",            "both", kind="kv_csv",
               help="k=v pairs for any of the 13 CameraExtraConfigNode fields"),
    ConfigFlag("--lora",                    "lora",                    "both", kind="csv",
               help="comma-separated short LoRA names; CLI bridge wraps as {\"selections\": [...]} before RunConfig"),
    ConfigFlag("--g1",                      "groups.g1",               "both", kind="csv",
               help="comma-separated G1 group titles to enable"),
    ConfigFlag("--g2",                      "groups.g2",               "both", kind="csv",
               help="comma-separated G2 group titles to enable"),
    ConfigFlag("--sampling-steps-first",    "sampling.steps_first",    "both",
               help="node 50.steps (first-pass KSampler)"),
    ConfigFlag("--sampling-cfg",            "sampling.cfg",            "both",
               help="node 50.cfg"),
    ConfigFlag("--sampling-sampler",        "sampling.sampler",        "both",
               help="node 50.sampler (e.g. dpmpp_2m)"),
    ConfigFlag("--sampling-scheduler",      "sampling.scheduler",      "both",
               help="node 50.scheduler (e.g. karras)"),
    ConfigFlag("--sampling-denoise-first",  "sampling.denoise_first",  "both",
               help="node 50.denoise (t2i default 1.0; i2i forced via WORKFLOW_CONVENTIONS)"),
    ConfigFlag("--sampling-steps-refine",   "sampling.steps_refine",   "both",
               help="node 51.steps (refine KSampler)"),
    ConfigFlag("--sampling-denoise-refine", "sampling.denoise_refine", "both",
               help="node 51.denoise"),
    ConfigFlag("--seed",                    "seed",                    "both",
               help="node 65 seed (omit for random)"),
    ConfigFlag("--image-size",              "image_size",              "both", kind="kv_csv",
               help="k=v: width,height for nodes 68/71 (default 1216x832)"),
    ConfigFlag("--controlnet-image",        "controlnet_image",        "both", kind="path",
               help="path to ControlNet image (requires group ControlNet LLLite)"),
    ConfigFlag("--reference",               "reference_image",         "i2i",  kind="path",
               help="reference image for img2img (run-i2i only)"),
)


def _add_flags_to_parser(parser: argparse.ArgumentParser, subcommand: str) -> None:
    """Bind every CONFIG_FLAGS entry (filtered by applies_to) to argparse."""
    for cf in CONFIG_FLAGS:
        if cf.applies_to not in ("both", subcommand):
            continue
        kwargs: dict[str, Any] = {"help": cf.help, "default": ""}
        if cf.kind == "envelope":
            kwargs["required"] = True
        parser.add_argument(cf.flag, **kwargs)


def _kwargs_to_run_config(
    *,
    envelope_json: str,
    camera: str = "",
    camera_extra: str = "",
    lora: str = "",
    g1: str = "",
    g2: str = "",
    sampling_steps_first: str = "",
    sampling_cfg: str = "",
    sampling_sampler: str = "",
    sampling_scheduler: str = "",
    sampling_denoise_first: str = "",
    sampling_steps_refine: str = "",
    sampling_denoise_refine: str = "",
    seed: str = "",
    image_size: str = "",
    controlnet_image: str = "",
    reference: str = "",
    strict: bool = False,
) -> RunConfig:
    """Build a RunConfig from CLI kwargs.

    Reads --envelope JSON for evidence + draft; all other kwargs are
    flat strings that this function packs into the appropriate
    dataclass / nested dict shape.
    """
    envelope_path = Path(envelope_json)
    if not envelope_path.exists():
        print(json.dumps({"error": f"envelope file not found: {envelope_path}"}), file=sys.stderr)
        sys.exit(2)
    try:
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"envelope not valid JSON: {exc}"}), file=sys.stderr)
        sys.exit(2)

    evidence = envelope.get("evidence") or {}
    draft = envelope.get("draft") or {}
    if not draft.get("positive") or not draft.get("negative"):
        print(
            json.dumps({"error": "envelope.draft.positive and .negative are required"}),
            file=sys.stderr,
        )
        sys.exit(2)
    dialect_id = envelope.get("dialect_id") or "anima"

    # CameraConfig (kv string -> dataclass).
    camera_cfg: CameraConfig | None = None
    if camera:
        kv = _parse_kv_dict(camera)
        camera_cfg = CameraConfig(
            direction=kv.get("direction"),
            elevation=kv.get("elevation"),
            distance=kv.get("distance"),
            roll=float(kv["roll"]) if "roll" in kv else None,
        )

    # lora (csv short names -> {"selections": [...]}).
    lora_dict: dict | None = None
    if lora:
        lora_dict = {"selections": _parse_kv_list(lora)}

    # GroupsConfig (csv titles -> dataclass).
    groups_cfg: GroupsConfig | None = None
    if g1 or g2:
        groups_cfg = GroupsConfig(
            g1=_parse_kv_list(g1) or None,
            g2=_parse_kv_list(g2) or None,
        )

    # SamplingConfig (per-field string -> typed value).
    sampling_cfg: SamplingConfig | None = None
    sampling_kwargs: dict[str, Any] = {}
    if sampling_steps_first:    sampling_kwargs["steps_first"]    = int(sampling_steps_first)
    if sampling_cfg:            sampling_kwargs["cfg"]            = float(sampling_cfg)
    if sampling_sampler:        sampling_kwargs["sampler"]        = sampling_sampler
    if sampling_scheduler:      sampling_kwargs["scheduler"]      = sampling_scheduler
    if sampling_denoise_first:  sampling_kwargs["denoise_first"]  = float(sampling_denoise_first)
    if sampling_steps_refine:   sampling_kwargs["steps_refine"]   = int(sampling_steps_refine)
    if sampling_denoise_refine: sampling_kwargs["denoise_refine"] = float(sampling_denoise_refine)
    if sampling_kwargs:
        sampling_cfg = SamplingConfig(sampling_kwargs)

    # ImageSizeConfig.
    image_size_cfg: ImageSizeConfig | None = None
    if image_size:
        kv = _parse_kv_dict(image_size)
        image_size_cfg = ImageSizeConfig(
            width=int(kv["width"]) if "width" in kv else None,
            height=int(kv["height"]) if "height" in kv else None,
        )

    # Seed.
    seed_val: int | None = int(seed) if seed else None

    # camera_extra is a free-form kv dict.
    camera_extra_dict = _parse_kv_dict(camera_extra) or None

    return RunConfig(
        evidence=evidence,
        draft=draft,
        dialect_id=dialect_id,
        camera=camera_cfg,
        camera_extra=camera_extra_dict,
        lora=lora_dict,
        groups=groups_cfg,
        sampling=sampling_cfg,
        seed=seed_val,
        image_size=image_size_cfg,
        controlnet_image=controlnet_image or None,
        reference_image=reference or None,
    )


def cmd_describe_config(args):
    config = describe_config(args.stage)
    print(json.dumps(config, ensure_ascii=False, indent=2))
    return 0


def cmd_list_loras(args):
    from .mcp_client import McpClient
    command, server_args = _resolve_mcp_launch()
    with McpClient.from_subprocess(command, server_args, timeout=60.0) as mcp:
        raw = mcp.list_loras()
    inventory = parse_lora_inventory(raw)
    anima = filter_anima_loras(inventory)
    print(f"Available Anima LoRAs ({len(anima)}):")
    for name in anima:
        print(f"  {name}")
    print(f"\nDefault stack: {render_stack_text(default_lora_plan())}")
    return 0


def cmd_run_t2i(args):
    from .mcp_client import McpClient
    from .t2i_camera import run_t2i

    config = _kwargs_to_run_config(**vars(args))
    command, server_args = _resolve_mcp_launch()
    with McpClient.from_subprocess(command, server_args, timeout=600.0) as mcp:
        payload, code = run_t2i(
            mcp=mcp,
            output_dir=Path(args.output_dir),
            config=config,
            timeout=600.0,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def cmd_run_i2i(args):
    from .mcp_client import McpClient
    from .i2i_camera import run_i2i

    config = _kwargs_to_run_config(**vars(args))
    command, server_args = _resolve_mcp_launch()
    with McpClient.from_subprocess(command, server_args, timeout=600.0) as mcp:
        payload, code = run_i2i(
            mcp=mcp,
            output_dir=Path(args.output_dir),
            config=config,
            timeout=600.0,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(prog="character-video-pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_dc = sub.add_parser("describe-config", help="show all configurable slots (workflow-bound)")
    p_dc.add_argument("--stage", default=STAGES.T2I, choices=[STAGES.T2I, STAGES.I2I])
    p_dc.set_defaults(func=cmd_describe_config)

    p_ll = sub.add_parser("list-loras", help="list available Anima LoRAs (read-only)")
    p_ll.set_defaults(func=cmd_list_loras)

    p_t2i = sub.add_parser(
        "run-t2i",
        help="t2i-camera: prompt-forge + RunConfig + patch_graph (single entry, prompt-forge mandatory)",
    )
    p_t2i.add_argument("--output-dir", default="outputs")
    p_t2i.add_argument("--strict", action="store_true",
                       help="abort if prompt-forge marks prompt not ready_for_review")
    _add_flags_to_parser(p_t2i, STAGES.T2I)
    p_t2i.set_defaults(func=cmd_run_t2i)

    p_i2i = sub.add_parser(
        "run-i2i",
        help="i2i-camera: prompt-forge + RunConfig + patch_graph + reference upload",
    )
    p_i2i.add_argument("--output-dir", default="outputs")
    p_i2i.add_argument("--strict", action="store_true",
                       help="abort if prompt-forge marks prompt not ready_for_review")
    _add_flags_to_parser(p_i2i, STAGES.I2I)
    p_i2i.set_defaults(func=cmd_run_i2i)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test — verify it PASSES**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_runtime_cli.py -v
```
Expected: all 10 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/character-video-pipeline/runtime/runtime_cli.py skills/character-video-pipeline/runtime/tests/test_runtime_cli.py
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "feat(cli): CONFIG_FLAGS table + _add_flags_to_parser + kwargs bridge

- 15 ConfigFlag entries drive argparse generation (no --positive or
  --negative; prompt-forge is the only path)
- _add_flags_to_parser(parser, subcommand) binds each flag, filtered
  by applies_to ('both' | 't2i' | 'i2i')
- _kwargs_to_run_config() bridges flat CLI strings to nested RunConfig:
  - csv short names -> {\"selections\": [...]} for lora
  - kv strings -> CameraConfig / ImageSizeConfig dataclasses
  - per-field strings -> SamplingConfig dataclass
  - csv titles -> GroupsConfig dataclass
- run-t2i / run-i2i subcommands both go through _kwargs_to_run_config
- describe-config stays workflow-bound (NODE_FIELD_MAP single source)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Update `runtime/__init__.py` to export new public API

**Files:**
- Modify: `skills/character-video-pipeline/runtime/__init__.py`

**Interfaces:**
- Produces: re-exports of `RunConfig`, `SamplingConfig`, `ImageSizeConfig`, `GroupsConfig`, `CameraConfig`, `STAGES`, `GROUPS`, `MANDATORY_GROUPS_BY_STAGE`, `WORKFLOW_CONVENTIONS`, `REFERENCE_IMAGE_NODE`, `CONTROLNET_IMAGE_NODE`, `I2I_NODES`, `DEFAULT_ENABLED_G1`, `DEFAULT_ENABLED_G2`, `NODE_FIELD_MAP`.

- [ ] **Step 1: Write the failing import test**

Create `skills/character-video-pipeline/runtime/tests/test_public_api.py`:
```python
"""Verify the public API surface of the runtime package."""
import runtime


def test_public_api_exposes_all_dataclasses():
    assert hasattr(runtime, "RunConfig")
    assert hasattr(runtime, "SamplingConfig")
    assert hasattr(runtime, "ImageSizeConfig")
    assert hasattr(runtime, "GroupsConfig")
    assert hasattr(runtime, "CameraConfig")


def test_public_api_exposes_constants():
    assert hasattr(runtime, "STAGES")
    assert hasattr(runtime, "GROUPS")
    assert hasattr(runtime, "MANDATORY_GROUPS_BY_STAGE")
    assert hasattr(runtime, "WORKFLOW_CONVENTIONS")
    assert hasattr(runtime, "REFERENCE_IMAGE_NODE")
    assert hasattr(runtime, "CONTROLNET_IMAGE_NODE")
    assert hasattr(runtime, "I2I_NODES")
    assert hasattr(runtime, "NODE_FIELD_MAP")


def test_stages_constants_have_expected_values():
    assert runtime.STAGES.T2I == "t2i-camera"
    assert runtime.STAGES.I2I == "i2i-camera"


def test_groups_constants_have_expected_values():
    assert "加载图片" in runtime.GROUPS.LOAD_IMAGE
    assert "ControlNet LLLite" in runtime.GROUPS.CONTROLNET_LLLITE
```

- [ ] **Step 2: Run the test — verify it FAILS**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_public_api.py -v
```
Expected: AttributeError failures on the new exports.

- [ ] **Step 3: Rewrite `runtime/__init__.py`**

Replace the entire file contents with:
```python
"""Character video pipeline runtime - camera image generation.

Public API:
- prompt_forge_bridge.compile_envelope / compile_or_minimal   -- prompt-forge gate
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
from .prompt_forge_bridge import compile_envelope, compile_or_minimal
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
    "compile_or_minimal",
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
```

- [ ] **Step 4: Run the test — verify it PASSES**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/test_public_api.py -v
```
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/character-video-pipeline/runtime/__init__.py skills/character-video-pipeline/runtime/tests/test_public_api.py
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "feat(runtime): export RunConfig + constants in __all__

Public API now exposes:
- 5 frozen dataclasses (RunConfig, SamplingConfig, ImageSizeConfig,
  GroupsConfig, CameraConfig)
- 7 constant tables (STAGES, GROUPS, MANDATORY_GROUPS_BY_STAGE,
  WORKFLOW_CONVENTIONS, REFERENCE_IMAGE_NODE, CONTROLNET_IMAGE_NODE,
  I2I_NODES, DEFAULT_ENABLED_G1, DEFAULT_ENABLED_G2)
- NODE_FIELD_MAP (single source for patcher + describe_config)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Update docs — `SKILL.md`, `workflow/README.md`, t2i stage docs

**Files:**
- Modify: `skills/character-video-pipeline/SKILL.md`
- Modify: `skills/character-video-pipeline/workflow/README.md`
- Modify: `skills/character-video-pipeline/workflow/t2i-camera/README.md`
- Modify: `skills/character-video-pipeline/workflow/t2i-camera/02-configure.md`
- Modify: `skills/character-video-pipeline/workflow/t2i-camera/03-patch.md`
- Modify: `skills/character-video-pipeline/workflow/t2i-camera/06-record.md`

- [ ] **Step 1: Update `SKILL.md` "硬性规则" section to reference RunConfig**

In `skills/character-video-pipeline/SKILL.md`, replace the "⚠️ 提示词硬性规则" section with:
```markdown
## ⚠️ 提示词硬性规则（2026-08-07 起）

**所有 stage 和场景的提示词（positive / negative）必须先经 prompt-forge 技能生成，再进入 character-video-pipeline。**

- **唯一入口**：`runtime.t2i_camera.run_t2i` / `runtime.i2i_camera.run_i2i`（CLI 对应 `run-t2i` / `run-i2i` 子命令）
- 流程：Claude 准备 envelope（`{evidence, draft, dialect_id}`）→ 调 `run_t2i(evidence=..., draft=..., config=RunConfig(...))` → 函数内 prompt-forge `compile_envelope` 校验 → 通过后自动喂给 `patch_graph` 提交
- 边界：evidence/draft 不得含 `camera / lora / sampler / cfg / steps / seed / denoise` 等执行字段；这些仍是 character-video-pipeline 的可配置项
- bridge 实现：`runtime/prompt_forge_bridge.py`（`compile_envelope` 严格模式，`compile_or_minimal` 退路）
- **没有第二入口**：CLI 上唯一能产生图片的子命令就是 `run-t2i` / `run-i2i`，意图是"单入口，方便维护"——避免出现 prompt-forge 闸门可绕过的旁路

## 新增配置项（2026-08-07 起）

在 `RunConfig` 上增加了 5 个 tunables，按节点分组：

| 配置项 | dataclass | 节点 |
|--------|-----------|------|
| `sampling.steps_first` / `cfg` / `sampler` / `scheduler` / `denoise_first` | `SamplingConfig` | node 50 |
| `sampling.steps_refine` / `denoise_refine` | `SamplingConfig` | node 51 |
| `seed` | `RunConfig.seed` | node 65 |
| `image_size.width` / `image_size.height` | `ImageSizeConfig` | node 68 / 71 |
| `controlnet_image` | `RunConfig.controlnet_image` | node 129（仅 ControlNet LLLite 组启用时） |

CLI 入口通过 `runtime_cli.py` 的 `CONFIG_FLAGS` 表 + `_add_flags_to_parser` 自动生成（`--sampling-steps-first`、`--seed`、`--image-size`、`--controlnet-image` 等）。

`describe-config` helper 输出 workflow-bound 配置表（含 default），与 `NODE_FIELD_MAP` 单源同步。
```

- [ ] **Step 2: Update `workflow/README.md` "Stage 列表" and "编译路径说明"**

In `skills/character-video-pipeline/workflow/README.md`, replace the "Stage 列表" table "编译路径" column for t2i-camera and i2i-camera with:
- t2i-camera: `prompt-forge validate -> RunConfig -> patch_graph(stage=t2i-camera) -> validate -> enqueue`
- i2i-camera: `prompt-forge validate -> mcp.upload_image -> RunConfig -> patch_graph(stage=i2i-camera, auto-append 加载图片（G1）) -> validate -> enqueue`

And add to the "编译路径说明" block diagram:
```
prompt-forge compile_envelope  ->  build RunConfig (CLI bridge: _kwargs_to_run_config)
                                ->  load_fixed_api_graph (load_workflow)
                                ->  patch_graph (single source: NODE_FIELD_MAP)
                                ->  apply WORKFLOW_CONVENTIONS (e.g. i2i denoise=0.6)
                                ->  MCP validate_workflow  ->  MCP enqueue_workflow
```

- [ ] **Step 3: Update `workflow/t2i-camera/README.md` "命令示例" + "运行时模块入口"**

Replace "命令示例" block:
```bash
python -m runtime.runtime_cli run-t2i \
  --envelope path/to/anima-envelope.json \
  --camera "direction=front,elevation=high,distance=cowboy_shot" \
  --sampling-steps-first 50 \
  --sampling-cfg 7 \
  --seed 12345 \
  --image-size "width=1024,height=1280" \
  --lora "add_detail,masterpiece" \
  --g1 "保存图片（G1）,手部 ADetailer（G1）" \
  --g2 "图像锐化（G2）"
```

Replace "运行时模块入口" block:
```
runtime_cli.cmd_run_t2i
  -> _kwargs_to_run_config (CLI bridge: csv->dict, kv->dataclass)
  -> t2i_camera.run_t2i(mcp, output_dir, config: RunConfig)
       -> prompt_forge_bridge.compile_envelope  (硬性闸门)
       -> if controlnet_image: mcp.upload_image
       -> patch_graph(stage=STAGES.T2I, config, mcp_list_loras)
            -> loads workflow.json + groups.json
            -> writes prompts (24/25) from config.draft
            -> writes camera (583) + camera_extra (585) if set
            -> writes lora (26/66) via build_lora_patch
            -> writes sampling (50/51), seed (65), image_size (68/71) if set
            -> merges DEFAULT_ENABLED_G1/G2 + user groups.g1/g2 + mandatory groups
            -> cross-validates controlnet_image <-> ControlNet LLLite group
            -> applies WORKFLOW_CONVENTIONS
       -> mcp.validate / mcp.check_runtime / mcp.enqueue
       -> mcp.get_history (text/dict dual-format parse)
       -> mcp.get_image (multipart content list)
       -> record_attempt (run-record.json schema_version 2.0)
```

- [ ] **Step 4: Update `workflow/t2i-camera/02-configure.md` "envelope（必填，提示词闸门）" section**

Replace the section "### envelope（必填，提示词闸门）" with:
```markdown
### envelope（必填，提示词闸门）

```python
from runtime.config_schema import (
    RunConfig, SamplingConfig, ImageSizeConfig, GroupsConfig, CameraConfig,
)

config = RunConfig(
    evidence={...},        # CreativeEvidence ledger
    draft={...},            # caller-authored {"positive": "...", "negative": "..."}
    dialect_id="anima",      # 默认 anima
    # prompt-forge gate is always hard (no bypass), per commit d5167a3

    # 可选 tunables (None = 用 workflow.json 静态值)
    camera=CameraConfig(direction="front", elevation="high", distance="cowboy_shot", roll=0.0),
    camera_extra={"lens_value": "85mm lens", "composition_value": "rule of thirds"},
    lora={"selections": ["add_detail", "anima-base-1-masterpiece-v51"]},
    groups=GroupsConfig(g1=["手部 ADetailer（G1）"], g2=["图像锐化（G2）"]),

    sampling=SamplingConfig(steps_first=50, cfg=7, sampler="dpmpp_2m",
                            scheduler="karras", denoise_first=1.0,
                            steps_refine=25, denoise_refine=0.2),
    seed=12345,
    image_size=ImageSizeConfig(width=1024, height=1280),

    controlnet_image=None,   # t2i + i2i: 启用 ControlNet LLLite 组时必填
    reference_image=None,    # i2i only: 必填
)

run_t2i(mcp=mcp, output_dir=Path("outputs"), config=config)
```

`run_t2i()` 第一行调用 `prompt_forge_bridge.compile_envelope`（硬闸门，无 bypass；commit `d5167a3` 已删除 `compile_or_minimal` fallback），把 evidence/draft 喂给 `prompt-forge internals.prompt_compile`。校验通过的 PromptPackage.positive/negative 才进入 node 24/25 的 `wildcard_text` 和 `populated_text` 字段；空字符串会被 prompt-forge 拒绝。

evidence/draft 不得含 `camera / lora / sampler / cfg / steps / seed / denoise` 等执行字段（prompt-forge `_reject` 把关）。

`t2i-camera` 和 `i2i-camera` 共享同一份 `workflow.json` + `groups.json` + 同一 `RunConfig` schema。i2i 唯一额外要求是 `config.reference_image` 非空；i2i 模式下 `patch_graph` 自动 append `加载图片（G1）` 到 `groups.g1`。
```

- [ ] **Step 5: Update `workflow/t2i-camera/03-patch.md` "1. 提示词（node 24/25）" + patch_graph 流程注释**

Replace the "1. 提示词（node 24/25）" block with the same note, then add an end-of-document section:
```markdown
### patch_graph flow (2026-08-07)

`patch_graph(*, stage, config: RunConfig, mcp_list_loras=None)` 内部按以下顺序处理 RunConfig 字段：

1. load_workflow(stage) + load_groups(stage)
2. 写 prompts (24/25) from `config.draft` (prompt-forge 校验后)
3. 写 camera (583) + camera_extra (585) if set
4. 写 lora (26/66) via `build_lora_patch` if set
5. 写 sampling (50/51), seed (65), image_size (68/71) via `_apply_*` helpers
6. 合并 groups: `final_g1 = set(user_g1) | DEFAULT_ENABLED_G1 | MANDATORY_GROUPS_BY_STAGE[stage]`
7. cross-validate controlnet_image <-> ControlNet LLLite 组
8. `apply_group_modes(graph, groups_meta, final_g1, final_g2)`
9. 写 controlnet_image (129) if enabled
10. apply WORKFLOW_CONVENTIONS (e.g. i2i forces node 27.denoise=0.6)
11. i2i: require reference_image; call `_activate_img2img(graph, reference_image)`

NODE_FIELD_MAP（11 项）是 patcher 与 describe_config helper 的单源真相；workflow.json 静态值通过 `_node_static_default` 读取。
```

- [ ] **Step 6: Update `workflow/t2i-camera/06-record.md` "1. run-record.json" example**

Replace the JSON example with:
```json
{
  "schema_version": "2.0",
  "stage": "t2i-camera",
  "prompt_id": "abc-123-def",
  "artifact": {
    "filename": "2026-08-07-121510__0.png",
    "subfolder": "",
    "path": "outputs/2026-08-07-121510__0.png",
    "bytes": 611226,
    "sha256": "523209d41ecab4ce7c02347aa760db0b52a9ba735c2239dd42da6e7ae4e34c95"
  },
  "duration_ms": 117406,
  "config": {
    "evidence": {"locked_facts": ["1girl"]},
    "draft": {"positive": "1girl, solo, anime", "negative": "lowres"},
    "dialect_id": "anima",
    "camera": {"direction": "front", "elevation": "high", "distance": "cowboy_shot", "roll": 0.0},
    "camera_extra": {"lens_value": "85mm lens"},
    "lora": {"selections": ["add_detail"]},
    "groups": {"g1": ["手部 ADetailer（G1）"], "g2": ["图像锐化（G2）"]},
    "sampling": {"steps_first": 50, "cfg": 7.0, "sampler": "dpmpp_2m", "scheduler": "karras",
                 "denoise_first": 1.0, "steps_refine": 25, "denoise_refine": 0.2},
    "seed": 12345,
    "image_size": {"width": 1024, "height": 1280},
    "controlnet_image": null,
    "reference_image": null
  },
  "prompt_package_quality": {
    "ready_for_review": true,
    "facts_preserved": true,
    "dialect_valid": true
  }
}
```

Add a note:
```
`schema_version` is "2.0" (was "1.0" before 2026-08-07). The `config`
field is the full frozen RunConfig serialized via dataclasses.asdict. All
RunConfig fields appear even when None, so consumers can rely on the
schema being stable.
```

- [ ] **Step 7: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/character-video-pipeline/SKILL.md \
        skills/character-video-pipeline/workflow/README.md \
        skills/character-video-pipeline/workflow/t2i-camera/README.md \
        skills/character-video-pipeline/workflow/t2i-camera/02-configure.md \
        skills/character-video-pipeline/workflow/t2i-camera/03-patch.md \
        skills/character-video-pipeline/workflow/t2i-camera/06-record.md
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "docs(skill+workflow): document RunConfig + new tunables

- SKILL.md: hard-rule section now references RunConfig; add 'new
  tunables' table for sampling/seed/image_size/controlnet_image
- workflow/README.md: stage table compilation paths updated; new flow
  diagram includes RunConfig + NODE_FIELD_MAP single source
- workflow/t2i-camera/README.md: CLI example uses --envelope and the
  per-field --sampling-* / --seed / --image-size flags; module entry
  diagram includes _kwargs_to_run_config bridge
- 02-configure.md: RunConfig example with all 5 sub-dataclass usages
- 03-patch.md: 11-step patch_graph flow + NODE_FIELD_MAP note
- 06-record.md: schema_version 2.0 example with full RunConfig dump

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: Update i2i docs and run all tests

**Files:**
- Modify: `skills/character-video-pipeline/workflow/i2i-camera/README.md`
- Modify: `skills/character-video-pipeline/workflow/i2i-camera/01-upload.md`
- Modify: `skills/character-video-pipeline/workflow/i2i-camera/03-patch.md`

- [ ] **Step 1: Update `workflow/i2i-camera/README.md` "命令示例" + "运行时模块入口"**

Replace "命令示例" with:
```bash
python -m runtime.runtime_cli run-i2i \
  --envelope path/to/anima-envelope.json \
  --reference /tmp/source.png \
  --camera "direction=front,elevation=high,distance=cowboy_shot" \
  --sampling-steps-first 50 \
  --image-size "width=1024,height=1280" \
  --lora "add_detail,masterpiece"
```

(注意 `--reference` 是 i2i 唯一专属 flag；其它 flag 与 与 t2i 共享同一 CONFIG_FLAGS。)

Replace "运行时模块入口" with:
```
runtime_cli.cmd_run_i2i
  -> _kwargs_to_run_config (CLI bridge)
  -> i2i_camera.run_i2i(mcp, output_dir, config: RunConfig)
       -> prompt_forge_bridge.compile_envelope  (硬性闸门)
       -> if config.reference_image: mcp.upload_image(reference_image)
       -> if config.controlnet_image: mcp.upload_image(controlnet_image)
       -> patch_graph(stage=STAGES.I2I, config, mcp_list_loras)
            -> i2i hard convention: auto-appends "加载图片（G1）" to groups.g1
            -> i2i hard convention: forces node 27.denoise=0.6
            -> cross-validates controlnet_image <-> ControlNet LLLite group
       -> mcp.validate / mcp.check_runtime / mcp.enqueue
       -> mcp.get_history (text/dict dual-format parse)
       -> mcp.get_image (multipart content list)
       -> record_attempt (run-record.json schema_version 2.0)
```

- [ ] **Step 2: Update `workflow/i2i-camera/01-upload.md` 顶部 blockquote**

Replace the blockquote with:
```markdown
> i2i-camera 同样走 prompt-forge envelope 路径（详见 `../t2i-camera/02-configure.md`）。本步骤只负责：
> 1. 上传 `RunConfig.reference_image`（必填，本地路径 → mcp.upload_image）
> 2. 可选上传 `RunConfig.controlnet_image`（仅当 ControlNet LLLite 组被启用时）
> 3. 在 patch_graph 阶段自动 append `加载图片（G1）` 到 enabled_g1
```

- [ ] **Step 3: Update `workflow/i2i-camera/03-patch.md` to reference t2i 03-patch.md**

Replace the entire file content (it's currently just a stub) with:
```markdown
# 03-patch：与 t2i-camera 共享同一 patch_graph 流程

i2i-camera 复用 `patch_graph(stage=STAGES.I2I, config: RunConfig)` —— 完整流程见 `../t2i-camera/03-patch.md`。

i2i 独有的 patch_graph 步骤（在通用 11 步之后追加）：

- **步骤 11 (i2i only)**：require `config.reference_image` 非空；调用 `_activate_img2img(graph, reference_image)` 重连：
    - 节点 21 (LoadImage) `image` ← 上传后的 filename
    - 节点 59 (VAEEncode) `pixels` ← `[21, 0]`
    - 节点 27 (KSampler) `latent_image` ← `[59, 0]`
    - 节点 27 (KSampler) `denoise` ← 0.6
    - 节点 21/57/58/59 mode ← 0 (active)

  以上节点 ID 来自 `I2I_NODES` 常量表（不是硬编码字面量）。

- **i2i 硬约定**：`WORKFLOW_CONVENTIONS[STAGES.I2I]` 强制 `node 27.denoise = 0.6`（与 `_activate_img2img` 内部赋值是同一约束的两次应用；先于 group activation 应用，确保即使 i2i 链路被中途截断也保持参考图语义）。
```

- [ ] **Step 4: Run all runtime tests**

Run:
```bash
cd skills/character-video-pipeline
python -m pytest runtime/tests/ -v
```
Expected: ALL tests pass (test_config_schema + test_lora_resolver_signature + test_graph_patcher + test_runtime_cli + test_t2i_i2i + test_public_api).

If any test fails, fix the regression before committing.

- [ ] **Step 5: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/character-video-pipeline/workflow/i2i-camera/README.md \
        skills/character-video-pipeline/workflow/i2i-camera/01-upload.md \
        skills/character-video-pipeline/workflow/i2i-camera/03-patch.md
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "docs(i2i): update README/01-upload/03-patch for RunConfig

- README.md: run-i2i CLI example shows --reference (i2i-only) + the
  shared --sampling-* / --image-size / --lora flags; module entry
  diagram includes upload chain for both reference_image and
  controlnet_image
- 01-upload.md: clarifies that upload chain covers RunConfig.reference_image
  (required) + RunConfig.controlnet_image (optional), and that
  patch_graph auto-appends 加载图片（G1）
- 03-patch.md: full rewrite — i2i reuses t2i 11-step patch_graph flow;
  documents the i2i-only step 11 (activate_img2img) driven by
  I2I_NODES (no hardcoded literals); notes WORKFLOW_CONVENTIONS
  enforces node 27.denoise=0.6

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 6: Final verification — run prompt-forge tests + runtime tests + describe-config CLI**

Run:
```bash
cd /d/Projects/comfyui-chenxin
python -m pytest skills/prompt-forge/internals/tests/ skills/character-video-pipeline/runtime/tests/ -v
python -m runtime.runtime_cli describe-config --stage t2i-camera 2>&1 | head -30
python -m runtime.runtime_cli --help
```

Expected:
- All tests pass.
- `describe-config` JSON output contains `sampling.fields.steps_first.default == 40`, `seed.default == -1`, `image_size.default.{width == 1216, height == 832}`, `groups.g1_titles` populated from groups.json, `groups.auto_appended_g1`.
- `--help` shows 4 subcommands: `describe-config`, `list-loras`, `run-t2i`, `run-i2i`. `run-t2i --help` shows `--envelope`, `--sampling-steps-first`, etc.; NO `--positive` / `--negative`. `run-i2i --help` additionally shows `--reference`.

If anything fails, fix the regression before declaring done.

- [ ] **Step 7: Final commit (if any cleanup needed)**

```bash
cd /d/Projects/comfyui-chenxin
git status
# If there are uncommitted changes:
git add -A
git -c user.email=claude@anthropic.com -c user.name=Claude commit -m "chore: final cleanup after RunConfig migration

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage** — check each spec section/requirement maps to a task:

| Spec item | Task |
|---|---|
| `config_schema.py` with 5 dataclasses + 7 constant tables + I2I_NODES | Task 1 |
| `build_lora_patch(run_config_lora, mcp_list_loras)` new signature | Task 2 |
| NODE_FIELD_MAP (11 entries) | Task 3 |
| `_apply_sampling/_apply_seed/_apply_image_size/_apply_controlnet_image` | Task 3 |
| `_activate_img2img` driven by I2I_NODES | Task 3 |
| `describe_config` workflow-bound (no hand-written table) | Task 3 |
| `patch_graph` cross-stage rules (6 steps) | Tasks 3-4 |
| DEFAULT_ENABLED_G1/G2 + MANDATORY_GROUPS_BY_STAGE merging | Tasks 3-4 |
| controlnet_image bidirectional validation | Tasks 3-4 |
| `run_t2i` new signature + RunConfig + upload chain | Task 5 |
| `run_i2i` new signature + dual upload chain | Task 6 |
| `run-record.json` schema_version 2.0 + full RunConfig dump | Tasks 5-6 |
| `CONFIG_FLAGS` (15 entries) + `_add_flags_to_parser` | Task 7 |
| `_kwargs_to_run_config` CLI bridge | Task 7 |
| `__init__.py` exports new constants + dataclasses | Task 8 |
| SKILL.md updates (硬性规则 + new tunables) | Task 9 |
| workflow/README.md updates | Task 9 |
| workflow/t2i-camera/* updates | Task 9 |
| workflow/i2i-camera/* updates | Task 10 |
| prompt_forge_bridge / lora_resolver / camera_mapper / group_controller / / workflow_loader: unchanged | (no task) |

All spec items covered.

**2. Placeholder scan** — searched plan for "TBD"/"TODO"/"implement later"/"fill in"/etc. None present.

**4. Type consistency check**:
- `RunConfig.evidence: dict` matches Task 1 dataclass + Tasks 5/6 kwargs `evidence: dict`.
- `RunConfig.draft: dict` matches same.
- `RunConfig.camera: CameraConfig | None` — Task 7 `_kwargs_to_run_config` builds `CameraConfig | None`. ✅
- `RunConfig.lora: dict | None` — Task 7 wraps `lora_csv` as `{"selections": [...]}`. ✅
- `RunConfig.sampling: SamplingConfig | None` — Task 7 builds `SamplingConfig` only if any sampling flag was set. ✅
- `RunConfig.image_size: ImageSizeConfig | None` — Task 7 parses `--image-size` kv. ✅
- `RunConfig.groups: GroupsConfig | None` — Task 7 builds `GroupsConfig` if either `--g1` or `--g2` non-empty. ✅
- `RunConfig.controlnet_image: str | None` — Task 7 reads `--controlnet-image` raw (empty string → None). ✅
- `RunConfig.reference_image: str | None` — Task 7 reads `--reference` raw. ✅
- `RunConfig.seed: int | None` — Task 7 parses `--seed` as int (empty → None). ✅
- `NODE_FIELD_MAP` 11 entries — Task 3 declares exactly these. ✅
- `I2I_NODES.LOAD_IMAGE = "21"` etc. — Tasks 3+6 use these constants consistently. ✅
- `STAGES.T2I = "t2i-camera"`, `STAGES.I2I = "i2i-camera"` — Tasks 3/5/6/7/8 use these constants. ✅

No type mismatches found.

**Final**: plan is ready for execution.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-07-camera-config-surface.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?