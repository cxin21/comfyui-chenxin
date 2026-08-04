# 技能与插件边界清单

更新时间：2026-08-04

## 生产入口

| 路径 | 状态 | 责任 |
|---|---|---|
| `skills/prompt-forge/SKILL.md` | active | 唯一生产入口：提示词、角色资产、相机镜头、Flux 多视角、LTX Director 视频和运行时证据 |
| `skills/prompt-forge/runtime/` | active | profile、adapter、draft、approval、consume、submit、history、artifact 和 RunRecord 合同 |
| `mcp/mcp_servers.json` | active | 上游 `comfyui-mcp` 的 stdio 注册 |
| `docs/MCP_BRIDGE.md` | active | Codex/Claude/本地 MCP 宿主适配说明 |

## 兼容技能（不可路由）

以下文件保留用于历史阅读和旧项目迁移，但均已设置 `status: legacy`、`triggers: []`，不属于当前四阶段生产流程：

| 路径 | 原用途 | 当前处理 |
|---|---|---|
| `skills/manga-orchestrator/SKILL.md` | 漫剧六阶段编排 | 停止作为入口，使用 Prompt Forge 四阶段链 |
| `skills/manga-stage-2-panels/SKILL.md` | AnimaStandardV7 分镜 | 历史兼容，不是 Flux flat-v2 生产 profile |
| `skills/manga-stage-3-review/SKILL.md` | 分镜美学评分 | 历史兼容，不替代 Stage 3 镜头图合同 |
| `skills/manga-stage-4-motion/SKILL.md` | 旧 LTX/I2V | 历史兼容，不替代 Yusu Director profile |
| `skills/lora-trainer/SKILL.md` | Anima LoRA 训练 | 不在当前生产链，需单独项目处理 |
| `skills/ffmpeg-pipeline/SKILL.md` | 字幕/拼接后处理 | 不在当前四阶段链，按需单独处理 |

没有实现的 `skills/manga-stage-1-lora/SKILL.md` 占位已删除；其责任不再由插件自动承诺。

## 当前四阶段 profile

| 阶段 | 受信 profile | 交付物 |
|---|---|---|
| Stage 1 | `camera-anima-base-v1` | 正面 `CharacterBaseImage` + RunRecord |
| Stage 2 | `flux2-klein-multiview-flat-v2` | 多视角资产 + accepted reference |
| Stage 3 | `camera-anima-v1` | G1 图生图镜头图 + RunRecord |
| Stage 4 | `ltx-yusu-director-v1` | Yusu Director 视频 + raw history + RunRecord |

## 不再维护的旧断言

以下历史文档中的路径或能力不能作为当前实现依据：

- `agents/`、`commands/`、`hooks/`（当前仓库没有这些目录）；
- `tests/test_applications.sh`（当前仓库没有该测试脚本）；
- AnimaStandardV7、`ltx23AllInOneWorkflowForRTX_v44`、旧六阶段自动漫剧链；
- Obsidian 自动同步、自动安装模型/节点、全自动无人审批 enqueue。

权威依据是 `skills/prompt-forge/SKILL.md`、`skills/prompt-forge/runtime/`、`docs/USAGE.md` 和 `docs/MCP_BRIDGE.md`。