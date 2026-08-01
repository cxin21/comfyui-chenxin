---
okm: timeless
status: active
kind: knowledge
type: reference
updated: 2026-07-30
source: "CivitAI Top 30 分析 — 2026-07-30"
tags:
  - prompt-forge
  - negative-prompt
---

# 负向 Prompt 策略

> **v3.1 核心更新**：CivitAI 全时段 Top 30 数据分析表明——**Flux 100% 使用空或极简负向，Pony top prompt 仅用 score_6/5/4**。
> 负向 Prompt 正在消亡。新模型（Flux/Anima/视频系）默认空，老模型（SD1.5/SDXL）保留标准。

## 核心原则

- **新模型负向 = 噪音**：T5/VLM 编码器太强，负向 token 的精确语义被叠加成模糊噪声方向 → CFG 失效
- **针对性 > 全面性**：3 个精准负向词 > 30 个乱堆
- **风格推开 > 质量排除**：推开不想要的风格（`anime, cartoon`）比排除 bad anatomy 更有效
- **Pony 负向靠 score，不靠描述**：`score_6, score_5, score_4` 就是 Pony 的完整负向

---

## 按模型分层（v3.1）

### Tier 0 — 不需要负向

| 模型 | 负向 | 说明 |
|------|------|------|
| **Flux.2 全系列** | `""`（空） | 官方明确不支持 |
| **Flux.1 Schnell** | `""`（空） | CFG=1-2 时负向无效 |
| **Anima Turbo** | `""`（空） | CFG=1 时负向无效 |
| **视频模型**（Wan/LTX/Kling/Hailuo） | `""`（空） | 负向破坏时序一致性 |

### Tier 1 — 极简负向（≤ 5 词）

| 模型 | 负向 | 说明 |
|------|------|------|
| **Pony V6** | `score_6, score_5, score_4` | **不需要** source_furry/source_3d/realistic。排行榜 top prompt 证明 3 个 score tag 足够 |
| **Anima Aesthetic** | `worst quality, low quality, blurry` | 官方推荐，不用 score |
| **Flux.1 Dev** | 最多 3-5 个描述性排除词 | 不用 embedding，不用长列表 |

### Tier 2 — 标准负向（5-15 词）

| 模型 | 负向 | 说明 |
|------|------|------|
| **SDXL** | `blurry, low quality, deformed, bad anatomy, disfigured, extra limbs, watermark, text, worst quality, jpeg artifacts` | 经典组合有效但不需更多 |
| **Illustrious / NoobAI** | `score_4, score_3, score_2, score_1, lowres, bad anatomy, bad hands, text, cropped, worst quality, low quality, jpeg artifacts, watermark` | 动漫模型标准 |
| **Anima Base** | 官方推荐：`worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, chromatic aberration` | — |
| **Qwen-Image 2.0** | 最多 5 词 | 大模型自身对齐强 |
| **HunyuanImage** | 5-10 个中文负向词 | 中文负向有效果 |

### Tier 3 — 完整负向（15-25 词 + Embedding）

| 模型 | 负向 | 说明 |
|------|------|------|
| **SD 1.5** | `embedding:easynegative, embedding:badhandv4, worst quality, low quality, normal quality, lowres, watermark, signature, text, jpeg artifacts, blurry, bad anatomy, bad hands, extra fingers, missing fingers, extra limbs, deformed, disfigured, mutation, ugly, poorly drawn face` | SD1.5 确实需要 embedding 负向 |

---

## 为什么 Flux/Anima 应该默认空负向

**数学原理**（classifier-free guidance）：

```
output = uncond + cfg × (positive - negative)
```

当 text encoder 很弱（SD1.5 CLIP）→ negative embedding 本身模糊 → 叠加影响小 → 多写几个词无所谓。
当 text encoder 很强（Flux T5/Mistral, Anima Qwen3）→ 每个 negative token 都有精确定义 → 10 个不同 negative token 的反方向叠加 → **指向噪声** → `positive - noise ≈ positive` → CFG 被削弱。

**排行榜实证**：Flux top 5 中 4 条空负向，1 条仅 3 词。

---

## 风格位移技巧（需要时使用）

写实推开动漫：`anime, cartoon, illustration`（3 词）
动漫推开写实：`photorealistic, realistic, photo`（3 词）
电影感推开 3D：`3d render, cgi, octane`（3 词）
高级感推开廉价：`cheap, stock photo, instagram filter`（3 词）

> ⚠️ 即使使用这些，也只在模型**确实**输出了不想要的风格时才加。
> 不要「预防性」加一大堆风格排除词——这会缩小模型的创意空间。

---

## 常见误区

1. **越长越好？** 前 5 词决定 90% 效果，后面是 placebo。Flux 加 20 词负向 = 自毁。
2. **万能模板走天下？** 不同场景不同负向。战斗场景和日常场景的负向完全不同。
3. **SD1.5 模板套新模型？** 50 词 SD1.5 负向模板在 Flux/Anima 上是**净损耗**。
4. **Pony 需要 source_furry 在负向里？** 排行榜 top prompt 不用。score_6/5/4 就够了。
