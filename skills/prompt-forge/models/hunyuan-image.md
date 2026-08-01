---
okm: dated
valid_until: 2026-10-30
family: hunyuan-image
full_name: "HunyuanImage 2.1/3.0 (Tencent)"
encoder: llm
note: "2.1: 17B; 3.0: 80B 自回归(当时最大开源)。前身 HunyuanDiT v1.2 已过时。"
tag_style: natural
negative:
  - "低质量"
  - "模糊"
  - "变形"
  - "丑陋"
  - "畸形"
  - "水印"
  - "文字"
source: "https://github.com/Tencent-Hunyuan/HunyuanImage-3.0"
updated: 2026-07-29
tags:
  - prompt-forge
  - model/image
  - llm-encoder
status: active
kind: knowledge
---

# HunyuanImage 2.1/3.0

腾讯混元文生图系列，**LLM 编码器 + 自回归架构**。

## 版本对比

| 版本 | 参数量 | 架构 | 状态 |
|------|--------|------|------|
| HunyuanDiT v1.2 | — | DiT | 已过时 |
| 2.1 | 17B | — | 可用 |
| 3.0 | 80B | 自回归 | 当时最大开源 |

## 负向提示词（推荐）

需要主动使用负向提示词，推荐组合：

- `低质量, 模糊, 变形, 丑陋, 畸形, 水印, 文字`

## 同类模型

- [[qwen-image]] — 阿里 Qwen-Image 2.0
- [[seedream]] — 字节 Seedream 4.5
- [[wan]] — 阿里通义 Wan（视频）

## 备注

3.0 为自回归架构，生成质量更高但推理成本也更高。不要使用已过时的 HunyuanDiT v1.2。
