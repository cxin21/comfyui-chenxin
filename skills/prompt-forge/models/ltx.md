---
okm: dated
valid_until: 2026-10-30
family: ltx
full_name: "LTX-Video / LTX-2 (Lightricks)"
encoder: llm
note: "LTX-Video 2B (极速); LTX-2 ~22B (4K/48fps/音画同步/最长20s)。英文+现在时态+景别开头。"
tag_style: natural
video_dimensions:
  - "运动主体+过程"
  - "物理质感"
  - "循环设计"
  - "景别(仅开头)"
motion_priority: "运动本身是第一主体——不是静态帧+运镜"
single_subject: true
single_subject_note: "多主体场景高失败率。超过1个独立运动主体的需求显式警告。"
negative_default: ""
negative_max: 0
negative_note: "v3.1: 视频模型默认空负向。排行榜数据 10/11 top video 空负向。CFG≤1 时负向无效。"
cfg_range: "1-2"
prompt_structure:
  - "[景别]  # Wide shot / Close-up——仅开头一句"
  - "[运动主体]  # 单主体，谁在动"
  - "[运动过程]  # 现在时态，具体动作序列，占50%+篇幅"
  - "[物理质感]  # 动得怎么样——参考 motion-glossary"
  - "[场景上下文]  # 简短"
camera_rule: "不显式写相机指令。LTX 仅要求景别开头(如 Wide shot of)，不需要跟踪/推拉/摇移。"
negative: []
source: "https://github.com/Lightricks/LTX-Video"
updated: 2026-07-29
tags:
  - prompt-forge
  - model/video
  - llm-encoder
status: active
kind: knowledge
---

# LTX 系列

Lightricks 的 LTX 视频生成模型系列，**速度极快**，适合快速迭代。

## 版本对比

| 版本 | 参数量 | 特性 |
|------|--------|------|
| LTX-Video | 2B | 极速推理，适合 8GB VRAM |
| LTX-2 | ~22B | 4K/48fps/音画同步/最长 20s |

## 提示词规范

必须遵循以下格式：

- **语言**: 英文
- **时态**: 现在时态（present tense）
- **结构**: 景别开头（如 `Wide shot of...`、`Close-up of...`）
- **维度**: 运镜 + 时序 + 速度

## 同类模型

- [[wan]] — 阿里通义 Wan，中文友好
- [[kling]] — 快手可灵，商业 API
- [[hailuo]] — MiniMax 海螺，商业 API

## 备注

8GB VRAM 环境下 LTX-Video 2B 是理想选择。LTX-2 升级到 4K 画质 + 原生音画同步，但需要更大显存。
