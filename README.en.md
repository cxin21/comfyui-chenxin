# comfyui-chenxin

A local ComfyUI plugin with a strict boundary between prompt authoring and
image execution. `prompt-forge` owns the prompt envelope; `camera-image` owns
the Anima camera workflow compiler, ComfyUI execution, and PNG verification.

## Active skills

| Skill | Responsibility | Side effects |
|---|---|---|
| `skills/prompt-forge/SKILL.md` | CreativeEvidence, prompt authoring, and quality checks | None |
| `skills/camera-image/SKILL.md` | T2I/I2I, LoRA, ControlNet, ComfyUI execution, and artifact verification | Local ComfyUI/MCP |

`camera-multiview` and `camera-video` are package placeholders and are outside
the current camera-image execution contract.

## Canonical flow

```text
Prompt Forge envelope
  -> validate_config
  -> fixed UI source + semantic config
  -> group selection
  -> strip_workflow once
  -> final API graph validation
  -> local ComfyUI enqueue/history
  -> verified PNG + submitted graph + run record
```

The only runtime workflow source is:

```text
skills/camera-image/camera_image/runtime/workflow_assets/camera-anima.json
```

API snapshots are not runtime alternatives. The compiler does not save a
temporary workflow, repair the graph after strip, or retain an old interface.

## Prerequisites and install

Assume ComfyUI is running at `http://127.0.0.1:8188` with the Anima model and
required custom nodes installed.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
powershell -ExecutionPolicy Bypass -File skills\prompt-forge\preflight-env.ps1
```

## Verification

```powershell
$root = (Get-Location).Path
Push-Location (Join-Path $root "skills/camera-image/camera_image")
$env:PYTHONPATH = (Get-Location).Path
python -m pytest runtime/tests -q
Pop-Location
$env:PYTHONPATH = $root
python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests -q
```

See:

- [`skills/camera-image/SKILL.md`](skills/camera-image/SKILL.md)
- [`docs/camera-image-flow.md`](docs/camera-image-flow.md)
- [`docs/MCP_BRIDGE.md`](docs/MCP_BRIDGE.md)
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)
- [`docs/USAGE.md`](docs/USAGE.md)
