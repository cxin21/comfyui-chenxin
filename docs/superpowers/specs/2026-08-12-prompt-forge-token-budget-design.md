# Prompt Forge 模型原生提示词与动态 Token 预算设计

日期：2026-08-12  
状态：设计已在对话中逐节确认，等待书面规格复核  
范围：Anima 图像提示词、MiniMax-H3 T2VA、MiniMax-H3 Ref2VA

## 1. 目标

重构 Prompt Forge，使其在各模型真实上下文边界内，以生成质量为最高优先级编写、压缩和审计提示词。

本设计必须同时满足：

- 使用模型真实 tokenizer 计数，不使用字符数或单词数冒充 token 数。
- 理论上下文只作为物理边界；使用更小、经真实生成校准的质量包络。
- 超限时先无损压缩；需要牺牲用户事实时停止并要求用户取舍。
- Anima 使用完整、可追溯、离线的专属 tag 字典。
- Anima 根据语义复杂度自适应选择 tag-only 或 tag 与自然语言混合表达。
- H3 镜头密度随时长和事件复杂度动态变化。
- 不提供其他模型 profile、通用模型注册表或动态 grammar 插件。
- 暂不提供本地 checkpoint 或 LoRA 覆盖层。
- 不提供旧 PromptPackage、draft、dialect_id 或兼容 adapter。

## 2. 非目标

- 不发现、下载或切换模型。
- 不把本地 checkpoint 或 LoRA 触发词写入 Prompt Forge 知识库。
- 不用固定中文到英文映射表替代 LLM 的语义判断。
- 不用 tag 字典自动拼装完整提示词。
- 不因为普通语义 tag 未收录就拒绝提示词。
- 不使用尾部 token 截断。
- 不为未来模型预留通用扩展接口。

## 3. 依据与模型边界

### 3.1 Anima

Anima 官方模型卡说明：

- 模型训练包含 Danbooru 风格 tags、自然语言 captions 及二者混合。
- 普通 tag 使用小写和空格；score tags 是使用下划线的例外。
- Danbooru 与 Gelbooru 写法不同时优先 Gelbooru。
- 推荐 tag 顺序为 quality/meta/year/safety、人数、角色、作品、artist、general tags。
- artist 必须使用 `@` 前缀。
- 训练包含 tag dropout，不要求罗列画面中的每个 tag。

ComfyUI 的 Anima tokenizer 使用 Qwen3-0.6B；编码器配置的 `max_position_embeddings` 为 32,768。ComfyUI tokenizer 本身设置了极大的表面 `max_length`，因此 Prompt Forge 必须主动执行真实上限检查。

### 3.2 MiniMax-H3

H3 官方 text encoder 使用 Qwen3-VL，多模态上下文上限为 262,144 positions。图片、特殊 tokens、模板和文本共享这个上下文。

H3 processor 使用：

- `patch_size = 16`
- `merge_size = 2`
- 最小图像像素数 65,536
- 最大图像像素数 16,777,216

H3 官方 Ref2VA 指南建议生成任务的 `detailed_description` 通常使用 350–500 英文词。这个范围证明理论 262K 上下文不是建议填满的文本预算。

### 3.3 研究原则

设计吸收以下研究结论：

- LLMLingua：使用预算控制器和从粗到细压缩，在预算内保留语义完整性。
- LongLLMLingua：关键内容密度与位置会影响长上下文表现，重复内容会稀释关键内容。
- LLMLingua-2：忠实的抽取式压缩比仅按单向信息熵删除 tokens 更适合保持语义。
- TIFA 与 T2I-CompBench++：计数、属性绑定、空间关系和多对象组合是图像生成中的高风险维度。

## 4. 总体架构

```text
用户需求
  ↓
Fact Ledger
  ├─ 用户锁定事实
  ├─ 用户明确事实
  ├─ 完成任务所需推断
  └─ Agent 可删除修饰
  ↓
┌──────────────────────┬──────────────────────┐
│ Anima Prompt Author  │ MiniMax-H3 Author    │
│ tag 检索与混合表达   │ 时间线、音画与引用   │
└──────────────────────┴──────────────────────┘
  ↓
Token Budget Planner
  ├─ 真实 tokenizer 计数
  ├─ 动态字段预算
  ├─ 边际信息收益排序
  └─ A+B 无损压缩
  ↓
Model-native Auditor
  ├─ 事实完整性
  ├─ 模型语法
  ├─ 主体绑定/引用一致性
  ├─ 时间可执行性
  └─ 音画一致性
  ↓
PromptArtifact
```

