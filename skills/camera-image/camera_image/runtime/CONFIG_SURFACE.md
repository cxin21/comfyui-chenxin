# Config Surface boundary

Every production stage has two separate objects:

1. A bundled fixed JSON workflow asset, verified by SHA-256 and the pinned UI
   structure fingerprint.
2. A stage Config Surface, which contains only semantic slots that the product
   permits a caller to change.

The runtime reads declared slots and compiles local patches. It never returns a
full workflow as the configuration result. Any graph input not declared by the
surface is implementation detail. In particular, `seed`, `sampler_name`,
`sampler`, `scheduler`, `steps`, `cfg`, and similar execution controls are
forbidden surface fields. They may remain inside a fixed workflow or an
immutable execution proof, but they cannot be supplied by a stage config or
patch.

LoRA selection is an atomic unit where the workflow provides both a LoRA
loader and a TriggerWord Toggle. The inventory is refreshed through MCP before
recommendation; the selected LoRA list, strengths, active state and trigger
words are validated together. A half-updated loader/toggle pair is rejected.

The live ComfyUI library is discovery evidence and release input only. Runtime
execution uses the bundled asset and fails closed on a missing asset, hash
mismatch, fingerprint drift, missing node or unexpected node type.

## Camera UI transport

The camera asset is a ComfyUI UI workflow, so its widget-array transport is kept separate from API graph transport. `read_fixed_ui_stage_config` returns semantic values only; `compile_fixed_ui_stage_patch` applies prompts, camera widgets, reference image, the atomic LoRA/TriggerWord pair, and group controls.

The camera surface names the two real `Fast Groups Bypasser (rgthree)` controllers explicitly: `fast_groups` (node 23) and `fast_groups_post_processing` (node 90, titled `Fast Groups Bypasser Post Processing`). Their semantic group selections are compiled into the atomic group patch; the UI controller nodes themselves remain fixed workflow structure. For `shot-image`, the image-loading G1 is a pinned profile invariant. The user supplies `reference_image`; its pinned group cannot be toggled as a user group.

For `multiview`, the fixed Flux asset declares two model-only LoRA loader slots. If a multiview plan carries a LoRA selection, the enqueue boundary requires a fresh MCP inventory, matching inventory hash, and presence verification before submission. A selected `lora_plan` is compiled atomically with its active trigger words: the active words are appended only to the declared view-prompt nodes. The video asset keeps its model and LoRA chain immutable because its business surface exposes motion, timeline, reference and output timing rather than model selection; those immutable model attachments remain part of the fixed execution proof.

The host MCP mapping should expose logical `list_local_models` and `model_metadata` operations. The current local Node server provides `list_local_models(model_type="loras")`; metadata remains fail-closed when the ComfyUI model-explorer node is unavailable.


## Fixed camera helper sequence

The complete live workflow is analyzed only when the fixed asset is refreshed. The runtime path is intentionally narrow:

```python
bundle = load_fixed_camera_bundle("character-base")
current = read_fixed_camera_config(bundle)
plan = build_fixed_camera_config(
    stage="character-base",
    prompts=prompts,
    camera=camera,
    camera_extra=current["values"]["camera_extra"],
    groups=groups,
    lora_plan=lora_plan,
)
compiled = compile_fixed_camera_config(bundle, plan)
# submit compiled["api_graph"] through the existing approval/queue gate
```

`camera_extra` contains all 13 `CameraExtraConfigNode` inputs, not just the four text values. The API compiler mirrors prompts, angle values, camera-extra values, LoRA text/list, and TriggerWord Toggle values into the executable graph. This closes the UI/API gap that otherwise produces a queue-successful image from stale or empty prompt fields.

The shot-image stage uses the same fixed UI asset and a separately hashed API variant with the G1 image branch active. Its reference image remains the only image input exposed by the surface; sampler and other internal nodes stay immutable.


## Result contract

A successful image submission returns the artifact plus a structured effective-configuration snapshot. The snapshot contains `effective_config.prompts`, `camera_angle`, `camera_extra`, `lora.stack_text`, the LoRA Loader raw selection payload, TriggerWord Toggle binding values, and `config_hash`. The snapshot is built from ComfyUI history prompt data when available, so it records what executed rather than only what was requested.
