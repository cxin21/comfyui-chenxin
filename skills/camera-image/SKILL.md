---
name: camera-image
description: Anima camera workflow consumer for t2i/i2i image generation. Invoked through the comfyui-chenxin-mcp unified tools (list_skills, describe_config, validate_config, run_skill).
status: active
side_effects: approval-gated-local-comfyui
owner: camera-image
dialect_id: anima
---

# camera-image

The `camera-image` skill runs the Anima camera workflow in a local ComfyUI server, producing single-frame stills for two stages:

- `t2i-camera` — text-to-image from a prompt only.
- `i2i-camera` — image-to-image from a reference photo plus a prompt.

Multiview character sheets and video generation are separate skills (`camera-multiview`, `camera-video`) and are out of scope here.

The skill is pure data. It does not own a CLI, a tool registry, or a transport. It declares what it can do via a `SkillData` entry-point, and the `comfyui-chenxin-mcp` engine drives it. The 4 unified MCP tools are the only entry points a host ever calls.

## When to use

| User says | Skill handles |
|-----------|---------------|
| "Generate an Anima camera-angle image of X" | `t2i-camera` |
| "Render this photo in the Anima camera style" | `i2i-camera` |
| "Use the camera workflow with ControlNet pose" | `t2i-camera` (group `ControlNet LLLite（G1）` enabled) |
| "What does the camera skill expose?" | `describe_config(skill="camera-image", stage="t2i-camera")` |
| "Validate this config before running" | `validate_config(skill, stage, config)` |

Do not invoke this skill for non-Anima checkpoints, video, or character sheet generation. Those are separate skills.

## Architecture

```
LLM host (Claude Code / Codex / OpenCode)
    │
    │  JSON-RPC 2.0 over stdio
    ▼
comfyui-chenxin-mcp server  (skills/_mcp)
    │   - 4 unified tools: list_skills, describe_config, validate_config, run_skill
    │   - engine/         (skill-agnostic execution core)
    │   - entry-points    (discovers installed skills)
    ▼
camera-image entry-point   (skills/camera-image/skill_data.py)
    │   - get_skill_data() -> SkillData
    │   - function pointers: describe_fn, apply_fn, prepare_fn, build_config_fn
    ▼
camera_image.runtime       (skill-specific logic)
    │   - source_workflow  (UI -> API strip)
    │   - graph_patcher    (tunable writer)
    │   - prompt_forge     (gate; lives in engine, not runtime)
    ▼
ComfyUI  (local @ http://127.0.0.1:8188)
```

The skill never imports `comfyui_chenxin_mcp`. The engine never imports `camera_image.runtime`. The only bridge is `camera_image/skill_data.py`, which imports the `SkillData` dataclass and provides function pointers that call into the runtime.

## The 5-step run flow

Every `run_skill` call walks the same flow. The engine in `skills/_mcp/src/comfyui_chenxin_mcp/engine/execute.py:run_skill` is the single source of truth.

```
1. compile_envelope    - prompt-forge gate; refuses if draft is not ready
2. upload stage_images - reference_image (i2i only) and/or controlnet_image
3. health              - mcp.health(); aborts if ComfyUI queue is not idle
4. prepare_fn          - copy source workflow, apply G1/G2 mode toggles,
                         upload to ComfyUI temp, get back an API graph
5. apply_fn            - write tunables (prompts, camera, lora, sampling, ...) to the graph
6. enqueue + wait      - submit prompt; poll /history/<id> for completion
7. download            - pull first image from history entry; sha256 + bytes
```

Failure at any step returns `{"accepted": false, "exit_code": 1}` with a structured error. The engine writes a `run-record.json` to `outputs/runs/<stage>_<timestamp>/` on success and a `record_attempt(...)` call to the local attempt log on any path.

## Stages

### `t2i-camera`

Mandatory envelope:
- `evidence` — CreativeEvidence ledger
- `draft` — must contain non-empty `positive` and `negative` strings

Optional tunables: `camera`, `camera_extra`, `lora`, `groups`, `sampling`, `seed`, `image_size`, `controlnet_image` (requires the `ControlNet LLLite（G1）` group).

If `controlnet_image` is provided, the engine uploads it and forces the `ControlNet LLLite（G1）` group to be enabled. The dependency rule is declarative (see `Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）")`).

### `i2i-camera`

