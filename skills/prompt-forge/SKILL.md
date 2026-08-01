---
name: prompt-forge
description: |
  文生图/视频提示词生成 — 提示词工程 skill。触发词:
  prompt, negative prompt, 提示词, 反向提示词, 分镜头, 运镜, 写分镜,
  anima, flux, sdxl, wan, ltx, hunyuan, comfyui, 图生视频, 文生视频.
  核心流程: ① 识别模型 → ② 查 recipe (skills/prompt-forge/recipes/MODELS.md)
  → ③ 生成提示词 → ④ 调 MCP (mcp__comfyui-mcp__*) 出图。
  "先出提示词,再调 MCP" — 这是本 skill 的第一性原理。
version: 4.0.0
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
  - 图生视频
  - 文生视频
---

# Prompt Forge v4.0

> **只做一件事**: 根据用户描述 + 模型选择，生成审美在线、结构正确的正向+负向 prompt，
> **然后调 MCP 出图/出视频**。
>
> **v4.0 重构**: 从 v3.1 的"查 Obsidian vault"改为"查 plugin 内 recipe"。
> 配方数据源 = `skills/prompt-forge/recipes/MODELS.md`(80 模型,带 YAML frontmatter)。
> 查询工具 = `skills/prompt-forge/internals/recipe_lookup.py`。
> 不再依赖 Obsidian vault。

## §0 触发时做什么(第一性原理)

```
用户说 "用 Anima 出金发精灵"
   ↓
① 识别模型: anima
   ↓
② 查 recipe: recipe_lookup --model anima → dialect 块 (30steps/CFG4.5/dpmpp_2m/3LoRA)
   ↓
③ 生成 prompt: 按 dialect + 用户内容组合 (正向 + 负向)
   ↓
④ 调 MCP: mcp__comfyui-mcp__generate_image (或 generate_video)
   ↓
⑤ 出图/出视频
```

**核心承诺**: 先出提示词,再调 MCP。没有 recipe 就不写 prompt — 这是质量保证。

## §1 执行流程

### Step 0 — 模型识别

用户说了模型名 → `python skills/prompt-forge/internals/recipe_lookup.py --model <id>` → 返回 dialect 块 + frontmatter。

- 命中 → 用 dialect 生成 prompt
- 未命中 → `AskUserQuestion` 问模型族 (Anima / Wan / Flux / SDXL / 视频系),或 fallback 通用参数

### Step 1 — 配方查询 (替代 v3.1 的 obsidian read)

从 recipe 的 frontmatter 提取:

| 字段 | 用途 |
|------|------|
| `dialect` | prompt 风格 (tag 系 / 自然语言系) |
| `negative_policy` | 是否支持负向 prompt |
| `triggers` | 模型触发词 / LoRA 触发词 |
| `sample_prompts` | 示例 prompt,参考结构 |

### Step 2 — 概念核提炼 (保留 v3.1 方法学)

从用户输入提炼 **1 句视觉概念核**(≤30 词),评估特异度 + 可执行度:

| 概念核 ≥ 14 分 | 稀疏模式(只填 3 段) |
|---|---|
| 概念核 < 14 分 | 完整模式(8 段全填) |

### Step 3 — 组装 prompt

按模型 dialect 组装:

- **tag 系** (Anima/Pony/SDXL/SD1.5): `score_9, score_8_up, [角色], [外貌], [场景], [风格]` + 负向
- **自然语言系** (Flux/Qwen): 句子,word order matters,无负向
- **视频系** (Wan/LTX): 镜头描述 + 运镜 + 时序

**前 10 token 决定画面基调**。每段自评 ≥ 7,低于阈值重写。

### Step 4 — 调 MCP (v4.0 新增 — "先出提示词再调 MCP")

```bash
# 文生图
mcp__comfyui-mcp__generate_image(prompt="<组装好的正向>", negative_prompt="<负向>", ...)
# 图生视频
mcp__comfyui-mcp__generate_video(prompt="<镜头描述>", image="<首帧>", ...)
```

具体工具名按意图选(by-intent 原则,已并入本 skill)。

### Step 5 — 自检 (10+1 项,保留 v3.1)

1. 8 段评分 ≥ 阈值
2. 内容 tag 经字典验证(如 tag 系)
3. 前 10 token = SUBJECT + STYLE
4. STYLE 在前 25% token 位置
5. 灯光为独立段
6. token 总数在限制内
7. 无抽象赞美词堆叠
8. STYLE 段显式命名媒介
9. LoRA 兼容性
10. 模型专属约束
11. 概念密度 > 0.6

## §2 配方数据源

```
skills/prompt-forge/
├── SKILL.md                     ← 本文件
├── recipes/MODELS.md            ← 80 模型 recipe (YAML frontmatter)
├── internals/recipe_lookup.py   ← 查询工具: --model <id> → dialect
├── internals/recipe_yaml.py     ← 配方格式维护 (幂等)
└── hardware/8gb.json            ← 8GB 显存参数
```

## §3 与 MCP 的关系

```
prompt-forge (本 skill) → mcp__comfyui-mcp__* (108 工具) → ComfyUI server
        ↑ 先出 prompt                                    ↑ 后出图
```

本 skill 负责**提示词质量**,MCP 负责**调用引擎**。两者解耦 — 提示词不好,MCP 再强也没用。

## §4 与漫剧的关系

用户说"全自动漫剧" → 不经过本 skill,直接走 `manga-orchestrator`。
但漫剧内部每个分镜的 prompt 由本 skill 的方法学生成。

## §5 第一性原理

> 为什么要有 prompt-forge?因为 **ComfyUI 只会按 prompt 出图,它不懂"审美"**。
> 同样一句"金发精灵",raw prompt 出糊图,带 dialect + 概念核 + 自检的 prompt 出精品。
> prompt-forge 是提示词质量的唯一 guard。
> 为什么并入 chenxin-core 的配方?因为**配方(dialect)和提示词方法(concept-core)是一体的** —
> 你不可能不查模型方言就写提示词。两者合一,才是一层完整的 skill。
