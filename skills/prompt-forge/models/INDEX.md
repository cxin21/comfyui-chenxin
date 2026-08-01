---
okm: dated
status: active
kind: pointer
valid_until: 2026-10-30
type: index
updated: 2026-07-29
tags:
  - prompt-forge
  - index
  - model
---

# 文生图模型索引

Prompt Forge 支持的文生图模型总索引。

## 文生图模型

| 模型 | Encoder | 提示词风格 | 适用场景 | 文件 |
|------|---------|-----------|---------|------|
| Anima | LLM (Qwen3-0.6B) | Gelbooru tag | 二次元、动漫风格 | [[models/anima]] |
| Pony Diffusion V6 XL | CLIP | score_* + Danbooru tag | 二次元（score 评分体系） | [[models/pony]] |
| Illustrious XL | CLIP | masterpiece + Danbooru tag | 二次元（传统质量堆栈） | [[models/illustrious]] |
| NoobAI XL | CLIP | masterpiece + Danbooru tag | 二次元（改进手部/解剖） | [[models/noobai]] |
| FLUX.1 / FLUX.2 | LLM (Mistral/Qwen) | 自然语言段落 | 通用/照片级真实 | [[models/flux]] |
| SDXL | CLIP | 标签+自然语言混合 | 通用基础模型 | [[models/sdxl]] |
| SD 1.5 | CLIP | 纯标签+括号权重 | 通用（庞大社区生态） | [[models/sd15]] |
| SD 3.5 | LLM | 自然语言短句 | 通用（中英文混合） | [[models/sd35]] |

## 按编码器分类

### LLM 编码器

- [[models/anima]] — Qwen3-0.6B
- [[models/flux]] — T5/Mistral-3/Qwen3
- [[models/sd35]] — MMDiT LLM

### CLIP 编码器

- [[models/pony]] — SDXL U-Net
- [[models/illustrious]] — SDXL U-Net
- [[models/noobai]] — SDXL U-Net (Illustrious derivative)
- [[models/sdxl]] — SDXL U-Net
- [[models/sd15]] — SD 1.5 U-Net

## 按提示词风格分类

### 自然语言

- [[models/flux]] — 段落式，JSON 支持，hex 色值
- [[models/sd35]] — 短句式，中英文混合

### Tag 标签

- [[models/anima]] — Gelbooru space-separated
- [[models/pony]] — score_* + underscore
- [[models/illustrious]] — masterpiece + underscore
- [[models/noobai]] — masterpiece + underscore
- [[models/sd15]] — 纯 tag + 括号权重

### 混合

- [[models/sdxl]] — tag + 自然语言

## 按架构分类

### DiT / MMDiT

- [[models/anima]] — Cosmos-Predict2-2B DiT
- [[models/sd35]] — MMDiT (8B/2.5B)

### U-Net

- [[models/pony]] — SDXL U-Net
- [[models/illustrious]] — SDXL U-Net
- [[models/noobai]] — SDXL U-Net
- [[models/sdxl]] — SDXL U-Net
- [[models/sd15]] — SD 1.5 U-Net
- [[models/flux]] — FLUX DiT

> [!info] 持续更新
> 此索引随模型调研进度同步更新。最后更新：2026-07-29。
