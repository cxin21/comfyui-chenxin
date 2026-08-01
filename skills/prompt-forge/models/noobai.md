---
okm: dated
valid_until: 2026-10-30
status: active
kind: knowledge
family: noobai
full_name: "NoobAI XL"
encoder: clip
architecture: "SDXL U-Net (Illustrious derivative)"
quality_prefix: ["masterpiece", "best quality", "amazing quality", "very aesthetic"]
note: "Illustrious 微调版，改善手部和解剖学。不用 score_*。"
tag_style: underscore
tag_separator: "_"
clip_skip: 1
negative: ["worst quality", "low quality", "bad anatomy", "error", "extra digit", "fewer digits", "cropped", "jpeg artifacts", "signature", "watermark", "blurry", "ugly", "deformed"]
source: "https://civitai.com/ (search NoobAI XL)"
updated: 2026-07-29
tags:
  - prompt-forge
  - model
  - text-to-image
  - clip-encoder
  - sdxl
---

# NoobAI XL

NoobAI XL 是 **Illustrious XL 的微调衍生模型**，专门改善手部和解剖学质量。继承了 Illustrious 的标签体系和质量前缀方案。

## 关联模型

- 基座模型：[[illustrious]]
- 同生态：[[pony]]

## 核心特征

### 质量体系

与 Illustrious 一致，使用标准质量堆栈：
`masterpiece, best quality, amazing quality, very aesthetic`

> [!important] 不用 score_*
> 和 Illustrious 一样，不采用 Pony 的 score_* 评分体系。

### 改进重点

NoobAI 的训练重点是改善以下常见 SDXL 问题：
- 手部畸形（extra digit / fewer digits）
- 解剖学错误（bad anatomy）
- 面部变形（ugly / deformed）

### Clip Skip

Clip Skip = 1（与 Illustrious 一致）。

## 标签风格

- 下划线分隔
- 继承 Illustrious 的标签体系

## 负向提示词

```
worst quality, low quality, bad anatomy, error, extra digit, fewer digits, cropped, jpeg artifacts, signature, watermark, blurry, ugly, deformed
```
