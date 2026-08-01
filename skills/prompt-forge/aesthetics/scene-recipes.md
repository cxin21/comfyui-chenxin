---
okm: timeless
status: active
kind: knowledge
type: mapping
updated: 2026-07-29
---

# 场景审美配方映射

> 场景关键词匹配表。运行时提取用户输入中的场景关键词，命中后 Read 对应的光影/构图/色彩配方文件，自动注入 prompt。

| 场景关键词 | 场景类型 | 光影配方 | 构图配方 | 色彩配方 | 氛围 |
|-----------|---------|---------|---------|---------|------|
| 战斗 / 魔法 / 武器 / 爆炸 | combat | [[lighting-rim-dramatic]] | [[composition-low-angle]] | [[color-warm-cool-contrast]] | dramatic, intense |
| 日常 / 散步 / 咖啡 / 逛街 | casual | [[lighting-natural-soft]] | [[composition-eye-level]] | [[color-warm-palette]] | relaxed, candid |
| 夜景 / 霓虹 / 酒吧 / 雨夜 | night | [[lighting-neon-noir]] | [[composition-wide-shot]] | [[color-teal-orange]] | moody, atmospheric |
| 古风 / 仙侠 / 汉服 / 山水 | xianxia | [[lighting-diffused-mist]] | [[composition-wide-shot]] | [[color-ink-wash]] | ethereal, serene |
| 肖像 / 头像 / 特写 | portrait | [[lighting-rembrandt]] | [[composition-cowboy-shot]] | [[color-skin-natural]] | intimate, dignified |
| 科幻 / 机甲 / 飞船 / 未来 | scifi | [[lighting-harsh-top]] | [[composition-dutch-angle]] | [[color-cool-blue]] | cold, technological |
| 自然 / 森林 / 山川 / 海 | nature | [[lighting-golden-hour]] | [[composition-landscape]] | [[color-earth-green]] | peaceful, vast |
| 室内 / 卧室 / 办公室 | indoor | [[lighting-window-soft]] | [[composition-medium-shot]] | [[color-neutral-warm]] | cozy, quiet |
| 雨天 / 雪天 / 风暴 | weather | [[lighting-overcast]] | [[composition-medium-shot]] | [[color-desaturated]] | melancholic, raw |

## 使用规则

1. **关键词提取**：从用户输入文本中扫描上表"场景关键词"列，按 `/` 分隔的每个词独立匹配
2. **多场景命中**：如果同时命中多个场景类型，按首次命中优先；若用户明确说了"室内 + 夜景"则手动指定
3. **配方注入**：命中场景类型后，Read 对应的光影/构图/色彩 3 个 wikilink 文件，将其内容注入到当前 prompt 生成流程
4. **氛围提示**：将"氛围"列的值追加到 prompt 的 mood/atmosphere 描述段
5. **未命中**：如果没有关键词命中，回退到 [[style-presets]] 让用户选一个风格预设
