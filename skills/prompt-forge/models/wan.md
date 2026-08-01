---
okm: dated
valid_until: 2026-10-30
family: wan
full_name: "Wan (Alibaba Tongyi)"
encoder: llm
architecture: "DiT + MoE"
note: "中文友好。2.1/2.2 开源; 2.2-S2V 音频驱动数字人。⚠️ 2.6/2.7 版本待核实。"
tag_style: natural
video_dimensions:
  - "运动主体+过程"
  - "物理质感"
  - "循环设计"
  - "运镜(仅必要时)"
motion_priority: "运动本身是第一主体——不是静态帧+运镜"
single_subject: true
single_subject_note: "多主体场景高失败率。超过1个独立运动主体的需求显式警告。"
negative_default: ""
negative_max: 0
negative_note: "v3.1: 视频模型默认空负向。排行榜数据 10/11 top video 空负向。CFG≤1 时负向无效。"
cfg_range: "1-2"
prompt_structure:
  - "[运动主体]  # 单主体，谁在动"
  - "[运动过程]  # 怎么动——具体动作序列，占50%+篇幅"
  - "[物理质感]  # 动得怎么样——参考 motion-glossary"
  - "[场景上下文]  # 在哪，什么环境"
  - "[氛围/光/色]  # 简短即可"
  - "[循环设计]  # 可选: 运动是否自然循环"
camera_rule: "不显式写相机指令——模型从场景理解中自主推断。仅在需要非自然相机运动时写。"
negative:
  - ""
source: "https://github.com/Wan-Video/Wan2.2"
updated: 2026-07-29
tags:
  - prompt-forge
  - model/video
  - llm-encoder
status: active
kind: knowledge
---

# Wan 系列

阿里通义 Wan 系列视频生成模型，**DiT + MoE** 架构，中文友好。

## 版本线

| 版本 | 特性 | 状态 |
|------|------|------|
| 2.1 | 基础视频生成 | 开源 |
| 2.2 | 视频生成 + S2V 音频驱动数字人 | 开源 |
| 2.6/2.7 | 待核实 | ⚠️ 传闻版本 |

## 提示词维度

视频提示词需覆盖三个额外维度：

- **运镜**: 镜头运动方式（推拉摇移跟）
- **时序叙事**: 时间线描述（先...然后...最后...）
- **运动速度**: 动作节奏（缓慢/快速/渐进）

## 负向提示词

`low quality, blurry, distorted, flickering`

## 同类模型

- [[ltx]] — LTX-Video 系列，英文提示词
- [[kling]] — 快手可灵，商业 API
- [[hailuo]] — MiniMax 海螺，商业 API
- [[qwen-image]] — 同门阿里 Qwen-Image（图像方向）

## 备注

中文视频生成的优选。2.2-S2V 支持语音驱动数字人（speech-to-video），适合漫剧说话场景。
