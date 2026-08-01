---
title: "comfyui-chenxin Skills + Agents 完整清单"
created: 2026-08-01
tags:
  - comfyui-chenxin
  - skills
  - agents
  - inventory
  - audit
source: 'session 2026-08-01 — user explicit ask: 列一下所有 skills 和 agents'
status: active
okm: dated
---

# decision: comfyui-chenxin Skills + Agents 完整清单(2026-08-01)

## 摘要

cxin21/comfyui-chenxin 插件当前(commit 7a17be1)的完整 Skills + Agents 清单。8 个真 SKILL.md + 1 个 stub + 6 个非 SKILL 的 internals + 3 个 L3 知识 fixture + 1 个 legacy + 7 个 agent = 总共 26 个文件。

## 📚 Skills(11 个 SKILL.md + 6 internals + 3 L3 + 1 legacy)

### L4 mega-skill(1 个)

#### chenxin-core

- 路径: skills/chenxin-core/SKILL.md
- name: chenxin-core
- 触发词(47 个):
  - comfyui, comfy ui, workflow
  - 出图, 跑工作流, 生成图片, 生成视频, 出视频
  - manga, 漫画, anime, anima, wan, ltx, ltx-2.3
  - hunyuan, flux, sdxl, sd 1.5, sd1.5, stable diffusion
  - krea, seedream, nano banana, Qwen-Image
  - ideogram, Recraft, Kling, Seedance, Veo, Sora
  - Runway, Luma, Stable Audio, ACE-Step
  - video, talking head, inpaint, upscale, controlnet, IP-Adapter, refiner, LoRA
  - 8 GB VRAM, 8GB, small VRAM, low VRAM
  - vae, unload model
- 用途: L4 mega-skill 路由层。关键词 → 工具/配方/工作流 dispatch
- 状态: 真, 已 audit

### L5 application skills(7 个)

#### manga-orchestrator

- 路径: skills/manga-orchestrator/SKILL.md
- version: 1.1.0
- 触发词: 全自动漫剧, 自驱动生成, 一键漫剧, orchestrate manga, 跑全流程, auto manga
- 用途: 6 阶段流水线编排
- 状态: 真

#### manga-stage-1-lora

- 路径: skills/manga-stage-1-lora/SKILL.md
- version: 0.0.1
- 触发词: 无
- 用途: STUB — 实际由 lora-trainer 覆盖
- 状态: stub(49 行)

#### manga-stage-2-panels

- 路径: skills/manga-stage-2-panels/SKILL.md
- version: 2.1.0
- 触发词: 生成分镜, 分镜面板, 生成 panels, stage 2, storyboard panels, 跑分镜
- 用途: Stage 2 分镜生成(锁定 AnimaStandardV7.json,73 节点)
- 状态: 真

#### manga-stage-3-review

- 路径: skills/manga-stage-3-review/SKILL.md
- version: 2.1.0
- 触发词: 审查分镜, 像素级审查, review panels, 评图, stage 3, judge images
- 用途: Stage 3 6 维美学评审(已 absorbed aesthetic-judge)
- 状态: 真

#### manga-stage-4-motion

- 路径: skills/manga-stage-4-motion/SKILL.md
- version: 3.1.0
- 触发词: 生成视频, 微动作, stage 4, 图生视频, 说话视频, 加台词, 唇型同步, talking head
- 用途: Stage 4 视频生成(锁定 ltx23..v44.json,78 节点)
- 状态: 真

#### ffmpeg-pipeline

- 路径: skills/ffmpeg-pipeline/SKILL.md
- version: 1.1.0
- 触发词: 加字幕, 合成视频, concat, make final, stage 5, 拼接视频
- 用途: Stage 5 字幕 + 拼接
- 状态: 真

#### lora-trainer

- 路径: skills/lora-trainer/SKILL.md
- version: 2.3.0
- 触发词: 训练 LoRA, 训 LoRA, 训 Anima LoRA, train LoRA, lora training, 训角色, 训场景
- 用途: Anima Standalone-Trainer wrapper(8 GB 显存友好)
- 状态: 真

