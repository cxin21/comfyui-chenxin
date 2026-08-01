---
name: prompt-forge
description: |
  文生图/视频提示词生成 — L4 路由器。触发词: prompt, negative prompt,
  提示词, 反向提示词, 分镜头, 运镜, 写分镜, anima, flux, sdxl, wan, ltx,
  hunyuan, comfyui, 文生视频.
  流程: ① 识别模型 → ② 10 维要素提取 → ③ scene-recipes 匹配 → ④ tag 字典验证
  → ⑤ 组装 prompt → ⑥ 11 项自检 → 调 mcp__comfyui-mcp__generate_image / video.
  本 skill 拥有 prompt 质量；MCP 拥有调用引擎。
version: 5.0.0
triggers:
  - prompt
  - negative prompt
  - 提示词
  - 反向提示词
  - 分镜头
  - 运镜
  - 写分镜
  - anima
  - flux
  - sdxl
  - wan
  - ltx
  - hunyuan
  - comfyui
  - 文生视频
---

# prompt-forge v5 — L4 路由器

## §0 第一性原理

> **ComfyUI 只画 prompt，没有 taste**。
> 决策表全在数据里：recipes/MODELS.md (81 个模型配方) + dictionary/ (140K tag 字典) + aesthetics/ (24 个场景配方)。
> Python 只做查询和规范化；LLM (Claude) 做组装和判断。
> prompt-forge 拥有 prompt **质量**；mcp__comfyui-mcp__* 拥有调用 **引擎**。

## §1 6 步流水线

```
用户: "用 Anima 出金发精灵女法师在樱花树下释放魔法的图"
   │
   ▼
① 模型识别 ──────── recipe_lookup.py --model anima
   │                  3-pass: exact(1.0) > alias(0.95) > weighted_fuzzy(≥0.5)
   │                  → {matched, matched_id, heading, frontmatter, dialect_block, score, match_path}
   │
   ▼
② 10 维要素提取 ── SKILL.md §3 框架
   │                  subject / action / scene / lighting / composition / color / style / mood / medium / quality
   │                  缺失维度标记 [unset]
   │
   ▼
③ scene-recipes ─── scene_match.py --query "樱花树下 释放魔法"
   │                  INDEX.md 关键词扫描 → top-3 scenes
   │                  → lighting/rembrandt.md + composition/cowboy-shot.md + color/warm-cool-contrast.md
   │                  miss → style-presets.md 兜底（3 个 preset）
   │
   ▼
④ tag 字典验证 ──── tag_lookup.py --query "金发" "精灵" "樱花"
   │                  3-pass: exact(1.0) > alias(0.95) > substring(≥0.6)
   │                  → [{canonical, category, count, aliases, score}, ...]
   │
   ▼
⑤ 组装 prompt ──── §4 编排原则
   │                  tag 系 (Anima): score_9, score_8_up, [subject], [action], [lighting], ...
   │                  + aesthetic 覆盖 (lighting + composition + color)
   │                  + dialect block (from step 1)
   │                  前 10 token 策略（按 encoder 类型）
   │
   ▼
⑥ 11 项自检 ──────── §5
                      ↓
                   mcp__comfyui-mcp__generate_image(prompt=..., negative_prompt=...)
```

## §2 数据源

```
skills/prompt-forge/
├── recipes/MODELS.md          81 模型 recipes（YAML frontmatter）
├── dictionary/                tag 字典（danbooru.csv 140K + wd14-tags.csv 11K + tag-index.json）
├── aesthetics/                24 个场景配方 + scene-recipes + style-presets + 4 个 glossary
├── negative/negative-prompts.md  负向模板
├── models/                    15 个模型元数据（encoder / tag_style / negative）
├── internals/                 5 个 stdlib Python 工具
└── hardware/8gb.json          8GB 显存决策矩阵（13-key schema v1）
```

## §3 10 维度框架

| 维度 | 描述 | 来源 |
|------|------|------|
| subject | 谁/什么 | 用户输入 |
| action | 在做什么 | 用户输入 |
| scene | 在哪里/什么场景 | scene_match.py / user |
| lighting | 光照类型 | aesthetics/lighting/ |
| composition | 构图 | aesthetics/composition/ |
| color | 色彩/色调 | aesthetics/color/ |
| style | 风格（动漫/写实/油画...） | 用户输入 + recipe |
| mood | 氛围（孤独/温馨...） | 用户输入 |
| medium | 媒介（水彩/胶片/...） | aesthetics/medium-glossary.md |
| quality | 质量锚点（masterpiece 链） | recipe frontmatter |

**缺失维度**：标记 `[unset]`，由 scene_match 或 style-presets 兜底。

## §4 组装原则

### 前 10 token 策略

| 编码器 | 策略 | 原因 |
|--------|------|------|
| **LLM** (Anima / Flux / Qwen / SD 3.5) | 主体+动作在前，质量锚点在尾 | LLM 全局注意力，第一句定骨架 |
| **CLIP** (Pony / Illustrious / SDXL / SD 1.5) | 按模型 `tag_order_strategy`（见 models/*.md） | CLIP 单向注意力，位置即权重 |

### 3 种 dialect

| dialect | 适用 | 例子 |
|---------|------|------|
| **tag 系** (Danbooru comma-separated) | Anima / Pony / SDXL / SD 1.5 | `score_9, score_8_up, pointy_ears, long_hair, ...` |
| **自然语言** (句子, 顺序敏感) | Flux / Qwen | `A young elf mage with long golden hair casts fire magic under cherry blossoms.` |
| **视频** (shot + camera + temporal) | Wan / LTX | `Wide shot → close-up → pan left → slow motion → dusk lighting` |

## §5 11 项自检

1. 10 维度齐全（缺则填 `[unset]`）
2. 所有 tag 经 tag_lookup.py 验证
3. 前 10 token = SUBJECT + ACTION
4. STYLE 在前 25% token 位置
5. lighting / composition / color 各为独立段
6. token 总数在模型限制内
7. 无抽象赞美词堆叠（"beautiful amazing stunning"）
8. STYLE 段显式命名媒介
9. LoRA 兼容性（trigger token 完整）
10. 模型专属约束（见 models/{name}.md）
11. 概念密度 > 0.6（具体词 ≥ 60%）

## §6 与 MCP / 触发词

```
prompt-forge (本 skill) → mcp__comfyui-mcp__* (108 工具) → ComfyUI
        ↑ 先出 prompt                                    ↑ 后出图
```

**触发词列表**（已从 v4 移除 `图生视频` 以避免与 stage-4-motion 路由歧义——视频 prompt 写作由 scene_match.py 走 video-archetypes.md 流程处理）：

`prompt` `negative prompt` `提示词` `反向提示词` `分镜头` `运镜` `写分镜`
`anima` `flux` `sdxl` `wan` `ltx` `hunyuan` `comfyui` `文生视频`