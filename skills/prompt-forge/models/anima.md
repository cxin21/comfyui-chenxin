---
okm: dated
valid_until: 2026-10-30
status: active
kind: knowledge
family: anima
full_name: "Anima (CircleStone Labs)"
encoder: llm
encoder_detail: "Qwen3-0.6B LLM"
architecture: "NVIDIA Cosmos-Predict2-2B DiT"
versions:
  base:
    steps: "30-50"
    cfg: "4-5"
    sampler: "er_sde"
    quality_prefix: ["masterpiece", "best quality", "score_7"]
  aesthetic:
    steps: "30-50"
    cfg: "4-5"
    sampler: "er_sde"
    quality_prefix: ["masterpiece", "best quality"]
    note: "不用任何 score_* 标签"
  turbo:
    steps: "8-12"
    cfg: "1"
    sampler: "euler"
    quality_prefix: ["masterpiece", "best quality"]
tag_style: space
tag_separator: ", "
score_separator: "_"
year_format: "year {year}"
artist_format: "@name"
safety_tags: ["safe", "sensitive", "nsfw", "explicit"]
tag_order_strategy: subject_first
prompt_order:
  description: "质量前缀→主体→环境→氛围→画师→year→安全标签。tag锚定前半，自然语言丰富后半。媒介紧跟质量前缀。"
  tag_anchor_portion:
    - "masterpiece, best quality  # Aesthetic 版不用 score_*; Base 版可加 score_7"
    - "[medium anchor]  # 媒介紧跟质量前缀"
    - "[source_anime]  # 可选"
    - "[character count]  # 1girl/1boy/solo"
    - "[character tag cascade]  # 从上到下：发→眼→脸→身→衣"
    - "[environment tag]"
  natural_language_portion:
    - "[spatial description]  # 空间层次"
    - "[lighting description]  # 光照氛围"
    - "[color + mood description]  # 色调情绪"
    - "[@artist_name]  # 画师引用"
    - "[year {current}]  # year token"
    - "[safety tag]  # safe/sensitive/nsfw/explicit"
  negative_strategy: "minimal"
negative:
  base: ["worst quality", "low quality", "blurry"]
  aesthetic: ["worst quality", "low quality", "blurry"]
  turbo: [""]
negative_note: "v3.1 精简: 现代 LLM encoder 负向应极简。Turbo CFG=1 空负向。不再需要 score_1/2/3, artist name, jpeg artifacts, chromatic aberration。"
license: "CircleStone Labs Non-Commercial License"
source: "https://huggingface.co/circlestone-labs/Anima"
updated: 2026-07-29
tags:
  - prompt-forge
  - model
  - text-to-image
  - llm-encoder
---

# Anima

Anima 是 CircleStone Labs 发布的文生图模型，使用 **Qwen3-0.6B LLM** 作为文本编码器，基于 **NVIDIA Cosmos-Predict2-2B DiT** 架构。这是目前少有的使用 LLM 原生编码器的文生图模型之一，能理解复杂自然语言提示词。

## 关联模型

同 LLM 编码器族：[[flux]]、[[qwen-image]]

## 标签体系

Anima 使用 **Gelbooru 标签优先** 规则。标签以空格分隔，score 标签使用下划线连接（如 `score_7`）。画师必须使用 `@name` 前缀格式。

## 版本差异

| 版本 | Steps | CFG | Sampler | 备注 |
|------|-------|-----|---------|------|
| base | 30-50 | 4-5 | er_sde | 支持 score_* 质量标签 |
| aesthetic | 30-50 | 4-5 | er_sde | **不用任何 score_* 标签** |
| turbo | 8-12 | 1 | euler | 快速出图，CFG=1 |

## 安全标签

Anima 支持四级安全标签：`safe`、`sensitive`、`nsfw`、`explicit`。生成时需显式指定期望的安全等级。

## 提示词结构

1. 质量前缀（quality_prefix）
2. 主体描述
3. 场景/环境
4. 画师（`@name` 格式）
5. 年份（`year {year}` 格式）
6. 安全标签

> [!warning] 负向提示词
> Aesthetic 版本的负向不用 score_1 / score_2 / score_3。Base 版本包含完整负向列表。
