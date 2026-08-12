---
name: camera-image
description: Execute local ComfyUI Anima still-image production for text-to-image or image-to-image using the fixed camera-image workflow. Use after prompt-forge has returned a production_ready Anima prompt_artifact, including when the request needs camera controls, image size, ControlNet, or camera-owned LoRA execution settings.
---

# Camera Image

Consume one complete `prompt_artifact` from Prompt Forge and execute one fixed Anima workflow. Do not author, repair, or extract prompt text in this skill.

## Stages

- Use `t2i-camera` for a still image without a source image.
- Use `i2i-camera` with `config.reference_image` for image-to-image.

Call `describe_config`, then `validate_config`, then `run_skill`. Pass the envelope in exactly this shape:

```json
{
  "prompt_artifact": {
    "artifact_version": 1,
    "status": "production_ready",
    "task": "anima",
    "model": "circlestone-labs/Anima"
  }
}
```

The abbreviated object above illustrates ownership only; execution requires the complete serialized artifact, including prompt, facts, trace, exact token report, audit, knowledge hash, and artifact hash. Raw positive/negative text is not an input.

## Fixed execution boundary

1. Recompute and validate the artifact hash, task, model, status, exact-token flag, conflict state, and empty sacrificed-fact set.
2. Upload declared local images and use only returned ComfyUI filenames.
3. Load `camera_image/runtime/workflow_assets/camera-anima.json`.
4. Apply camera-owned runtime options and selected group modes to the UI graph.
5. Write artifact positive/negative text to nodes 24/25.
6. Strip UI to API exactly once, then validate the exact API graph and local runtime.
7. Enqueue once, wait for terminal history, download the output, and record byte count and SHA-256.

Use `config.camera`, `camera_extra`, `sampling`, `seed`, `image_size`, `lora`, `groups`, `controlnet_image`, and stage images only as described by `describe_config`. These are camera execution settings; never copy them into Prompt Forge or the `prompt_artifact`.

Regional text-prompt groups are not supported by this artifact contract. Unknown fields, missing dependencies, changed artifacts, invalid groups, missing nodes, or failed outputs stop execution. Do not create a bypass or fallback graph.

Read [the camera image flow](../../docs/camera-image-flow.md) for exact sequence and acceptance evidence.