仅提供三个明确入口：

- `author_anima_prompt`
- `author_h3_t2va_prompt`
- `author_h3_ref2va_prompt`

三个入口可以复用事实账本、token 计数和压缩基础设施，但不能经由通用模型注册表或 grammar dispatch 选择实现。

## 5. Token 计量

### 5.1 生产要求

- Anima 使用与本地 ComfyUI 相同的 Qwen3-0.6B tokenizer。
- H3 使用官方 Qwen3-VL tokenizer。
- tokenizer 不可用时可以输出探索稿，但必须设置 `token_count_verified=false`。
- `token_count_verified=false` 的 artifact 禁止进入 camera 执行技能。
- 字符数、英文单词数和经验比例只能用于界面预估，不能用于生产放行。

### 5.2 四层边界

每种任务具有四个边界：

```text
target_range < soft_limit < quality_limit < model_hard_limit
```

- `target_range`：正常目标工作区。
- `soft_limit`：超过后启动无损压缩。
- `quality_limit`：超过后不得继续自动加入内容。
- `model_hard_limit`：编码器物理边界，正常提示词不应接近。

统一关系：

```text
soft_limit = ceil(target × 1.25)
quality_limit = min(profile_quality_cap, ceil(target × 1.60))
B_effective = min(B_quality, B_context_available)
```

## 6. Anima 动态预算

### 6.1 正向提示词

```text
B_anima_positive = clamp(
  128
  + 48 × max(0, subjects - 1)
  + 24 × explicit_relations
  + 32 × complex_actions
  + 24 × environment_clusters
  + 64 × natural_language_bridges,
  128,
  512
)
```

变量定义：

- `subjects`：需要分别绑定属性的主体数量。
- `explicit_relations`：左右、前后、持有、注视、交互等显式关系数量。
- `complex_actions`：单个稳定 tag 无法清楚表达的动作或因果过程数量。
- `environment_clusters`：具有独立空间或关键道具的环境组数量。
- `natural_language_bridges`：必须用自然语言表达的主谓归属段数量，通常为 0 或 1。

边界：

```text
target ≤ 512
soft_limit ≤ 640
quality_limit ≤ 768
hard_limit = 32,768
```

### 6.2 负向提示词

```text
B_anima_negative = clamp(
  32 + 8 × exclusion_groups,
  32,
  96
)
```

```text
negative_quality_limit = 128
```

负向提示词只覆盖质量缺陷、结构错误、技术缺陷和用户明确排除项，不反写正向内容。

## 7. H3 动态预算

### 7.1 镜头密度

```text
max_shots = 1 + floor((duration_seconds - 1) / 3)
```

这是上限，不是目标。只有引入新信息、视点、空间、状态或时间变化时才能切镜。简单连续动作优先使用单镜头。

### 7.2 T2VA

```text
B_h3_t2va = clamp(
  140
  + 20 × duration_seconds
  + 70 × max(0, shots - 1)
  + exact_dialogue_tokens,
  180,
  900
)
```

```text
soft_limit ≤ 1,125
quality_limit ≤ 1,200
```

### 7.3 Ref2VA

```text
B_h3_ref2va = clamp(
  420
  + 90 × reference_count
  + 24 × duration_seconds
  + 80 × max(0, shots - 1)
  + exact_dialogue_tokens,
  650,
  1,600
)
```

```text
soft_limit ≤ 2,000
quality_limit ≤ 2,400
```

### 7.4 多模态上下文

图片完成 H3 processor 的智能缩放后：

```text
visual_tokens(image) =
  ceil(resized_width / 32)
  × ceil(resized_height / 32)
```

```text
B_context_available =
  262,144
  - visual_tokens
  - chat_template_tokens
  - special_tokens
  - runtime_safety_margin
```

视觉 tokens 影响物理安全边界，但上下文剩余很多时也不得提高文本质量预算。

## 8. 边际信息收益

用户锁定事实无条件进入。其他候选内容按以下密度排序：

```text
utility_density =
  priority
  × adherence_risk
  × source_confidence
  × non_redundancy
  ÷ token_cost
```

初始权重：

### 8.1 priority

- 用户锁定事实：强制，不参与淘汰。
- 用户明确要求：4。
- 完成画面所必需的推断：3。
- Agent 审美增强：1。

