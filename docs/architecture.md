# 系统架构

## 目标

插件的生产边界只有一条：Prompt Forge 将用户目标编译成可审计的工作流计划，再由受控本地编排器在 approval 和一次性 consumption 之后提交 ComfyUI。

## 分层

```text
┌─────────────────────────────────────────────────────────────┐
│ MCP Host: Codex / Claude Code / compatible local host        │
├─────────────────────────────────────────────────────────────┤
│ Host-neutral MCP Bridge: logical tools → host tool names     │
├─────────────────────────────────────────────────────────────┤
│ Prompt Forge Skill: prompt, asset, profile, stage routing    │
├─────────────────────────────────────────────────────────────┤
│ Runtime: draft / approval / consume / submit / record        │
├─────────────────────────────────────────────────────────────┤
│ Profiles + adapters: camera / Flux / Yusu timeline contracts  │
├─────────────────────────────────────────────────────────────┤
│ ComfyUI MCP + loopback REST (transport only)                 │
├─────────────────────────────────────────────────────────────┤
│ Local ComfyUI + models + Custom Nodes + saved workflows      │
└─────────────────────────────────────────────────────────────┘
```

## 生产模块

| 模块 | 唯一职责 |
|---|---|
| `skills/prompt-forge/SKILL.md` | 生产入口、四阶段路由、提示词和安全边界 |
| `skills/prompt-forge/runtime/mcp_bridge.py` | 适配宿主 MCP 调用并记录哈希证据 |
| `skills/prompt-forge/runtime/workflow_discovery.py` | 读取 UI/API/strip/runtime/validation 证据 |
| `skills/prompt-forge/runtime/adapters/camera.py` | 相机工作流的 pinned、allowlisted 归一化 |
| `skills/prompt-forge/runtime/adapters/flux_multiview.py` | Flux flat-v2 双输入和多视角合同 |
| `skills/prompt-forge/runtime/adapters/yusu_timeline.py` | LTX Director 时间线、帧数、FPS、时长和段落连续性 |
| `skills/prompt-forge/runtime/profiles/` | 工作流名称、指纹、节点、模型、输出和资源 pin |
| `skills/prompt-forge/runtime/local_orchestrator.py` | 只在已审批、已消费后跨 loopback transport 边界 |
| `skills/prompt-forge/runtime/runtime_cli.py` | JSON 输入输出，不拥有宿主 callable |

## 四阶段数据流

```text
PromptIntent / story / art bible
  → PromptBuild (positive + negative + constraints)
  → Stage 1 CharacterBaseImage + RunRecord
  → Stage 2 angle assets + accepted reference
  → Stage 3 accepted shot image + RunRecord
  → Stage 4 video + raw history + verified artifact + RunRecord
```

每个箭头都绑定 hash、lineage、profile 和能力证据。任何断链都会停止，不用下游摘要反推上游事实。

## 副作用边界

```text
read / compile / inspect / normalize
  → draft
  → display exact hash
  → external approval
  → one-time consume
  → rebuild executable graph
  → queue idle + intent sentinel
  → enqueue once
  → raw history + artifact verification
```

- Prompt 编译和工作流规划无副作用；
- REST 只作为健康、队列、history 和最终受控提交的 transport；
- MCP bridge 默认只读，不替代审批和 consumption；
- queue 非空、profile 漂移、转换 warning/error 或 hash 不匹配时 fail closed；
- legacy 技能不参与以上链路。

## 资源边界

仓库不包含：模型权重、Custom Nodes、ComfyUI 数据库、保存工作流实体、用户输出、审批文件和 MCP 宿主 SDK。安装脚本只注册 MCP 配置；宿主适配和本机资源由部署者负责。

## 兼容层

以下目录仅作为历史参考，frontmatter 已标记 `status: legacy` 且触发器为空：

- `skills/manga-orchestrator/`
- `skills/manga-stage-2-panels/`
- `skills/manga-stage-3-review/`
- `skills/manga-stage-4-motion/`
- `skills/lora-trainer/`
- `skills/ffmpeg-pipeline/`

它们不应再被当作当前四阶段生产入口。没有实现的 `manga-stage-1-lora` 占位已移除。