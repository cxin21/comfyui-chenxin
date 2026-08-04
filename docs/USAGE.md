# 四阶段生产使用说明

本文只描述当前受支持的角色一致性到视频生产链。历史兼容技能和可选后处理说明已经退役，不是本流程的替代路径。

## 0. 共同输入

开始前准备：

- 目标：要生成哪个角色、哪条故事线、哪个镜头或哪段视频；
- 背景：剧情拆解、影视资产、角色事实、风格和现实限制；
- 交付标准：正/反提示词、基础图、多视角设定图、镜头图、视频以及可审计证据；
- 边界：不安装模型、不修改用户工作流、不清理 history/output、不绕过审批。

信息缺失但不会改变工作流选择时，先按显式假设完成探索版本；会改变资产、节点或安全边界时必须停在 draft。

## 1. Prompt Forge → 正面角色基础图

1. 读取 Prompt Forge 的 PromptIntent、剧情和影视资产信息。
2. 生成正向提示词、反向提示词以及尺寸、镜头、风格和一致性约束。
3. 通过 MCP 读取受信的相机基础工作流 UI/API/strip/runtime/validation 证据。
4. 只修改 profile 允许的输入，生成正面角色基础图。
5. 从 ComfyUI raw history 读取输出，验证 PNG、路径、SHA-256、lineage 和 front-facing acceptance。
6. 记录 Stage 1 RunRecord，产出 `CharacterBaseImage`，供 Stage 2 使用。

任何工作流指纹漂移、转换错误、队列非空或输出无法验证，都必须停止。

## 2. Flux2-Klein → 多视角角色设定图

生产 profile：`flux2-klein-multiview-flat-v2`。

1. 验证 Stage 1 的 `CharacterBaseImage` 和 RunRecord 完整匹配。
2. 由受控本地 orchestrator 注入 `McpBridge`，实际调用 `get_workflow`、`strip_workflow`、`validate_workflow` 和 `check_workflow_runtime`。
3. 使用上传文件名 `prompt-forge/<lineage_id>/character-base-<sha256>.png`，禁止覆盖不同内容。
4. 只允许 profile 白名单里的两个 base-image 节点使用同一上传文件；pose、模型、LoRA、sampler、scheduler 和其他字段保持不变。
5. 生成并验证 front、right_45、right、rear_45、rear、left_45、left 等角度资产。
6. 通过 `select-reference` 和 `accept-reference` 明确接受可作为 Stage 3 参考的角度。

原始分组 Flux 工作流不是生产 fallback；flat-v2 profile 缺失或证据漂移时 fail closed。

## 3. Prompt Forge → 相机 G1 镜头图

1. 基于本次镜头目标再次生成正向、反向和运动/构图提示词。
2. 绑定已接受的角色角度、故事线、角色事实和镜头约束。
3. 选择相机工作流的 G1 图生图组，并使用 pinned camera profile。
4. 只应用 allowlisted camera patch 和 G1 路径检查，不使用通用 UI→API 猜测。
5. 生成具体镜头图，验证 raw history、输出 PNG、hash、orientation 和 shot lineage。
6. 记录 Stage 3 RunRecord，镜头图必须标记为 accepted 才能进入 Stage 4。

## 4. LTX Director → 视频

生产 profile：`ltx-yusu-director-v1`。

1. 验证镜头图已被 Stage 3 接受，且 source story/asset/angle lineage 完整。
2. 读取并校验 `LTX全新导演台工作流.json` 的真实 UI/API/运行时证据。
3. 在 Yusu LTX Director 节点写入镜头图和 Prompt Forge 生成的提示词。
4. 由 timeline adapter 处理帧数、FPS、时长、分辨率、段落连续性和对白约束。
5. 经过 draft → approval → consume → exclusive intent 后才允许 enqueue。
6. 等待 ComfyUI terminal history，验证视频字节 hash、分辨率、FPS、帧数、时长和 raw graph。
7. 写入 Stage 4 RunRecord，向用户返回 prompt id、artifact 路径、hash 和技术元数据。

## 宿主接入

MCP 协议本身与宿主无关。Codex、Claude Code 或其他宿主需要：

1. 注册 `mcp/mcp_servers.json` 中的 `comfyui-mcp`；
2. 提供 `host_call_tool(tool_name, arguments) -> JSON-compatible result`；
3. 用实际宿主工具名构造 `runtime.mcp_bridge.McpBridge`；
4. 将 bridge 注入 `build_multiview_draft_with_mcp`、`submit-character-base` 或 `submit-stage`。

桥接层不会替宿主调用 MCP，也不会给纯 JSON caller 颁发 production trust。

## 常用运行时命令

`skills/prompt-forge/runtime/runtime_cli.py` 提供 JSON 边界命令，包括：

- `discover`、`fingerprint`、`plan`、`plan-character-base`；
- `plan-multiview`、`select-reference`、`accept-reference`；
- `plan-shot`、`activate-g1`、`verify-img2img-path`；
- `plan-video`、`plan-stage-execution`、`patch-yusu`；
- `approve-plan`、`consume-approval`、`approve-stage`、`consume-stage`；
- `submit-character-base`、`submit-stage`、`wait-stage`、`record-stage`；
- `verify-video`、`pipeline-state`、`record`。

命令只接受 UTF-8 JSON 或 stdin。规划命令不产生副作用；纯 JSON 无法携带受控 callable 时必须返回 typed rejection。

## 失败处理

- 队列非空：等待并重新读取能力，不直接提交；
- profile/fingerprint/API graph 漂移：重建 draft，不复用旧 approval；
- enqueue 超时：保留 receipt，先查 history，不盲目重试；
- 输出缺失或 hash 不匹配：不能写成功 RunRecord；
- MCP 工具不可用：报告缺口和替代方案，不猜工具名、不伪造 receipt。