# Usage

## Boundaries

`prompt-forge` authors and audits prompt text. `camera-image` consumes the
validated prompt envelope and owns ComfyUI/MCP compilation, execution, and
artifact verification.

Prompt Forge does not inspect models, nodes, workflows, GPU state, or
execution. Camera-image does not silently rewrite prompt content or invent a
fallback prompt.

## Install and preflight

Assume ComfyUI is already running at `http://127.0.0.1:8188` with the Anima
checkpoint and required custom nodes installed.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
powershell -ExecutionPolicy Bypass -File skills\prompt-forge\preflight-env.ps1
```

The preflight gate must pass before changing or executing production skill code.

## camera-image request flow

1. Call `list_skills` and confirm `camera-image` is registered.
2. Call `describe_config` for the selected stage.
3. Build an envelope whose `draft.positive` and `draft.negative` are non-empty.
4. Put execution controls in `config`, not in the prompt envelope.
5. Call `validate_config` with the same envelope/config shape used by `run_skill`.
6. Stop on validation errors.
7. Call `run_skill`.
8. Accept the result only when `accepted=true`, the PNG exists, the hash is
   present, and the run record and submitted graph are available.

The detailed compiler and acceptance contract is
[`camera-image-flow.md`](camera-image-flow.md).

## Minimal T2I request

```json
{
  "skill": "camera-image",
  "stage": "t2i-camera",
  "envelope": {
    "evidence": {"locked_facts": []},
    "draft": {
      "positive": "1girl, masterpiece, anime portrait",
      "negative": "lowres, bad anatomy"
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

## Verification commands

```powershell
$root = (Get-Location).Path
Push-Location (Join-Path $root "skills/camera-image/camera_image")
$env:PYTHONPATH = (Get-Location).Path
python -m pytest runtime/tests -q
Pop-Location
$env:PYTHONPATH = $root
python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests -q
```

The live acceptance gate must cover basic T2I, basic I2I, T2I+LoRA,
T2I+ControlNet, and the LoRA+ControlNet combinations. Validation without a
real artifact is not completion.
