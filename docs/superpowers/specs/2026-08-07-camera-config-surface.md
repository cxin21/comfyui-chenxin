# Camera Config Surface — 2026-08-07

## Context

The character-video-pipeline skill has a fixed ComfyUI workflow (`workflow/t2i-camera/workflow.json`, shared by t2i-camera and i2i-camera stages). Today only a small subset of node inputs are user-tunable; many inputs (sampling steps/cfg/sampler/scheduler/denoise, seed, image dimensions, ControlNet image) are locked to workflow.json static values. Users cannot express "I want a different seed" / "I want a wider image" / "I want to use ControlNet LLLite for pose guidance" without modifying the workflow file itself.

This spec exposes a curated, workflow-bound configuration surface so that:
- Sampling (nodes 50/51), seed (65), image size (68/71), and the ControlNet LLLite image (node 129) become first-class user options.
- The CLI helper `describe-config` lists every tunable, with defaults read live from workflow.json, so the surface stays in sync with the workflow.
- The user never edits the workflow to add a tunable — they only consume the published surface.
- The single-entry-point rule (all prompt text goes through prompt-forge) continues to hold.

No backwards compatibility: this spec replaces the current `patch_graph(*, positive, negative, camera, ...)` signature and the corresponding CLI flags.

## Decisions

1. **Node-grouped semantic schema** (decision §1): every tunable is a field on `RunConfig` / sub-dataclasses. The schema uses semantic names (`sampling.steps_first`, `image_size.width`) rather than raw node IDs so the surface reads naturally to humans and LLMs.
2. **Single source of truth: NODE_FIELD_MAP** (decision §3 fix): every field the patcher writes is enumerated in `NODE_FIELD_MAP` (path → `(node_id, input_field)`). The patcher, the helper, and the CLI flag table all read from this map. Adding a tunable is a one-line change.
3. **Stage-as-constant, conventions-as-table** (decision §4 fix): stage identifiers, group titles, mandatory groups per stage, workflow-level hard conventions (e.g. i2i forces `node 27.denoise = 0.6`), and per-stage reference-image / controlnet-image node ids are all tables. No string literals scattered through the patcher.
4. **CLI flags generated from CONFIG_FLAGS table** (decision §5 fix): argparse wiring is derived from a single `CONFIG_FLAGS` tuple; per-flag metadata includes `applies_to` (`"both"` / `"t2i"` / `"i2i"`), `kind` (`"scalar"` / `"csv"` / `"kv_csv"` / `"path"` / `"envelope"`), and `help` text.
5. **No backwards compatibility**: old `patch_graph(*, positive=..., camera=..., enabled_g1=..., ...)` is deleted. Old CLI flags (`--positive`, `--negative`, `--camera`, `--lora`, `--g1`, `--g2`, `--reference`) are replaced by the `CONFIG_FLAGS` schema.
6. **Workflow-bound, not hard-coded** (decision §3): `describe_config` reads NODE_FIELD_MAP + the loaded workflow.json to extract default values for every tunable. If workflow.json changes a default, the helper output updates automatically.
7. **i2i hard conventions stay enforced** (decision §4): the patcher auto-appends `加载图片（G1）` to `groups.g1` when `stage == STAGES.I2I`; reference_image is required; KSampler denoise is forced to `0.6` via `WORKFLOW_CONVENTIONS`. These are not user-configurable.

## Architecture

### Modules touched

```
skills/character-video-pipeline/runtime/
├── config_schema.py     # NEW — dataclasses + constants
├── graph_patcher.py     # rewrite: RunConfig-driven, NODE_FIELD_MAP, single-source describe_config
├── t2i_camera.py        # rewrite: construct RunConfig, call patch_graph(config=...)
├── i2i_camera.py        # rewrite: construct RunConfig (with reference_image), call patch_graph(config=...)
├── runtime_cli.py       # rewrite: CONFIG_FLAGS-driven argparse
└── __init__.py          # export RunConfig + constants + helpers
```

### Public API surface (new)

