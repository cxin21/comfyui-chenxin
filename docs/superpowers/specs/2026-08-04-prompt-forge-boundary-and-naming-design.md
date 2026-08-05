# Prompt Forge 边界与命名重设计

## 目标

按处女原则把插件收敛为两个可解释、可测试、可独立路由的技能：

- `prompt-forge`：无副作用的提示词编译器；
- `character-video-pipeline`：当前四阶段角色一致性到视频的受控生产编排器。

删除已弃用技能、旧计划、旧规范和兼容性说明，避免宿主继续看到已经不再支持的入口。

## 第一性原理

一个技能的边界由四件事决定：用户意图、输入输出合同、副作用权限和失败责任。若两个能力的用户意图和副作用不同，就不应共用一个可路由入口；若几个阶段共享同一条不可绕过的安全不变量，就不应拆成多个可独立路由入口。

当前 `prompt-forge` 同时包含两类不同能力：

1. PromptIntent → PromptBuild 的纯编译；
2. ComfyUI 工作流发现、MCP 调用、审批、一次性消费、enqueue、history、artifact 和 RunRecord。

第一类不应拥有外部副作用，第二类必须拥有严格的副作用边界。因此单一 `prompt-forge` 名称不足以描述当前生产编排。

Stage 1–4 不能拆成四个技能。四阶段共同维护 lineage、profile hash、approval、consumption、receipt、raw history 和 artifact eligibility；拆分后会增加跨技能绕过检查的路径。四阶段应继续作为一个生产技能内部的状态机。

## 命名决策

- 仓库/插件名 `comfyui-chenxin` 保留：它描述生态归属和安装对象。
- 纯编译技能名 `prompt-forge` 保留：它准确描述 PromptIntent 到 PromptBuild 的能力。
- 新增生产技能名 `character-video-pipeline`：它准确描述四阶段交付物和 ComfyUI 编排责任。
- `runtime`、receipt 类型、artifact 子目录和旧 RunRecord 中的 `prompt-forge-*` 机器标识在第一版迁移中保持不变，避免破坏已有本地证据；只有在单独的 schema migration 中才升级机器命名。

## 目标目录

```text
skills/
├── prompt-forge/
│   ├── SKILL.md                 # 纯提示词编译入口，无 MCP/提交权限
│   ├── SPEC.md                  # PromptIntent/PromptBuild 合同
│   ├── internals/               # 归一化、recipe、tag、scene、compiler
│   ├── aesthetics/              # 纯提示词审美知识
│   ├── dictionary/              # 纯标签和中英映射
│   ├── models/                  # 当前支持的模型方言
│   ├── negative/                # 纯反向提示词知识
│   ├── references/              # PromptBuild 合同和方言参考
│   ├── recipes/                 # recipe 数据源
│   ├── hardware/                # 纯资源决策数据
│   └── evals/                   # prompt 编译回归集
└── character-video-pipeline/
    ├── SKILL.md                 # 四阶段生产入口
    └── runtime/                 # profiles、adapters、MCP、状态、提交和证据测试
```

`character-video-pipeline` 的 runtime 可以继续使用 Python 包名 `runtime`，但其工作目录、CLI 文档和测试入口必须改为 `skills/character-video-pipeline/runtime`。纯 `prompt-forge` 不得导入该 runtime，也不得通过文档暗示它会执行生成。

## 删除清单

### 技能目录

删除以下整个目录，不保留 `status: legacy` 兼容入口：

- `skills/ffmpeg-pipeline/`
- `skills/lora-trainer/`
- `skills/manga-orchestrator/`
- `skills/manga-stage-2-panels/`
- `skills/manga-stage-3-review/`
- `skills/manga-stage-4-motion/`

未实现的 `skills/manga-stage-1-lora/SKILL.md` 已经删除，不重新创建。

### 旧计划和规范

删除已经被 2026-08-04 生产设计替代的旧计划/规范：

