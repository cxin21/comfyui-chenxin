---
okm: dated
valid_until: 2026-10-30
family: kling
full_name: "Kling 可灵 3.0 (Kuaishou)"
encoder: llm
note: "商业API。中文直出。15s/4K/60fps。运镜需具体描述。"
tag_style: natural
video_dimensions:
  - "运动主体+过程"
  - "物理质感"
  - "循环设计"
motion_priority: "运动本身是第一主体——不是静态帧+运镜"
single_subject: true
single_subject_note: "多主体场景高失败率。超过1个独立运动主体的需求显式警告。"
negative_default: ""
negative_max: 0
negative_note: "v3.1: 视频模型默认空负向。排行榜数据 10/11 top video 空负向。CFG≤1 时负向无效。"
cfg_range: "1-2"
prompt_structure:
  - "[运动主体]  # 单主体，谁在动。中文自然语言。"
  - "[运动过程]  # 怎么动——具体动作序列，占50%+篇幅"
  - "[物理质感]  # 动得怎么样——参考 motion-glossary"
  - "[场景上下文]  # 简短"
camera_rule: "不显式写相机指令——除非需要非自然运动。可灵从场景理解自主推断相机行为。"
negative: []
source: "https://kling.kuaishou.com"
updated: 2026-07-29
tags:
  - prompt-forge
  - model/video
  - llm-encoder
  - commercial-api
status: active
kind: knowledge
---

# Kling 可灵 3.0

快手可灵视频生成模型，**商业 API**，中文直出。

## 核心能力

- **时长**: 最长 15 秒
- **分辨率**: 4K
- **帧率**: 60fps
- **语言**: 中文原生支持

## 提示词要点

- 运镜指令需要**具体描述**（如 "镜头从左向右缓慢平移" 而非 "平移镜头"）
- 中文自然语言，不需要 tag 堆叠
- 视频提示词覆盖：运镜 + 时序 + 速度

## 同类模型

- [[hailuo]] — MiniMax 海螺，商业 API
- [[wan]] — 阿里通义 Wan，开源
- [[ltx]] — LTX 系列，开源极速
- [[seedream]] — 字节 Seedream（图像方向）

## 备注

商业 API 无本地部署选项，需通过官方平台或授权第三方调用。