```python
from runtime import (
    # config schema
    RunConfig, SamplingConfig, ImageSizeConfig, GroupsConfig, CameraConfig,
    # constants
    STAGES, GROUPS, MANDATORY_GROUPS_BY_STAGE, WORKFLOW_CONVENTIONS,
    REFERENCE_IMAGE_NODE, CONTROLNET_IMAGE_NODE,
    # patcher + helper
    patch_graph, describe_config, NODE_FIELD_MAP,
    # existing public API (unchanged signatures)
    run_t2i, run_i2i, McpClient, compile_envelope, compile_or_minimal,
    # LoRA / camera / group helpers
    build_lora_patch, map_camera, validate_camera_extra, CAMERA_EXTRA_FIELDS,
    apply_group_modes, MODE_ACTIVE, MODE_BYPASS,
    load_workflow, load_groups, list_group_titles,
    record_attempt, parse_lora_inventory, filter_anima_loras,
    default_lora_plan, render_stack_text,
)
```

## Data flow

```
caller constructs RunConfig(evidence, draft, ...)
        │
        ▼
prompt_forge_bridge.compile_envelope(evidence, draft, dialect_id)
        │  raises on invalid envelope
        ▼
run_t2i(...) / run_i2i(...)         ← gate is enforced inside these functions
        │
        ▼
graph_patcher.patch_graph(stage=STAGES.T2I, config=RunConfig)
        │   1. load workflow + groups
        │   2. write prompts (24/25)
        │   3. write camera (583) + camera_extra (585)
        │   4. write LoRA (26/66) via build_lora_patch
        │   5. write sampling (50/51) via _apply_sampling
        │   6. write seed (65) via _apply_seed
        │   7. write image_size (68/71) via _apply_image_size
        │   8. validate controlnet_image ↔ ControlNet LLLite group
        │   9. auto-append mandatory groups for stage
        │  10. apply group modes
        │  11. write controlnet_image (129) if enabled
        │  12. apply WORKFLOW_CONVENTIONS (e.g. node 27.denoise = 0.6 for i2i)
        │  13. stage-specific activation: i2i switches KSampler latent to VAEEncode
        ▼
mcp.validate_workflow / mcp.check_runtime / mcp.enqueue / poll / download
        │
        ▼
record_attempt(success/failed) → return payload
```

## Components

### `config_schema.py`

```python
@dataclass(frozen=True)
class CameraConfig:
    direction: str | None = None    # node 583 pos_x (semantic)
    elevation: str | None = None    # node 583 pos_y
    distance:  str | None = None    # node 583 pos_z
    roll:     float | None = None   # node 583 roll

@dataclass(frozen=True)
class SamplingConfig:
    steps_first:    int | None = None     # node 50.steps
    cfg:            float | None = None   # node 50.cfg
    sampler:        str | None = None     # node 50.sampler
    scheduler:      str | None = None     # node 50.scheduler
    denoise_first:  float | None = None   # node 50.denoise
    steps_refine:   int | None = None     # node 51.steps
    denoise_refine: float | None = None   # node 51.denoise

@dataclass(frozen=True)
class ImageSizeConfig:
    width:  int | None = None   # node 68
    height: int | None = None   # node 71

@dataclass(frozen=True)
class GroupsConfig:
    g1: list[str] | None = None
    g2: list[str] | None = None

@dataclass(frozen=True)
class RunConfig:
    # prompt-forge gate (always required)
    evidence:     dict
    draft:        dict
    dialect_id:   str   = "anima"
    strict_prompt: bool = False
    # existing tunables
    camera:       CameraConfig | None = None
    camera_extra: dict | None         = None
    lora:         dict | None         = None
    groups:       GroupsConfig | None  = None
    # new tunables
    sampling:     SamplingConfig | None = None
    seed:         int | None            = None
    image_size:   ImageSizeConfig | None = None
    # stage-specific
    reference_image:   str | None = None   # i2i only
    controlnet_image: str | None = None   # iff group enabled

class STAGES:
    T2I = "t2i-camera"
    I2I = "i2i-camera"

@dataclass(frozen=True)
class GroupTitle:
    LOAD_IMAGE:         str = "加载图片（G1）"
    CONTROLNET_LLLITE:  str = "ControlNet LLLite（G1）"
GROUPS = GroupTitle()

MANDATORY_GROUPS_BY_STAGE: dict[str, list[str]] = {
    STAGES.I2I: [GROUPS.LOAD_IMAGE],
}

WORKFLOW_CONVENTIONS: dict[str, dict] = {
    STAGES.I2I: {"denoise_override": {"27": 0.6}},
}

REFERENCE_IMAGE_NODE:   dict[str, str] = {STAGES.I2I: "21"}
CONTROLNET_IMAGE_NODE: dict[str, str] = {STAGES.T2I: "129", STAGES.I2I: "129"}
```

