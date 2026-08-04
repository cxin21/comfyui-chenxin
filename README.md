# comfyui-chenxin(中文)

> **Claude Code 专用的 Local-first ComfyUI 超级技能包。** 80 个模型提示词配方 + 662 个工作流模板 + VRAM 感知模型选择 + 知识自更新 + 漫剧端到端流水线。
>
> 英文版请看 → [`README.en.md`](README.en.md)。

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

# 3. 生成 — 示例(用 ComfyUI 自带 text-to-image 模板,**无需任何外部工作流文件**)
"用 ComfyUI 自带 text-to-image 模板生成一张金发精灵女法师在樱花树下释放魔法的图, 1024x1024"
```

**前置条件**:本地 ComfyUI 服务于 `http://127.0.0.1:8188` + ≥ 8 GB 显存。插件未检测到 ComfyUI 运行时会自动拉起(由 `scripts/bootstrap.sh` 完成)。

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
│ L4  Skill 编排器(prompt-forge 超级 Skill)                  │
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
| **prompt-forge** | `skills/prompt-forge/SKILL.md` | L4 超级 Skill,关键词 → 工具/配方/工作流 路由 | "comfyui" / "出视频" / "anima" / "wan" / "ltx" 等 |
| **manga-orchestrator** | `skills/manga-orchestrator/SKILL.md` | Stage 0:6 阶段流水线编排 | "全自动漫剧" / "auto manga" |
| **manga-stage-1-lora** | `skills/manga-stage-1-lora/SKILL.md` | LoRA 训练编排(占位,实际由 lora-trainer 覆盖)| "训 LoRA" |
| **manga-stage-2-panels** | `skills/manga-stage-2-panels/SKILL.md` | Stage 2:锁定 `AnimaStandardV7.json` 生成分镜 | "生成分镜" / "stage 2" |
| **manga-stage-3-review** | `skills/manga-stage-3-review/SKILL.md` | Stage 3:6 维美学评审(已吸收 `aesthetic-judge`)| "审查分镜" / "judge images" |
| **manga-stage-4-motion** | `skills/manga-stage-4-motion/SKILL.md` | Stage 4:锁定 `ltx23AllInOneWorkflowForRTX_v44.json` 图生视频 + 说话 | "生成分镜视频" / "图生视频" / "talking head" |
| **ffmpeg-pipeline** | `skills/ffmpeg-pipeline/SKILL.md` | Stage 5:拼接 + SRT 字幕 + 可选烧入 | "加字幕" / "concat" |
| **lora-trainer** | `skills/lora-trainer/SKILL.md` | Anima Standalone-Trainer 封装;8 GB 显存友好 | "训 Anima LoRA" / "lora training" |
| prompt-forge internals(3 文件)| `skills/prompt-forge/internals/{recipe_yaml.py,recipe_lookup.py,hardware_decide.py,context_graph.md,workflow-{config-guard,resolver}.md}` | 库函数 | (自动加载)|
| prompt-forge internals/legacy(1 文件)| `internals/legacy/prompt-forge-methodology.md` | 保留的 v3.1 提示词工程方法学(2026-07-30 硬删除 `~/.claude/skills/prompt-forge/` 后保留)| (只读)|

### MCP(9 个) — `mcp/`

| 文件 | 用途 |
|---|---|
| `mcp/README.md` | Layer-2 驱动文档。仅注册上游 npm MCP server。 |
| `mcp/mcp_servers.json` | 注册上游 `comfyui-mcp`；Prompt Forge 会先协商当前实际工具能力，不依赖写死的 MCP 工具名。 |

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

### 知识底座(L3) — `skills/prompt-forge/`

| 文件 | 行数 | 用途 |
|---|---|---|
| `recipes/MODELS.md` | 2462 | 80 个模型提示词配方,带 YAML frontmatter(每个配方含 id/family/modality/dialect/license/triggers)。 |
| `templates_index.json` | 6651 | 662 个工作流模板,按类别(3d=11 api=242 archived=23 audio=22 conditioning=26 get_started=5 image=92 upscale=22 utility=138 video=81)和模态(3d=36 image=435 video=152 audio=32 vector=2 mixed=5)分类。 |
| `hardware/8gb.json` | 58 | VRAM 决策矩阵:15 个 allowed_quant,swap_blocks=40,sampler_defaults=euler/4/1.0,preference=[lightning_x2v, lightx2v, fcn, native]。 |
| `runtime/` | — | v7 本地执行合同：TaskContext、CapabilityReport、workflow fingerprint、immutable pending bundle、ExecutionDraft、hash-bound approval event、canonical consumption namespace、one-shot consumption、approved ExecutionPlan、camera/Flux allowlist patch、normalized artifacts、RunRecord 与 JSON CLI。Stage 1 `plan` 产未批准 draft；Stage 2 production draft 只能由本地授权 orchestrator 的 `build_multiview_draft_with_mcp` 在进程内实际调用 `get_workflow`/`strip_workflow`/`validate_workflow`/`check_workflow_runtime` 后生成。纯 JSON `plan-multiview` 不能把自填 receipt 变成 draft，纯 JSON `patch-flux` 也不能声称已提交，二者均 fail closed。Stage 2 必须依次受控 conversion→draft→外部审批→消费→受控本地 MCP enqueue；所有 stage 共用 exact `draft_hash` 审批与同一 root 的一次性消费。 |

