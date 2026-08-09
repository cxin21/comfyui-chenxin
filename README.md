# comfyui-chenxin

面向本地 ComfyUI 的提示词与图像生产插件。项目将提示词创作与实际执行
严格分开：`prompt-forge` 负责提示词契约，`camera-image` 负责 Anima
相机图像工作流的编译、执行和输出验收。

## Active skills

| Skill | 职责 | 副作用 |
|---|---|---|
| `skills/prompt-forge/SKILL.md` | CreativeEvidence、提示词生成与质量校验 | 无 |
| `skills/camera-image/SKILL.md` | T2I/I2I、LoRA、ControlNet、ComfyUI 执行与 PNG 验收 | 本地 ComfyUI/MCP |

`camera-multiview` 和 `camera-video` 目前只保留包结构，不属于本次
camera-image 运行契约。

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

运行时唯一工作流源是：

```text
skills/camera-image/camera_image/runtime/workflow_assets/camera-anima.json
```

API 快照不是运行时替代源；不保存临时工作流，不在 strip 后补线，不保留
旧接口兼容层。

## Prerequisites and install

假设 ComfyUI 已运行在 `http://127.0.0.1:8188`，且已安装 Anima 模型及
所需自定义节点。

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

详细使用方式见：

- [camera-image skill](skills/camera-image/SKILL.md)
- [camera-image canonical flow](docs/camera-image-flow.md)
- [MCP execution boundary](docs/MCP_BRIDGE.md)
- [troubleshooting](docs/TROUBLESHOOTING.md)
- [usage](docs/USAGE.md)

Prompt Forge 不安装模型、节点或工作流，也不调用 MCP。生产执行失败时
必须保留真实错误，不生成伪造成功状态。
