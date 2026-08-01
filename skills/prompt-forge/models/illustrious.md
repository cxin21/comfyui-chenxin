---
okm: dated
valid_until: 2026-10-30
status: active
kind: knowledge
family: illustrious
full_name: "Illustrious XL (OnomaAIResearch)"
encoder: clip
architecture: "SDXL U-Net"
versions:
  v01:
    steps: "28-35"
    cfg: "5-7"
    sampler: "dpmpp_2m_karras"
quality_prefix: ["masterpiece", "best quality", "amazing quality", "very aesthetic", "absurdres"]
era_tags: ["newest", "recent", "mid", "early", "old"]
note: "不用 Pony 的 score_* 体系。质量前缀是 SDXL-base 堆栈。"
tag_style: underscore
tag_separator: "_"
year_format: none
artist_format: name_only
clip_skip: 1
prompt_order:
  description: "质量前缀→era_tag→媒介→角色。tag 级联从上到下。媒介紧跟质量前缀。"
  cascade:
    - "masterpiece, best quality, amazing quality, very aesthetic, absurdres"
    - "[era tag]  # newest/recent/mid/early/old —— 紧跟质量前缀"
    - "[medium/style anchor]  # 媒介紧跟质量+era"
    - "[character count]  # 1girl/1boy/solo"
    - "[hair cascade: color → length → style]"
    - "[eyes: color]"
    - "[face: expression]"
    - "[body: skin → build]"
    - "[clothing: top → bottom → accessories]"
    - "[pose + action]"
    - "[environment]"
    - "[artist name]  # 直接写，无前缀"
  negative_strategy: "standard"
negative: ["score_4", "score_3", "score_2", "score_1", "lowres", "bad anatomy", "bad hands", "text", "cropped", "worst quality", "low quality", "jpeg artifacts", "watermark"]
license: "CivitAI (check model page)"
source: "https://civitai.com/ (search Illustrious XL)"
updated: 2026-07-29
tags:
  - prompt-forge
  - model
  - text-to-image
  - clip-encoder
  - sdxl
---

# Illustrious XL

Illustrious XL 是 OnomaAIResearch 开发的 SDXL 微调模型。与 Pony 不同，Illustrious 使用传统的 **SDXL-base 质量堆栈**（masterpiece / best quality / amazing quality），而不是 score_* 体系。

## 关联模型

同属 SDXL 微调生态：[[pony]]、[[noobai]]

## 核心特征

### 质量体系

> [!important] 与 Pony 的关键区别
> Illustrious **不使用 Pony 的 score_* 体系**。质量前缀是 SDXL-base 标准堆栈：
> `masterpiece, best quality, amazing quality, very aesthetic, absurdres`

### 年代标签（Era Tags）

Illustrious 支持年代标签来控制画风时期：
`newest`、`recent`、`mid`、`early`、`old`

### 画师标签

画师标签格式为 `name_only`（直接写画师名，无需前缀）。

### Clip Skip

Clip Skip = 1（默认值）。

## 标签风格

- 下划线分隔（如 `blue_eyes`、`long_hair`）
- 不支持 year 格式标签

## 负向提示词

```
score_4, score_3, score_2, score_1, lowres, bad anatomy, bad hands, text, error, missing fingers, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, ugly, deformed
```
