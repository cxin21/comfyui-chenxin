---
okm: dated
valid_until: 2026-10-30
family: hailuo
full_name: "Hailuo 海螺 2.3 (MiniMax)"
encoder: llm
note: "商业API。物理运动真实。⚠️ 运镜指令语法以官方最新文档为准。"
tag_style: natural
video_dimensions:
  - "运动主体+过程"
  - "物理质感(MiniMax核心优势)"
  - "循环设计"
motion_priority: "运动本身是第一主体——MiniMax 的物理运动真实感是差异化优势，充分利用。"
single_subject: true
single_subject_note: "多主体场景高失败率。超过1个独立运动主体的需求显式警告。"
negative_default: ""
negative_max: 0
negative_note: "v3.1: 视频模型默认空负向。排行榜数据 10/11 top video 空负向。CFG≤1 时负向无效。"
cfg_range: "1-2"
prompt_structure:
  - "[运动主体]  # 单主体，谁在动。中文自然语言。"
  - "[运动过程]  # 怎么动——具体动作序列，占50%+篇幅。MiniMax 物理强，放心写详细的运动物理。"
  - "[物理质感]  # 动得怎么样——参考 motion-glossary。MiniMax 的强项。"
  - "[场景上下文]  # 简短"
camera_rule: "不显式写相机指令。运镜语法以官方最新文档为准，仅在必要时使用。"
negative: []
source: "https://hailuoai.com"
updated: 2026-07-29
tags:
  - prompt-forge
  - model/video
  - llm-encoder
  - commercial-api
status: active
kind: knowledge
---

# Hailuo 海螺 2.3

MiniMax 海螺视频生成模型，**商业 API**，以物理运动真实感著称。

## 核心优势

- **物理运动**: 运动轨迹自然，符合真实物理规律
- **语言**: 中文自然语言提示词

## 注意事项

> [!warning] 运镜语法
> 运镜指令的**具体语法**以官方最新文档为准，不同版本可能有调整。使用前务必查阅最新 API 文档。

## 提示词维度

- **运镜**: 镜头运动（推拉摇移跟）
- **时序**: 时间线叙事
- **速度**: 运动节奏

## 同类模型

- [[kling]] — 快手可灵，商业 API
- [[wan]] — 阿里通义 Wan，开源
- [[ltx]] — LTX 系列，开源极速

## 备注

与可灵同为国产商业视频 API。物理运动真实感是差异化优势，适合需要精确物理模拟的场景。