### 8.2 adherence_risk

- 身份、数量、属性绑定、空间关系：1.5。
- 动作因果、连续性、镜头落点：1.3。
- 构图、关键道具、对白：1.2。
- 光线、材质、风格修饰：1.0。

### 8.3 source_confidence

- 明确用户事实或 Anima canonical tag：1.0。
- 已验证 alias：0.85。
- 未验证长尾 tag：0.6。

### 8.4 non_redundancy

- 新信息：1.0。
- 部分重复：0.5。
- 完全重复：0。

这些是首版工程参数，必须通过固定评测集校准，不得描述成模型固有真理。

## 9. 字段预算分配

### 9.1 Anima 正向提示词

| 字段 | 优先级 | 建议占比 | 最高占比 |
|---|---:|---:|---:|
| 协议前缀 | 强制 | 6%–10% | 12% |
| 主体锚点 | 强制 | 15%–22% | 28% |
| 外观与属性绑定 | 高 | 18%–24% | 30% |
| 动作与关系 | 高 | 18%–25% | 32% |
| 构图与相机 | 中高 | 8%–14% | 18% |
| 环境与关键道具 | 中 | 10%–16% | 22% |
| 光线与视觉风格 | 中低 | 8%–14% | 18% |
| 自然语言桥 | 条件启用 | 0%–18% | 25% |

预算借用顺序：

```text
风格余量
→ 环境余量
→ 构图余量
→ 动作与关系
→ 属性绑定
```

主体身份、数量和用户锁定事实的预算不能被借走。

输出顺序：

```text
质量/meta/年份/安全
→ 人数
→ 角色
→ 作品
→ @artist
→ 属性与一般语义 tags
→ 必要自然语言桥
```

### 9.2 Anima 负向提示词

| 字段 | 建议占比 |
|---|---:|
| 官方质量基线 | 35%–45% |
| 解剖、数量和结构错误 | 20%–30% |
| 图像技术缺陷 | 15%–25% |
| 用户明确排除内容 | 10%–20% |

### 9.3 H3 T2VA

| 字段 | 建议占比 |
|---|---:|
| 固定结构与标签 | 3%–5% |
| `integrated_multimodal_description` | 72%–82% |
| `overall_soundscape` | 8%–12% |
| `non_diegetic_music` | 3%–8% |
| 安全余量 | 5% |

每个镜头内部：

| 内容 | 建议占比 |
|---|---:|
| 开场状态与构图 | 20%–25% |
| 主体动作与状态变化 | 30%–40% |
| 相机运动 | 10%–15% |
| 同步声音与对白 | 10%–20% |
| 动作结果与落点 | 10%–15% |

### 9.4 H3 Ref2VA

| 字段 | 建议占比 |
|---|---:|
| `subject_definitions` | 12%–18% |
| `summary` | 3%–5% |
| `retention_analysis` | 10%–16% |
| `detailed_description` | 52%–64% |
| `overall_soundscape` | 5%–8% |
| `non_diegetic_music` | 2%–5% |
| 安全余量 | 5% |

稳定外观只在 `subject_definitions` 完整定义；`retention_analysis` 只描述保留关系；`detailed_description` 只写当前镜头真正可见和发生变化的内容。

## 10. Anima 离线 Tag 字典

### 10.1 范围

字典是 Anima 专属知识库，不是所有模型共享的 tag registry。

```text
knowledge/anima/
├── protocol.json
├── tags.sqlite
├── manifest.json
└── budget-policy.json
```

不包含：

- 中文固定翻译表。
- checkpoint 差异。
- LoRA 触发词。
- 其他模型字段。
- 自动提示词模板。

### 10.2 SQLite 数据结构

```sql
CREATE TABLE tags (
  tag_id INTEGER PRIMARY KEY,
  canonical TEXT NOT NULL UNIQUE,
  anima_form TEXT NOT NULL,
  category TEXT NOT NULL,
  usage_count INTEGER NOT NULL,
  source TEXT NOT NULL,
  source_version TEXT NOT NULL,
  verification_status TEXT NOT NULL
);

CREATE TABLE aliases (
  alias TEXT NOT NULL,
  tag_id INTEGER NOT NULL REFERENCES tags(tag_id),
  source TEXT NOT NULL,
  confidence REAL NOT NULL,
  PRIMARY KEY(alias, tag_id)
);
```

### 10.3 来源优先级