### `graph_patcher.py`

```python
# Single source of truth — patcher and helper both read this.
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

def patch_graph(*, stage=STAGES.T2I, config: RunConfig,
                 mcp_list_loras: Callable | None = None) -> dict:
    """Apply every tunable to workflow.json. Mandatory at minimum:
    config.evidence + config.draft (prompt-forge gate is the caller's job)."""

def describe_config(stage=STAGES.T2I) -> dict:
    """Build the helper output from NODE_FIELD_MAP + workflow.json static
    values + groups.json titles. No hand-written field table."""

def _node_static_default(graph, node_id, field):
    """Read workflow.json static value for (node, input)."""

def _apply_sampling(graph, s: SamplingConfig): ...
def _apply_seed(graph, seed: int): ...
def _apply_image_size(graph, size: ImageSizeConfig): ...
def _apply_controlnet_image(graph, image_name: str): ...
def _set_prompt(graph, node_id, text): ...           # existing
def _set_camera(graph, coords): ...                    # existing
def _set_camera_extra(graph, extra): ...              # existing
def _set_lora(graph, lora_patch): ...                  # existing
def _activate_img2img(graph, image_name, ri_node="21"): ...  # existing
```

**Cross-stage rules inside `patch_graph`**:
1. Validate `controlnet_image` ↔ `GROUPS.CONTROLNET_LLLITE` (both directions):
   - `controlnet_image` provided but group not in `g1` → raise `ValueError`.
   - Group in `g1` but `controlnet_image is None` → raise `ValueError`.
2. Auto-append `MANDATORY_GROUPS_BY_STAGE[stage]` to `g1`.
3. After `apply_group_modes`, write `controlnet_image` to `CONTROLNET_IMAGE_NODE[stage]["image"]` (only when provided and group is active).
4. Apply `WORKFLOW_CONVENTIONS[stage]` (e.g. i2i forces `node 27.denoise = 0.6`).
5. i2i: require `reference_image`; call `_activate_img2img(graph, reference_image)`.

### `runtime_cli.py`