All of `t2i-camera`'s inputs, plus:

- `reference_image` — **required**, local file path. The engine uploads it to ComfyUI before queueing.
- The `加载图片（G1）` group is **auto-appended** to `groups.g1` for this stage (you do not pass it; the engine does).

The engine's `_activate_img2img` rewires `node 27` (KSampler) to consume the VAE-encoded reference instead of an empty latent, and forces `denoise=0.6`.

## Configurable items

The full schema is returned by `describe_config(skill="camera-image", stage="t2i-camera" | "i2i-camera")`. The following table summarises every slot. Defaults come from the source UI workflow at `workflow/source/文生图相机视角.json`; `None` means "fall through to that static value".

| Slot | Type | Default | Where it lands |
|------|------|---------|----------------|
| `envelope.draft.positive` | str | **required** | node 24 (ImpactWildcardProcessor) |
| `envelope.draft.negative` | str | **required** | node 25 (ImpactWildcardProcessor) |
| `camera.direction` | enum | `"front"` | node 583 (CameraAngleNode.pos_x) |
| `camera.elevation` | enum | `"eye-level"` | node 583 (CameraAngleNode.pos_y) |
| `camera.distance` | enum | `"full_body"` | node 583 (CameraAngleNode.pos_z) |
| `camera.roll` | float `[0, 1]` | `0` | node 583 (CameraAngleNode.roll) |
| `camera_extra.*` | object | see below | node 585 (CameraExtraConfigNode) |
| `lora.selections` | list[str] | 3-LoRA default stack | nodes 26, 66 |
| `sampling.steps_first` | int | 40 | node 50 (KSampler.steps) |
| `sampling.cfg` | float | 4 | node 50 (KSampler.cfg) |
| `sampling.sampler` | str | `"dpmpp_2m"` | node 50 (KSampler.sampler) |
| `sampling.scheduler` | str | `"karras"` | node 50 (KSampler.scheduler) |
| `sampling.denoise_first` | float | 1.0 | node 50 (KSampler.denoise) |
| `sampling.steps_refine` | int | 25 | node 51 (KSampler.steps) |
| `sampling.denoise_refine` | float | 0.2 | node 51 (KSampler.denoise) |
| `seed` | int | random | node 65 |
| `image_size.width` | int | 1216 | node 68 (EmptyLatentImage.width) |
| `image_size.height` | int | 832 | node 71 (EmptyLatentImage.height) |
| `controlnet_image` | path | `null` | node 129 (Load Image ControlNet) |
| `reference_image` | path | `null` (t2i) / required (i2i) | node 21 (LoadImage) |
| `groups.g1` | list[str] | defaults + auto | toggles G1 group nodes |
| `groups.g2` | list[str] | defaults | toggles G2 group nodes |

The exact source for this table is `NODE_FIELD_MAP` in `camera_image/runtime/graph_patcher.py`. There is no separate "field list" to maintain — if the field map changes, `describe_config` picks it up automatically.

### `camera.direction` / `elevation` / `distance` enums

The semantic values are mapped to `pos_x`/`pos_y`/`pos_z` floats in `[-1, 1]` by `runtime/camera_mapper.py`. The full enum surface:

| Field | Accepted values |
|-------|-----------------|
| `direction` | `front`, `right_45`, `right`, `rear_45`, `rear`, `back`, `left_45`, `left` |
| `elevation` | `high`, `high-angle`, `eye-level`, `low`, `low-angle` |
| `distance` | `extreme_close_up`, `close_up`, `medium`, `cowboy_shot`, `full_body`, `wide` |

### `camera_extra` (node 585)

13 toggles + values. The validator in `runtime/camera_mapper.py` fills in defaults for any key you omit:

| Field | Default | Notes |
|-------|---------|-------|
| `extreme_type` | `"无"` | one of `无`, `极限俯视`, `极限仰视` |
| `extreme_weight` | 10 | non-negative number |
| `lens_enabled` | `true` | bool |
| `lens_value` | `"85mm lens"` | string |
| `dof_enabled` | `false` | bool |
| `dof_value` | `"shallow depth of field"` | string |
| `dof_weight` | 1.3 | non-negative number |
| `movement_enabled` | `false` | bool |
| `movement_value` | `"handheld camera"` | string |
| `composition_enabled` | `true` | bool |
| `composition_value` | `"rule of thirds"` | string |
| `style_enabled` | `false` | bool |
| `style_value` | `"cinematic"` | string |

