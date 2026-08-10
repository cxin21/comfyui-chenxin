# comfyui-chenxin

面向本地 ComfyUI 的提示词与媒体生产插件。项目将提示词创作与实际执行
严格分开：`prompt-forge` 负责提示词契约，媒体技能负责固定工作流的编译、
执行和输出验收。

## Active skills

| Skill | 职责 | 副作用 |
|---|---|---|
| `skills/prompt-forge/SKILL.md` | CreativeEvidence、提示词生成与质量校验 | 无 |
| `skills/camera-image/SKILL.md` | T2I/I2I、LoRA、ControlNet、ComfyUI 执行与 PNG 验收 | 本地 ComfyUI/MCP |
| `skills/camera-multiview/SKILL.md` | Flux2-Klein 固定姿势人物多视图与 PNG 验收 | 本地 ComfyUI/MCP |
| `skills/camera-video/SKILL.md` | MiniMax H3 文生视频、单图参考、多图参考与 MP4 验收 | 本地 ComfyUI/MCP |

三个技能各自拥有独立的 canonical flow；`camera-image` 使用固定 UI 源，
`camera-multiview` 和 `camera-video` 直接使用已导出的固定 API 源。生产
技能不在运行时发现、转换或修复工作流。详见
[`camera-video-flow.md`](docs/camera-video-flow.md)。

## Canonical flow

### camera-image

```text
Prompt Forge envelope
  -> semantic config and group selection
  -> fixed UI source
  -> strip_workflow once
  -> validate API graph
  -> ComfyUI enqueue/history
  -> verified artifacts
```

### camera-multiview

```text
two required image paths
  -> fixed API asset and pose manifest
  -> patch nodes 111 and 667 only
  -> validate API graph
  -> ComfyUI enqueue/history
  -> download all saved PNGs
```

### camera-video

```text
prompt and optional reference image paths
  -> fixed MiniMax H3 API asset
  -> patch only prompt, duration, and declared image filenames
  -> validate API graph and local runtime
  -> ComfyUI enqueue/history
  -> download all saved MP4s
```

所有流程都禁止临时工作流、运行时发现源和兼容分支；只有
`camera-image` 有 UI-to-API 转换；`camera-multiview` 和 `camera-video` 直接
使用已导出的 API 源。运行时只写入各技能声明的配置字段。

## Prerequisites and install

假设 ComfyUI 已运行在 `http://127.0.0.1:8188`，且已安装所选技能固定
工作流所需的模型和自定义节点。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

