---
name: camera-video
description: Execute local ComfyUI MiniMax-H3 text-to-video-with-audio or one/three-image reference-to-video-with-audio using fixed release workflows. Use after prompt-forge has returned a model-native h3_t2va or h3_ref2va prompt (via compile_h3_t2va_artifact / compile_h3_ref2va_artifact).
---

# Camera Video

Consume the model-native `prompt` dict from Prompt Forge; do not accept raw prompt text or author video fields here.

## Select one stage

| Stage | Prompt task | Required config |
|---|---|---|
| `t2v-video` | `h3_t2va` | numeric `duration` |
| `i2v-video` | `h3_ref2va` | `duration`, `reference_image_1` |
| `multi-i2v-video` | `h3_ref2va` | `duration`, `reference_image_1..3` |

Call `describe_config`, `validate_config`, then `run_skill`. The envelope contains the `prompt` dict (from compile_h3_*_artifact) and optional `prompt_ref`. `duration` is a JSON number from 2 through 15 and must equal the final audited shot end time. Reference count must equal the prompt's ordered reference set; changing a picture's owner, order, or verified dimensions invalidates the build.

## Execution

1. Resolve the prompt (direct dict, or via BuildLog ref if `prompt_ref` is given).
2. Load the stage's hash-locked API graph from `camera_video/runtime/workflow_assets/manifest.json`.
3. Upload required local images and write only returned filenames in strict order.
4. Revalidate the prompt in the graph patcher, then write only its `text`, duration, and image filenames.
5. Validate the project graph, ComfyUI graph, and local runtime.
6. Enqueue once, wait for terminal history, download every saved MP4, and record byte count and SHA-256.

Do not discover or strip a workflow, change models or samplers, add missing images, reuse one image under another label, alter duration, or create a fallback branch. Report the owning boundary when validation or execution fails.

Read [the camera video flow](../../docs/camera-video-flow.md) for node bindings and acceptance evidence.
