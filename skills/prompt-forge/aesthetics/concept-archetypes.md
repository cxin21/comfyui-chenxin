---
okm: timeless
status: active
kind: knowledge
type: reference
description: "从 CivitAI 全时段排行榜 Top 30 提炼的 6 种高效视觉概念原型。纯 prompt 策略，不涉及 LoRA。"
source: "CivitAI Most Reactions All Time — 2026-07-30 分析"
updated: 2026-07-30
tags:
  - prompt-forge
  - concept-design
  - archetype
  - text-to-image
---

# 概念原型目录

> **为什么需要概念原型？** 排行榜数据显示：强概念 + 简单 prompt > 弱概念 + 精细 prompt。
> 概念原型是「在什么语义空间里采样」的决策，不是「怎么写 prompt」的格式。

## 使用方式

用户输入中检测到概念基因 → 匹配原型 → 按原型的 prompt 模式生成。
概念基因足够强（特异性 ≥ 7 且可执行性 ≥ 7）→ 允许稀疏填充（只填 3-4 段）。
概念基因弱 → 走完整 8 段框架。

---

## 原型 1：Frame within Frame（画框中的画框）

**机制**：一个物理容器/边界内包含另一个不协调的场景。视觉张力来自「内外空间的矛盾」。

**概念基因**：容器/窗口/门/镜子 + 容器内超现实内容

**Prompt 模式**（自然语言）：
```
Within/Through [frame object] [optional: state], we see [unexpected scene inside]. [result/effect].
```

**Prompt 模式**（tag）：
```
[frame object], [scene inside], [juxtaposition keyword], [atmosphere]
```

**为什么有效**：强制模型建立两个独立空间的深度关系和光照一致性，天然防止「flat composition」。无需任何 LoRA 即可产生视觉冲击力。

**排行榜案例**：
- `Within a crystal ball (on an old worn wooded table), we see a waterfall. A river of water pours into the room.` (13,766 👍)

**变体**：
| 容器 | 内容 | 效果 |
|------|------|------|
| 水晶球/雪球 | 瀑布/火山/星空 | 微型世界 |
| 窗户/门框 | 另一个时空/季节 | 空间撕裂 |
| 镜子/水面反射 | 不同的自己/场景 | 身份错位 |
| 画框/相框 | 活着的画中世界 | 虚实交界 |
| 破墙/裂缝 | 墙后的奇异世界 | 空间入侵 |

**适用模型**：Flux（自然语言一句话即可）、SDXL。Pony 需要 tag 化（`crystal_ball, waterfall, indoors, surreal`）。

---

## 原型 2：Genre Displacement（类型位移）

**机制**：把一个熟悉的文化符号/IP/类型放到完全错误的媒介、风格或语境中。视觉张力来自「认知框架的冲突」。

**概念基因**：[熟悉事物] + [不匹配的媒介/风格/时代]

**Prompt 模式**（自然语言）：
```
a [medium] of [familiar concept], but [twist/parody element]. featuring [key visual details]. [tone], [color palette]
```

**Prompt 模式**（tag）：
```
[style anchor], [familiar concept tag], [twist element tag], parody
```

**为什么有效**：熟悉事物提供识别锚点（瞬间理解），类型位移提供新鲜感（停留观看）。这是 meme 的视觉等价物。

**排行榜案例**：
- `a digital illustration of a movie poster titled "Finding Emo", finding nemo parody poster, featuring a depressed cartoon clownfish with black emo hair, eyeliner, and piercings` (12,375 👍)

**变体**：
| 熟悉事物 | 位移到 | 效果 |
|---------|--------|------|
| 经典电影海报 | 亚文化/3D渲染/水墨 | 文化错位幽默 |
| 名画 | 赛博朋克/像素风/乐高 | 经典重制 |
| 日常物品 | 史诗电影镜头语言 | 荒谬崇高感 |
| 品牌/logo | 废墟/后末日/古代 | 文明考古学 |
| 童话/神话 | 现代职场/科幻 | 叙事碰撞 |

**适用模型**：Flux（最擅长理解概念转折）、SDXL。需要模型能理解「parody」/「in the style of」这类元概念。

---

## 原型 3：Textural Duality（质感二元性）

**机制**：一个主体/画面上同时存在两种不相容的材质、质感或视觉语言。通常沿中轴线/对角线/上下分割。

**概念基因**：[半边/部分 A] 是 [质感 A] + [另半边/部分 B] 是 [质感 B]

**Prompt 模式**（自然语言）：
```
[shot type] of [subject]. The [left/right/top/bottom] side is [texture A + details]. The [opposite] side is [texture B + details]. [unifying element e.g. eye, light].
```

**Prompt 模式**（tag）：
```
[shot], [subject type], [texture A keywords], [texture B keywords], duality, split composition
```

**为什么有效**：人类视觉系统对边界和对比高度敏感。两种不相容质感的并置制造了「视觉摩擦」，强迫眼睛来回扫描。不需要 LoRA，纯 prompt 即可实现。

**排行榜案例**：
- `A close-up of a face... The left side is yellow with symbols and doodles, while the right side is dark with mechanical elements. The eye is a striking shade of yellow.` (16,046 👍)

**变体**：
| 质感 A | 质感 B | 效果 |
|--------|--------|------|
| 有机/植物/皮肤 | 机械/金属/电路 | 赛博格美学 |
| 彩色/图案/涂鸦 | 黑白/素描/网格 | 完工 vs 未完工 |
| 实体/石头/木材 | 透明/全息/数据流 | 虚实并置 |
| 冰/晶体 | 火焰/熔岩 | 元素对立 |
| 古典/巴洛克 | 极简/几何 | 时代碰撞 |