```text
Anima 官方显式规则
→ Gelbooru canonical
→ Danbooru compatibility alias
```

普通语义 tag 未收录时只标记 `unverified`。保留命名空间、错误 score 语法和错误 artist 语法可以阻止生产。

### 10.4 可复现清单

`manifest.json` 必须记录：

- dictionary version。
- 数据源 URL 或不可变资源标识。
- source revision 与获取日期。
- precedence。
- row count。
- SQLite SHA-256。
- builder SHA-256。

相同输入快照必须产生相同 SQLite 哈希。不得复用旧版缺少完整来源链的 tag-index。

词典构建还有一项发布硬门：每个数据源必须记录许可证或服务条款依据，并确认允许在插件中再分发衍生索引。无法确认再分发权时，该数据源只能用于研究和本地构建，不能进入随插件发布的 `tags.sqlite`。词典完整性不能以忽略数据许可为代价。

## 11. Tag 数据流

### 11.1 检索

LLM 先生成概念查询，而不是 tag：

```json
{
  "concept": "long blonde hair",
  "owner": "subject_1",
  "dimension": "appearance",
  "locked": true
}
```

字典返回少量候选及来源、频率和置信度。

### 11.2 选择

LLM 根据主体归属和画面意图选择候选。查询结果不能自动进入提示词。

### 11.3 编排

选择后的 tags 进入对应语义槽；复杂主谓、空间和动作因果使用自然语言桥。tag 与自然语言不得重复同一事实。

### 11.4 审计

审计输出：

- `canonical`
- `known_alias`
- `unverified`
- `invalid_protocol_tag`
- `wrong_underscore_form`
- `artist_prefix_missing`
- `duplicate_semantics`
- `possible_binding_conflict`

审计报告建议但不自动改写提示词。

## 12. Fact Ledger

每个事实使用不可变记录：

```json
{
  "fact_id": "subject_1.hair.color",
  "value": "blonde",
  "origin": "user",
  "locked": true,
  "owner": "subject_1",
  "dimension": "appearance",
  "rendered_by": ["blonde hair"],
  "token_cost": 3
}
```

`origin` 只允许：

- `user_locked`
- `user_explicit`
- `necessary_inference`
- `agent_embellishment`

任何输出片段都必须能追溯到事实；没有来源的内容不得悄悄进入生产提示词。

## 13. A+B 压缩算法

### 13.1 Pass 1：精确去重

删除完全重复的 tag、形容词、主体描述和声音描述。

### 13.2 Pass 2：语义去重

仅在两个表达确定承载同一事实时，保留更符合模型方言且 token 成本更低的一项。

### 13.3 Pass 3：结构提取

- Anima：主体稳定属性由 tag 表达，自然语言不重复。
- H3 Ref2VA：稳定外观提到 `subject_definitions`。
- H3 全局环境声提到 `overall_soundscape`。
- H3 非叙事音乐提到 `non_diegetic_music`。

### 13.4 Pass 4：词面压缩

允许删除空泛增强词、合并并列短语、删除多余冠词、采用更短 canonical tag 和稳定引用标签。

禁止压缩：

- 用户原始对白与画面文字。
- 数量、否定关系、时间戳。
- 主体编号和引用标签。
- 方位、颜色、归属和动作结果。
- 用户锁定措辞。

### 13.5 Pass 5：删除 Agent 自增内容

超过软上限后，可以删除未被用户要求的装饰性背景、次要材质、空泛氛围和重复风格强化。

用户明确提供的事实不能自动删除。如果 Pass 5 后仍超过质量上限，返回预算冲突。

### 13.6 禁止尾部截断

不得采用 `tokens[:limit]` 或任何等价做法。

## 14. 超限报告

```json
{
  "status": "budget_conflict",
  "actual_tokens": 1034,
  "quality_limit": 768,
  "mandatory_tokens": 711,
  "agent_optional_tokens": 0,
  "excess_tokens": 266,
  "protected_causes": [
    {
      "dimension": "multi_subject_binding",
      "tokens": 124,
      "reason": "three subjects require separate appearance ownership"
    }
  ],
  "user_choices": [
    {
      "choice": "simplify_environment",
      "estimated_saving": 82,
      "facts_affected": ["environment.secondary_props"]
    },
    {
      "choice": "split_into_two_images",
      "estimated_saving": 210,
      "facts_affected": []
    }
  ]
}
```

报告必须说明每个取舍影响的事实，不返回勉强可生产的提示词。

