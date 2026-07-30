---
name: prompt-forge
description: "文生图/视频提示词生成。审美优先——自动匹配场景注入光影/构图/色彩配方，查 Obsidian vault 模型元数据+tag字典验证。用户说'写提示词/prompt/分镜/运镜/negative prompt'或报模型名(Anima/Flux/Pony/Illustrious/Wan/Kling等)时触发。"
version: 3.1.0
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
  - pony
  - illustrious
  - sdxl
  - wan
  - kling
  - 可灵
  - hailuo
  - 海螺
  - comfyui
  - 图生视频
  - 文生视频
---

# Prompt Forge v3.1

> **只做一件事**: 根据用户描述 + 模型选择，生成审美在线、结构正确的正向+负向 prompt。
> **v3.1 更新**: 概念核驱动 + 稀疏填充 + STYLE 前移至 #3 + 概念密度自检。不再强制 8 段全填。
> **不放**模型参数/版本号/tag列表/审美词表——这些在 Obsidian vault 里，运行时查。

## §1 执行流程

### Step 0 — 模型识别

用户说了模型名 → `obsidian read path="10-Projects/prompt-forge/models/<family>.md"` (**不要加 `vault=` 参数**) → 解析 frontmatter。正文中的 `[[wikilink]]` 需手动 `Read` 跟进。

**模型版本**: 读取 `versions` 字段。有多个版本时默认用第一个 (通常 base/general)，用户说"Turbo/Aesthetic/Dev/Schnell"时才切。视频模型只有单一版本直接读。

用户没说 → `AskUserQuestion` 问模型族 (Anima / Pony / Illustrious / Flux / SDXL / SD1.5 / 视频系)。

### Step 0.5 — 概念核提炼

从用户输入提炼 **1 句视觉概念核**（不超 30 词），评估两个维度：

| 维度 | 标准 | 1-10 分 |
|------|------|---------|
| **特异性** | 这个视觉概念有多独特？「水晶球里的瀑布」= 9，「森林里的女孩」= 3 | 独特场景/反常识组合/类型位移 → 高分 |
| **可执行性** | prompt 能否直接表达？「爱」= 2，「一个女孩蹲在森林里」= 8 | 有具体视觉元素 → 高分 |

**概念核 ≥ 14 分** → 标记「强概念」→ Step 1 进入**稀疏模式**（只填 3 段，其余标记 `[concept-driven]`）
**概念核 < 14 分** → 标记「弱概念」→ Step 1 走**完整 8 段**

**为什么需要这一步？** 排行榜数据证明：强概念 + 简单 prompt > 弱概念 + 精细 prompt。概念核提炼避免「把水晶球瀑布填满 8 段」的过度工程化。

**概念原型参考**：`obsidian read path="aesthetics/concept-archetypes.md"` — 6 种高效视觉概念原型。
检测到概念基因（如 Frame-within-Frame / Genre-Displacement / Silhouette-Epic）→ 优先按原型的 prompt 模式生成。

### Step 1 — 按需提取（强概念稀疏 / 弱概念全填）

从用户输入提取内容。**不再强制 8 段全填**：

| 模式 | 触发条件 | 必填段 | 可选段 | 策略 |
|------|---------|--------|--------|------|
| **稀疏模式** | 概念核 ≥ 14 分 | SUBJECT + ENV + STYLE（3 段） | 其余 5 段标记 `[concept-driven]`，只做微调 | 保护概念纯度，不过度填充 |
| **完整模式** | 概念核 < 14 分 | 全部 8 段 | — | 用丰富的技术维度弥补概念复杂度不足 |

**8 段框架**：`obsidian read path="workflows/image-8-segments.md"` — 段顺序/详表/稀疏vs完整/评分/模型特化。STYLE 在 #3（v3.1 前移）。

### Step 2 — 审美匹配

从 Step 1 的 action/env 提取**场景关键词**。

```
obsidian read path="aesthetics/scene-recipes.md" → 匹配场景类型
  ├─ 命中: Read 对应配方文件 ([[lighting-xxx]] → lighting/lighting-xxx.md)
  └─ 未命中: AskUserQuestion → 3 个风格预设 → Read style-presets.md → 注入
```

用户说画师名 → 按模型 `artist_format` 注入风格维度。

### Step 3 — tag 字典验证