```python
@dataclass(frozen=True)
class ConfigFlag:
    flag: str
    dest_path: str          # dot-path into RunConfig
    applies_to: str         # "both" | "t2i" | "i2i"
    kind: str = "scalar"    # "scalar" | "csv" | "kv_csv" | "path" | "envelope"
    help: str = ""

CONFIG_FLAGS: tuple[ConfigFlag, ...] = (
    ConfigFlag("--envelope",                "envelope",                "both", kind="envelope"),
    ConfigFlag("--positive",                "positive_override",      "both"),
    ConfigFlag("--negative",                "negative_override",      "both"),
    ConfigFlag("--camera",                  "camera",                  "both", kind="kv_csv"),
    ConfigFlag("--camera-extra",            "camera_extra",            "both", kind="kv_csv"),
    ConfigFlag("--lora",                    "lora_selections",         "both", kind="csv"),
    ConfigFlag("--g1",                      "groups.g1",               "both", kind="csv"),
    ConfigFlag("--g2",                      "groups.g2",               "both", kind="csv"),
    ConfigFlag("--sampling-steps-first",    "sampling.steps_first",    "both"),
    ConfigFlag("--sampling-cfg",            "sampling.cfg",            "both"),
    ConfigFlag("--sampling-sampler",        "sampling.sampler",        "both"),
    ConfigFlag("--sampling-scheduler",      "sampling.scheduler",      "both"),
    ConfigFlag("--sampling-denoise-first",  "sampling.denoise_first",  "both"),
    ConfigFlag("--sampling-steps-refine",   "sampling.steps_refine",   "both"),
    ConfigFlag("--sampling-denoise-refine", "sampling.denoise_refine", "both"),
    ConfigFlag("--seed",                    "seed",                    "both"),
    ConfigFlag("--image-size",              "image_size",              "both", kind="kv_csv"),
    ConfigFlag("--controlnet-image",        "controlnet_image",        "both", kind="path"),
    ConfigFlag("--reference",               "reference_image",         "i2i",  kind="path"),
)

def _add_flags_to_parser(parser, subcommand: str) -> None:
    """Bind every CONFIG_FLAGS entry (filtered by applies_to) to argparse."""

# Subcommands: describe-config, list-loras, run-t2i, run-i2i.
# describe-config is the workflow-bound helper.
# run-t2i and run-i2i share CONFIG_FLAGS (i2i additionally gets --reference).
```

`describe-config --stage t2i-camera` output (excerpt):
```json
{
  "stage": "t2i-camera",
  "workflow": "t2i-camera",
  "slots": {
    "sampling": {
      "source": "config.sampling",
      "nodes": ["50", "51"],
      "fields": {
        "steps_first":    {"node": "50", "default": 40},
        "cfg":            {"node": "50", "default": 4},
        "sampler":        {"node": "50", "default": "dpmpp_2m"},
        "scheduler":      {"node": "50", "default": "karras"},
        "denoise_first":  {"node": "50", "default": 1.0},
        "steps_refine":   {"node": "51", "default": 25},
        "denoise_refine": {"node": "51", "default": 0.2}
      }
    },
    "seed":       {"source": "config.seed", "node": "65", "default": 665005389889224},
    "image_size": {"source": "config.image_size", "nodes": ["68", "71"],
                   "default": {"width": 1216, "height": 832}},
    "controlnet_image": {"source": "config.controlnet_image", "node": "129",
                          "required_if": "groups.g1 contains 'ControlNet LLLite（G1）'"},
    "reference_image":   {"source": "config.reference_image", "node": "21",
                          "required_if": "stage == 'i2i-camera'"},
    "groups":     {"source": "config.groups",
                   "g1_titles": [...], "g2_titles": [...],
                   "auto_appended_g1": {
                     "ControlNet LLLite（G1）": "when controlnet_image provided",
                     "加载图片（G1）": "when stage == 'i2i-camera'"
                   }}
  }
}
```

### Error table (raised → caller pattern)

| Source | Detection point | Behaviour |
|---|---|---|
| envelope missing draft.positive/negative | `compile_envelope` (prompt-forge) | `ValueError` raised; not caught by `run_t2i`/`run_i2i` (gate failed) |
| `RunConfig.draft` empty strings | `patch_graph` (in `_set_prompt`) | `ValueError("positive/negative is required")` |
| i2i missing `reference_image` | `patch_graph` (`stage == STAGES.I2I`) | `ValueError` |
| `controlnet_image` set but group not enabled | `patch_graph` cross-validation | `ValueError` |
| Group enabled but `controlnet_image` not set | `patch_graph` cross-validation | `ValueError` |
| LoRA short name not in inventory | `lora_resolver.resolve_lora_names` | `ValueError(LoRA X not found)` |
| NODE_FIELD_MAP references missing node | patcher write → KeyError | `KeyError` (workflow invariant break — fail loud) |
| MCP health / enqueue / poll / download failure | `run_t2i`/`run_i2i` outer try | `record_attempt(failed)` + return `(payload, exit_code=1)` |

## Testing

