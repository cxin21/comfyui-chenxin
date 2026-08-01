---
okm: dated
valid_until: 2026-10-30
status: active
kind: knowledge
family: sdxl
full_name: "SDXL (Stability AI)"
encoder: clip
architecture: "SDXL U-Net"
quality_prefix: ["masterpiece", "best quality"]
tag_style: mixed
note: "标签 + 自然语言混合。Token 限制 154。v3.1: 混合语法 = quality_tags + style_token + natural_language_scene + weighted_tags"
prompt_order:
  description: "混合风格。tag 锚定主体+风格，自然语言描述场景+光影。前 25% 必须含风格/媒介 token。"
  hybrid_structure:
    - "[quality tags]  # masterpiece, best quality"
    - "[style/medium anchor]  # 媒介紧跟质量前缀: concept_art/digital_painting/photo_realism"
    - "[subject tags]  # 1girl, hair, eyes, clothing..."
    - "[natural language scene]  # 环境、氛围、光影用自然语言描述"
    - "[weighted details]  # (key_element:1.2)"
    - "[color + mood]  # 自然语言或调色板描述"
    - "[composition tags]  # cinematic_composition, depth_of_field..."
  negative_strategy: "standard"
negative: ["blurry", "low quality", "deformed", "bad anatomy", "disfigured", "extra limbs", "watermark", "text", "worst quality", "jpeg artifacts"]
negative_note: "v3.1: 保留经典组合但不扩大。SDXL 负向 10-12 词足够，不加更多。"
clip_skip: 1
source: "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0"
updated: 2026-07-29
tags:
  - prompt-forge
  - model
  - text-to-image
  - clip-encoder
  - sdxl
---

# SDXL (Stable Diffusion XL)

Stability AI 的 SDXL 是文生图领域的基础模型，双 CLIP 编码器 + U-Net 架构。支持标签与自然语言混合提示词。

## 关联模型

基于 SDXL 架构的微调模型：[[pony]]、[[illustrious]]、[[noobai]]

## 核心规则

### 提示词风格

> [!info] 混合风格
> SDXL 支持**标签 + 自然语言混合**。可以先用标签描述核心元素，再用自然语言补充细节。

### Token 限制

Token 限制为 **154**。超过限制的部分会被截断。

### 质量前缀

标准质量前缀：
`masterpiece, best quality`

### Clip Skip

Clip Skip = 1（默认值，无需特殊设置）。

## 负向提示词

```
blurry, low quality, deformed, ugly, bad anatomy, disfigured, poorly drawn face, mutation, extra limbs, watermark, text, worst quality, jpeg artifacts
```
