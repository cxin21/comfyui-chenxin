---
name: camera-multiview
description: |
  Use proactively when the user asks for a fixed character multiview set (multi-pose character sheet, three-view, reference-sheet) from a full-body image and a face image. Runs the locked Flux2-Klein workflow through local ComfyUI MCP - load this skill immediately on any such request rather than improvising with generic image-generation tools.
---

# camera-multiview

Execute the single `multiview` stage with the bundled API workflow and the
bundled pose assets.

This workflow consumes only the two reference images. It has no prompt input,
so the MCP envelope must be `{}` and no prompt authoring skill is involved.

## Contract

Expose exactly two image inputs:

- `full_body_image`: local full-body image; patch only node `111.inputs.image`.
- `face_image`: local face image; patch only node `667.inputs.image`.

Keep every other workflow input fixed. In particular, do not expose or infer
group switches, prompts, samplers, LoRA, ControlNet, dimensions, seeds, or
alternate workflows.

Keep the API asset and its manifest authoritative:

`camera_multiview/runtime/workflow_assets/Flux2-Klein人物一键多视图工作流.json`

Hydrate `姿势骨架1.png` through `姿势骨架13.png` from the adjacent `pose/`
directory. Preserve this node mapping exactly:

`152,154,360,364,148,149,147,373,150,367,368,151,757`

correspond to poses `1` through `13` respectively.

## Procedure

1. Pass the project preflight gate before production execution.
2. Use `list_skills`, `describe_config`, and `validate_config` for the
   `camera-multiview` / `multiview` contract.
3. Require both local image paths. Do not accept a partial request.
4. Load the bundled API graph and verify the manifest, node topology, titles,
   node count, and fixed asset hashes.
5. Reuse an existing ComfyUI input when a fixed pose filename is already
   present; upload it only when absent.
6. Deep-copy the graph and replace only nodes `111` and `667` with the two
   uploaded user-image filenames.
7. Validate the exact graph with MCP, require the local runtime, enqueue it,
   and wait for `history` status `success`.
8. Return every saved image artifact. This stage uses `artifact_mode=all`.

## Fail closed

Do not discover a workflow at runtime, call `strip_workflow`, rewrite links,
toggle groups, repair a converted graph, fall back to an older asset, or add a
compatibility branch. If the fixed asset, mapping, or graph validation fails,
stop and report the invariant that failed. To change the contract, publish a
new fixed API asset, manifest, implementation, tests, and flow document
together.

Read [`../../docs/camera-multiview-flow.md`](../../docs/camera-multiview-flow.md)
for the full request shape, ownership boundaries, acceptance evidence, and
failure diagnosis.
