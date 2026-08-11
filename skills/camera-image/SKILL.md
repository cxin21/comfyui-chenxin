---
name: camera-image
description: |
  Use proactively for any Anima camera still-image request (text-to-image or image-to-image) on local ComfyUI. Handles LoRA selection, ControlNet, group-controlled workflow features, configuration validation, and real output execution through the fixed release asset pipeline. Load this skill immediately when the user asks to generate, render, or iterate on a camera image - do not bypass it by calling generic ComfyUI tools directly.
---

# camera-image

Generate one Anima camera still through the unified `comfyui-chenxin-mcp` tools.
The skill has exactly two stages:

- `t2i-camera`: prompt plus optional workflow features.
- `i2i-camera`: reference image plus prompt and optional workflow features.

Read [the canonical flow](../../docs/camera-image-flow.md) when changing the
workflow, compiler, execution contract, or acceptance tests.

## Non-negotiable rules

1. Use the fixed UI source asset:
   `camera_image/runtime/workflow_assets/camera-anima.json`.
2. Use `workflow/{stage}/groups.json` as the group membership contract.
3. Treat the source UI graph as a complete superset. Nodes in disabled groups
   are valid source nodes; do not delete them or reinterpret them as errors.
4. Apply configuration and group modes to the UI graph before conversion.
5. Convert the selected UI graph exactly once with MCP `strip_workflow`.
6. Validate the resulting API graph before enqueueing it.
7. Never save a temporary workflow, load an API snapshot as the runtime source,
   rewire the stripped graph, silently skip invalid groups, or add a legacy
   compatibility path.
8. Fail closed when a required input, group dependency, node reference, output
   connection, model, MCP capability, or artifact check is invalid.

## Public MCP contract

Use the four unified tools:

| Tool | Purpose |
|---|---|
| `list_skills` | Confirm `camera-image` and its stages are registered. |
| `describe_config` | Read the current stage schema, defaults, groups, and dependencies. |
| `validate_config` | Check the envelope and dependency rules without rendering. |
| `run_skill` | Compile, validate, execute, wait, download, and record the result. |

`validate_config` and `run_skill` take the same `envelope` and `config` shape.
The server converts the JSON config into the internal `RunConfig`; direct
engine callers must perform that conversion themselves.

## Required input contract

Both stages require an envelope with non-empty prompt fields:

```json
{
  "profile_id": "anima.miaomiao-harem.anima-1.5",
  "prompt": {
    "positive": "score_9, score_8_up, 1girl, anime portrait, cinematic lighting",
    "negative": "low quality, bad anatomy"
  }
}
```

`i2i-camera` additionally requires `config.reference_image`.
Image paths are local input paths; the engine uploads them first and writes the
returned ComfyUI filename into the UI graph.

Use `describe_config` for the complete current config surface. Common fields:

- `camera`, `camera_extra`
- `sampling`, `seed`, `image_size`
- `lora.selections`
- `groups.g1`, `groups.g2`
- `controlnet_image`
- `reference_image` for `i2i-camera`

`lora.selections` is a list of dicts (NOT bare strings — the old list[str]
shape was removed in v0.1.5). Each entry requires `name`; `strength_model`
and `strength_clip` default to 1.0 if omitted. Examples:

```python
config.lora = {
    "selections": [
        {"name": "GUOMAN", "strength_model": 0.8},            # model 0.8, clip = 0.8
        {"name": "add_detail", "strength_model": 0.6,
         "strength_clip": 0.4},                              # differential strength
        {"name": "anima-base-1-masterpiece-v51", "active": False},  # skip this LoRA
    ]
}
# Empty list or missing key = use the default 3-LoRA stack (all strength 1.0).
```

Do not put execution fields such as `seed`, `steps`, `cfg`, `sampler`,
`denoise`, `camera`, or `lora` into Prompt Forge `evidence` or `prompt`.

## Group semantics

Groups are compile-time feature selections. The final enabled set is the union
of default groups, user groups, and stage-mandatory groups.

- `i2i-camera` automatically enables the image-loading group.
- ControlNet requires both `controlnet_image` and the ControlNet group.
- Enabling a group requires all of its declared dependencies.
- An unknown group title fails before compilation.
- A group member missing from the fixed UI source fails before compilation.

The source graph may contain bypassed groups. Only the selected API graph must
be executable and closed.

## Execution gates

The engine executes this exact sequence:

```text
prompt-forge gate
  -> upload declared images
  -> ComfyUI health / queue guard
  -> load fixed UI source
  -> write config to UI widgets
  -> apply group modes
  -> strip UI to API once
  -> validate API graph structure
  -> validate workflow with ComfyUI MCP
  -> check local runtime
  -> enqueue {"workflow": api_graph}
  -> reject returned node errors
  -> poll history
  -> download and hash the image
  -> write run record and submitted graph
```

The final API graph must have resolved node references and at least one valid
image output. The output must come from the designated workflow output path,
not from an arbitrary history entry.

## Stage-specific invariants

### `t2i-camera`

- No reference image is required.
- ControlNet is valid only when its group and uploaded control image are both
  present.
- LoRA is written to the ordinary serializable `lora_syntax` input of the
  `LoRA Text Loader (LoraManager)` node before strip.

### `i2i-camera`

- `reference_image` is required and uploaded before compilation.
- The source UI branch selects the reference latent before strip.
- The compiled graph must route the VAE-encoded reference to the first
  sampler and use `denoise=0.6`.
- ControlNet and LoRA may be enabled together; both complete subgraphs must
  remain connected to the sampler.

### ControlNet

The enabled graph must retain the complete contract:

```text
control image -> ControlNet path -> AnimaLLLiteApply
model patch loader -> AnimaLLLiteApply.model_patch
                         -> sampler -> output
```

The model patch is a real graph link, not a post-conversion insertion.


The live acceptance gate must include real PNG output and submitted-graph
assertions for:

1. basic text-to-image;
2. basic image-to-image;
3. text-to-image with custom LoRA;
4. text-to-image with ControlNet;
5. text-to-image with LoRA plus ControlNet;
6. image-to-image with LoRA plus ControlNet.

Do not report success from validation alone. A successful run requires a
non-empty artifact, a valid image file, a recorded submitted API graph, and
correct feature-specific connections.