## Groups

The source UI workflow contains 30+ "group" containers — bundles of nodes that can be enabled or bypassed as a unit via the `mode=0` (enabled) / `mode=4` (bypassed) flag. The `groups.g1` and `groups.g2` config fields let you toggle them by title.

### Default always-on groups

The skill keeps these on for every run, regardless of what the user passes (you cannot disable them — your `groups` selections are unioned with these, never subtracted):

| Group | Title | Effect |
|-------|-------|--------|
| G1 | `保存图片（G1）` | node 35 Image Saver writes the final PNG |
| G1 | `第二轮采样器（G1）` | node 51 KSampler runs the refine pass |
| G1 | `相机视角生图（G1）` | nodes 583 + 585 (camera angle + extras) |
| G2 | `图像锐化（G2）` | node 111 ImageSharpen |
| G2 | `对比度（G2）` | node 96 AdjustContrast |

### Stage-mandatory groups

`i2i-camera` auto-appends `加载图片（G1）` to `groups.g1`. You don't have to pass it; the engine does it for you. If you do pass it, that's fine (set union).

`t2i-camera` has no stage-mandatory groups.

### Optional toggleable groups

Every other group title in `workflow/t2i-camera/groups.json` and `workflow/i2i-camera/groups.json` is opt-in. Use `describe_config` to get the full current list (titles change with workflow updates). Common examples:

- `面部 ADetailer（G1）` — facial fixup pass
- `手部 ADetailer（G1）` — hand fixup pass
- `Detailer（瑕疵修复）（G1）` — general defect repair
- `Ultimate SD 放大器（G1）` — high-res upscaler chain
- `移除背景（G1）` — background removal

Enable by adding the title to `groups.g1` or `groups.g2`. To bypass everything not in your list, the engine already handles that — any group title not in the final enabled set gets `mode=4`.

## LoRA

The `lora` slot is a dict with one optional key, `selections`. Empty / missing / `None` falls through to the default 3-LoRA stack.

### Default 3-LoRA stack

```
<lora:anima-base-1-masterpiece-v51:1.00>
<lora:add_detail:1.00>
<lora:gpt-image-2_anima-base1_v1-1:1.00>
```

Plus trigger words: `masterpiece`, `very aesthetic`, `@gpt-image-2`.

### Custom selection

```json
{
  "lora": {
    "selections": ["add_detail", "anima-base-1-masterpiece-v51"]
  }
}
```

The resolver (`runtime/lora_resolver.py:resolve_lora_names`) accepts short names (`add_detail`) or full filenames (`Anima\add_detail.safetensors`). Matching is:

1. Exact short-name (case-insensitive) against the normalized inventory.
2. Exact full-name match.
3. Substring match (must be unique; ambiguous matches raise).

Only LoRAs in the `Anima` folder are considered. The engine calls `mcp.list_loras()` to get the inventory when `selections` is non-empty; if you do not have an MCP resolver wired up, only the default stack is allowed.

## Envelopes

An "envelope" is the input the `run_skill` tool takes for `envelope`. It is the prompt-forge dialect shape. Three top-level keys:

```json
{
  "evidence": { "locked_facts": [...], "continuity_locks": [...] },
  "draft":    { "positive": "...", "negative": "..." },
  "dialect_id": "anima"
}
```

Field discipline (enforced both locally in `_check_envelope` and again by prompt-forge):

**Forbidden in `evidence` and `draft`:** `workflow`, `node`, `hash`, `gpu`, `execution`, `mode`, `runtime`, `profile`, `camera`, `lens`, `lora`, `loras`, `checkpoint`, `sampler`, `seed`, `steps`, `cfg`, `denoise`. These belong to camera-image, not prompt-forge.

**Required in `draft`:** `positive` and `negative` must be non-empty strings.

**`dialect_id`:** the skill is `anima` (hardcoded in `SkillData.dialect_id`). Other skills will register other dialects.

The engine runs `compile_envelope(evidence, draft, "anima")` as step 1. If prompt-forge rejects the envelope (forbidden field, empty draft, `ready_for_review=false`, etc.), the run aborts with a structured error and never reaches ComfyUI.

## Common error paths and what to do

