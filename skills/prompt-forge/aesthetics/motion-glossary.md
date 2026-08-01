---
okm: timeless
status: active
kind: knowledge
type: reference
description: "运动物理质感词库——视频 prompt 的核心不是描述「有什么」，而是描述「怎么动」。"
source: "CivitAI Video Top 30 分析 — 2026-07-30"
updated: 2026-07-30
tags:
  - prompt-forge
  - video
  - motion
  - reference
---

# 运动物理质感词库

> **视频 prompt 的核心原则**：运动是第一主体。不是「在画面里有什么」，而是「有什么在动、怎么动、为什么看起来像真的」。

## 使用方式

视频 prompt 中，运动描述占 prompt 的 50%+ 篇幅。每个视频 prompt 至少包含：
- 1 个**运动主体**（谁/什么在动）
- 1 个**运动过程**（怎么动——具体动作序列）
- 1 个**物理质感词**（动得怎么样——本节词库）

---

## 运动物理质感

### 流体/水下运动

| 描述 | 视觉效果 | 适用场景 |
|------|---------|---------|
| `floats and swims with natural, realistic motion` | 肢体划水/水流推动/重量感消失 | 水下生物/游泳 |
| `smooth, weightless, and slightly delayed, consistent with fluid motion in water` | 惯性延迟/动作滞后于意图 | 精确水下物理 |
| `gently paddling, gliding upward, slowly drifting down` | 上升→悬停→下降的循环 | 水族箱/海洋 |
| `feathery gills subtly waving with the current` | 被动跟随水流/微小振荡 | 水生生物细节 |
| `air bubbles rise to the top` | 上升气泡/浮力 | 水下场景标配 |
| `drifting in zero gravity / suspended mid-water` | 完全失重/360°漂浮 | 太空/深海 |
| `soft wiggle to reorient` | 微小调整运动/关节扭动 | 小型水生生物 |

### 风/空气运动

| 描述 | 视觉效果 | 适用场景 |
|------|---------|---------|
| `the cold wind gently blows the delicate strands of hair` | 发丝飘动/方向性/间歇性 | 户外人像 |
| `hair is slightly fluttering` | 轻微颤动/高频小幅 | 近景人像 |
| `wind ripples through fabric and hair` | 衣物+头发同时响应 | 全身风动 |
| `leaves and petals drift lazily through the air, caught in a soft breeze` | 缓慢飘落/不规则路径 | 诗意场景 |
| `dust and particles swirl in the air, suspended mid-motion` | 颗粒悬浮/漩涡运动 | 废墟/阳光光束 |

### 微动作/生物运动

| 描述 | 视觉效果 | 适用场景 |
|------|---------|---------|
| `slowly blinks, then gently nuzzles` | 闭眼→蹭→缩 | 可爱动物 |
| `soft feathers shift slightly as it moves` | 羽毛层叠位移/蓬松感 | 鸟类/毛绒 |
| `its gills pulse softly, eyes blink slowly` | 器官节律性运动 | 奇幻生物 |
| `the ears quiver as she makes an expression` | 耳朵随表情联动 | anime/兽耳角色 |
| `tiny face tucks into the folds, looking cozy` | 藏脸/依偎/缩进 | 温馨/萌系 |
| `cheerful expression collapses / eyes distort and dissolve` | 表情瞬间崩塌 | 冲击/喜剧效果 |
| `jagged cracks run across its face as the structure shatters` | 裂缝蔓延/碎裂扩散 | 破坏/动作 |

### 冲击/爆炸运动

| 描述 | 视觉效果 | 适用场景 |
|------|---------|---------|
| `rockets into the frame, captured at the precise moment of impact` | 高速进入→冻结瞬间 | 动作/体育 |
| `chips burst outward like shrapnel, fine crumbs scatter in all directions` | 碎片径向扩散/悬浮 | 破坏效果 |
| `larger fragments spiral off, trailing trails of debris` | 螺旋碎片+拖尾 | 慢动作破坏 |
| `explosive impact — the glove sinks in and the surface collapses` | 形变+崩溃 | 打击感 |

### 循环/持续运动

| 描述 | 视觉效果 | 适用场景 |
|------|---------|---------|
| `floats slowly through space, drifting — the scene loops calmly` | 无限漂移/回归原点 | 循环 GIF |
| `one tilts its body as it turns, another performs a soft wiggle` | 交替运动/非同步 | 群组场景 |
| `the gelatinous cube wobbles and undulates` | 弹性变形/振荡 | 奇幻/像素 |
| `gently sways as if suspended` | 钟摆式摆动 | 悬浮/催眠 |

---

## 运动速度与节奏

### 速度副词

| 速度 | 词 | 帧数感知 |
|------|-----|---------|
| 极慢 | `imperceptibly slow, glacial pace` | 几乎静止，呼吸感 |
| 慢 | `slowly, gently, gradually, lazily` | 可见变化，适合抒情/氛围 |
| 中速 | `steadily, smoothly, continuously` | 自然运动，最安全的选择 |
| 快 | `rapidly, quickly, suddenly, instantly` | 动作/冲击，慎用——易产生模糊 |
| 变速 | `accelerates, decelerates, eases into, builds up to` | 专业级控制 |

### 节奏词

| 节奏 | 词 | 适用 |
|------|-----|------|
| 循环 | `loops, oscillates, sways back and forth` | GIF/短视频 |
| 渐进 | `gradually, progressively, bit by bit` | 叙事推进 |
| 突发 | `suddenly, bursts into, explodes` | 冲击/惊吓 |
| 延迟 | `slightly delayed, lagging behind, trailing` | 物理真实感（惯性） |

---

## 运动质量评估

好的视频 prompt 中的运动描述：
- ✅ 包含运动**方式**（怎么动），不只是运动**内容**（动什么）
- ✅ 物理质感明确（weightless/buoyant/resistant/jerky/smooth）
- ✅ 运动是**连续的**（有过程），不是**离散的**（只有结果）
- ❌ `she dances` — 太抽象，模型不知道跳什么舞
- ✅ `she sways gently from side to side, her skirt rippling with each movement` — 具体到每个身体部位的联动

---

## 快速匹配（供 SKILL.md Step V2 使用）

从用户输入检测运动类型 → 注入对应物理质感描述：

| 运动类型 | 检测关键词 | 注入质感描述 |
|---------|-----------|------------|
| 流体/水下 | swim, float, water, ocean, aquarium | `smooth, weightless, slightly delayed, fluid motion` |
| 风/空气 | wind, breeze, blow, flutter, hair | `gently blows, fluttering, rippling through` |
| 微动作/生物 | blink, nuzzle, breathe, pulse, quiver | `slowly blinks, gently nuzzles, shifts slightly` |
| 冲击/碰撞 | hit, crash, smash, explode, burst | `captured at precise moment of impact, burst outward, suspended mid-air` |
| 循环/振荡 | loop, sway, wobble, drift, oscillate | `loops calmly, oscillates, sways back and forth` |

