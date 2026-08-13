---
name: camera-image
description: Execute local ComfyUI Anima still-image production for text-to-image or image-to-image using the fixed camera-image workflow. Use after prompt-forge has returned a model-native Anima prompt (via compile_prompt_artifact with task="anima"), including when the request needs camera controls, image size, ControlNet, or camera-owned LoRA execution settings.
---

# Camera Image

Consume the model-native `prompt` dict from Prompt Forge and execute one fixed Anima workflow. Do not author, repair, or extract prompt text in this skill.

## Stages

- Use `t2i-camera` for a still image without a source image.
- Use `i2i-camera` with `config.reference_image` for image-to-image.

Call `describe_config`, then `validate_config`, then `run_skill`. Pass the envelope in exactly this shape:

```json
{
  "prompt": {
    "positive": "1girl, red qipao, cinematic ...",
    "negative": "lowres, bad anatomy ..."
  }
}
```

The `prompt` dict is the `prompt` field returned by `compile_prompt_artifact` with `task="anima"`. You may also pass an optional `prompt_ref` (the 32-character BuildLog ref id) instead of or alongside the prompt; when present, the server resolves and re-verifies it.

## Fixed execution boundary

1. Resolve the prompt (direct dict, or via BuildLog ref if `prompt_ref` is given).
2. Upload declared local images and use only returned ComfyUI filenames.
3. Load `camera_image/runtime/workflow_assets/camera-anima.json`.
4. Apply camera-owned runtime options and selected group modes to the UI graph.
5. Write positive/negative text to nodes 24/25.
6. Strip UI to API exactly once, then validate the exact API graph and local runtime.
7. Enqueue once, wait for terminal history, download the output, and record byte count and SHA-256.

Use `config.camera`, `camera_extra`, `sampling`, `seed`, `image_size`, `lora`, `groups`, `controlnet_image`, and stage images only as described by `describe_config`. These are camera execution settings; never copy them into the prompt dict.

Regional text-prompt groups are not supported by this prompt contract. Unknown fields, missing dependencies, invalid groups, missing nodes, or failed outputs stop execution. Do not create a bypass or fallback graph.

Read [the camera image flow](../../docs/camera-image-flow.md) for exact sequence and acceptance evidence.

## Prompt input is permissive

The `envelope.prompt` field is **not bound to any specific prompt-authoring
skill**. The camera-image skill accepts any prompt dict that the Anima model
can render — typically `{"positive": "...", "negative": "..."}` strings.
How that dict was authored is irrelevant to this skill.

- **No checksum lock.** The camera skill does not verify a content hash
  against any external source. It does not know or care whether the
  prompt was produced by Prompt Forge, by another skill, by a hand-edit,
  or by copy-paste from a tutorial.
- **`prompt_ref` is optional.** It only resolves a BuildLog ref server-side
  when one is explicitly provided in `envelope.prompt_ref`. Without it,
  the skill uses `envelope.prompt` directly, untouched.
- **No "must-call-first" check.** You may invoke camera-image without
  ever calling `compile_prompt_artifact`. Prompt Forge is **recommended**
  for quality (ledger discipline, anti-pattern scrubbing, dictionary
  preflight, aesthetic coverage), but it is **not required** by this skill.
- **No production_ready gate at this layer.** If `envelope.prompt_ref`
  is set, the server resolves it and may refuse a stale ref — that is
  a ref-liveness check, not a prompt-content seal. The camera skill
  itself never refuses a prompt based on its origin.