| Failure | Symptom | Recovery |
|---------|---------|----------|
| `prompt-forge rejected envelope` | exit_code=1, error contains `prompt-forge` | Fix `envelope.draft` (forbidden field, empty, or `ready_for_review=false`); re-run |
| `ComfyUI queue not idle` | exit_code=1, error mentions running/pending jobs | Wait for ComfyUI to drain; re-run |
| `controlnet_image provided but group not enabled` | `validate_config` returns `ok=false` | Either add `ControlNet LLLite（G1）` to `groups.g1` or omit `controlnet_image` |
| `reference_image is required for i2i-camera` | engine raises before enqueue | Pass `reference_image` as a local file path |
| `node N missing from workflow` | engine raises during `apply_fn` | Source UI workflow is corrupt or modified; reinstall via `scripts/install.ps1` |
| `execution failed: node N: ...` | exit_code=1, history shows `status.status_str=error` | Read the node error; fix config or workflow; re-run |
| `no output images in history entry` | run completed but artifact not found | Workflow output node may have been bypassed by a group toggle; check `groups` |
| `LoRA name X is ambiguous` | `apply_fn` raises | Use a more specific short name; substring matches must be unique |

## MCP integration

This skill is auto-discovered. After `pip install -e skills/camera-image`, the entry-point

```toml
[project.entry-points."comfyui_chenxin_mcp.skills"]
camera-image = "camera_image.skill_data:get_skill_data"
```

is registered. The MCP server picks it up at startup via `importlib.metadata.entry_points()` in `registry.discover_skills()`. No code in `skills/_mcp` needs to change to add new skills — the engine is data-driven.

### Quick MCP session

```text
list_skills()
  -> {"skills": [{"name": "camera-image", "stages": ["t2i-camera", "i2i-camera"], "output_type": "images"}]}

describe_config(skill="camera-image", stage="t2i-camera")
  -> {"stage": "t2i-camera", "workflow": "t2i-camera", "source_workflow": "...", "slots": {...}}

validate_config(skill="camera-image", stage="t2i-camera", config={...})
  -> {"ok": true, "errors": [], "stage": "t2i-camera", "skill": "camera-image"}

run_skill(skill="camera-image", stage="t2i-camera", envelope={...}, config={...}, output_dir="outputs")
  -> {"exit_code": 0, "payload": {"accepted": true, "prompt_id": "...", "artifact": {...}, "duration_ms": 12345, "run_record_path": "..."}}
```

See `skills/_mcp/README.md` for the MCP server package doc.

## Tests

```bash
# skill-level (camera-image itself)
pytest skills/camera-image/tests/

# engine-level (the shared execution core)
pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/

# combined
pytest skills/camera-image/tests/ skills/_mcp/src/comfyui_chenxin_mcp/tests/
```

What the tests cover:

- `skills/camera-image/tests/test_skill_data.py` — SkillData field validity; function pointers resolve against the real source workflow.
- `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_describe.py` — `describe_config` returns a schema with the expected slot names against the real source workflow.
- `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_validate.py` — declarative `Rule` checks fire in both directions; envelope shape validated.
- `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_execute.py` — `run_skill` flow with mocked `McpClient`; image upload order; `output_type` routing; `groups=None` and `groups.g2=None` regression coverage.
- `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_server_smoke.py` — spawn the real stdio server, exercise all 4 tools against the installed `camera-image`.

Tests use the real source workflow at `skills/camera-image/workflow/source/文生图相机视角.json`; no mock workflow JSON.

## Boundary rules

These are enforced by code review and by the engine's import surface:

- `skills/_mcp/src/comfyui_chenxin_mcp/engine/*` must NOT import any `camera_image.runtime.*` module. The engine reaches the skill only via `SkillData` function pointers.
- `skills/camera-image/camera_image/runtime/*` must NOT import `comfyui_chenxin_mcp`. The runtime is pure skill logic.
- `camera_image/skill_data.py` is the only file allowed to import both — the `SkillData` dataclass from the engine, plus the function pointers from the runtime.
- `prompt_forge` lives in `engine/`, not `runtime/`. The skill calls it via the engine; it never imports it directly.
- `mcp_bridge.py`, `schema.py`, `t2i_camera.py`, `i2i_camera.py`, `validators.py`, `runtime_cli.py` are deleted. If you see references to them, they are stale v1 leftovers — open a doc fix PR.