| 模型 encoder 类型 | 验证方式 |
|------------------|---------|
| **CLIP + tag 系** (Pony/Illustrious/SDXL/SD1.5) | `Bash grep` vault `tags/danbooru.csv` (140K tag)。**批量验证**: 一次 grep 传入所有待查 tag (管道分隔 `tag1\|tag2\|...`)，命中的用，未命中逐个换近义词重查 |
| **LLM + tag 锚点** (Anima) | grep danbooru.csv + **Gelbooru 优先** (官方要求)。tag 锚点部分验证, 自然语言部分跳过 |
| **LLM + 自然语言** (Flux/Qwen/Seedream/HunyuanImage) | 跳过字典验证。用自然语言描述 |
| **视频模型** | 跳过字典验证。自然语言 + 运镜/时序 |

**不验证的 tag** (模型专属固定 tag, 不依赖字典):
- 质量锚点 (`masterpiece`, `score_9`, `best quality`...)
- 分级 tag (`rating_safe`, `safe`, `nsfw`...)
- source tag (`source_anime`...)
- year tag
- 画师 tag

### Step 4 — 组装配重

**核心原则: 前 10 token 决定画面基调。每部分生成后自评得分，低于阈值重写。**

#### 组装规则

8 段框架、评分细则、模型特化规则 → `obsidian read path="workflows/image-8-segments.md"`。

Token 预算分配 → `obsidian read path="reference/token-budget.md"`。

**核心原则**: 前 10 token 决定画面基调。每段自评 ≥ 7（稀疏模式仅前 3 段），低于阈值重写。

### Step 5 — 自检输出

**10+1 项自检** (PASS/FAIL 表):

1. **8 段评分 ≥ 阈值** (强概念模式：前3段 ≥ 7；完整模式：全部 ≥ 7，MATERIAL 段可 ≥ 5)
2. 内容 tag 经字典验证 (grep danbooru.csv)
3. 前 10 token = **SUBJECT + STYLE** (主体+媒介锚定)
4. **STYLE 在前 25% token 位置**（媒介是第一性约束，不可在末尾）
5. **灯光为独立段** (最高 ROI，不可与其他段合并)
6. token 总数在限制内 (SD1.5:77, SDXL:154, Flux:32K)
7. 无抽象赞美词堆叠 (beautiful/amazing/stunning 不能替代具体描述)
8. STYLE 段显式命名了媒介 (否则默认 generic stock photo)
9. LoRA 兼容性 (Anima 不用 SDXL LoRA, Pony 不用 SDXL LoRA)
10. 模型专属约束 (Pony Clip Skip=2, Flux.2 无负向, Anima Aesthetic 无 score...)
11. **概念密度 > 0.6** (去重计数：多少个 token 指向不同的语义区域？同义词堆叠 = 冗余 = 降低密度)

**强制三段式输出**: 10维度提取表 → 自检 PASS/FAIL → 纯净 prompt

---

## §2 提取与组装框架

> 8 段详表、评分细则、模型特化、token 预算 → 均在 vault 中。
> - `obsidian read path="workflows/image-8-segments.md"` — 完整 8 段框架 + 评分 + 模型特化
> - `obsidian read path="reference/token-budget.md"` — token 预算分配

**核心原则**: 前 10 token 决定画面基调。每段自评 ≥ 7（稀疏模式仅前 3 段），低于阈值重写。过填充扣分——同义词堆叠 3+ 个 → 扣 1 分。

---

## §3 概念原型匹配（优先）+ 场景配方（降级）

### 第一优先：概念原型匹配

从 Step 0.5 的概念核检测概念基因。`obsidian read path="aesthetics/concept-archetypes.md"` → 匹配 6 种原型：

- 检测到「容器+内部超现实场景」→ 原型 1: Frame-within-Frame
- 检测到「熟悉事物+不匹配的媒介/风格」→ 原型 2: Genre Displacement
- 检测到「半边A质感+半边B质感」→ 原型 3: Textural Duality
- 检测到「神话/奇幻+纪实/纪录片风格」→ 原型 4: Mythological Documentary
- 检测到「剪影+宏大背景」→ 原型 5: Silhouette Epic
- 检测到「纯氛围/无具体主体」→ 原型 6: Atmosphere-as-Subject

命中原型 → 按原型 prompt 模式注入 composition/lighting/color，不再额外走场景配方。

