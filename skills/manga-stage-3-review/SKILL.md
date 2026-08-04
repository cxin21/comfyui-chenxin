---
name: manga-stage-3-review
description: "AI 漫剧 Stage 3 — 像素级审查。对 Stage 2 的 panels 调 aesthetic-judge 逐张评分（6 维），生成双层 review.md 报告，< 7.0 自动 re-do 1 次，标 failed + redo_list。Also load prompt-forge first for VRAM/recipe context."
version: 2.1.0
author: Claude Code
status: legacy
triggers: []
allowed-tools: Bash, Read, Write, "mcp__comfyui-mcp__*"
---
> Legacy compatibility only. Do not route production work here; use
> skills/prompt-forge/SKILL.md and its four-stage character-to-video flow.

# Manga Stage 3 — 像素级审查 (v2.1, ported — 6 维)

> **Plugin path**: `skills/manga-stage-3-review/SKILL.md`
> **Upstream**: L5 application skill. Load `prompt-forge` (L4) first for VRAM/recipe context
> before scoring — `prompt-forge/SKILL.md` step 7 routes here for stage 3 of manga pipeline.

## 1. 概述

Stage 3 接受 Stage 2 的 PNG panels，**自动**完成：
1. 调 manga-stage-3-review 内部 6 维算法 skill 对每张图 **6 维** 评分（构图 / 光线 / 色彩 / 细节 / 风格 / **氛围**）
2. 生成双层 review.md（**6 维总表** + 每镜详细）
3. 按阈值（< 7.0 / 10）标 verified / failed
4. failed panel **自动**调 Stage 2 `--panel N` 重跑 1 次
5. 重跑后仍 < 7.0 → 标 verified=false + redo_list.json
6. 更新 pipeline_state.json
7. 同步 review.md 到 Obsidian vault

**无 ControlNet / IP-Adapter**，纯 LoRA 角色一致性（B1 决策）。

> **v2 重要变更**：评分维度 5 → **6**（新增"氛围"维度）；review.md 模板增 `atmosphere` 列；schema 增 `atmosphere` 字段。

## 2. 关键设计决策（用户 2026-07-27 修订）

| 决策 | 选择 | 实施 |
|------|------|------|
| A2 | **总分 < 7.0** 标 re-do | 与 Stage 2 重试阈值一致 |
| **A2.5** | **6 维评分** | **构图 / 光线 / 色彩 / 细节 / 风格 / 氛围**（v2 新增） |
| B3 | **混合** | failed 自动 re-do 1 次，仍 < 7.0 标 failed |
| C3 | **双层报告** | **6 维总表** + 每镜详细小节 |
| F3 | **标失败 + redo_list.json** | 失败 panel 不强 re-do |
| 同步 | review.md → Obsidian | 跨项目可检索 |

## 3. 架构

```
skills/manga-stage-3-review/
├── SKILL.md                       ← 本文件
├── bootstrap.sh
├── scripts/
│   ├── scan-panels.sh
│   ├── review-template.sh         ← v2 已加 atmosphere
│   ├── mark-redo.sh
│   ├── state-update.sh
│   └── sync-vault.sh
└── templates/
    └── review.md.template         ← v2 已加 atmosphere
```

## 4. 端到端流程

```
Stage 2 输出
  ├─ 04_outputs/01_panels/scene_NN.png
  └─ 04_outputs/01_panels/manifest.json
                ↓
        bash scripts/bootstrap.sh --project-root <path> --stage manga-stage-3-review
                ↓
  Step 1: 前置检查（Stage 2 完成）
  Step 2: 扫描所有 panels
  Step 3: 生成 review.md 模板（6 维双层）
  Step 4: 核心循环（每 panel）
    a. 内部 6 维算法评分（已 absorbed aesthetic-judge skill）
    b. 写 review.md
    c. mark-redo 标 verified/failed
    d. < 7.0 → Stage 2 重跑 1 次
    e. 重审仍 < 7.0 → verified=false + redo_list.json
  Step 5: 写 redo_list.json
  Step 6: 更新 manifest.json + state
  Step 7: 同步到 Obsidian vault
                ↓
  manifest.json (含 stage3_review, atmosphere 字段)
  03_storyboard/04_review.md (6 维双层报告)
  redo_list.json
  vault/stages/stage-3-review-<title>-<date>.md
```

## 5. 触发词

| 用户说 | 行为 |
|--------|------|
| "审查分镜" / "像素级审查" / "stage 3" / "评图" / "judge images" | 调 bootstrap.sh |
| "续审 stage 3" | bootstrap.sh 跳过 stage3_verified=true |
| "再审 [panel 号]" | bootstrap.sh --panel N |

## 6. 输入参数

| 参数 | 必需 | 默认 | 说明 |
|------|------|------|------|
| `--project-root` | ✅ | - | 项目根 |
| `--threshold` | ❌ | 7.0 | re-do 阈值 |
| `--auto-redo` | ❌ | true | failed panel 自动 re-do |
| `--max-retries` | ❌ | 1 | 最大重试 |
| `--panel` | ❌ | - | 单 panel 重审 |
| `--sync-vault` | ❌ | true | 同步到 Obsidian |

## 7. 双层 review.md 模板（C3，v2 已加 atmosphere）

