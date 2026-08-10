# Usage

## Boundaries

`prompt-forge` authors and audits prompt text. `camera-image` consumes the
validated prompt envelope and owns ComfyUI/MCP compilation, execution, and
artifact verification.
`camera-multiview` consumes the same engine envelope but exposes only two image
inputs and executes its bundled fixed API workflow.
`camera-video` consumes the same engine envelope and exposes three fixed
MiniMax H3 stages: text-to-video, single-reference image-to-video, and
three-reference image-to-video.

Prompt Forge does not inspect models, nodes, workflows, GPU state, or
execution. Media skills do not silently rewrite prompt content or invent a
fallback workflow.

## Install and runtime readiness

Assume ComfyUI is already running at `http://127.0.0.1:8188` with the models
and custom nodes required by the selected fixed workflow installed.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

Prompt Forge has no mandatory preflight. Before a production run, validate the
selected skill configuration and its declared local runtime requirements at
the execution boundary.

## camera-image request flow

1. Call `list_skills` and confirm `camera-image` is registered.
2. Call `describe_config` for the selected stage.
3. Build an envelope whose authored draft has non-empty prompt fields, an
   ordered `structure` covering the selected dialect dimensions, and exact
   `tags` for the Anima dialect.
4. Put execution controls in `config`, not in the prompt envelope.
5. Call `validate_config` with the same envelope/config shape used by `run_skill`.
6. Stop on validation errors.
7. Call `run_skill`.
8. Accept the result only when `accepted=true`, the PNG exists, the hash is
   present, and the run record and submitted graph are available.

The detailed compiler and acceptance contract is
[`camera-image-flow.md`](camera-image-flow.md).
For the fixed multiview flow, use [`camera-multiview-flow.md`](camera-multiview-flow.md).
For video, use [`camera-video-flow.md`](camera-video-flow.md).

## camera-multiview request flow

1. Call `list_skills` and confirm `camera-multiview` exposes `multiview`.
2. Call `describe_config`; it must expose only `full_body_image` and
   `face_image`.
3. Supply both local image paths in `config`.
4. Call `validate_config` with the same envelope and config used for execution.
5. Stop on validation or fixed-asset errors.
6. Call `run_skill` and accept the result only when history succeeds, all saved
   PNG artifacts are present, and the submitted graph is recorded.

### Minimal multiview request

```json
{
  "skill": "camera-multiview",
  "stage": "multiview",
  "envelope": {
    "evidence": {"locked_facts": []},
    "draft": {
      "positive": "fixed multiview workflow, cinematic lighting, anime style",
      "negative": "none",
      "tags": ["solo"],
      "structure": [
        {"name": "subject", "text": "fixed multiview workflow"},
        {"name": "action_or_pose", "text": "multiview"},
        {"name": "scene", "text": "cinematic"},
        {"name": "lighting", "text": "cinematic lighting"},
        {"name": "style", "text": "anime style"}
      ]
    },
    "dialect_id": "anima"
  },
  "config": {
    "full_body_image": "E:/images/person-full-body.png",
    "face_image": "E:/images/person-face.png"
  },
  "output_dir": "outputs/camera-multiview"
}
```

Do not add groups, LoRA, ControlNet, sampler values, dimensions, seed, or
workflow JSON to this request. Those values are fixed by the bundled API asset.

## camera-video request flow

1. Call `list_skills` and confirm the requested video stage is registered.
2. Call `describe_config`; it must expose only the fields listed by the stage.
3. Supply a non-empty prompt, a duration from 2 through 15 seconds, and the
   required local reference image paths for the selected stage.
4. Call `validate_config` with the same envelope and config used for execution.
5. Stop on validation or fixed-asset errors.
6. Call `run_skill` and accept the result only when ComfyUI history succeeds,
   the submitted graph contains the exact patched values, and every saved MP4
   is present with byte count and SHA-256.

### Minimal text-to-video request

```json
{
  "skill": "camera-video",
  "stage": "t2v-video",
  "envelope": {
    "evidence": {"locked_facts": []},
    "draft": {},
    "dialect_id": "minimax_h3"
  },
  "config": {"prompt": "a person walking in afternoon light", "duration": 4},
  "output_dir": "outputs/camera-video"
}
```

Use `reference_image_1` for `i2v-video`; use all three
`reference_image_1`, `reference_image_2`, and `reference_image_3` for
`multi-i2v-video`. Do not pass workflow JSON, groups, LoRA, ControlNet, or
model/runtime overrides.

The video skill does not expose a UI workflow or a group-selection phase. Its
three API assets are selected by stage and are hash-locked; the only request
transformation is writing the declared fields and uploaded filenames.

## Minimal T2I request

```json
{
  "skill": "camera-image",
  "stage": "t2i-camera",
  "envelope": {
    "evidence": {"locked_facts": []},
    "draft": {
      "positive": "1girl, masterpiece, anime portrait, cinematic lighting, anime style",
      "negative": "lowres, bad anatomy",
      "tags": ["1girl", "solo"],
      "structure": [
        {"name": "subject", "text": "1girl"},
        {"name": "action_or_pose", "text": "portrait"},
        {"name": "scene", "text": "cinematic"},
        {"name": "lighting", "text": "cinematic lighting"},
        {"name": "style", "text": "anime style"}
      ]
    },
    "dialect_id": "anima"
  },
  "config": {
    "seed": 42,
    "sampling": {"steps_first": 30, "cfg": 4.5},
    "image_size": {"width": 1216, "height": 832}
  },
  "output_dir": "outputs"
}
```

## Minimal I2I request

Use the same envelope and add a local `reference_image` path:

```json
{
  "stage": "i2i-camera",
  "config": {
    "reference_image": "C:/images/reference.png"
  }
}
```

The engine uploads the image, selects the reference latent branch before strip,
and enforces the stage denoise contract.

## Feature requests

- LoRA: `config.lora.selections`.
- ControlNet: `config.controlnet_image` plus the exact ControlNet group title
  returned by `describe_config`.
- Other optional features: enable their group and satisfy the dependency rules
  returned by `describe_config`.

Do not pass full workflow JSON to the public config surface. Do not use a local
workflow file as an alternative runtime source.