## 15. 生产质量硬门

质量采用硬门，不使用可相互抵消的总分。

### 15.1 事实完整门

- 所有锁定事实都有输出承载。
- 数量、颜色、归属、对白和动作结果未改变。
- 没有未经支持的新主体、道具或剧情。

### 15.2 Token 预算门

- 使用真实 tokenizer。
- `actual <= quality_limit`。
- 未发生尾部截断。
- `sacrificed_facts=[]`。

### 15.3 Anima 方言门

- 协议 tag 合法。
- 普通 tag 使用小写和空格。
- score 语法正确。
- artist 使用 `@`。
- tag 顺序正确。
- 自然语言桥不重复 tag 内容。
- 未验证 tag 被明确报告。

### 15.4 Anima 绑定门

每个主体分别审计身份、外观、服装、持有物、动作和空间位置。关键属性无法确定归属时拒绝生产。

### 15.5 H3 时间可执行门

- 时间戳严格递增并位于时长内。
- 动作能在所属时间段内完成。
- 镜头密度符合时长限制。
- 对白长度与可用时间匹配。
- 动作具有开始、发展和结果。

### 15.6 H3 引用一致门

- 每个引用标签都有定义。
- 标签跨章节保持相同含义。
- retention 与镜头实际使用一致。
- 引用数量与本地固定工作流完全匹配。
- 不创建不存在的资源。

### 15.7 H3 音画一致门

- 对白只出现在 `<d>` 中。
- speaker ID 稳定。
- 物理声音与动作同步。
- 全局声音不在各镜头机械重复。
- 非叙事音乐不混入环境声。

## 16. Artifact 状态与证据

只允许：

- `production_ready`
- `budget_conflict`
- `quality_rejected`

Artifact 至少包含：

```json
{
  "token_budget": {
    "target": 384,
    "soft_limit": 480,
    "quality_limit": 615,
    "hard_limit": 32768,
    "actual": 352,
    "verified": true
  },
  "field_allocation": {},
  "tag_audit": {},
  "compression": {
    "performed": true,
    "removed_redundancy": [],
    "sacrificed_facts": []
  },
  "diagnostics": {
    "semantic_density": 0.82,
    "dictionary_coverage": 0.91,
    "redundancy_ratio": 0.07,
    "binding_clarity": 0.96,
    "timeline_density": 0.78
  }
}
```

诊断指标不参与生产放行，也不能抵消硬门失败。

## 17. 源码边界

```text
skills/prompt-forge/
├── SKILL.md
├── prompt_forge/
│   ├── artifact.py
│   ├── fact_ledger.py
│   ├── token_budget.py
│   ├── compression.py
│   ├── anima_author.py
│   ├── anima_audit.py
│   ├── anima_dictionary.py
│   ├── h3_t2va_author.py
│   ├── h3_ref2va_author.py
│   └── h3_audit.py
├── knowledge/
│   ├── anima/
│   │   ├── protocol.json
│   │   ├── tags.sqlite
│   │   ├── manifest.json
│   │   └── budget-policy.json
│   └── h3/
│       ├── t2va-budget-policy.json
│       └── ref2va-budget-policy.json
├── scripts/
│   ├── build_anima_dictionary.py
│   ├── query_anima_tags.py
│   ├── count_prompt_tokens.py
│   └── audit_prompt.py
└── tests/
```

删除：

- 通用 `profiles.py`。
- grammar dispatch。
- 模型注册表。
- 兼容 adapter。
- Prompt Forge README。
- checkpoint/LoRA overlay。
- 中文固定翻译表。
- 其他模型占位目录。

## 18. 测试设计

### 18.1 Tokenizer Golden Tests

- Anima 与本地 ComfyUI tokenizer 一致。
- H3 与官方 tokenizer 一致。
- 覆盖中文、英文、tag、artist、特殊标签和对白。
- 覆盖四层预算边界。
- 使用真实缩放尺寸验证 H3 视觉 token 公式。

### 18.2 字典测试

- canonical 精确命中。
- Gelbooru canonical 优先。
- Danbooru 写法只作为 alias。
- 普通下划线 tag 提示为空格形式。
- score tags 保留下划线。
- 未知 tag 只警告。
- artist 缺少 `@` 时失败。
- 查询结果稳定排序。

### 18.3 Fact Ledger 测试

