---
name: manga-orchestrator
description: "AI 漫剧自驱动 orchestrator — 6 阶段流水线自动串联。从用户触发（'全自动生成漫剧 [书名]'）到最终视频，全程零人工干预。Also load prompt-forge first for VRAM/recipe context."
version: 1.1.0
author: Claude Code
triggers:
  - "全自动漫剧"
  - "自驱动生成"
  - "一键漫剧"
  - "orchestrate manga"
  - "跑全流程"
  - "auto manga"
allowed-tools: Bash, Read, Write, "mcp__comfyui-mcp__*"
---

# Manga Orchestrator — AI 漫剧自驱动编排 (v1.1, ported)

> **Plugin path**: `skills/manga-orchestrator/SKILL.md`
> **Upstream**: This is an L5 application skill. Load `prompt-forge` (L4 mega-skill) FIRST
> for VRAM/recipe context — `prompt-forge/SKILL.md` step 7 routes here for multi-stage pipelines.

## 1. 任务

接收单一用户触发（"全自动生成漫剧 [书名]" 或 "跑全流程 [项目]"），**零人工干预**完成 6 阶段流水线：

```
Stage 0 (bootstrap) → Stage 1 (LoRA) → Stage 2 (panels)
  → Stage 3 (review) → Stage 4 (motion) → Stage 5 (subtitle+concat)
  → 最终 mp4 + Obsidian vault 同步
```

## 2. 与其他 Skill 的关系

| 阶段 | 调用的 Skill / Agent |
|------|---------------------|
| 0 | `skills/manga-orchestrator/bootstrap.sh`（项目骨架，本 skill 自带脚本） |
| 1 | `skills/lora-trainer/SKILL.md`（训练 LoRA，1 路径 v2.2） |
| 2 | `skills/manga-stage-2-panels/SKILL.md` + comfyui-director agent |
| 3 | `skills/manga-stage-3-review/SKILL.md` + manga-stage-3-review 内部 6 维算法 skill |
| 4 | `skills/manga-stage-4-motion/SKILL.md` + comfyui-director agent |
| 5 | `skills/ffmpeg-pipeline/SKILL.md`：字幕 + 拼接 |
| **同步** | **`obsidian-suite:writing` skill** — 每次 Stage 完成自动写 vault |

> **自驱动 = 全流程无中断 + 自动写笔记**。

## 3. 输入参数

| 参数 | 必需 | 默认 | 说明 |
|------|------|------|------|
| `--title-cn` | ✅ | - | 中文书名 |
| `--title-en` | ✅ | - | 拼音书名（路径） |
| `--synopsis` | ✅ | - | 故事梗概（自动生成 01_plan.md） |
| `--characters` | ❌ | [] | 角色名列表 |
| `--scenes` | ❌ | [] | 场景名列表 |
| `--style` | ❌ | cinematic | 画风预设 |
| `--panel-count` | ❌ | 24 | 总分镜数 |
| `--auto-fix` | ❌ | true | 失败时自动 retry 一次 |
| `--max-hours` | ❌ | 24 | 单项目最长编排时间 |
| `--dry-run` | ❌ | false | 只打印计划不执行 |

## 4. 端到端流程

```
用户: "全自动生成漫剧 [书名]"
  ↓
解析参数 (title-cn/en, synopsis, characters, scenes, panel-count)
  ↓
读 01_plan.md 或从 synopsis 推断（Stage 0 任务）
  ↓
─── Stage 0: bootstrap ───
bash scripts/bootstrap.sh --title-cn "..." --title-en "..." --characters "..." --scenes "..."
  → 生成 02_assets/, 03_storyboard/01_plan.md, pipeline_state.json
  → sync vault: 00-Inbox/processed/decision-{date}-manga-orchestrator.md
  ↓
─── Stage 1: LoRA 训练 ───
对每个 character/scene:
  → bash lora-trainer/scripts/train-anima-standalone.sh --name <name> --refs <dir>
  → 5 张 test 图 + manga-stage-3-review 内部 6 维评分 ≥ 7.0 → lora_verified
  → sync vault: knowledge-{date}-{char-name}-lora-verified.md
  ↓
─── Stage 2: 分镜面板 ───
bash skills/manga-stage-2-panels/bootstrap.sh --project-root ...
  → 逐 panel 跑 AnimaStandardV7，自动评分 < 7.0 重试 1 次
  → 落盘 manifest.json + 02_panels/ + 03_storyboard/02_panels/
  → sync vault: stages/stage-2-panels-{title}-{date}.md
  ↓
─── Stage 3: 像素级审查 ───
bash skills/manga-stage-3-review/bootstrap.sh --project-root ...
  → 6 维评分（构图/光线/色彩/细节/风格/氛围）< 7.0 重试 1 次
  → 写 04_review.md + redo_list.json
  → sync vault: stages/stage-3-review-{title}-{date}.md
  ↓
─── Stage 4: 视频生成 ───
bash skills/manga-stage-4-motion/bootstrap.sh --project-root ...
  → LTX-2.3 一体（视频+音频），speaking 场景可选 --lip-sync → I2V_InfiniteTalk
  → 落盘 04_outputs/02_micro_motion/scene_NN.mp4
  → sync vault: stages/stage-4-motion-{title}-{date}.md
  ↓
─── Stage 5: 字幕 + 合成 ───
bash skills/ffmpeg-pipeline/bootstrap.sh --project-root ...
  → 拼接所有 scene + 加字幕 → final.mp4
  → sync vault: stages/stage-5-final-{title}-{date}.md
  ↓
─── 交付 ───
  → final.mp4 路径打印
  → vault 一份完整项目总结
  → pipeline_state.json.stages["all"] = completed
```

