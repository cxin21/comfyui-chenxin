# comfyui-chenxin(中文)

> **Claude Code 专用的 Local-first ComfyUI 超级技能包。** 80 个模型提示词配方 + 662 个工作流模板 + VRAM 感知模型选择 + 知识自更新 + 漫剧端到端流水线。
>
> 英文版请看 → [`README.md`](README.md)。

[![License: MIT](https://img.shields.io/badge/License-MIT-FFD27D.svg)](LICENSE)
[![Claude Code: required](https://img.shields.io/badge/Claude_Code-plugin-5BAEE3.svg)](https://claude.com/claude-code)
[![ComfyUI: required](https://img.shields.io/badge/ComfyUI-local--GPU-9aa3b2.svg)](https://www.comfy.org/)
[![GitHub release](https://img.shields.io/github/v/release/cxin21/comfyui-chenxin)](https://github.com/cxin21/comfyui-chenxin/releases)

---

## 🚀 快速开始

```bash
# 1. 在 Claude Code 中安装插件
/plugin marketplace add cxin21/comfyui-chenxin
/plugin install comfyui@chenxin

# 2. (一次性,每台机器) 初始化知识库
/chenxin-init

# 3. 生成 — 示例:Wan 2.2 出 5 秒金发精灵女法师释放灭世级魔法视频
"用 Wan 2.2 出 5 秒视频:金发精灵女法师释放灭世级魔法, 加台词 +
 后期, 8GB VRAM 友好"
```

**前置条件**:本地 ComfyUI 服务于 `http://127.0.0.1:8188` + ≥ 8 GB 显存。插件未检测到 ComfyUI 运行时会自动拉起(见 [`auto_launch.py`](mcp/extensions/auto_launch.py))。

---

## 🧭 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│ L8  Distribution (npm + Claude Code plugin marketplace)     │
├─────────────────────────────────────────────────────────────┤
│ L7  ~~跨 CLI 适配器~~  → 未构建(仅服务 Claude Code)        │
├─────────────────────────────────────────────────────────────┤
│ L6  遥测 / 健康 / SLO                                       │
├─────────────────────────────────────────────────────────────┤
│ L5  应用层(漫剧编排 + 6 个兄弟 Skill)                      │
├─────────────────────────────────────────────────────────────┤
│ L4  Skill 编排器(chenxin-core 超级 Skill)                  │
├─────────────────────────────────────────────────────────────┤
│ L3  知识底座(80 recipes + 662 templates + hw 配置文件)     │
├─────────────────────────────────────────────────────────────┤
│ L2  MCP 驱动(comfyui-mcp 108 工具 + 4 个 CLI 增强)         │
├─────────────────────────────────────────────────────────────┤
│ L1  ComfyUI 引擎(你的本地 GPU + custom_nodes)              │
└─────────────────────────────────────────────────────────────┘
```

详见 [`docs/architecture.md`](docs/architecture.md)。

---

## 📚 完整资源清单

### Skills(11 个) — `skills/`

| Skill | 路径 | 用途 | 触发词 |
|---|---|---|---|
| **chenxin-core** | `skills/chenxin-core/SKILL.md` | L4 超级 Skill,关键词 → 工具/配方/工作流 路由 | "comfyui" / "出视频" / "anima" / "wan" / "ltx" 等 |
| **manga-orchestrator** | `skills/manga-orchestrator/SKILL.md` | Stage 0:6 阶段流水线编排 | "全自动漫剧" / "auto manga" |
| **manga-stage-1-lora** | `skills/manga-stage-1-lora/SKILL.md` | LoRA 训练编排(占位,实际由 lora-trainer 覆盖)| "训 LoRA" |
| **manga-stage-2-panels** | `skills/manga-stage-2-panels/SKILL.md` | Stage 2:锁定 `AnimaStandardV7.json` 生成分镜 | "生成分镜" / "stage 2" |
| **manga-stage-3-review** | `skills/manga-stage-3-review/SKILL.md` | Stage 3:6 维美学评审(已吸收 `aesthetic-judge`)| "审查分镜" / "judge images" |
| **manga-stage-4-motion** | `skills/manga-stage-4-motion/SKILL.md` | Stage 4:锁定 `ltx23AllInOneWorkflowForRTX_v44.json` 图生视频 + 说话 | "生成分镜视频" / "图生视频" / "talking head" |
| **ffmpeg-pipeline** | `skills/ffmpeg-pipeline/SKILL.md` | Stage 5:拼接 + SRT 字幕 + 可选烧入 | "加字幕" / "concat" |
| **lora-trainer** | `skills/lora-trainer/SKILL.md` | Anima Standalone-Trainer 封装;8 GB 显存友好 | "训 Anima LoRA" / "lora training" |
| chenxin-core internals(3 文件)| `skills/chenxin-core/internals/{recipe_yaml.py,recipe_lookup.py,hardware_decide.py,context_graph.md,workflow-{config-guard,resolver}.md}` | 库函数 | (自动加载)|
| chenxin-core internals/legacy(1 文件)| `internals/legacy/prompt-forge-methodology.md` | 保留的 v3.1 提示词工程方法学(2026-07-30 硬删除 `~/.claude/skills/prompt-forge/` 后保留)| (只读)|

### MCP(9 个) — `mcp/`

| 文件 | 用途 |
|---|---|
| `mcp/README.md` | Layer-2 驱动文档。说明 4 个 CLI 增强 + 工作流集成。 |
| `mcp/mcp_servers.json` | 注册上游 `comfyui-mcp`(npm,~108 工具)key 为 `comfyui-mcp` → 智能体可见为 `mcp__comfyui-mcp__*`。 |
| `mcp/extensions/_shared.py` | 辅助函数:`wait_for_port`、`wait_for_http`、`load_hardware`(支持 `8.json` 或 `8gb.json` 回退)、`load_templates_index`、`resolve_comfyui_path`,JSON 标准输出契约。 |
| `mcp/extensions/auto_launch.py` | 按需拉起 ComfyUI;轮询 `/system_stats` 直至 200。 |
| `mcp/extensions/vram_decide.py` | 读 `hardware/<vram>.json`;输出 quant + 采样器默认值 + 阻塞标记。 |
| `mcp/extensions/template_get.py` | 按 use_case / modality / category 过滤 `templates_index.json`。 |
| `mcp/extensions/gui_save.py` | 将工作流 JSON 保存到 ComfyUI `user/default/workflows/`,带 `_manifest.json` 附属。 |
| `mcp/extensions/test_smoke.sh` | 4 个 CLI 冒烟测试(13/13 通过)。 |
| `mcp/extensions/__init__.py` | 包标记。 |

### Agents(7 个) — `agents/`

| Agent | 用途 |
|---|---|
| `chenxin-orchestrator.md` | Sonnet,Tool:Read/Bash/Grep/Glob/Task。读 `SPEC.md`,找下一未勾选 phase,spawn builder + reviewer。 |
| `chenxin-builder.md` | Sonnet,Tool:Write/Edit/Read/Bash/Grep/Glob/Skill。实现一个 phase 范围。 |
| `chenxin-reviewer.md` | Sonnet,Tool:Read/Bash/Grep/Glob/Task。**5 维对抗性审查**(代码 / 安全 / workflow-JSON / VRAM / 配方)。 |
| `chenxin-doctor.md` | Haiku。VRAM + 健康诊断 + 桥接 `mcp__comfyui-mcp__health_check`。 |
| `chenxin-update-bot.md` | Haiku。周期上游 diff(SlavaSexton + Comfy-Org 模板 + HF 博客 RSS)。 |
| `chenxin-publisher.md` | Sonnet。bump 版本、open release PR、建 GitHub Release。 |
| `comfyui-director.md` | Sonnet。**ComfyUI 文生图 / 视频导演** — 编排层。6 阶段流水线 + 锁定工作流 + 节点白名单(v4 重写版)。 |

### Commands(6 个) — `commands/`

安装后可用的斜杠命令:

| 命令 | 描述 |
|---|---|
| `/chenxin-init` | 一次性安装 + 引导机器块(`scripts/install.{ps1,sh}` + `scripts/bootstrap.sh`)。 |
| `/chenxin-build [phase]` | 通过 `chenxin-orchestrator` 跑下一未勾选 phase。 |
| `/chenxin-review` | 手动触发 5 维对抗性审查(支持 `--strict` 标志)。 |
| `/chenxin-doctor` | 通过 `chenxin-doctor` 子智能体 + 冒烟测试做健康检查。 |
| `/chenxin-publish` | bump 版本 + 生成 CHANGELOG + open release PR。 |
| `/chenxin-update` | 通过 `chenxin-update-bot` 拉最新 L3 底座 delta。 |

### Hooks(4 个) — `hooks/`

| 文件 | 触发 | 动作 |
|---|---|---|
| `hooks/hooks.json` | 定义 3 个事件匹配器 | (配置)|
| `hooks/scripts/on-session-start.sh` | `SessionStart` | 从 `SPEC.md` 打印当前 phase + 建议的下一步命令。 |
| `hooks/scripts/on-write-sync-vault.sh` | `PostToolUse[Write|Edit]` | 若 target ∈ {`SPEC.md`,`plugin.json`,`marketplace.json`},运行 `scripts/obsidian-sync.sh`。 |
| `hooks/scripts/on-stop-phase-gate.sh` | `Stop` | 检查 `git status`,若有未提交改动打印 PR 模板友好的提示。 |

### Scripts(11 个) — `scripts/`

| 脚本 | 用途 |
|---|---|
| `install.ps1` / `install.sh` | 一次性安装程序(跨平台)。 |
| `bootstrap.sh` | 健康检查 + 首次运行时读 machine-block。 |
| `check_updates.py` | 周更守护 — 4 个上游源(SlavaSexton、Comfy-Org/templates、Comfy-Org/skills、HF 博客 RSS)。 |
| `diff_recipes.py` | 每个配方相对上游的方言 delta。 |
| `phase-next.sh` / `find-next-phase.sh` | Git-as-orchestrator 助手。 |
| `obsidian-sync.sh` | 写决策笔记到用户 Obsidian vault(白名单清理过的 EVENT)。 |
| `self-update.sh` | 自更新节奏驱动。 |
| `validate-plugin-schema.sh` / `validate-marketplace.sh` | JSON 架构校验器(在 CI + pre-publish 跑)。 |

### 知识底座(L3) — `skills/chenxin-core/`

| 文件 | 行数 | 用途 |
|---|---|---|
| `recipes/MODELS.md` | 2462 | 80 个模型提示词配方,带 YAML frontmatter(每个配方含 id/family/modality/dialect/license/triggers)。 |
| `templates_index.json` | 6651 | 662 个工作流模板,按类别(3d=11 api=242 archived=23 audio=22 conditioning=26 get_started=5 image=92 upscale=22 utility=138 video=81)和模态(3d=36 image=435 video=152 audio=32 vector=2 mixed=5)分类。 |
| `hardware/8gb.json` | 58 | VRAM 决策矩阵:15 个 allowed_quant,swap_blocks=40,sampler_defaults=euler/4/1.0,preference=[lightning_x2v, lightx2v, fcn, native]。 |

---

## 🧪 测试(全部真实,非 mock)

> 插件中的每个测试都针对真实数据调用实际脚本/CLI/二进制。**无 mock**。测试套件端到端证明组件行为(除了硬件依赖的 ComfyUI 服务 — 插件不要求该服务)。

| 测试 | 结果 | 实际测试内容 |
|---|---|---|
| `mcp/extensions/test_smoke.sh` | **13/13 PASS** | 调 4 个 CLI 工具(auto_launch、vram_decide、template_get、gui_save)— 校验 CLI 表面、stdout JSON 契约、退出码语法(0/2/3/4),以及 vram_decide 对不存在模型返回 `blocked=true`。 |
| `tests/test_obsidian_sync.sh` | **4/4 PASS** | 对真实 `/tmp/obsidian-sync-sandbox-$$` vault 跑 `scripts/obsidian-sync.sh`;校验路径穿越白名单(敌意 EVENT 参数 → 安全文件名)、event 默认 unknown、vault 缺失时非致命退出 0。 |
| `tests/test_check_updates.sh` | **17/17 PASS** | 对实际 `~/.cache` 和 `git ls-remote` 调 `check_updates.py` 和 `diff_recipes.py`;校验 JSON 封装、--help 退出 0、幂等自 diff(找出 13 个未变配方)。 |
| `tests/test_applications.sh` | **7/7 PASS** | 通过 `awk` 读每个 SKILL.md;校验 YAML frontmatter 分隔符、`name:` 和 `description:` 存在、`description` 字面含 "chenxin-core"。 |
| `scripts/validate-plugin-schema.sh` | **OK** | 解析 `.claude-plugin/plugin.json` 和 `marketplace.json`;校验 name 匹配 slug + dependencies path 存在。 |
| `scripts/validate-marketplace.sh` | **OK** | 同上,针对 `marketplace.json`(交叉校验 `plugin.json` name 存在 + slug 正则)。 |

跑全部:

```bash
bash mcp/extensions/test_smoke.sh
bash tests/test_obsidian_sync.sh
bash tests/test_check_updates.sh
bash tests/test_applications.sh
bash scripts/validate-plugin-schema.sh
bash scripts/validate-marketplace.sh
```

---

## 🔗 Obsidian Vault 集成

插件每次对关键文件做实质改动,会向用户 Obsidian vault 写一条 trace 文件。契约由 hook + 幂等脚本强制执行。

- **Vault 默认路径**:`D:/ObsidianWorkSpace/workspace/00-Inbox/processed/`
- **覆盖**:`OBSIDIAN_VAULT_PATH=/path/to/vault bash scripts/obsidian-sync.sh <event>`
- **关闭**:`OBSIDIAN_VAULT_PATH=/dev/null`
- **完整契约**:见 [`docs/OBSIDIAN_SYNC.md`](docs/OBSIDIAN_SYNC.md)
- **故障排除**:见 [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)

### Vault → Git 反向桥

关键 vault 决策已镜像到本仓库 `docs/vault-bridge/`(见 [`docs/vault-bridge/README.md`](docs/vault-bridge/README.md)),团队可通过 `git grep` 检索,无需 vault 访问。

---

## 🤝 贡献方式

1. Fork + 新建分支(`phase/PX.Y-task-name`)。
2. 实现 + 提交(`scripts/install.sh`)。
3. 用 `.github/PULL_REQUEST_TEMPLATE.md` 开 PR(自动填充复选框)。
4. 等待 5 维对抗性审查(`agents/chenxin-reviewer.md`)→ 人工批准。
5. `phase-gate.yml` 自动合并,开下一 phase 分支。

完整规范见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

---

## 📜 许可证

MIT — 见 [`LICENSE`](LICENSE)。

第三方致谢: [`ATTRIBUTION.md`](ATTRIBUTION.md)。

---

## 🔗 链接

- GitHub: https://github.com/cxin21/comfyui-chenxin
- 灵感来源: [SlavaSexton/ComfyUI-Agent-Kit](https://github.com/SlavaSexton/ComfyUI-Agent-Kit)
- 底层 MCP: [artokun/comfyui-mcp](https://github.com/artokun/comfyui-mcp)
- 知识上游: [Comfy-Org/workflow_templates](https://github.com/Comfy-Org/workflow_templates)
- Claude Code: https://claude.com/claude-code
- Vault(Obsidian):`~/.claude/rules/obsidian-workflow.md`(workspace 规则)