```markdown
# 像素级审查报告 — <title_cn>

**项目**: <title_en>
**Stage**: 3 / 6
**生成日期**: 2026-07-27
**审查范围**: 24 个 panels
**阈值**: < 7.0 标 re-do
**维度数**: 6（构图 / 光线 / 色彩 / 细节 / 风格 / 氛围）

## 总表

| # | 场景 | 构图 | 光线 | 色彩 | 细节 | 风格 | 氛围 | 总分 | 状态 |
|---|------|------|------|------|------|------|------|------|------|
| 1 | 京都夜樱 | 8 | 7 | 8 | 7 | 9 | 8 | 7.8 | ✅ |
| 2 | 京都夜樱 | 6 | 5 | 7 | 5 | 7 | 6 | 6.0 | ⚠ re-do |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

**统计**:
- 平均: 7.5
- 各维度平均: 构图 7.3 / 光线 7.0 / 色彩 7.5 / 细节 6.8 / 风格 7.8 / 氛围 7.4
- 通过率: 83% (20/24)
- Re-do: 4 个

## 待 re-do 列表（4 个）

| # | 场景 | 总分 | 主要问题 | 建议 |
|---|------|------|---------|------|
| 2 | 京都夜樱 | 6.0 | 光线 5.0, 氛围 6.0 | 加"golden hour rim light" |
| 5 | 十字伤 | 5.8 | 细节 4.0（手部）| 提升 LoRA 强度到 0.9 |

## 已 verified 的 panel（20 个）

略

## 详细审查（每镜独立）

### Panel 1 — 京都夜樱 / 绯村剑心
- 路径: `04_outputs/01_panels/scene_01.png`
- 原始 prompt: `feicun_jianxin, young swordsman...`
- **6 维评分**:
  - 构图: 8/10
  - 光线: 7/10
  - 色彩: 8/10
  - 细节: 7/10
  - 风格: 9/10
  - **氛围: 8/10** — 暮春感强，剑心孤独情绪到位
  - **总分: 7.8/10** ✅
- 改进建议: 可加 "rim lighting from right"
```

## 8. 核心循环详解

```
Step 4: 对每个 panel:

  v1: 首次审查
    mcp__comfyui-mcp__view_image(scene_NN.png)
    (内部 6 维 + 建议 — 已 absorbed aesthetic-judge)

  v1 评分 → review.md + manifest.json.stage3_review

  if 总分 >= 7.0:
    verified = true
  else if 总分 < 7.0 且 retry_count < 1:
    retry_count += 1
    Stage 2 --panel N 重跑
    v2: 重新评分
    if v2 >= 7.0: verified = true
    else: verified = false + redo_list
  else:
    verified = false + redo_list
```

## 9. 输出 schema（v2 已加 atmosphere）

### 04_outputs/01_panels/manifest.json

```json
{
  "panels": [
    {
      "id": 1,
      "stage2": { ... },
      "stage3_review": {
        "v1": {
          "composition": 8,
          "lighting": 7,
          "color": 8,
          "detail": 7,
          "style": 9,
          "atmosphere": 8,
          "total": 7.8,
          "suggestions": ["rim lighting from right"]
        },
        "v2": null,
        "verified": true,
        "retry_count": 0
      }
    }
  ]
}
```

### 04_outputs/01_panels/redo_list.json

```json
{
  "generated_at": "2026-07-27",
  "threshold": 7.0,
  "dimensions": 6,
  "items": [
    {
      "panel_id": 2,
      "scene": "京都夜樱",
      "v1_score": 6.0,
      "v2_score": 6.5,
      "retry_count": 1,
      "main_issues": ["光线 5.0", "氛围 6.0"],
      "suggestions": ["加 golden hour rim light", "增强场景情绪化"]
    }
  ]
}
```

## 10. 续跑

`bootstrap.sh --resume`：跳过 stage3_review.verified == true 的。

## 11. 与下游接口

- ✅ verified → Stage 4 (LTX-2.3 微动作+说话) 直接使用
- ⚠ failed → 人工调整或 Stage 2 --panel N 重跑

## 12. Obsidian 同步

`D:/ObsidianWorkSpace/workspace/10-Projects/claude-code/stages/stage-3-review-<title>-<date>.md`

```yaml
---
title: "Stage 3 Review — <title>"
created: 2026-07-27
tags: [stage-3, review, manga-pipeline, comfyui-mcp, 6-dimensions]
source: "<project_root>/03_storyboard/04_review.md"
status: active
---
```

## 13. 性能估算 / Caveats / 升级路径 / 引用

- 性能：24 panels × 6 维评分 ≈ 5-8 min（纯 mcp__comfyui-mcp__view_image + aesthetic-judge）
- Caveats：mcp__comfyui-mcp__view_image 需要 ComfyUI 在线
- 升级：[ ] 加并行 review；[ ] 加语义 diff（vs 上一次生成）

## 14. 相关引用

- **上游**: `skills/prompt-forge/SKILL.md`（L4 — 必须先加载 for VRAM/recipe）
- 上游: `skills/manga-stage-2-panels/SKILL.md` (Stage 2 panels)
- 下游: `skills/manga-stage-4-motion/SKILL.md` (Stage 4 视频)
- 评分器: manga-stage-3-review 内部 6 维算法 skill
- orchestrator: `skills/manga-orchestrator/SKILL.md` §4 Stage 3

## 15. 版本

- v2.1.0（2026-07-30）：P1.1 ported — frontmatter 声明 prompt-forge 上游；路径全部改为 plugin 内
- v2.0.0（2026-07-27）：评分维度 5→6（加 atmosphere）；review.md 模板增列；schema 增字段；与 aesthetic-judge 对齐
- v1.0.0（旧）：5 维评分