## L3/L4 internals(在 skills/chenxin-core/internals/,非 SKILL.md)

| 文件 | 行数 | 用途 |
|---|---|---|
| recipe_yaml.py | 350 | 幂等加 YAML frontmatter 到 recipes/MODELS.md |
| recipe_lookup.py | 174 | CLI: 按 id/substring 查 recipe dialect |
| hardware_decide.py | 166 | CLI: VRAM-aware 模型推荐 |
| context_graph.md | 57 | L1-L8 数据流图(纯文档) |
| workflow-config-guard.md | 4.5 KB | 4 步备份-修改-执行-恢复 SOP |
| workflow-resolver.md | 7.4 KB | AnimaStandardV7(73)+ ltx23(78)节点映射 |

## L3 知识底座(在 skills/chenxin-core/ 下,3 个)

| 文件 | 行数 | 用途 |
|---|---|---|
| recipes/MODELS.md | 2462 | 80 个 model 配方,带 YAML frontmatter |
| templates_index.json | 6651 | 662 个工作流模板 |
| hardware/8gb.json | 58 | 8 GB VRAM 决策矩阵 |

## 🤖 Agents(7 个)

### chenxin-orchestrator

- 路径: agents/chenxin-orchestrator.md
- model: sonnet
- tools: Read, Write, Edit, Bash, Grep, Glob, Agent
- 用途: 读 SPEC.md,找下一未勾选 phase,spawn chenxin-builder + chenxin-reviewer
- 状态: 真

### chenxin-builder

- 路径: agents/chenxin-builder.md(48 行)
- model: sonnet
- tools: Read, Write, Edit, Bash, Grep, Glob, Skill
- 用途: 实现一个 phase 的代码变更
- 状态: 真

### chenxin-publisher

- 路径: agents/chenxin-publisher.md(45 行)
- model: sonnet
- tools: Read, Write, Edit, Bash, Grep, Glob
- 用途: bump 版本,生成 CHANGELOG,open release PR
- 状态: 真

### chenxin-update-bot

- 路径: agents/chenxin-update-bot.md(89 行)
- model: haiku
- tools: Read, Bash, Grep, Glob
- 用途: 周更拉 4 上游源
- 状态: 真

### chenxin-reviewer ⭐

- 路径: agents/chenxin-reviewer.md(63 行)
- model: sonnet
- tools: Read, Bash, Grep, Glob, Task
- 用途: 5 维对抗性审查
- 5 维 slot:
  1. code-reviewer — 质量
  2. security-reviewer — 安全
  3. **chenxin-doctor** — workflow JSON(原 aesthetic-judge 已 absorbed)
  4. comfyui-doctor — VRAM
  5. recipe-expert — prompt dialect
- 阈值: blockers == [] AND passed ≥ 4/5
- 状态: 真

### chenxin-doctor

- 路径: agents/chenxin-doctor.md(38 行)
- model: haiku
- tools: Read, Bash, Grep, Glob, mcp__comfyui-mcp__health_check, list_local_models, get_system_stats, get_logs
- 用途: VRAM + 健康诊断
- 状态: 真

### comfyui-director ⭐

- 路径: agents/comfyui-director.md(310 行)
- model: sonnet
- tools: mcp__comfyui-mcp__*, Read, Glob, Grep, Bash
- version: 4.0.0
- 用途: 编排层 — 6 阶段流水线,锁定工作流 + 节点白名单
- 状态: 真(v3→v4 audit 修复完)

## 📊 统计

| 维度 | 数量 |
|---|---|
| 真 SKILL.md | 8(1 L4 + 7 L5) |
| Stub SKILL.md | 1(manga-stage-1-lora) |
| L4 internals | 6 |
| L3 知识底座 | 3 |
| L3 legacy | 1 |
| **Total skills 文件** | **19** |
| 真 agents | 7 |
| Stub agents | 0 |
| **Total agent 文件** | **7** |
| agent (sonnet) | 5 |
| agent (haiku) | 2 |
| agent 用 mcp 工具 | 2 |

## 状态

下一步:逐个过 8 个真 SKILL.md(用户已要求)。准备好回复"下一个"以继续。
