# comfyui-chenxin

A local ComfyUI plugin with a strict boundary between prompt authoring and
image / video execution. `prompt-forge` owns the prompt envelope; the three
`camera-*` skills own the fixed-workflow compiler, ComfyUI execution, and
artifact verification.

## Active skills

| Skill | Responsibility | Side effects |
|---|---|---|
| `skills/prompt-forge/SKILL.md` | CreativeEvidence, prompt authoring, and quality checks | None |
| `skills/camera-image/SKILL.md` | T2I/I2I, LoRA, ControlNet, ComfyUI execution, and PNG verification | Local ComfyUI/MCP |
| `skills/camera-multiview/SKILL.md` | Fixed-pose Flux2-Klein character multiview and PNG verification | Local ComfyUI/MCP |
| `skills/camera-video/SKILL.md` | MiniMax H3 text-to-video and image-reference video and MP4 verification | Local ComfyUI/MCP |

Each `camera-*` skill owns a single fixed release asset and exposes a closed
contract; there is no runtime workflow discovery or fallback path.

## Canonical flow

```text
Prompt Forge envelope
  -> validate_config
  -> fixed source (UI for camera-image, API for camera-multiview / camera-video)
  -> group selection (camera-image only)
  -> strip_workflow once (camera-image only)
  -> final API graph validation
  -> local ComfyUI enqueue / history
  -> verified PNG or MP4 + submitted graph + run record
```

The only runtime workflow sources are:

- `skills/camera-image/camera_image/runtime/workflow_assets/camera-anima.json`
- `skills/camera-multiview/camera_multiview/runtime/workflow_assets/Flux2-Klein人物一键多视图工作流.json`
- `skills/camera-video/camera_video/runtime/workflow_assets/{minimax-h3-t2v,minimax-h3-i2v-single,minimax-h3-i2v-multi}.json`

API snapshots are not runtime alternatives. The compiler does not save a
temporary workflow, repair the graph after strip, or retain an old interface.

## Prerequisites and install

Assume ComfyUI is running at `http://127.0.0.1:8188` with the model and
required custom nodes installed for the selected fixed workflow.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

## See also

- [camera-image skill](skills/camera-image/SKILL.md)
- [camera-image canonical flow](docs/camera-image-flow.md)
- [camera-multiview skill](skills/camera-multiview/SKILL.md)
- [camera-multiview canonical flow](docs/camera-multiview-flow.md)
- [camera-video skill](skills/camera-video/SKILL.md)
- [camera-video canonical flow](docs/camera-video-flow.md)
- [MCP execution boundary](docs/MCP_BRIDGE.md)
- [troubleshooting](docs/TROUBLESHOOTING.md)
- [usage](docs/USAGE.md)
