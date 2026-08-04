# comfyui-chenxin

面向 ComfyUI 的本地优先 Prompt Forge 插件。当前生产主链是“角色一致性 → 多视角 → 镜头图 → 视频”的四阶段流程，支持 Codex、Claude Code 以及其他能提供 MCP 调用的宿主。

> 重要边界：插件不携带模型、Custom Nodes 或保存的工作流文件；它只提供提示词编译、工作流合同、证据校验和受控编排。真正执行前，必须确认本机 ComfyUI、模型、节点和工作流已安装并通过 profile 校验。

## 生产流程

```text
共同目标 / 剧情拆解 / 影视资产
        │
        ▼
1. Prompt Forge 生成正向与反向提示词
   文生图相机视角工作流 → 正面角色基础图（CharacterBaseImage）
        │  接受、哈希、RunRecord
        ▼
2. Flux2-Klein 人物一键多视图
   生产 profile：flux2-klein-multiview-flat-v2
   → front / right_45 / right / rear_45 / rear / left_45 / left 等角度资产
        │  选择并接受可作为参考的角度
        ▼
3. Prompt Forge 再次生成镜头提示词
   文生图相机视角工作流的 G1 图生图组
   → 具体镜头图（shot image）
        │  绑定故事、角色、角度和镜头证据
        ▼
4. LTX 全新导演台
   profile：ltx-yusu-director-v1
   Yusu LTX Director 加载镜头图与提示词 → 视频 + 原始 history + RunRecord
```

每一阶段都必须产生可验证的交接证据。不能用聊天文本、截图、手填 receipt 或旧 approval 代替证据。

## 最小边界

### 唯一生产入口

`skills/prompt-forge/SKILL.md` 是唯一生产技能入口，负责：

- PromptIntent / PromptBuild 编译；
- 正向、反向提示词和镜头提示词质量合同；
- 角色基础图、多视角、镜头图、视频四阶段路由；
- Stage 1/2/3/4 的 profile、哈希、审批、消费、提交和 RunRecord 约束。

运行时实现位于 `skills/prompt-forge/runtime/`，包括：

- `runtime_cli.py`：JSON 输入输出的规划、审批、消费、提交和验证命令；
- `local_orchestrator.py`：审批/消费之后的本地提交边界；
- `mcp_bridge.py`：宿主无关 MCP 工具适配、能力协商和哈希调用证据；
- `profiles/`：受信工作流、节点、模型、分辨率和输出合同；
- `tests/`：运行时合同、回归和 live 证据测试。

### 兼容性技能

`skills/manga-*`、`skills/lora-trainer/` 和 `skills/ffmpeg-pipeline/` 是历史兼容文档，已标记为 `status: legacy` 且不再拥有自动触发器。它们不属于当前四阶段生产链，不应绕过 Prompt Forge 直接调用。没有实现的 `manga-stage-1-lora` 占位已移除。

## 安装前提

1. ComfyUI 已部署并运行在 `http://127.0.0.1:8188`。
2. 相机基础图、Flux 多视角和 LTX 导演台工作流已经保存到 ComfyUI，并与本仓库 profile 的名称、指纹、API graph hash、节点和模型合同一致。
3. 相应的 Checkpoint、LoRA、Custom Nodes 和显存配置已在 ComfyUI 本机可用；插件不会替你下载或安装这些资源。
4. Python 3.11+、pytest（开发验证）和 `ffprobe`（视频技术元数据校验）可用。
5. MCP 宿主已注册 `mcp/mcp_servers.json` 中的 `comfyui-mcp`。Codex/Claude 等宿主需要提供一个 `host_call_tool(tool_name, arguments)`，再构造 `runtime.mcp_bridge.McpBridge`。

## 安装

Windows（Claude Code 注册脚本）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

Linux/macOS：

```bash
bash scripts/install.sh
```

这两个脚本只负责 MCP 配置、Claude Code 示例注册和 `comfyui-mcp` 的可选安装；它们不会安装 ComfyUI、模型、Custom Nodes 或工作流。其他 MCP 宿主请按其配置格式注册同一个 stdio MCP server。

## 审批与执行合同

生产提交严格遵循：

```text
能力发现 → 工作流读取/转换/验证 → draft
→ 展示 exact draft_hash → 外部 approval
→ 一次性 consume → 重建 executable graph
→ queue idle 检查 → exclusive intent → enqueue
→ raw history → artifact hash/metadata → RunRecord
```

- 规划阶段没有副作用；
- `approve-*` 只接受本次展示的精确 hash；
- `consume-*` 是一次性、原子、不可复用的消费记录；
- 队列非空、profile 漂移、工作流指纹漂移、转换 warning/error、证据缺失时 fail closed；
- POST 超时或结果不确定时保留 receipt，先查 history，不盲目重试；
- `runtime_cli.py` 无法携带 Python callable，因此纯 JSON CLI 不能伪造生产 MCP conversion proof；生产 Stage 2 转换必须由受控本地 orchestrator 注入 `McpBridge` 或等价 callable。

## MCP 桥接

宿主无关桥接层见 [`docs/MCP_BRIDGE.md`](docs/MCP_BRIDGE.md)。核心原则：

- 逻辑工具名与宿主实际工具名分离；
- 只接受 JSON-compatible 参数和响应；
- 记录逻辑工具、实际工具、参数哈希、响应哈希和宿主信息；
- side effect 默认关闭；
- raw `workflow_tools` 与 `McpBridge` 不能同时传入；
- 桥接层不负责 UI→API 转换、不绕过审批、不替代一次性 enqueue 合同。

## 验证

在仓库根目录执行：

```powershell
$env:PYTHONPATH = "skills/prompt-forge"
py -3 -m pytest -q skills/prompt-forge
py -3 -m compileall -q skills/prompt-forge/runtime
ruff check skills/prompt-forge/runtime
```

工作流 profile 和 live 证据测试默认会在缺少本机 ComfyUI/模型/节点时跳过或 fail closed；这不等同于已完成真实生成。真实生产结论必须同时给出 prompt id、raw history、artifact 绝对路径、SHA-256、技术元数据和 RunRecord。

## 文档索引

- [四阶段使用说明](docs/USAGE.md)
- [系统架构](docs/architecture.md)
- [MCP 桥接层](docs/MCP_BRIDGE.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [Prompt Forge 规范](skills/prompt-forge/SPEC.md)
- [受控角色到视频设计](docs/superpowers/specs/2026-08-04-controlled-character-video-pipeline-design.md)
- [边界清理计划](docs/superpowers/plans/2026-08-04-plugin-boundary-cleanup-plan.md)

## 当前不承诺

- 不承诺全新安装后自动拥有模型、节点和工作流；
- 不承诺 Codex/其他宿主自动获得 MCP callable，宿主适配仍需注册；
- 不把旧漫剧六阶段、LoRA 训练、字幕拼接技能包装成当前生产流程；
- 不在未通过 approval、consumption、history 和 artifact 校验前声称已生成成功。

许可证：MIT。上游 MCP 驱动归属见 [`ATTRIBUTION.md`](ATTRIBUTION.md)。