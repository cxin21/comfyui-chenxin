---
name: camera-video
description: |
  Use proactively for any MiniMax H3 text-to-video or image-reference-to-video request on local ComfyUI (single-image or three-image reference). The three locked release workflows (t2v / i2v-single / i2v-multi) only expose prompt, duration, and reference image fields. Load this skill immediately on any video generation request - do not bypass with generic ComfyUI tools.
---

# camera-video

Use the skill as a closed, fixed-workflow executor. Read the detailed
contract in [`docs/camera-video-flow.md`](../../docs/camera-video-flow.md) when
you need node mappings, request examples, validation evidence, or failure
diagnosis.

## Select exactly one stage

| Stage | Required config |
|---|---|
| `t2v-video` | `prompt`, `duration` |
| `i2v-video` | `prompt`, `duration`, `reference_image_1` |
| `multi-i2v-video` | `prompt`, `duration`, `reference_image_1`, `reference_image_2`, `reference_image_3` |

Accept only a non-empty string `prompt` and a finite numeric `duration` from
2 through 15 seconds. Treat reference images as local file paths. Do not
accept any other camera-video config field; do not reuse or invent a missing
reference image. Author `prompt` with the canonical MiniMax H3 contract in
[`../prompt-forge/references/minimax-h3.md`](../prompt-forge/references/minimax-h3.md):
its production-header duration and ordered `@图片N` prefix must match the
actual config.

## Execute the fixed contract

1. Require a valid Prompt Forge evidence envelope and the selected stage. The
   actual `config.prompt` is the sole video prompt source and is compiled by
   the fixed `minimax_h3` Prompt Forge dialect; `envelope.draft` is forbidden.
   Pass only the configured duration and actual reference-image count as
   validation context; never fabricate a second structure or timeline.
2. Load the stage's hash-locked API graph from
   `camera_video/runtime/workflow_assets/manifest.json`.
3. Apply only the declared prompt, duration, and reference-image values to a
   copy of that graph.
4. Upload required local images through the shared engine and use only the
   returned ComfyUI filenames.
5. Validate the exact submitted API graph and require the local ComfyUI
   runtime.
6. Enqueue once, poll ComfyUI history to a terminal state, and download every
   saved MP4 artifact.
7. Accept success only when the artifact is non-empty and its byte count and
   SHA-256 are recorded with the submitted graph and run record.

The bundled graphs are already API-format release assets. Do not discover a
workflow, load a UI workflow, call `strip_workflow`, toggle groups, alter
models or samplers, repair connections, add a fallback, or create a runtime
compatibility branch. If a fixed asset, node, model, validator, or runtime
precondition fails, stop and report the owning boundary.

The source graphs were normalized before release to remove isolated invalid
nodes and an optional SageAttention performance node that is not a universal
runtime dependency. That release decision is not a runtime downgrade or a
permission to modify the graph during execution.
