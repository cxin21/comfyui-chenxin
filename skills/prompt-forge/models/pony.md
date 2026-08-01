---
okm: dated
valid_until: 2026-10-30
status: active
kind: knowledge
family: pony
full_name: "Pony Diffusion V6 XL (AstraliteHeart)"
encoder: clip
architecture: "SDXL U-Net"
versions:
  v6:
    steps: "26-38"
    cfg: "variable (5-7 community)"
    sampler: "euler_ancestral"
quality_prefix: ["score_9", "score_8_up", "score_7_up", "score_6_up", "score_5_up", "score_4_up"]
rating_tags: ["rating_safe", "rating_questionable", "rating_explicit"]
source_tags: ["source_anime", "source_cartoon", "source_furry", "source_3d"]
tag_style: underscore
tag_separator: "_"
year_format: "year_{year}"
artist_format: none
artist_supported: false
artist_note: "Pony V6 XL 基模型训练时已移除画师名称。部分社区 finetune 可能重新加入——以 CivitAI 示例为准。"
tag_order_strategy: score_first
clip_skip: 2
prompt_order:
  description: "严格从上到下物理级联。前10 token = score锚 + 角色tag + 1girl。媒介/风格tag紧跟质量前缀之后，不在末尾。"
  cascade:
    - "score_9, score_8_up, score_7_up"
    - "[source_tag]  # source_anime/source_cartoon/source_furry/source_3d"
    - "[rating_tag]  # rating_safe/rating_questionable/rating_explicit"
    - "[character_tag]  # 角色锚点: san/link/2B/oc"
    - "1girl / 1boy / solo"
    - "[shot type]  # full_body/cowboy_shot/portrait/upper_body"
    - "[pose]  # squatting/standing/sitting/fighting_stance"
    - "[hair cascade: color → length → bangs → style]"
    - "[eyes: color → effect]"
    - "[face: expression → markings]"
    - "[body: skin → build → chest → hips]"
    - "[clothing: top → bottom → accessories → outerwear]"
    - "[environment: location → time → weather]"
    - "[style/medium anchors]  # concept_art/realistic/ink_illustration"
    - "[BREAK if needed]"
    - "[LoRA references]"
  negative_strategy: "score_only"
negative: ["score_6", "score_5", "score_4"]
negative_note: "v3.1 更新: 排行榜 top prompt 只用 score_6/5/4。不需要 source_furry/source_3d/realistic 在负向中。"
license: "CivitAI (check model page)"
source: "https://civitai.com/models/257749/pony-diffusion-v6-xl"
updated: 2026-07-29
tags:
  - prompt-forge
  - model
  - text-to-image
  - clip-encoder
  - sdxl
---

# Pony Diffusion V6 XL

Pony Diffusion V6 XL 是 AstraliteHeart 开发的 SDXL 微调模型，以 **score_* 质量评分体系** 和 **双维度标签系统**（rating + source）为标志性特征。

## 关联模型

同属 SDXL U-Net 生态：[[illustrious]]、[[noobai]]

## 核心规则

### Score 质量前缀（必须放最前面）

```
score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up
```

**tag_order_strategy = score_first**：提示词必须以 score 标签开头。

### 双维度标签系统

> [!important] 关键规则
> `rating_*` 和 `source_*` 是**两个独立维度**，必须同时写入提示词。缺一不可。

- **rating 维度**：`rating_safe` / `rating_questionable` / `rating_explicit`
- **source 维度**：`source_anime` / `source_cartoon` / `source_furry` / `source_3d`

### Clip Skip

> [!warning] 必须设置
> **Clip Skip = 2**，不是默认的 1。这是 Pony 的硬性要求。

### 画师标签

Pony V6 XL 基模型训练时已移除画师名称，**不支持画师标签**。部分社区 finetune 可能重新加入，以 CivitAI 模型页示例为准。

## 标签风格

- 下划线分隔（如 `blue_eyes`、`long_hair`）
- year 格式：`year_{year}`（如 `year_2023`）

## 负向提示词

```
score_4, score_3, score_2, score_1, source_furry, source_3d, realistic, photorealistic
```

注意：负向中的 source_furry / source_3d 用于排除不需要的风格维度。