### 第二优先：风格方向

用户**明确说了风格方向** (如"赛博朋克""吉卜力""水墨风") → **优先用该风格的审美组合**。`obsidian read path="aesthetics/style-presets.md"` → 匹配风格名 → 手动 Read wikilink 配方。

### 降级：场景配方匹配

概念原型未命中 + 风格未明确 → 场景配方匹配。

从 Step 1 的 action/env 提取**场景关键词**。

```
obsidian read path="aesthetics/scene-recipes.md" → 匹配场景类型
  ├─ 命中: Read 对应配方文件 ([[lighting-xxx]] → lighting/lighting-xxx.md)
  └─ 未命中: AskUserQuestion → 3 个风格预设 → Read style-presets.md → 注入
```

### 风格询问触发

以下情况触发 `AskUserQuestion`:
- 从用户输入未检测到**任何**概念基因**且**未检测到场景关键词**且**未说风格方向
- 用户描述过于模糊 (只有"一个女孩")

给 3 个风格预设让用户选 (从 `aesthetics/style-presets.md` 取): 史诗/暗黑/华丽/清新/复古/极简。

### 画师注入

按模型 `artist_format`: Anima=`@name`, Illustrious/SDXL 动漫=`name` (直接写), Flux=`in the style of name`, Pony 基模型不支持。

---

## §4 输出规范

### 三段式 (缺一段视为不完整)

**第 1 段 — 10 维度提取表**: 每维标注提取结果 + 来源 (用户原话/推断/审美匹配)

**第 2 段 — 自检 PASS/FAIL 表**: 9 项逐项判定 + 说明

**第 3 段 — 纯净 prompt** (code block, 可直接粘贴 ComfyUI):

```
正向 prompt
```
```
负向 prompt
```

### 禁止项

- ❌ 凭记忆编 tag (必须先 grep vault danbooru.csv)
- ❌ Danbooru 纯 tag 模型用自然语言复合短语
- ❌ 权重 > 1.5
- ❌ Flux.2 写负向 (官方不支持)
- ❌ Anima 用 SDXL LoRA / Pony 用 SDXL LoRA
- ❌ 输出含注释/分隔符混入 prompt
- ❌ 重要信息藏在长句从句里
- ❌ 负向照搬 SD1.5 万能模板 —— **负向只用模型 frontmatter 的 `negative` 字段**，不额外追加
- ❌ Flux/Anima/视频模型写长负向 —— **默认空负向**。仅在具体问题出现时加 ≤3 个精准排除词。现代 LLM encoder 上每个负向 token 削弱 CFG 效力
- ❌ 不写 safety tag (Anima 默认 `safe`, 用户无明确 NSFW 意图时不用 `nsfw`)

---

## §5 视频 Prompt

> **v3.1 核心更新**: 视频不是「图像 prompt + 运镜」。运动本身是第一主体。

视频 prompt 的完整框架、5 要素、组装规则、自检项 → **不在本文件**。全部在 vault：

- `obsidian read path="workflows/video-5-elements.md"` — 5 要素框架 + 相机/负向规则 + 组装顺序 + 自检
- `obsidian read path="aesthetics/video-archetypes.md"` — 5 种视频概念原型 + 匹配策略
- `obsidian read path="aesthetics/motion-glossary.md"` — 运动物理质感词库 + 快速匹配表
- 模型 frontmatter (`models/wan.md` 等) — `prompt_structure` + `camera_rule` + `negative_default`

### 执行流程（编排逻辑）

1. **V0** — 模型识别（读取模型 frontmatter）+ 概念原型匹配（读 video-archetypes）
2. **V1** — 5 要素提取（运动过程 ≥ 50% 篇幅，单主体硬约束）
3. **V2** — 运动质感词注入（读 motion-glossary 快速匹配表）
4. **V3** — 相机：默认不写，仅非自然运动时写
5. **V4** — 负向：默认空
6. **V5** — 组装：运动主体→场景→运动过程(核心)→物理质感→循环设计

---

## §6 img2img / I2V 策略

**核心差异**: 参考图已决定大部分画面内容，prompt 只描述**与参考图的不同之处**。

