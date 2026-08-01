---
okm: timeless
status: active
kind: knowledge
type: presets
updated: 2026-07-29
---

# 风格预设

> 7 个开箱即用的风格配方。用户未指定风格方向时，AskUserQuestion 给出 3 个预设供选择。

| 预设 | 光影 | 色彩 | 氛围 |
|------|------|------|------|
| 史诗 | [[lighting-rim-dramatic]] | [[color-warm-cool-contrast]] | grand, cinematic, heroic |
| 暗黑 | [[lighting-neon-noir]] | [[color-desaturated]] | gritty, noir, oppressive |
| 赛博朋克 | [[lighting-neon-noir]] | [[color-teal-orange]] | neon-drenched, cybernetic, dystopian, high-tech low-life |
| 华丽 | [[lighting-golden-hour]] | [[color-warm-palette]] | luxurious, ornate, rich |
| 清新 | [[lighting-natural-soft]] | [[color-earth-green]] | fresh, airy, natural |
| 复古 | [[lighting-window-soft]] | [[color-neutral-warm]] | nostalgic, vintage, warm |
| 极简 | [[lighting-diffused-mist]] | [[color-desaturated]] | sparse, zen, negative space |

## 选择逻辑

1. 若用户已指定风格方向（如"要史诗感"），直接匹配对应预设，不弹选择
2. 若用户未指定，从 7 个预设中随机抽 3 个，通过 AskUserQuestion 让用户选
3. 选中后 Read 对应的光影 + 色彩 wikilink 文件，注入 prompt 生成流程
4. 如果用户同时命中了 [[scene-recipes]] 中的场景，**场景配方优先于风格预设**（场景决定光影/构图，预设只补色彩/氛围）

## 预设适用场景建议

| 预设 | 适合场景 |
|------|---------|
| 史诗 | combat, scifi |
| 暗黑 | night, weather |
| 华丽 | portrait, xianxia |
| 清新 | nature, casual |
| 复古 | indoor, portrait |
| 极简 | portrait, indoor |
