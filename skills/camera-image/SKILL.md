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
| "Render this photo in the Anima camera style" | `i2i-camera` (requires `reference_image`) |
| "Use the camera workflow with ControlNet pose" | `t2i-camera` (group `ControlNet LLLite（G1）` enabled, plus `controlnet_image`) |
| "Inject a signature stamp" | `t2i-camera` (group `添加签名（G1）` enabled, plus `signature_image`) |
| "Use region prompts to mask R/G/B areas" | `t2i-camera` (group `区域提示词（G1）` enabled, plus `red_image`/`green_image`/`blue_image` and matching `red_prompt`/`green_prompt`/`blue_prompt`) |
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
    │   - registry.py     (entry-point discovery)
    ▼
camera-image entry-point   (skills/camera-image/skill_data.py)
    │   - get_skill_data() -> SkillData
    │   - function pointers: describe_fn, prepare_fn, build_config_fn
    ▼
camera_image.runtime       (skill-specific logic)
    │   - source_workflow  (UI patch + strip + upload)
    │   - graph_patcher    (format-aware tunable writer; used by source_workflow)
    │   - prompt_forge     (gate; lives in engine, not runtime)
    ▼
ComfyUI  (local @ http://127.0.0.1:8188)
```

The skill never imports `comfyui_chenxin_mcp`. The engine never imports `camera_image.runtime`. The only bridge is `camera_image/skill_data.py`, which imports the `SkillData` dataclass and provides function pointers that call into the runtime.

## The 5-step run flow

Every `run_skill` call walks the same flow. The engine in `skills/_mcp/src/comfyui_chenxin_mcp/engine/execute.py:run_skill` is the single source of truth.

```
1. compile_envelope    - prompt-forge gate; refuses if draft is not ready
2. upload stage_images - one per ImageSpec; uploads only those whose
                         group dependency is enabled or whose required flag
                         is set; replaces local path with ComfyUI filename
3. health              - mcp.health(); aborts if ComfyUI queue is not idle
4. prepare_fn          - load source UI workflow, apply RunConfig tunables
                         to widgets_values, apply G1/G2 mode toggles,
                         upload fully-patched UI to ComfyUI, return the
                         stripped API graph (config already baked in)
5. enqueue + wait      - submit prompt; poll /history/<id> for completion
6. download            - pull first image from history entry; sha256 + bytes
```

The `prepare_fn` step is the single execution-side entry point. It owns the complete UI→API transformation: it writes tunables to the **complete UI workflow** (before upload) and applies mode toggles, then ComfyUI's strip step lifts every widget value into the API dict. The engine never patches the stripped API graph separately — the API graph returned by `prepare_fn` already carries every tunable.

`apply_run_config` (in `runtime/graph_patcher.py`) is format-aware: it detects UI vs API by the shape of `graph[node_id]["inputs"]` (list = UI, dict = API) and writes to `widgets_values[index]` or `inputs[name]` accordingly. The UI→API mapping is hardcoded in `_UI_WIDGET_INDEX` against `workflow/source/文生图相机视角.json`.

Failure at any step returns `{"accepted": false, "exit_code": 1}` with a structured error. The engine writes a `run-record.json` to `outputs/runs/<stage>_<timestamp>/` on success and a `record_attempt(...)` call to the local attempt log on any path.

## Stages

### `t2i-camera`

Mandatory envelope:
- `evidence` — CreativeEvidence ledger
- `draft` — must contain non-empty `positive` and `negative` strings

Optional tunables: `camera`, `camera_extra`, `lora`, `groups`, `sampling`, `seed`, `image_size`, `controlnet_image` (requires the `ControlNet LLLite（G1）` group), `red_image`/`green_image`/`blue_image` (require the `区域提示词（G1）` group), `red_prompt`/`green_prompt`/`blue_prompt` (require the `区域提示词（G1）` group), `signature_image` (requires the `添加签名（G1）` group).

If `controlnet_image` is provided, the engine uploads it and forces the `ControlNet LLLite（G1）` group to be enabled. The dependency rule is declarative (see `Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）")`).

### `i2i-camera`

All of `t2i-camera`'s inputs, plus:

- `reference_image` — **required**, local file path. The engine uploads it to ComfyUI before queueing. Adding `加载图片（G1）` to `groups.g1` is bidirectional — enabling the group requires `reference_image`, and providing `reference_image` enables the group automatically.
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
| `red_image` | path | `null` | 区域提示词 channel Red input |
| `green_image` | path | `null` | 区域提示词 channel Green input |
| `blue_image` | path | `null` | 区域提示词 channel Blue input |
| `red_prompt` | str | `null` | node 3 (ImpactWildcardProcessor) |
| `green_prompt` | str | `null` | node 4 (ImpactWildcardProcessor) |
| `blue_prompt` | str | `null` | node 5 (ImpactWildcardProcessor) |
| `signature_image` | path | `null` | 添加签名 input |
| `groups.g1` | list[str] | defaults + auto | toggles G1 group nodes |
| `groups.g2` | list[str] | defaults | toggles G2 group nodes |

The exact source for this table is `NODE_FIELD_MAP` in `camera_image/runtime/graph_patcher.py` plus the region-prompt node ids in `_UI_WIDGET_INDEX`. There is no separate "field list" to maintain — if the field map changes, `describe_config` picks it up automatically.

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

## Dependency rules

The skill declares **10 declarative rules** in `camera_image/skill_data.py`. The engine's `validate_config` walks every rule and emits a structured error for any unmet implication. Rules are pure data, not procedural if-checks.

| # | Condition | Implies | Direction | Meaning |
|---|-----------|---------|-----------|---------|
| 1 | `config:controlnet_image` | `group:ControlNet LLLite（G1）` | bidirectional | Setting `controlnet_image` requires the group; enabling the group requires the image. |
| 2 | `stage:i2i-camera` | `group_auto:加载图片（G1）` | forward | i2i stage auto-appends the load-image group. |
| 3 | `group:加载图片（G1）` | `config:reference_image` | bidirectional | Enabling the group requires `reference_image`; providing it enables the group. |
| 4 | `group:区域提示词（G1）` | `config:red_image` | forward | The region-prompt group implies red mask image. |
| 5 | `group:区域提示词（G1）` | `config:green_image` | forward | The region-prompt group implies green mask image. |
| 6 | `group:区域提示词（G1）` | `config:blue_image` | forward | The region-prompt group implies blue mask image. |
| 7 | `group:区域提示词（G1）` | `config:red_prompt` | forward | The region-prompt group implies red channel text. |
| 8 | `group:区域提示词（G1）` | `config:green_prompt` | forward | The region-prompt group implies green channel text. |
| 9 | `group:区域提示词（G1）` | `config:blue_prompt` | forward | The region-prompt group implies blue channel text. |
| 10 | `group:添加签名（G1）` | `config:signature_image` | bidirectional | Enabling the signature group requires `signature_image`; providing it enables the group. |

`condition`/`implies` use the prefixes `config:`, `group:`, `stage:`, `group_auto:`. `group_auto:` means the engine will append the group itself (no caller work).

## Groups

The source UI workflow contains 30+ "group" containers — bundles of nodes that can be enabled or bypassed as a unit via the `mode=0` (enabled) / `mode=4` (bypassed) flag. The `groups.g1` and `groups.g2` config fields let you toggle them by title.

### Group title constants

The four canonical group titles are pinned in `runtime/config_schema.py:GROUPS`:

```python
GROUPS.LOAD_IMAGE       = "加载图片（G1）"
GROUPS.CONTROLNET_LLLITE = "ControlNet LLLite（G1）"
GROUPS.AREA_PROMPT      = "区域提示词（G1）"
GROUPS.ADD_SIGNATURE    = "添加签名（G1）"
```

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
- `添加签名（G1）` — signature stamp (requires `signature_image`)
- `区域提示词（G1）` — region-prompt masking (requires `red_image`/`green_image`/`blue_image` + `red_prompt`/`green_prompt`/`blue_prompt`)
- `ControlNet LLLite（G1）` — ControlNet pose conditioning (requires `controlnet_image`)

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

## stage_images

Each stage declares a tuple of `ImageSpec(config_key, required, requires_group)` in `skill_data.py:stage_images`. The engine uploads them **in order** before the workflow runs, replacing the local path with the ComfyUI-assigned filename on the config object the patcher sees.

### `t2i-camera` — 6 specs (none required)

| Order | config_key | required | requires_group |
|-------|------------|----------|----------------|
| 1 | `controlnet_image` | no | `ControlNet LLLite（G1）` |
| 2 | `reference_image` | no | `加载图片（G1）` |
| 3 | `red_image` | no | `区域提示词（G1）` |
| 4 | `green_image` | no | `区域提示词（G1）` |
| 5 | `blue_image` | no | `区域提示词（G1）` |
| 6 | `signature_image` | no | `添加签名（G1）` |

### `i2i-camera` — 6 specs (1 required)

| Order | config_key | required | requires_group |
|-------|------------|----------|----------------|
| 1 | `reference_image` | **yes** | (always) |
| 2 | `controlnet_image` | no | `ControlNet LLLite（G1）` |
| 3 | `red_image` | no | `区域提示词（G1）` |
| 4 | `green_image` | no | `区域提示词（G1）` |
| 5 | `blue_image` | no | `区域提示词（G1）` |
| 6 | `signature_image` | no | `添加签名（G1）` |

### Upload semantics

- A spec whose `requires_group` is **enabled** in `groups.g1` (or auto-appended for i2i's `加载图片`) becomes a real upload target.
- A spec whose group is **not enabled** is a no-op — no upload, no validation error.
- A spec marked **`required=True`** always uploads (for `i2i-camera`, `reference_image` always uploads).
- An optional spec whose group IS enabled but the path is `null` triggers the declarative Rule check (see Dependency rules) and emits a structured `validate_config` error.

## Common error paths and what to do

| Failure | Symptom | Recovery |
|---------|---------|----------|
| `prompt-forge rejected envelope` | exit_code=1, error contains `prompt-forge` | Fix `envelope.draft` (forbidden field, empty, or `ready_for_review=false`); re-run |
| `ComfyUI queue not idle` | exit_code=1, error mentions running/pending jobs | Wait for ComfyUI to drain; re-run |
| `group 'ControlNet LLLite（G1）' must be enabled` | `validate_config` returns `ok=false` | Either add the group to `groups.g1` or omit `controlnet_image` |
| `config 'reference_image' required by group '加载图片（G1）'` | `validate_config` returns `ok=false` | Provide `reference_image` as a local file path, or remove `加载图片（G1）` from `groups.g1` |
| `config 'red_image' required by group '区域提示词（G1）'` | `validate_config` returns `ok=false` | Provide all three R/G/B images + matching text prompts, or remove `区域提示词（G1）` from `groups.g1` |
| `config 'signature_image' required by group '添加签名（G1）'` | `validate_config` returns `ok=false` | Provide `signature_image` or remove the group |
| `reference_image is required for i2i-camera` | engine raises before enqueue | Pass `reference_image` as a local file path |
| `node N missing from workflow` | engine raises during `prepare_fn` | Source UI workflow is corrupt or modified; reinstall via `scripts/install.ps1` |
| `no UI widget index mapping for node N input M` | engine raises during `prepare_fn` | New tunable added but `_UI_WIDGET_INDEX` not updated; add the mapping in `runtime/graph_patcher.py` |
| `execution failed: node N: ...` | exit_code=1, history shows `status.status_str=error` | Read the node error; fix config or workflow; re-run |
| `no output images in history entry` | run completed but artifact not found | Workflow output node may have been bypassed by a group toggle; check `groups` |
| `LoRA name X is ambiguous` | `prepare_fn` raises | Use a more specific short name; substring matches must be unique |

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

### Example: region prompts + signature

```json
{
  "skill": "camera-image",
  "stage": "t2i-camera",
  "envelope": {
    "evidence":  { "locked_facts": [] },
    "draft":     { "positive": "1girl, masterpiece", "negative": "lowres" },
    "dialect_id": "anima"
  },
  "config": {
    "groups": {
      "g1": ["区域提示词（G1）", "添加签名（G1）"]
    },
    "red_image":    "C:/masks/red.png",
    "green_image":  "C:/masks/green.png",
    "blue_image":   "C:/masks/blue.png",
    "red_prompt":   "red clothing, silk",
    "green_prompt": "green leaves, foliage",
    "blue_prompt":  "blue sky, gradient",
    "signature_image": "C:/brand/sig.png",
    "camera": { "direction": "front", "distance": "medium" },
    "sampling": { "steps_first": 30, "cfg": 4.5 },
    "seed": 42
  }
}
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

- `skills/camera-image/tests/test_skill_data.py` — SkillData field validity; all 10 dependency rules match code; all 6 stage_images per stage match code; function pointers resolve against the real source workflow.
- `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_describe.py` — `describe_config` returns a schema with the expected slot names against the real source workflow.
- `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_validate.py` — declarative `Rule` checks fire in both directions; envelope shape validated; region-prompts and signature rules exercised.
- `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_execute.py` — `run_skill` flow with mocked `McpClient`; image upload order; `output_type` routing; `groups=None` and `groups.g2=None` regression coverage; stage_images walk for both stages.
- `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_server_smoke.py` — spawn the real stdio server, exercise all 4 tools against the installed `camera-image`.

Tests use the real source workflow at `skills/camera-image/workflow/source/文生图相机视角.json`; no mock workflow JSON.

## Boundary rules

These are enforced by code review and by the engine's import surface:

- `skills/_mcp/src/comfyui_chenxin_mcp/engine/*` must NOT import any `camera_image.runtime.*` module. The engine reaches the skill only via `SkillData` function pointers.
- `skills/camera-image/camera_image/runtime/*` must NOT import `comfyui_chenxin_mcp`. The runtime is pure skill logic.
- `camera_image/skill_data.py` is the only file allowed to import both — the `SkillData` dataclass from the engine, plus the function pointers from the runtime.
- `prompt_forge` lives in `engine/`, not `runtime/`. The skill calls it via the engine; it never imports it directly.
- v1 leftovers — `mcp_bridge.py`, `schema.py`, `t2i_camera.py`, `i2i_camera.py`, `validators.py`, `runtime_cli.py` — are deleted. If you see references to them, they are stale — open a doc fix PR.