- 每个输出片段可追溯。
- 锁定事实永不进入可删除集合。
- Agent 修饰与用户事实严格区分。
- 属性不能跨主体迁移。

### 18.4 变形测试

- 重复事实不显著增加最终 tokens。
- 调换用户描述顺序不改变事实账本。
- 增加锁定事实后必须保留。
- 删除 Agent 修饰不改变主体、动作或构图。
- 增加主体后预算增长且绑定仍明确。
- 增加 H3 时长后动作阶段和镜头上限增长。
- 增加参考图后视觉 tokens 与引用预算同步增长。
- 超过软上限时压缩，超过质量上限时返回预算冲突。

## 19. 基准语料

首版至少 200 个任务：

| 类型 | 数量 |
|---|---:|
| Anima 单主体 tag | 25 |
| Anima 多主体与属性绑定 | 30 |
| Anima 数量、空间与交互 | 25 |
| Anima 混合提示词 | 20 |
| Anima 字典与 token 边界 | 20 |
| H3 T2VA 时长与镜头 | 30 |
| H3 T2VA 对白与音画 | 15 |
| H3 Ref2VA 单图 | 15 |
| H3 Ref2VA 三图 | 15 |
| H3 超限与错误结构 | 5 |

每个任务保存原始意图、锁定事实、允许推断、禁止发明、预期字段、预算范围和必须失败条件。

## 20. 真实生成校准

代表性任务使用固定工作流、固定模型、固定分辨率或时长、相同采样参数和至少四个固定 seeds。

预算档位：

```text
0.6×, 0.8×, 1.0×, 1.25×, 1.6×
```

Anima 评测：

- 主体数量。
- 属性绑定。
- 空间关系。
- 动作和关键物件。
- 构图和风格一致性。
- 图像技术质量。

H3 评测：

- 开场状态和动作完成度。
- 镜头时间点。
- 身份与服装连续性。
- 参考图保留。
- 对白、speaker 和音画同步。
- 结尾落点。
- 视频与音频技术质量。

自动评测只用于筛选，最终参数通过人工成对比较确认。

## 21. 参数选择

分别绘制 token 数与事实遵循率、绑定成功率、技术质量、冗余度和失败率的关系。

- `target`：事实遵循率距该任务观测最大值不超过 1 个百分点时所需的最短提示词。
- `soft_limit`：通过样例长度的第 90 百分位。
- `quality_limit`：增加 tokens 不再改善遵循率，或开始增加串线、冲突和未完成动作的位置。
- Anima tag-only、Anima hybrid、H3 各时长段、H3 单图和三图分别校准。

参数分别写入三个明确 policy 文件，不使用通用模型配置。

## 22. 发布验收

必须 100% 满足：

- 锁定事实零损失。
- 零尾部截断。
- 零旧字段和兼容路径。
- 零其他模型 profile。
- 零 checkpoint/LoRA 覆盖层。
- 字典来源和哈希完整。
- H3 字段顺序、引用和时间戳合法。
- 所有生产 artifact 使用真实 tokenizer。
- `sacrificed_facts` 始终为空。
- 超限任务返回明确取舍报告。
- 安装后的插件缓存版本与项目版本一致。
- 缓存中的 Prompt Forge 关键文件哈希与源码一致。
- 缓存中不存在旧 dictionary、dialects、internals 或 PromptPackage 文件。

随机生成质量不设虚假的绝对分数；必须与未压缩提示词和人工专家提示词进行成对比较，并保留输出证据。

## 23. 参考资料

- Anima 官方模型卡：https://huggingface.co/circlestone-labs/Anima
- ComfyUI Anima tokenizer：https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/text_encoders/anima.py
- ComfyUI Qwen3-0.6B 配置：https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/text_encoders/llama.py
- MiniMax-H3 text encoder：https://github.com/MiniMax-AI/MiniMax-H3/blob/main/text_encoder/config.json
- MiniMax-H3 processor：https://github.com/MiniMax-AI/MiniMax-H3/blob/main/processor/preprocessor_config.json
- H3 T2VA 指南：https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/base-en.txt
- H3 Ref2VA 指南：https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt
- LLMLingua：https://arxiv.org/abs/2310.05736
- LongLLMLingua：https://arxiv.org/abs/2310.06839
- LLMLingua-2：https://arxiv.org/abs/2403.12968
- TIFA：https://arxiv.org/abs/2303.11897
- T2I-CompBench++：https://arxiv.org/abs/2307.06350