| Layer | File | Coverage |
|---|---|---|
| `config_schema` dataclasses | `runtime/tests/test_config_schema.py` | field defaults, frozen, nested dataclass access |
| `graph_patcher.NODE_FIELD_MAP` single source | `runtime/tests/test_graph_patcher.py` | every entry: helper output contains same path as patcher writes |
| `patch_graph` writes | same | each RunConfig field → workflow node input; defaults pass through when None |
| `patch_graph` cross-validation | same | controlnet_image ↔ group both directions |
| `patch_graph` mandatory group auto-append | same | i2i adds `加载图片（G1）` even when caller omits |
| `patch_graph` WORKFLOW_CONVENTIONS | same | i2i forces `node 27.denoise = 0.6`; t2i untouched |
| `describe_config` helper | same | every NODE_FIELD_MAP entry appears in output with correct default |
| `runtime_cli` flag routing | `runtime/tests/test_runtime_cli.py` | every CONFIG_FLAGS entry resolves to correct dest |
| `runtime_cli` stage filter | same | `--reference` only on run-i2i; `--controlnet-image` on both |
| `t2i_camera` / `i2i_camera` end-to-end | `runtime/tests/test_t2i_i2i.py` | health / validate / runtime / enqueue / wait / download (mcp_client mocked) |
| prompt-forge tests | `prompt-forge/internals/tests/*` | unchanged (already passing) |

## Scope

**In scope** (this implementation cycle):
1. Create `runtime/config_schema.py`.
2. Rewrite `runtime/graph_patcher.py`: `patch_graph(*, stage, config, mcp_list_loras)`; add NODE_FIELD_MAP + `_apply_*` helpers; single-source `describe_config`.
3. Rewrite `runtime/runtime_cli.py`: `CONFIG_FLAGS` table + `_add_flags_to_parser`.
4. Rewrite `runtime/t2i_camera.py` / `runtime/i2i_camera.py`: build `RunConfig` from kwargs, call `patch_graph(config=...)`.
5. Update `runtime/__init__.py` public API.
6. Add `runtime/tests/test_config_schema.py`; update existing test files to use new signatures.
7. Update docs: `SKILL.md`, `workflow/README.md`, `workflow/t2i-camera/README.md`, `workflow/t2i-camera/02-configure.md`, `workflow/t2i-camera/03-patch.md`, `workflow/t2i-camera/06-record.md`, `workflow/i2i-camera/README.md`, `workflow/i2i-camera/01-upload.md`, `workflow/i2i-camera/03-patch.md` to reflect new config surface + CLI flags.

**Out of scope** (explicit non-goals):
- ❌ Modify `prompt-forge/**` (any file).
- ❌ Modify `workflow/t2i-camera/workflow.json` or `workflow/t2i-camera/groups.json` (read-only).
- ❌ Modify comfyui-mcp / MCP protocol.
- ❌ Modify vault notes.
- ❌ Modify `.codex-plugin/plugin.json` or `scripts/install.ps1`.
- ❌ Add a `raw_nodes` escape hatch.
- ❌ Add per-LoRA `strengths` field.
- ❌ Auto-validate image_size multiples (8/64 alignment).
- ❌ Compatibility shim for old `patch_graph(*, positive=..., ...)` signature.
- ❌ Modify character-video-pipeline workflow assets.

**Preconditions for implementation**:
1. User approved this spec.
2. writing-plans skill invoked to produce the implementation plan.

## Spec self-review

- [x] No TBD / TODO / placeholder language.
- [x] RunConfig and 4 sub-dataclass fields fully specified with types.
- [x] STAGES, GROUPS, MANDATORY_GROUPS_BY_STAGE, WORKFLOW_CONVENTIONS, REFERENCE_IMAGE_NODE, CONTROLNET_IMAGE_NODE constants have explicit values.
- [x] NODE_FIELD_MAP: 11 entries enumerated.
- [x] CONFIG_FLAGS: 17 entries enumerated with `applies_to`, `kind`, `help` placeholders.
- [x] Error table covers every raise path mentioned.
- [x] Test plan maps 1:1 to scope items.
- [x] Out-of-scope list is independently verifiable (no future-decision dependencies).