- `docs/superpowers/plans/2026-08-01-prompt-forge-v5.md`
- `docs/superpowers/plans/2026-08-02-prompt-forge-v6.md`
- `docs/superpowers/plans/2026-08-02-prompt-forge-v7-slice1-runtime-base.md`
- `docs/superpowers/plans/2026-08-02-prompt-forge-v7-slice2-multiview.md`
- `docs/superpowers/plans/2026-08-02-prompt-forge-v7-slice3-shot-img2img.md`
- `docs/superpowers/plans/2026-08-02-prompt-forge-v7-slice4-ltx-video.md`
- `docs/superpowers/plans/2026-08-03-prompt-forge-v7-readiness.md`
- `docs/superpowers/plans/2026-08-04-plugin-boundary-cleanup-plan.md`
- `docs/superpowers/plans/2026-08-04-controlled-character-video-pipeline-plan.md`
- `docs/superpowers/plans/2026-08-04-controlled-character-video-pipeline-v2-plan.md`
- `docs/superpowers/specs/2026-08-01-prompt-forge-v5-design.md`
- `docs/superpowers/specs/2026-08-02-prompt-forge-v6-design.md`
- `docs/superpowers/specs/2026-08-02-prompt-forge-v7-character-to-video-design.md`

保留当前生产设计、本规范和当前实施计划，作为唯一可追溯设计依据：

- `docs/superpowers/specs/2026-08-04-controlled-character-video-pipeline-design.md`
- `docs/superpowers/specs/2026-08-04-prompt-forge-boundary-and-naming-design.md`
- `docs/superpowers/plans/2026-08-04-prompt-forge-boundary-naming-implementation-plan.md`

## 文档与 metadata 处理

- README 只介绍两项 active skill，不再出现 legacy/兼容技能列表。
- `application-inventory.md` 只列生产入口、纯编译入口和 MCP 注册。
- `docs/architecture.md` 把纯编译层和生产编排层分开，移除旧目录章节。
- `docs/USAGE.md` 的 Prompt 编译命令使用 `skills/prompt-forge`，四阶段命令使用 `skills/character-video-pipeline/runtime`。
- `docs/TROUBLESHOOTING.md` 删除旧技能迁移说明，只保留当前两层边界的故障处理。
- `.claude-plugin/plugin.json` 和 marketplace metadata 删除 manga、LoRA、旧自动漫剧等过时关键词和描述。
- `CHANGELOG.md` 保留历史版本事实，但不得声称旧技能仍随当前版本发布；弃用说明改成“已从当前包删除”。
- install 脚本只负责宿主/MCP 注册，不下载模型、节点或工作流。

## 迁移与不变量

1. 先复制/移动 runtime 和测试到 `skills/character-video-pipeline/runtime`，再修改 import、路径计算、CLI、文档和环境变量。
2. 纯 `prompt-forge` 的回归测试必须继续覆盖 PromptIntent、recipe、tag、scene 和 PromptBuild；不得依赖 ComfyUI 或 MCP。
3. pipeline 测试必须继续覆盖 profile、MCP bridge、approval、consumption、idempotent enqueue、history、artifact 和四阶段 handoff。
4. 新增边界测试：只有 `prompt-forge/SKILL.md` 和 `character-video-pipeline/SKILL.md` 为 active；两者的描述、权限和路径不交叉；仓库不存在删除清单中的目录/文件。
5. 已有本地 receipt、RunRecord 和 artifact 不迁移、不删除；只更新新运行的默认文档路径和测试路径。
6. 任何删除操作只针对本清单的精确路径，不递归清理 `.live-artifacts`、`.superpowers`、ComfyUI 输出或用户工作流。

## 验收标准

- `skills/` 下只有两个 `SKILL.md`，且分别对应纯编译和四阶段生产。
- `prompt-forge` 不再声明 MCP、ComfyUI enqueue、approval 或 artifact 提交权限。
- `character-video-pipeline` 成为唯一拥有 runtime/MCP/提交权限的技能。
- README、架构、使用、清单、故障排查和 metadata 不引用已删除路径。
- 所有 JSON profile 可解析，Python runtime 可编译，纯编译和 pipeline 测试路径均可运行。
- 无模型、节点、工作流、历史 artifact 被删除。
