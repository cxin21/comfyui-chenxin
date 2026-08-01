---
okm: timeless
status: active
kind: knowledge
type: reference
description: "视频概念原型——从 CivitAI 视频排行榜提炼的 5 种高效视频视觉概念。纯 prompt 策略。"
source: "CivitAI Video Most Reactions All Time — 2026-07-30 分析"
updated: 2026-07-30
tags:
  - prompt-forge
  - video
  - concept-design
  - archetype
---

# 视频概念原型

> **与图像原型的本质区别**：图像原型关注「什么画面」，视频原型关注「什么运动」。
> 视频的视觉冲击力来自运动设计，不是帧质量。

## 视频 vs 图像：本质区别

| 维度 | 图像 Prompt | 视频 Prompt |
|------|-----------|-----------|
| **第一主体** | 人/物/场景——「有什么」 | **运动过程**——「怎么动」 |
| **语言形式** | tag / 混合 / 自然语言 | **纯自然语言段落**（运动是时序的） |
| **质量来源** | 单帧精美度 | **物理可信度** + 时序一致性 |
| **负向** | 按模型分层 | **默认空**（CFG ≤ 1 时负向无效） |
| **相机** | 构图元素 | **隐式**——模型从场景推断 |
| **复杂度上限** | 多角色/多场景 OK | **单主体 + 单运动** |

## 使用方式

用户输入检测到视频需求 → 匹配原型 → 按原型模式生成运动描述。
**核心约束**：单主体 + 单运动。多主体场景显式警告高失败率。

---

## 原型 1：Micro-Motion Portrait（微动作肖像）

**机制**：一个主体占据画面主体，只做极小幅度的运动。视觉焦点不在「做了什么」，而在「运动本身的质感」。

**核心要素**：主体 + 1-2 种微动作 + 物理质感细节

**Prompt 模式**：
```
[subject description]. [micro-motion 1: how a body part moves], [micro-motion 2: how another part responds]. [physics quality: how wind/water/light interacts with the motion]. [atmosphere].
```

**为什么有效**：视频模型在「高细节单帧 + 小幅帧间变化」上表现最好。微动作属于模型的 sweet spot——帧间差异足够小，时序一致性天然高。

**排行榜案例**：
- `stunning blonde girl... the cold wind gently blows the delicate strands of blonde hair` (4,426 👍)
- `The charming smile of a girl with animal ears. Her hair is slightly fluttering, ears quivering` (5,882 👍)

**变体**：
| 主体 | 微动作 | 物理互动 |
|------|--------|---------|
| 人像/半身 | 眨眼/微笑/转头的微动 | 风吹发丝/光线变化 |
| 动物 | 耳朵抖动/鼻子嗅/尾巴轻摆 | 皮毛随风/胡须颤动 |
| 机器人 | LED闪烁/关节微调/镜头对焦 | 金属反光/蒸汽排放 |
| 植物 | 花瓣开合/叶子转动/露珠滑落 | 风中摇曳/光斑移动 |

---

## 原型 2：Physics Showcase（物理展示）

**机制**：运动本身是唯一看点。不靠角色/故事/场景，纯靠物理运动的真实感（或超现实感）吸引观看。

**核心要素**：运动主体 + 详细运动描述（50%+ prompt篇幅）+ 物理质感词 + 环境约束（水/太空/风）

**Prompt 模式**：
```
[subject] [primary motion with manner]. [detailed physics: how body parts move sequentially]. [environmental interaction: how surroundings respond]. [motion quality words]. [loop hint].
```

**为什么有效**：人类对「违背物理但看起来像真的」有着天然的观看欲望。正确描述了物理约束的运动让人想反复看。

**排行榜案例**：
- `The axolotls float and swim with natural and realistic motion... smooth, weightless, and slightly delayed, consistent with fluid motion in water` (4,040 👍)
- `The astronaut floats slowly through space, drifting in zero gravity. Inside the transparent fishbowl helmet, the giant fish head gently sways` (3,915 👍)

**变体**：
| 物理环境 | 运动特征 | 吸引力来源 |
|---------|---------|-----------|
| 水下 | 惯性延迟/悬浮/划水 | 失重的优雅 |
| 太空 | 零重力/360°旋转/缓慢漂移 | 绝对自由感 |
| 强风 | 阻力/衣物紧贴/发丝飞舞 | 力的可视化 |
| 胶质/弹性体 | 弹跳/变形/振荡 | 触觉满足感 |
| 颗粒/流体 | 飞溅/扩散/漩涡 | 混乱中的秩序 |

---

## 原型 3：Impact Freeze（冲击冻结）

**机制**：一个物体高速撞击另一个物体，画面冻结在最大冲击瞬间。所有碎片/颗粒/形变悬浮在空中。

**核心要素**：撞击物 + 被撞物 + 冲击瞬间描述 + 碎片运动 + 冻结/慢动作

**Prompt 模式**：
```
[A] rockets/slams/crashes into [B], captured at the precise moment of impact. [A] sinks into [B]'s surface. [debris description]. [cracks/deformation]. [suspended mid-air, freeze-frame]. [lighting/background].
```

**为什么有效**：冲击冻结 = 一张超高信息密度的静止帧 + 碎片仍在运动中的时间张力。

**排行榜案例**：
- `A boxing glove rockets into the frame... captured at the precise moment it collides with a cookie's face. Chocolate chips burst outward like shrapnel` (3,642 👍)

**⚠️ 注意**：这是不可逆运动——看一遍就结束。适合冲击力但不适合循环播放。标记为 `[one-shot, not loopable]`。

---

## 原型 4：Creature Cuteness（生物萌动）

**机制**：一个可爱生物做一件让人融化的微小动作。不靠特效/故事，纯靠生物行为的感染力。

**核心要素**：可爱生物 + 微小温馨动作 + 柔软材质（羽毛/绒毛/毛线）+ 温暖光

**Prompt 模式**：
```
[ultra-realistic close-up of] [cute creature]. [soft texture details]. [tiny action sequence]. [how body/feathers/fur respond to the movement]. [warm, gentle lighting]. [peaceful, dreamy atmosphere].
```

**为什么有效**：人类对「可爱生物做小事」有不可抗拒的观看冲动。这是互动率最高的视频类型。

**排行榜案例**：
- `An ultra-realistic close-up of a single fluffy yellow baby duckling wrapped in a soft pastel crochet blanket... slowly blinks, then gently nuzzles its tiny face into the folds` (4,115 👍)

---

## 原型 5：Single-Line Concept（一句话概念）

**机制**：只写一个概念核，不加运动指导、不加视觉描述。让模型自由发挥。

**核心要素**：1 句话 = 主体 + 动作。不超过 15 词。

**Prompt 模式**：
```
[subject] [action verb] [optional: context]. [style hint: 最多 2 词].
```

**为什么有效**：概念够强时，额外指导只会限制模型的创意空间。

**排行榜案例**：
- `gelatinous cube,anime-style,glowing` (4,010 👍, 5词)
- `the robot plays the violin while dancing at the same time` (3,886 👍, 10词)

**⚠️ 风险**：极简 prompt 下输出高度不确定。只有概念真正独特时才用。
