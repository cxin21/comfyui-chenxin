# Mood / Texture

> 情绪回答"画面感觉如何"，质感回答"空气和表面看起来怎样"。两者经常共现但分工不同：mood 是情绪基调，texture 是物质层叠加。

## 核心公式
> Mood（情绪基调）× Atmosphere（空气介质）× Surface（表面材质）× Particle（粒子细节）四层自由叠加，但 Mood 内只取一个词，Texture 三层可同时挂。

## 变体维度表

| 维度 | 可选标签 |
|---|---|
| Mood（情绪） | `melancholic` / `dramatic` / `epic` / `calm` / `lonely` / `mysterious` / `cheerful` / `ethereal` / `tense` |
| Atmosphere（空气） | `fog` / `smoke` / `rain` / `snow` / `wind` / `dust` / `embers` |
| Surface（表面） | `wet` / `frost` / `cracks` / `worn` / `polished` / `matte` / `lace` / `silk` / `velvet` / `leather` |
| Particle（粒子） | `sakura petals` / `petals` / `leaves` / `debris` / `bubbles` / `light particles` |

## 氛围链
`cheerful` → `lonely` → `melancholic` → `tense`

(从明亮欢快到阴沉威胁，情绪强度沿链递增。)

## 使用提示
- Mood 维度互斥：`melancholic` + `cheerful` 是情绪矛盾，模型将随机选其一。
- Atmosphere 可叠加：`fog` + `dust` 读作废墟；`rain` + `neon lights` 读作都市夜景。
- Surface 是物体绑定而非场景：`wet` 描述地面或街道，`cracks` 描述墙面或皮肤——同一主体只挂一个 Surface。
- Particle 与 Atmosphere 独立：粒子是浮在空气中的细节，气氛是整体的空气介质。
- `ethereal` 空灵超脱，适合奇幻场景而非日常叙事。
- 情绪词地雷（勿作 mood 使用）：`serene` 解析到 `character` 类别、`nostalgic` 解析到 `copyright` 类别、`romantic` / `dreamy` / `peaceful` 未收录（无法验证）。替换用 `calm` / `melancholic` / `mysterious` / `ethereal` 等已验证的 general 类别词。

## 法典验证场景
### 场景 A — 雨夜独行
tags: `melancholic`, `rain`, `wet`, `dust`
备注: 雨中湿地面 + 飘尘，孤独忧郁氛围。

### 场景 B — 春日告白
tags: `cheerful`, `wind`, `sakura petals`, `silk`
备注: 微风飘樱 + 丝绸衣物，柔和欢快。

### 场景 C — 战后废墟
tags: `tense`, `dust`, `cracks`, `embers`
备注: 扬尘 + 龟裂地表 + 余烬，末日战后氛围。

### 场景 D — 雪夜温泉
tags: `calm`, `snow`, `steam`, `frost`
备注: 飘雪 + 蒸汽 + 霜花，和平静谧。