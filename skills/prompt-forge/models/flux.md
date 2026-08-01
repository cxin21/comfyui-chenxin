---
okm: dated
valid_until: 2026-10-30
status: active
kind: knowledge
family: flux
full_name: "FLUX.1 / FLUX.2 (Black Forest Labs)"
encoder: llm
encoder_detail: "FLUX.1: T5+CLIP; FLUX.2 pro/flex/dev: Mistral-3 24B VLM; FLUX.2 klein: Qwen3 8B"
tag_style: natural
note: "自然语言段落。不用 Danbooru tag。括号权重无效。"
negative_support: false
negative_note: "v3.1: FLUX.2 全系列不支持负向。FLUX.1 Schnell CFG=1-2 负向无效 = 空即可。FLUX.1 Dev 仅在特定问题出现时加 ≤3 描述性排除词。默认全空。"
negative_default: ""  # 排行榜 top prompt 100% 空或 ≤3 词
tag_order_strategy: medium_first
prompt_order:
  description: "媒介在第一句锚定。小说式视觉描写，不枚举标签。每个句子引入新视觉信息。"
  natural_language:
    - "[medium anchor]  # 第一句：媒介/风格约束 latent 子空间"
    - "[subject + context]  # 第二句：谁 + 在哪 + 做什么"
    - "[spatial + atmosphere]  # 第三句：空间层次 + 氛围 + 光"
    - "[color + mood]  # 第四句：色调 + 情绪"
    - "[composition + camera]  # 第五句：怎么看（景别/焦段/角度）"
    - "[style references]  # 可选：inspired by A and B"
  concept_density: "每个句子引入新视觉信息，不重复描述同一事物"
json_support: true
hex_color_support: true
multi_ref_support: true
max_tokens: 32768
recommended_length: "30-80 words"
source: "https://docs.bfl.ai/guides/prompting_guide_flux2"
updated: 2026-07-29
tags:
  - prompt-forge
  - model
  - text-to-image
  - llm-encoder
---

# FLUX.1 / FLUX.2

Black Forest Labs 的 FLUX 系列是目前最先进的文生图模型之一，使用 **VLM/LLM 编码器** 而非传统 CLIP，支持**自然语言段落**作为提示词。

## 关联模型

同 LLM 编码器族：[[anima]]、[[qwen-image]]、[[sd35]]

## 编码器版本

| 模型 | 编码器 |
|------|--------|
| FLUX.1 全系列 | T5 + CLIP |
| FLUX.2 pro / flex / dev | Mistral-3 24B VLM |
| FLUX.2 klein | Qwen3 8B |

## 核心规则

### 自然语言

> [!important] 不用 Danbooru tag
> FLUX 使用**自然语言段落**作为提示词。标签堆栈（tag pile）对 FLUX 无效。括号权重也无效。

### 推荐长度

**30-80 words** 为最佳范围。最大 token 限制 32768，但过长的提示词会稀释关键信息。

### 负向提示词

> [!warning] FLUX.2 不支持负向
> FLUX.2 全系列不支持负向提示词。FLUX.1 Schnell CFG=1-2 负向无效。只有 FLUX.1 Dev 可用 5-10 个描述性排除词（不用 embedding）。

## 高级功能

| 功能 | 支持 |
|------|------|
| JSON prompting（结构化提示词） | 是 |
| Hex 色值控制 | 是 |
| Multi-reference（多图参考） | 是 |

### JSON Prompting

FLUX 官方推荐 JSON 格式的提示词来实现精确控制，可以指定颜色、构图、光照等属性的具体值。

### Hex 色值

支持在提示词中使用 `#RRGGBB` 格式的十六进制颜色值来精确控制画面色彩。

### Multi-Reference

支持传入多张参考图片来约束生成结果。
