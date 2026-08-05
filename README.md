# comfyui-chenxin

面向本地 ComfyUI 的提示词与角色到视频生产插件。项目刻意拆成两个边界清晰的技能：`prompt-forge` 只负责由 Claude/Codex 创作并审查高质量提示词；`character-video-pipeline` 负责审批后的 ComfyUI/MCP 生产执行。

## 两个 active 技能

| 技能 | 责任 | 副作用 |
| --- | --- | --- |
| `skills/prompt-forge/SKILL.md` | CreativeEvidence、模型提示词方言、视觉风格、精确 tag 校验、PromptPackage 质量审查 | 无 |
| `skills/character-video-pipeline/SKILL.md` | 四阶段工作流发现、审批、提交、历史与资产证据 | 仅 approval-gated local ComfyUI/MCP |

Prompt Forge 不检查模型是否安装，也不读取或执行工作流；模型资料只描述提示词语言。生产技能只消费已审查的 PromptPackage，不重新创作或静默改写提示词。

## 四阶段生产路径

```text
Claude/Codex + CreativeEvidence
  -> Prompt Forge: 正向/反向基础图 PromptPackage
  -> 相机视角文生图: 正面基础图
  -> Flux2-Klein: 人物多视图设定图
  -> Prompt Forge: 镜头 PromptPackage（继承 continuity locks）
  -> 相机视角 G1 图生图: 具体镜头图
  -> Prompt Forge: 双语 LTX 视频 PromptPackage
  -> LTX Yusu Director: 视频 + history + RunRecord
```

每一阶段都必须通过 profile、工作流指纹、审批、一次性消费、history 和 artifact 校验；证据缺失时 fail closed。

## 前提与安装

假设 ComfyUI 已部署并运行在 `http://127.0.0.1:8188/`。本仓库不携带模型权重、Custom Nodes 或工作流实体；这些由外部 ComfyUI 环境和生产技能管理。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

```bash
bash scripts/install.sh
```

安装脚本只登记 MCP 配置和宿主示例，不下载模型或伪造可用能力。

## 验证

```powershell
$env:PYTHONPATH = "skills/prompt-forge"
py -3 -m pytest -q skills/prompt-forge/internals/tests
$env:PYTHONPATH = "skills/character-video-pipeline"
py -3 -m pytest -q skills/character-video-pipeline/runtime/tests
py -3 -m compileall -q skills/prompt-forge/internals skills/character-video-pipeline/runtime
```

Prompt Forge 的验证不需要 ComfyUI；live 生产测试必须显式 opt-in，并由 `character-video-pipeline` 负责。

## 文档

- [使用说明](docs/USAGE.md)
- [系统架构](docs/architecture.md)
- [MCP Bridge](docs/MCP_BRIDGE.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [Prompt Forge 规范](skills/prompt-forge/SPEC.md)
- [角色到视频技能](skills/character-video-pipeline/SKILL.md)

## 明确边界

- 不自动安装 ComfyUI、模型、Custom Nodes 或工作流。
- 不在 Prompt Forge 中调用 MCP、提交任务或保存 RunRecord。
- 没有 Claude/Codex 的 caller-authored 草稿时，Prompt Forge 校验失败，不生成 fallback prose。

许可证：MIT。上游 MCP 归属见 [`ATTRIBUTION.md`](ATTRIBUTION.md)。
