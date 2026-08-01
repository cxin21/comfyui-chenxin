---
okm: dated
valid_until: 2026-10-30
family: qwen-image
full_name: "Qwen-Image 2.0 (Alibaba)"
encoder: llm
tag_style: natural
note: "中英混合自然语言。1K token 长指令。基本不用负向。"
negative_support: minimal
source: "https://github.com/QwenLM/Qwen-Image"
updated: 2026-07-29
tags:
  - prompt-forge
  - model/image
  - llm-encoder
status: active
kind: knowledge
---

# Qwen-Image 2.0

Qwen-Image 2.0 是阿里通义千问团队的图像生成模型，采用 LLM 编码器，支持**中英混合自然语言**输入。

## 核心特征

- **编码器**: LLM（非 CLIP），支持最长 1K token 的详细描述
- **提示词风格**: 自然语言，无需 tag 堆叠
- **负向提示词**: 基本不需要，模型对负向支持极简
- **语言**: 中英混合直出，中文原生支持

## 同类模型

- [[seedream]] — 字节 Seedream 4.5，中文直出
- [[hunyuan-image]] — 腾讯混元，LLM 编码器
- [[wan]] — 阿里通义 Wan 系列（视频方向）

## 备注

适合中文场景的复杂构图描述，提示词工程重点放在**正向描述**而非负向约束上。