| 原则 | 说明 |
|------|------|
| 不重复描述已有内容 | 参考图已有蓝天不写 `blue sky`，已有白衣不写 `white dress` |
| 只描述变化/新增 | 换发色只写 `red hair`，换背景只写新背景 |
| denoise 决定 prompt 权重 | 0.3-0.5: 微调, 只写要改的细节; 0.6-0.8: 大改, prompt 接近 txt2img; 0.8+: 基本等于 txt2img |
| 保留风格一致 | 加 `same style`, `consistent with original` 防画风突变 |

**I2V (图生视频)**: 不重复描述静态内容，重点描述**想让什么动起来 + 运镜方式**。动作幅度要合理，参考图姿态 → 动作变化不能太跳跃。

---

## §7 LoRA 集成

> LoRA 是**可选推荐**。除非用户明确说要 LoRA，否则不主动加。

### 查询

用户说要 LoRA → `mcp__comfyui-mcp__search_civitai_models(query, types=["LORA"], base_models=[按模型族选])`:

| 模型族 | base_models |
|--------|-------------|
| SD 1.5 | `["SD 1.5"]` |
| SDXL / Illustrious / NoobAI | `["SDXL 1.0"]` |
| Pony | `["Pony"]` |
| Flux.1 | `["Flux.1"]` |
| Anima | ⚠️ 生态早期，找明确标注 Anima 兼容的 LoRA；无兼容时不加 |

### 规则

- 单 LoRA 权重: 0.6-1.0；多 LoRA 总权重 ≤ 1.5-2.0，最多 2-3 个
- **触发词必须在正向 prompt 中**，放开头或主体描述前
- 触发词来源: 用户提供 > CivitAI 示例图 prompt > 模型元数据
- ❌ Anima 不能用 SDXL LoRA (DiT vs UNet 架构不兼容)
- ❌ Pony 不能用 SDXL LoRA (标签体系不同)

---

## §8 Vault 数据管理

### 路径
`D:\ObsidianWorkSpace\workspace\10-Projects\prompt-forge/`

### 数据布局
```
models/         ← 模型元数据 (.md + YAML frontmatter + wikilink)
   anima.md, pony.md, flux.md, sdxl.md, wan.md, ...
workflows/      ← prompt 结构规范（canonical，SKILL.md 引用）
   image-8-segments.md  ← 图像 8 段框架唯一权威
   video-5-elements.md  ← 视频 5 要素框架唯一权威
reference/      ← 参考数据
   token-budget.md      ← token 预算分配
aesthetics/     ← 审美配方 (.md, wikilink 互联)
   concept-archetypes.md ← 6种图像概念原型
   video-archetypes.md   ← 5种视频概念原型
   motion-glossary.md    ← 运动物理质感词库
   medium-glossary.md    ← 50+媒介描述词速查
   lighting/    ← 光影配方 9 个
   composition/ ← 构图配方 7 个
   color/       ← 色彩配方 9 个
   scene-recipes.md  ← 场景→配方映射表
   style-presets.md  ← 7 个风格预设
tags/           ← tag 字典 (CSV, Bash grep)
   danbooru.csv (140K), wd14-tags.csv (10K)
negative/       ← 负向模板
changelog/      ← 版本变更记录
```

### 刷新

tag 字典 7 天提醒刷新。Run:
```bash
curl -o "D:/ObsidianWorkSpace/workspace/10-Projects/prompt-forge/tags/danbooru.csv" \
  "https://cdn.jsdelivr.net/gh/DominikDoom/a1111-sd-webui-tagcomplete@main/tags/danbooru.csv"
```

模型元数据: 模型发布新版本时手动编辑对应 .md 文件 frontmatter。每年更新 `year` 占位符。

### 读数据方式

所有 vault .md 文件用以下方式读取（效果等价，任选其一）:

**方式 A**: `Bash: obsidian read path="10-Projects/prompt-forge/..."`（返回原始 markdown，**不要加 `vault=` 参数**——会自动定位到当前活动的 vault）

**方式 B**: `Read` 直接读绝对路径 `D:/ObsidianWorkSpace/workspace/10-Projects/prompt-forge/...`

**wikilink 跟进**: obsidian CLI 返回的仍是原始 markdown（`[[flux]]` 不会自动展开）。需要手动 `Read` wikilink 目标文件: `[[file-name]]` → `同目录/file-name.md`。

tag 验证: `Bash grep`（CSV 纯数据，不需要 obsidian）。
