# Detail & Mood

## 核心公式
> 画面质感与情绪基调——让画面「看起来像什么」和「给人什么感觉」。灯光/光影/色调标签是合法词典标签（见 aesthetics/lighting.md 与 palette.md），本文件专注非光影的质感/氛围/特效标签。

## 变体维度表

| 维度 | 可选标签 |
|---|---|
| 水墨 | `ink splash, ink wash, calligraphic brushstrokes, watercolor texture` |
| 漫画 | `comic-style, halftone dots, screentone patterns, comic, greyscale` |
| 素描 | `sketch, lineart, scribbly shading` |
| 绘画 | `painterly` |
| 胶片 | `film grain, vintage film grain, heavy film grain overlay, emulsion scratch` |
| 黑白 | `greyscale, black and white, monochrome, spot color, limited palette` |
| 运动线 | `motion lines` |
| 速度线 | `speed lines` |
| 运动模糊 | `motion blur` |
| 多重运动模糊 | `multiple overlapping motion blurs` |
| 残影 | `afterimages, afterimages due to excessive speed` |
| 景深 | `depth of field, shallow depth of field, bokeh` |
| 剪影 | `silhouette, backlit silhouette` |
| 镜头光晕 | `lens flare, lens flare streaks` |
| 辉光溢出 | `bloom` |
| 柔焦 | `soft focus, soft-focus` |
| 色差 | `chromatic aberration` |
| 暗角 | `vignette` |
| 多重曝光 | `multiple exposure effect` |
| 数字故障 | `digital glitch effects, glitch art` |
| VHS / CRT | `VHS distortion, tracking errors, scan lines, CRT scanlines` |
| 像素化 | `pixelated outlines, blocky pixelated texture` |
| 数据流 | `data stream effects, binary code particles` |
| 电影感 | `cinematic, cinematic composition, cinematic angle` |
| 戏剧张力 | `dramatic tension, dramatic shadows` |
| 空灵 | `ethereal, dreamcore, dreamlike` |
| 暗黑 | `dark atmosphere, suspenseful, tense` |
| 明暗对照 | `chiaroscuro` |
| 诗意 | `poetic atmosphere` |
| 混乱 | `chaos, explosive composition` |

## 氛围链

`单质感 + 单氛围 (cinematic + dramatic tension) → 质感混搭 (ink + comic) → 质感+特效+氛围 (film grain + motion blur + dark atmosphere)`

## 使用提示

- 同一 prompt 不混搭超过 2 种质感——`ink splash` + `comic-style` 合理；`ink splash` + `film grain` + `glitch` 是车祸。
- 氛围词只选 1 个，它是全局情绪基调——`cinematic` + `ethereal` 可以（史诗空灵），`dark atmosphere` + `poetic` 矛盾。
- `motion lines` 偏漫画风格，`motion blur` 偏摄影风格——二选一即可；`speed lines` + `motion blur` 可叠加但不要叠 3 个以上运动标签。
- 运动标签适合高强度动作（后入、骑乘、种付、传教士冲刺）。
- 数字效果（glitch / VHS / 数据流）是强风格标签，选 1 个即可；适合赛博/催眠/偷拍场景。
- 光线/光影/色调标签是合法词典标签（`neon lights`、`rim light`、`warm color`、`cool color`、`light particles` 等均可直接使用；标准命名与反模式见 aesthetics/lighting.md、palette.md、anti-patterns.md）。
- 环境天气描写（`rain, snow, fog, steam, stormy, dust particles, underwater`）和时辰/大气标签可直接使用。

## 法典验证场景

### 场景 A — 水墨古风
tags: `ink splash, ink wash, poetic atmosphere, kimono`
备注: 单质感 + 单氛围——古风诗意。

### 场景 B — 漫画动作
tags: `comic-style, motion lines, speed lines, dramatic tension`
备注: 质感和运动标签组合——高强度动作漫画风。

### 场景 C — 胶片偷拍
tags: `film grain, depth of field, voyeurism, night, from outside`
备注: 胶片质感 + 偷窥视角——记录感。

### 场景 D — 赛博故障
tags: `digital glitch effects, chromatic aberration, cyberpunk, neon glow`
备注: 数字效果 + 色调——赛博机械催眠场景。