**适用模型**：全部。Split composition 是跨模型通用的强信号。

---

## 原型 4：Mythological Documentary（神话纪实）

**机制**：把神话/奇幻/超自然主题当做纪实/纪录片/科学观察对象来处理。视觉张力来自「不可信的对象 + 可信的呈现方式」。

**概念基因**：[神话生物/奇幻场景] + [纪录片/纪实/科学媒介风格]

**Prompt 模式**（自然语言）：
```
[documentary medium anchor], [precise spatial setup]. [mythical subject] [naturalistic action description]. [atmospheric conditions], [cinematic terms]. [color palette], [style references].
```

**Prompt 模式**（tag）：
```
[quality prefix], [shot type], [mythical creature tags], [natural environment], [documentary style tags], [cinematic lighting tags]
```

**为什么有效**：纪实风格提供大量具体视觉约束（自然光、胶片颗粒、浅景深、真实材质），施加到神话主题 → 「看起来像是真的拍到了」。

**排行榜案例**：
- `national geographic style... thrilling showdown between the ancient mummy and the colossal sand boss` (14,742 👍)
- `Silhouette of a Woman fighting a giant DARK mononoke Monster... 2000s vintage RAW photo, photorealistic, candid camera` (11,326 👍)

**变体**：
| 神话元素 | 纪实风格 | 效果 |
|---------|---------|------|
| 龙/精灵/九尾狐 | 国家地理/动物纪录片 | 神话生物学 |
| 魔法战斗 | 战地摄影/路透社 | 魔法新闻学 |
| 古代遗迹/失落文明 | 考古发掘记录 | 考古 fantasy |
| 鬼魂/超自然 | 科学仪器/热成像 | 超自然调查 |
| 巨人/泰坦 | 航拍/卫星图像 | 规模震撼 |

**适用模型**：Flux（T5 能完美理解 National Geographic / documentary style）、SDXL。

---

## 原型 5：Silhouette Epic（剪影史诗）

**机制**：主体以大面积剪影形式出现，细节被压暗/逆光吞没，背景反而是视觉焦点。视觉张力来自「未知的细节 + 壮丽的背景」。

**概念基因**：[主体] silhouette + [宏大/壮丽/戏剧化背景] + [强烈逆光/背光]

**Prompt 模式**（自然语言）：
```
Silhouette of [subject] [action] against [epic background]. [atmospheric conditions]. [cinematic composition]. [light description — key to silhouette effect].
```

**Prompt 模式**（tag）：
```
silhouette, [subject], [action], [epic background], backlighting, rim lighting, [atmosphere]
```

**为什么有效**：剪影 = 人类视觉中最强的图形-背景分离信号。不用描述主体的任何细节（降低了 prompt 难度），背景负责所有视觉冲击力。

**排行榜案例**：
- `image of a dusty desert with a 1930s female explorer... standing looking up at an Egyptian pyramid, silhouetted at sunset` (11,179 👍)
- `Silhouette of a Woman fighting a giant DARK mononoke Monster Boss... Milky Way, atmospheric haze` (11,326 👍)

**变体**：
| 剪影主体 | 背景 | 效果 |
|---------|------|------|
| 孤独旅者/骑士 | 夕阳/山脉/沙漠 | 史诗孤独 |
| 对战双人 | 爆炸/风暴/日食 | 动作高潮 |
| 城市楼顶人物 | 霓虹天际线/雨夜 | 赛博 noir |
| 树/建筑/动物 | 超级月亮/极光/银河 | 自然崇高 |
| 舞者/运动员 | 舞台聚光灯/尘雾 | 动态张力 |

**适用模型**：全部。`silhouette` 是所有模型都理解的强视觉信号。

---

## 原型 6：Atmosphere-as-Subject（氛围即主体）

**机制**：不描述任何具体物体，只描述光、雾、色、影、运动。让模型从「氛围参数」中自主涌现出视觉内容。最极端的「少即是多」策略。

**概念基因**：[情绪/氛围引用] + [天气/自然现象] + [抽象视觉现象] + [媒介]

**Prompt 模式**：
```
[mood/cultural reference], [weather/atmospheric condition], [abstract visual phenomenon], [medium]. [optional: one spatial hint].
```

**为什么有效**：不指定「是什么」→ 模型从氛围参数的约束空间中自由采样 → 结果是统计上的独特组合。高熵生成——放弃控制「有什么」，换取「独特」。

**排行榜案例**：
- `Dead can dance, misty morning, unreal shapes emerge from the fog, photo realism.` (11,814 👍, **仅 12 词**)

**变体**：
| 氛围引用 | 天气/现象 | 媒介 |
|---------|---------|------|
| Dead can dance / Cocteau Twins | mist / fog / haze | photo realism |
| Blade Runner / Akira | neon rain / smog | cinematic still |
| Studio Ghibli / Miyazaki | summer clouds / wind through grass | hand-painted cel animation |
| David Lynch / Twin Peaks | eerie stillness / flickering light | 1990s TV footage |

**⚠️ 风险**：输出高度不确定。适合追求「独特感」的场景，不适合需要精确控制的场景。

**适用模型**：Flux。不推荐 Pony/SD1.5（tag 模型无法处理抽象氛围）。