Prompt Forge v7 deterministic gate（live 测试默认跳过）：

```powershell
$env:PYTHONPATH='skills/prompt-forge'
Remove-Item Env:PROMPT_FORGE_LIVE -ErrorAction SilentlyContinue
python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q
python skills/prompt-forge/internals/evaluate.py
```

真实 ComfyUI Experiment A/B 默认跳过。已有 A/B 使用 REST，只证明 selected history 图（指纹 `2efbc0fd43749828754dea7989f88806a944628e064d3c9c6876ee602726724f`）内部无漂移并匹配 workflow id/profile；它们是 render/graph characterization，不是 MCP 生产路径或完整审批证据。审查时只读重算的当前保存工作流指纹为 `7fa7a85e005182c6be42a3f3193add3fb41531ef0fae28e1cbd54a791e72e20a`，与历史指纹不同，不能混写为“current saved 未漂移”。未来 B 首轮只 exclusive-create immutable `pending-<draft_hash>.json` 后停止；bundle、approval event、`approve-plan` 与 `consume-approval` 必须绑定同一 existing canonical resolved `consumption_root`，parent/child/alias 不能更换消费 namespace。恢复还必须提供绑定 exact hash 的 `PROMPT_FORGE_APPROVAL_FILE`，并在 POST 前 atomic consume。缺 bundle、过期、篡改、root 不一致、资源/队列不安全或已消费均 fail closed。

Experiment C 默认同样跳过。Stage 2 只接受 accepted/front-facing `CharacterBaseImage` 与对应完整 Stage 1 RunRecord；accepted descriptor 必须精确匹配一条 raw history 的 `type=output`/subfolder/filename 并解析到同一 canonical PNG。真实文件 SHA-256、lineage、canonical path/root、raw history、approved plan 和 consumption sentinel 必须一致。当前 verified Flux fingerprint 为 `fff6236efa6727ac6584d61f640a63f9602b2d07a545d216b96a870a681e6faf`；两个 base inputs 固定为 nodes `111/667`，pose/view prompt/model 字段不变且不注入 FLUX negative prompt。实际 UI→API 调用为 `get_workflow(format=api)`，receipt 记录真实 tool name、arguments、response digest 与受信本地 orchestrator provenance。消费后仅受控本地 MCP enqueue 边界可先原子写入 consumption-bound submission intent、再重算 graph 并提交；in-progress/success/failed intent 均禁止再次调用，失败 receipt 必须保留并先查 server。receipt 与 raw history 的 `prompt[3].extra_data.prompt_forge_enqueue_request_id` 必须绑定同一 request id。纯 JSON `patch-flux` fail closed。Stage 2 RunRecord 再从 canonical output root 读取 PNG 字节计算 hash。Stage 3 选择还必须明确 `accepted=true`、`CharacterAngleView`、`reference_eligible=true`、`semantic_conflict=false` 与 `hash_verified=true`。生产路径必须由真实 comfyui-mcp load/strip(or slice)/UI→API/runtime/validate 产生零 error executable graph，之后才可生成 `pending-c-<draft_hash>.json`；receipt 是受信本地 orchestrator 的可审计观察，不是虚构的 MCP 加密签名。REST 或失真转换不能充当证明。当前 comfyui-mcp 0.49.0 转换仍为 70 warnings/86 validation errors，因此没有上传、enqueue 或通过的 Experiment C 结论。

---

## 🧪 测试(全部真实,非 mock)

> 插件中的每个测试都针对真实数据调用实际脚本/CLI/二进制。**无 mock**。测试套件端到端证明组件行为(除了硬件依赖的 ComfyUI 服务 — 插件不要求该服务)。

