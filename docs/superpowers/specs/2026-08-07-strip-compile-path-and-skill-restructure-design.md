# Strip Compile Path & Skill Restructure Design

Date: 2026-08-07
Scope: camera stages (character-base t2i + shot-image img2img), unified under `run-image`.
Status: approved (no fallback; fixed API path deleted; git revert is the safety net).

## Problem

The current compile path loads a **fixed API snapshot** (`camera-anima.api.json` /
`camera-anima-shot-image.api.json`) — a frozen export of one group configuration
— then transports widget values into it and runs `normalize_camera_api_graph` to
repair converter losses. Consequences:

1. **Group controllers do not work.** `patch_group_toggles` sets UI node modes,
   but `normalize_camera_api_graph` never reads mode, so bypassed groups still
   run. Worse, 13 of 15 G2 groups and most G1 groups are **absent from the API
   snapshot** (they were bypassed at export time), so they can never be enabled.
2. **t2i vs img2img camera coordinates diverge** (angle vs normalized vector),
   enforced by `test_camera_config_helper.py:73`.
3. The `normalize_camera_api_graph` hack (re-add lora text, reconnect output
   fallbacks, drop orphan nodes) reimplements what a proper converter already
   does.

## Root cause

ComfyUI `/prompt` accepts **only API format** (`server.py:1072` `validate_prompt`
reads `class_type`, not node `mode`). Bypass (mode=4) is a **frontend** behavior:
exclude the node and rewire downstream inputs to upstream (passthrough). The
fixed API snapshot is one such pre-converted graph, frozen at one state.

## Solution: compile from the original UI workflow via MCP strip

`comfyui-mcp` exposes `get_workflow` with `action:"strip"` (source:
`src/tools/workflow-library.ts:110`):

> "strip a workflow to a clean, flat API graph, resolving Get/Set buses,
> Reroutes, subgraph definitions, and **bypassed/muted nodes into real
> connections** ... Provide exactly one of: path, filename, or graph."

This is the maintained UI→API converter that correctly handles bypass. New
compile path:

1. `load_camera_ui_bundle(stage)` → load only the UI original
   (`camera-anima.json`) + profile. **No API snapshot.**
2. `compile_camera_ui_patch(stage, ui, stage_config)` → patch UI: prompts,
   camera, camera_extra, lora unit, **group modes** (now effective).
3. `get_workflow(filename, format="api")` MCP call → flat API graph with
   bypass resolved into real passthrough connections.
4. Submit the stripped API graph.

`patch_group_toggles` now has real effect: bypassed groups are resolved to
passthrough by strip; active groups run. All 19 G1 + 15 G2 groups are available
(the original UI workflow carries every node).

### run_image changes

- New `strip_resolver` param (mirrors `lora_resolver`). Default
  `_default_strip_resolver` spawns an MCP bridge (`mcp_spawn`) and calls
  `get_workflow` `action:"strip"` with the patched UI as `graph`. Injectable for
  offline tests.
- `_build_compiled_graph` becomes: patch UI → strip → API graph.
- img2img: the UI LoadImage node (21) widget is set to the uploaded filename
  during patch; strip maps it to the API `image` input. (No separate
  `patch_img2img_graph` API passthrough.)

### Removed (no fallback)

- Runtime loading of `camera-anima.api.json` / `camera-anima-shot-image.api.json`.
- `normalize_camera_api_graph` and the profile `api_normalization` section.
- `patch_img2img_graph` (API-layer img2img passthrough).
- `compile_fixed_camera_api_plan` transport logic.
- The `.api.json` asset files + `manifest.json` `api_assets` entries.
- `REQUIRED_WORKFLOW_TOOLS` is **left unchanged** (the multiview `execution.py` path
  still references `get_workflow`). run-image's `_default_strip_resolver` spawns a
  lightweight bridge via `_McpProcess` that requires only `get_workflow`, avoiding
  the retired-`get_workflow` handshake issue. Migrating `execution.py` to
  `get_workflow action:strip` is a follow-up, out of scope here.

### Kept

- `camera-anima.json` (UI original, single source).
- `compile_fixed_ui_stage_patch` → renamed `compile_camera_ui_patch` (UI patching).
- `patch_lora_unit`, `patch_group_toggles` (UI-level, now effective).
- `config_surface.py`, `CAMERA_CONSTRAINTS`, `describe_fixed_camera_config`.

## Skill document restructure

`SKILL.md` → thin entry: overview, preflight iron law, reading rules, stage
index (points to `workflow/`). Each stage gets a process directory under
`workflow/` with step docs.

```
skills/character-video-pipeline/
  SKILL.md                      # thin: overview + preflight gate + reading rules + stage index
  preflight-env.ps1
  workflow/
    README.md                   # stage index + shared conventions (package format, config, attempt state)
    run-image/                  # camera image run (t2i + img2img unified)
      README.md                 # flow overview + t2i/img2img branch notes
      01-preflight.md           # Step 0 env + Step 0b cross-attempt state
      02-package.md             # load PromptPackage, detect t2i/img2img, config overrides
      03-patch.md               # patch UI original: prompts/camera/camera_extra/group modes/lora
      04-strip.md               # MCP get_workflow action:strip -> flat API graph (bypass resolved)
      05-submit.md              # queue guard + submit + wait + verify history
      06-record.md              # artifact + manifest + run record + attempt state
    multiview/README.md         # structural alignment only (compile path unchanged)
    video/README.md             # structural alignment only (compile path unchanged)
  runtime/                      # refactored compile path
```

## Verification

- **Offline (sandbox):** fake `strip_resolver` returns a canned API graph; tests
  verify patch→strip→submit wiring, group-mode propagation into the patched UI,
  and that run-image no longer references the fixed API assets.
- **Host e2e (user runs; needs MCP network):** real t2i + real img2img
  generation through `get_workflow action:strip`. This is the acceptance gate for
  strip correctness on the camera-anima custom nodes (LoraManager,
  CameraAngleNode, rgthree). The sandbox cannot run strip (npx network blocked).

## Known risks

1. **strip correctness unverified in sandbox.** Cannot spawn MCP (npx network
   blocked). Offline tests use a fake resolver; real correctness is the host
   e2e gate. If strip mishandles a custom node, fix forward (no in-code
   fallback; git revert available).
2. **`get_workflow` retirement.** comfyui-mcp 0.41.0 folds `get_workflow`
   into `get_workflow action:strip`. `execution.py` (multiview path, out of
   scope) still references `mcp_tools["get_workflow"]` — noted as follow-up,
   not blocking run-image.
3. **Runtime MCP dependency.** run-image now calls MCP strip per generation
   (previously needed no MCP for the graph). Accepted: group-controller
   availability outweighs one extra MCP call.