## 5. 架构：bash 调度 + Claude Agent 编排

| 阶段 | 谁做 |
|------|------|
| 解析用户输入 | **Agent** |
| Stage 0-5 调度 | **bash**（每个 stage 调对应 skill）|
| 决策（失败重试/分支） | **Agent** |
| 进度监控 | **bash** + pipeline_state.json |
| Vault 同步 | **Agent**（自动用 `obsidian-suite:writing` skill） |
| 日志 | **bash**（写到 `05_manifests/orchestrator.log`） |

## 6. 关键调度策略

### 6.1 状态机（pipeline_state.json）

```json
{
  "project": "wuyin_jianxin",
  "stages": {
    "0": { "status": "completed", "completed_at": "2026-07-27T08:00:00" },
    "1": { "status": "running", "started_at": "2026-07-27T08:05:00" },
    "2": { "status": "pending" },
    "3": { "status": "pending" },
    "4": { "status": "pending" },
    "5": { "status": "pending" }
  },
  "all_completed": false
}
```

每完成一个 stage，调 `state-update.sh completed <stage-id>` 更新状态。

### 6.2 失败处理

| 失败 | 策略 |
|------|------|
| Stage X 失败 | 标 `failed`，继续 Stage X+1（如 04_outputs 已有部分 panel，可继续） |
| Stage 0 失败 | **停止** — 项目骨架未建立，后续无法做 |
| Stage 1 部分失败 | 跳过失败的 character/scene，标 `lora_verified: false` |
| ComfyUI 服务挂 | 重试 3 次，每次 30 秒；仍失败则人工干预 |
| max-hours 超时 | 标 `timeout`，保留已完成 stage 输出 |

### 6.3 自驱动原则

- **零中断**：每个 Stage 完成后自动启动下一 Stage
- **零询问**：除非用户显式说"逐步确认"，否则不问
- **零手动**：不打开 ComfyUI 浏览器界面（除非 OOM 调试）
- **vault 同步**：每个 Stage 完成自动用 `obsidian-suite:writing` skill 写笔记

### 6.4 进度可见性

- 实时：打印每个 stage 的 status + 主要进度
- `pipeline_state.json` 持续可读
- `05_manifests/orchestrator.log` 滚动日志
- Stage 完成时桌面通知（如果 Stop hook 注册）

## 7. 输出

- 最终：项目目录下 `04_outputs/05_final/` 含拼接 mp4
- vault：`D:/ObsidianWorkSpace/workspace/10-Projects/claude-code/projects/{title-en}/` 一个完整笔记 + 6 个 stages/ 子笔记
- pipeline_state.json：全部 stages[].status = completed

## 8. 与 ComfyUI 的关系

- **Stage 0/5**：只用 bash，不调 ComfyUI
- **Stage 1**：独立 venv 训练，**不需要** ComfyUI 在线（v2.2 单路径）
- **Stage 2/4**：必须 ComfyUI 在线服务（`http://127.0.0.1:8188`）
- **Stage 3**：只用 mcp__comfyui-mcp__view_image 读图

**前置检查**：orchestrator 启动时 `mcp__comfyui-mcp__get_system_stats` 确认 ComfyUI 在线。如离线，提示用户重启 licyk 启动器。

## 9. 已知 Caveats

1. **前提**：ComfyUI 服务必须启动（否则 Stage 2/4 失败）
2. **Stage 1 独立**：v2.2 单路径用 Anima-Standalone-Trainer 独立 venv，不需要 ComfyUI
3. **ffmpeg-pipeline 已就绪**：v1.0.0 完成 Stage 5 concat + SRT + 可选字幕烧入
4. **orchestrator 不是单一 bash**：是 bash + Claude Agent 协作的 *orchestration pattern*，需要在 Claude 会话中运行

## 10. 升级路径

- [x] 加 `ffmpeg-pipeline` skill ✓ (v1.0)
- [ ] 加 desktop notification（基于 Stop hook）
- [ ] 加项目级 checkpoint（resume from any stage）
- [ ] 加并行 Stage 1（多 character LoRA 并行训练）
- [ ] 加 statusline 实时显示

## 11. 版本

- v1.1.0（2026-07-30）：P1.1 ported — frontmatter 声明 prompt-forge 上游；路径全部改为 plugin 内
- v1.0.0（2026-07-27）：MVP 版本 — Stage 0-4 + vault 同步；Stage 5 用 ffmpeg 临时脚本；前置检查 ComfyUI 服务

## 12. 相关引用

- **上游**: `skills/prompt-forge/SKILL.md`（L4 mega-skill — 必须先加载）
- 6 个依赖 skills: `skills/manga-orchestrator/`（自含 bootstrap）/ `skills/lora-trainer/` / `skills/manga-stage-2-panels/` / `skills/manga-stage-3-review/` / `skills/manga-stage-4-motion/` / `skills/ffmpeg-pipeline/`
- 外部依赖: manga-stage-3-review 内部 6 维算法 skill / `obsidian-suite:writing` skill
- ComfyUI: MCP server 必需在线（Stage 2/4）
- vault: `D:/ObsidianWorkSpace/workspace/10-Projects/claude-code/`
- 调度 Agent: `comfyui-director`（Stage 2/4）
