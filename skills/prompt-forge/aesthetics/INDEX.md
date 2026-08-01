---
okm: timeless
status: active
kind: index
type: scene-keyword-index
updated: 2026-08-02
---

# Scene Keyword Index

> Lightweight keyword → scene lookup table consumed by `internals/scene_match.py`.
> Format: `scene | keywords | lighting | composition | color`.
> One row per scene. Keywords are Chinese (comma-separated) plus implicit Latin
> support via the tokenizer. Recipes reference files under `aesthetics/`.

| scene | keywords | lighting | composition | color |
|-------|----------|----------|-------------|-------|
| night_street | 夜景,霓虹,街景,都市夜 | lighting/lighting-neon-noir | composition/composition-low-angle | color/color-teal-orange |
| golden_hour | 黄昏,日落,金色时刻,夕阳 | lighting/lighting-golden-hour | composition/composition-eye-level | color/color-warm-palette |
| soft_window | 室内,窗光,柔光,自然光 | lighting/lighting-window-soft | composition/composition-medium-shot | color/color-neutral-warm |
| dramatic_rim | 戏剧,逆光,边缘光,剪影 | lighting/lighting-rim-dramatic | composition/composition-cowboy-shot | color/color-warm-cool-contrast |
| rembrandt | 伦勃朗,古典肖像,三角光 | lighting/lighting-rembrandt | composition/composition-cowboy-shot | color/color-warm-palette |
| harsh_top | 顶光,正午阳光,烈日 | lighting/lighting-harsh-top | composition/composition-eye-level | color/color-desaturated |
| overcast | 阴天,柔光,均匀光 | lighting/lighting-overcast | composition/composition-wide-shot | color/color-desaturated |
| diffused_mist | 雾,柔焦,朦胧,仙境 | lighting/lighting-diffused-mist | composition/composition-wide-shot | color/color-cool-blue |
| natural_soft | 自然柔光,日出,清晨 | lighting/lighting-natural-soft | composition/composition-medium-shot | color/color-skin-natural |
| low_angle | 仰拍,英雄,权力 | lighting/lighting-rim-dramatic | composition/composition-low-angle | color/color-warm-cool-contrast |
| dutch_angle | 倾斜,不安,心理 | lighting/lighting-harsh-top | composition/composition-dutch-angle | color/color-warm-cool-contrast |
| wide_landscape | 风景,远景,开阔 | lighting/lighting-natural-soft | composition/composition-landscape | color/color-earth-green |