| 测试 | 结果 | 实际测试内容 |
|---|---|---|
| `tests/test_obsidian_sync.sh` | **4/4 PASS** | 对真实 `/tmp/obsidian-sync-sandbox-$$` vault 跑 `scripts/obsidian-sync.sh`;校验路径穿越白名单(敌意 EVENT 参数 → 安全文件名)、event 默认 unknown、vault 缺失时非致命退出 0。 |
| `tests/test_check_updates.sh` | **17/17 PASS** | 对实际 `~/.cache` 和 `git ls-remote` 调 `check_updates.py` 和 `diff_recipes.py`;校验 JSON 封装、--help 退出 0、幂等自 diff(找出 13 个未变配方)。 |
| `tests/test_applications.sh` | **7/7 PASS** | 通过 `awk` 读每个 SKILL.md;校验 YAML frontmatter 分隔符、`name:` 和 `description:` 存在、`description` 字面含 "prompt-forge"。 |
| `scripts/validate-plugin-schema.sh` | **OK** | 解析 `.claude-plugin/plugin.json` 和 `marketplace.json`;校验 name 匹配 slug + dependencies path 存在。 |
| `scripts/validate-marketplace.sh` | **OK** | 同上,针对 `marketplace.json`(交叉校验 `plugin.json` name 存在 + slug 正则)。 |

跑全部:

```bash
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

## Prompt Forge v7 Stage 3/4 execution boundary

The character-to-video path is now represented as explicit, hash-bound stages:

1. `accept-reference` records the human acceptance of one verified Flux angle.
2. `plan-stage-execution` binds a Stage 3 camera img2img or Stage 4 Yusu Director plan to a fresh local capability report and the exact API graph.
3. `approve-stage` and `consume-stage` require a newly displayed draft, an exact approval event, and an exclusive consumption record.
4. `build-stage-submission` reconstructs the exact executable graph and request. `submit_stage(...)` is the only Stage 3/4 enqueue boundary, requires an injected trusted-local callable plus the canonical consumed-namespace receipt path, and reserves an exclusive submission intent before the call. `runtime.comfy_submit.ComfyPromptSubmitter` is only the local UTF-8 transport injected into that boundary; calling it directly does not prove approval, consumption, or idempotency.
5. `submit-character-base` provides the equivalent consumed Stage 1 boundary; `wait-stage` only polls history. `record-stage` requires raw history (not an optional summary), while `record` can bind Stage 1 submission, consumption, receipt, and raw-history evidence.

No approval event is synthesized from chat text. `submit-character-base` and
`submit-stage` are explicit side-effect commands, but they only accept already
approved/consumed evidence and write an intent/receipt before the loopback
POST; `wait-stage` is read-only. The local runtime evidence now covers the
complete exploratory chain: Stage 1 front-base acceptance, Stage 2 multiview
generation, Stage 3 camera img2img, and Stage 4 LTX video. The camera UI-to-API
converter still reports the observed 7 warnings / 3 errors, so Stage 3 uses
the pinned normalization bridge and submits the normalized graph with the
original UI workflow attached as UTF-8 provenance; unrelated conversion drift
remains fail-closed.

### Production profile correction (2026-08-03)

Stage 2 production uses `PromptForge-Flux2-Klein-multiview-flat-v2.json`, not
the legacy `Flux2-Klein人物一键多视图工作流.json`. The promoted flat graph has
fingerprint `9dc2b01e2aea0b051113b187b134d007f452df6c83cfcbbd8d325eaa4c29e4da`,
validates with zero errors/health warnings, and is local-only. The legacy graph
is retained for comparison because its current converter output contains
unresolved custom-node buses and dangling references; it is not a safe fallback.
No Stage 2 upload or enqueue is authorized without a fresh zero-error MCP
conversion receipt, exact profile/API hash, explicit approval, and terminal
artifact evidence. A local exploratory run has now produced real evidence:
Stage 2 prompt `3d8627ab-ec60-46b2-b648-77d8662412ed` completed successfully;
Stage 3 prompt `fe64ee38-a437-44de-9c15-1de7d9bc1f75` produced
`2026-08-03-231455_anima-aesthetic-v1.1_2026080304.png`; Stage 4 prompt
`dd6f2956-1041-461c-a000-a766fb0c125f` produced `屿僳_00004_.mp4`.
The local evidence is retained under `.live-artifacts/` (ignored from Git).
The flat output map also avoids a false claim: node `761` is `rear_45`, node
`609` is `rear`, and node `565` remains `side_unknown` because it emits a
left/right batch whose per-image semantics are not yet pinned.
Stage 4 additionally pins the Director graph's base model, all three LTX LoRAs,
Euler sampler, `linear_quadratic` scheduler, and active `1280x720` resolution;
the inactive custom `1280x736` widget is not treated as the output size. Because
the guide frame is 1216x832 and the Director uses `maintain aspect ratio` plus
32-pixel snapping, the effective output contract is explicitly `1024x704`;
the Stage 4 artifact verifier now checks width, height, 24 fps, and the LTX
`8n+1` decoded frame rule (24 logical frames -> 25 output frames). Any drift in
these inputs or output dimensions fails closed before the run record is accepted,
and the full LTX profile digest is pinned so a caller cannot remove a contract
and replace it with a self-authored profile hash.

- Vault(Obsidian):`~/.claude/rules/obsidian-workflow.md`(workspace 规则)
