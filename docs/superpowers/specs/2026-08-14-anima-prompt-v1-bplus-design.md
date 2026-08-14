# Anima Prompt v1 B+ 设计基线

**状态：** 已批准的重写基线  
**日期：** 2026-08-14  
**适用目录：** `skills/anima-prompt-v1/`  
**架构原则：** 全新接口；不保留旧 `anima_prompt`、旧 provider 或旧 schema 的兼容层。

## 1. 目的与第一性原理

本技能只服务于 Anima 模型。它的职责不是把所有用户意图压成固定模板，而是把用户意图、可验证的模型协议和可追溯的 Tag Catalog 组合成可复制的 Anima 正向/负向提示词。

系统将三个问题分开：

1. 当前技能 LLM 判断用户想表达什么、哪些事实是明确要求、哪些内容只是推断；
2. Tag Catalog 证明某个 tag 的规范形式、类别、命中方式和 provenance；
3. 脚本保留结构、校验关系、生成不可变草稿、报告问题，并把关系候选安全地写入独立 overlay。

核心不变量：模型负责“表达什么以及采用何种表达方式”，Catalog 负责“这个 tag 是什么以及证据在哪里”，脚本负责“不得悄悄改写用户事实”。

## 2. 目标与非目标

### 必须实现

- 结构化 `PromptBrief`，保留事实、来源、锁定状态和未知项；
- 内部 `VisualRelationGraph`，表达多主体、动作归属、遮挡、空间和场景关系；
- `tag-led`、`hybrid`、`natural-language-led` 三种表达路线，默认 `hybrid`；
- Anima-Base、Anima-Aesthetic、Anima-Turbo 三种模型变体策略；
- 用户明确的 trigger、wildcard、weight、锁定片段和未知内容原样保真；
- 独立的 positive author 与 negative author；
- 带 provenance 的 exact、alias、prefix、category/facet、accepted related、fuzzy 查询；
- 只读、非阻断的 Inspector；
- 人类可复制的 POSITIVE/NEGATIVE 和固定五字段机器输出；
- 生成结束后由当前技能 LLM 判断是否建立关系，并提交结构化关系 JSON；
- 关系候选与基础 Catalog 分离，只有 accepted 关系可用于 related 搜索。

### 明确不做

- 不使用固定 prompt 槽位、固定长度或通用固定质量前缀；
- **不把 Anima 的质量协议当作可选建议。** “不使用通用固定质量前缀”不等于“不执行 Anima 变体的强制质量词策略”；
- 不根据模糊匹配擅自替换用户 tag；
- 不删除或改写未知 tag、NSFW 内容、自然语言和用户锁定片段；
- 不让脚本代替 LLM 推断视觉语义或生成 cooccurrence；
- 不把 Inspector 变成阻断式门禁或生产证明；
- 不把 candidate 自动升级为 accepted；
- 不为旧接口保留兼容适配层。

## 3. Anima 模型协议

事实来源为 [Anima 官方模型卡](https://huggingface.co/circlestone-labs/Anima)。Anima 使用小写 tag；空格形式优先，只有 score tag 保留下划线。质量/元数据/安全类 tag 应位于提示词前部。

### 3.1 变体解析

`ModelProfile` 必须在 authoring 前确定。用户只说“Anima”而没有提供变体时，按 Anima-Base 执行，并在 `assumptions` 记录“未指定变体，按 Base 处理”；不得退化为通用 Unknown/Custom 质量策略。

| 变体 | 正向强制质量词 | 负向强制质量词 | score 规则 |
|---|---|---|---|
| Anima-Base | `masterpiece`, `best quality`, `score_7` | `worst quality`, `low quality`, `score_1`, `score_2`, `score_3` | `score_7` 必须存在；负向 score 三项必须存在 |
| Anima-Aesthetic | `masterpiece`, `best quality` | `worst quality`, `low quality` | 不自动加入 `score_*` |
| Anima-Turbo | `masterpiece`, `best quality` | `worst quality`, `low quality` | 不自动加入 `score_*` |

规则：

- 上表词组属于 Anima 协议事实，必须在 `PromptBrief` 中以 `quality` domain 的 typed fact/segment 进入流程，reason 为 `required_by_anima_variant`；
- mandatory quality terms 必须有 Catalog exact 或 alias 命中及官方 provenance；fuzzy 命中不能满足强制项；
- `safe` 是官方安全 tag，不是质量词。非明确露骨请求默认加入；用户明确选择其他安全设置时，以用户事实为准，并在 advisory 说明；
- `highres`、`absurdres` 是 meta tag，不是质量词，不得因为“强制质量词”而自动加入；
- Anima-Aesthetic 和 Anima-Turbo 不得无请求地继承 Base 的 `score_*`；
- 质量词缺少 Catalog provenance 时，不得伪造官方事实：保留字面、标记 advisory，并把该缺口写入输出元数据。

## 4. 端到端数据流

```text
用户请求
  -> IntentParser -> PromptBrief
  -> ModelProfile / Anima mandatory quality seed
  -> Catalog Resolver -> TagHit + provenance
  -> VisualRelationGraph
  -> RouteDecision
  -> Positive Author + Negative Author
  -> PromptPlan (staging)
  -> immutable PromptDraft
  -> read-only Inspector -> InspectionReport
  -> PromptOutput {positive, negative, notes, assumptions, advisories}
  -> 当前技能 LLM 判断关系
  -> RelationSubmission JSON
  -> Validator -> candidate relation overlay
  -> 人工/独立流程接受 -> accepted related search
```

质量协议的插入点是 `ModelProfile` 确定之后、Catalog Resolver 之前。技能 LLM 必须将变体必需项种入 `PromptBrief` 的 typed facts/exclusions；脚本 workflow 负责保留和校验，不替 LLM 猜测用户未表达的视觉内容。

Prompt 生成先完成，关系提交后置。关系提交失败不得阻断已经生成的 prompt。

## 5. 目录与模块边界

```text
skills/anima-prompt-v1/
├─ SKILL.md
├─ agents/openai.yaml
├─ references/
│  ├─ intent-and-relation-graph.md
│  ├─ catalog-architecture.md
│  ├─ authoring-and-routing.md
│  ├─ inspection-and-output.md
│  └─ evaluation.md
├─ anima_prompt_v1/
│  ├─ domain.py, draft.py, output.py
│  ├─ authoring/{intent,relation_graph,routing,positive,negative,protocol,relation_submission,workflow}.py
│  ├─ catalog/{models,storage,builder,search,relations,relation_overlay,facets,cli}.py
│  └─ inspection/{types,checks,conflicts,weights,token_estimate}.py
├─ knowledge/{source,tags.sqlite,tag-catalog.sqlite,relation-overlay.sqlite,manifest.json}
├─ scripts/{build_catalog,search_catalog,verify_catalog,export_catalog,submit_relations}.py
└─ tests/
```

| 模块 | 负责 | 不负责 |
|---|---|---|
| `authoring.intent` | 解析意图、来源、锁定和未知 | 直接生成最终 prompt |
| `authoring.routing` | 选择路线和 Anima 变体策略 | 改变事实集合 |
| `authoring.positive` | 组织质量、meta、安全、视觉和关系片段 | 擅自添加未授权细节 |
| `authoring.negative` | 组织用户排除、场景缺陷和变体必需质量项 | 注入固定长 negative 表 |
| `catalog` | 存储、索引、命中、provenance 和 accepted 关系读取 | 改写用户 tag |
| `inspection` | 只读发现问题 | 修 prompt 或阻断输出 |
| `relation_submission` | 校验 LLM 提交的关系 JSON | 推断关系语义 |
| `output` | 序列化复制文本和元数据 | 把诊断混入 prompt |

## 6. PromptBrief 与来源

```text
PromptBrief
├─ facts[]
├─ exclusions[]
├─ locked_segments[]
├─ subjects[]
├─ relations[]
├─ scene, style, lighting, camera
├─ inferred[], unknowns[], notes[]
└─ source_priority
```

每条 `IntentFact` 至少保留：`value`、`kind`、`source`、`locked`、`confidence`、`user_text`、`subject_id`、`representation_hint`、`notes`。来源优先级为：

```text
user > local_model > official > community > default
```

Anima 变体质量项是 `official` profile fact；它们不是用户视觉事实，也不能覆盖用户明确排除。但它们必须进入 authoring contract，否则 PromptDraft 不满足模型协议。

## 7. VisualRelationGraph

节点：`subject`、`attribute`、`action`、`scene`、`style`、`lighting`、`camera`、`region`。边至少支持：

```text
subject --has_attribute--> attribute
subject --performs--> action
subject --located_at--> region
subject --interacts_with--> subject
subject --occludes--> subject
subject --faces--> subject
scene --contains--> subject
scene --uses_style/lighting/camera--> node
```

动作必须保留执行者，目标存在时保留目标；遮挡、左右、前后、远近和明确“不互动”必须可表达。缺失关系只产生 advisory；不得凭空补关系。

## 8. Routing、Authoring 与不可变草稿

路线只改变表达方式，不改变事实集合：

- `tag-led`：离散外观属性密集；
- `hybrid`：默认，tag 表达属性，prose 表达动作、关系、遮挡和场景；
- `natural-language-led`：复杂空间、叙事、因果和遮挡为主。

authoring 顺序建议为：

```text
Anima quality/meta/safety prefix
-> locked segments
-> subject and appearance
-> clothing and action
-> relation and scene
-> style, lighting, camera
```

顺序是组织策略，不是固定槽位。正向和负向作者独立运行；negative 由用户排除、场景必要缺陷和 Anima 变体强制质量项组成，不得注入隐藏长表。

`PromptPlan` 是 staging；`PromptDraft` 是不可变值。每个 `PromptSegment` 保留 channel、origin、representation、locked、fact/subject ID、Catalog hit、source、relation ID 和文本。最终文本必须由 segments 渲染，Inspector 只能读。

## 9. Tag Catalog

Catalog 分层为：

```text
Source -> Concept/Record -> Name/Alias -> Search projections
```

必须保留 source URI、license、snapshot、fetch time、checksum、raw schema、record/category/description/language/confidence、name type 和 provenance。查询模式：`exact`、`alias`、`prefix`、`category/facet`、`related`、`fuzzy`；auto 顺序为 exact canonical、exact alias、prefix、category/facet、accepted related、fuzzy。

`TagHit` 至少包含：`record_id`、`canonical_name`、`prompt_form`、`category`、`score`、`matched_name`、`match_type`、`aliases`、`source`、`source_version`、`facets`、`provenance`。

Anima 官方质量项必须有官方协议 provenance。alias 只能证明名称关系，不能证明 parent/child/related/cooccurrence。candidate 关系不得进入基础 Catalog 的 related 默认结果。

## 10. 关系维护协议

当前技能 LLM 在生成 PromptOutput 后自行判断是否需要建立关系；需要时只提交本次 Catalog 命中的 exact `record_id`，否则提交空关系数组。脚本不做语义分析，只校验：

- JSON schema、record ID 范围、节点存在性；
- `parent`、`child`、`related` 类型；
- confidence、rationale、evidence 非空；
- 重复、反向冲突、来源和模型字段；
- 禁止提交 `cooccurrence`。

合法 proposal 写入独立 overlay 的 `candidate` 状态；不自动 accepted。cooccurrence 只接受真实统计 provenance，不能由 LLM 凭空生成。关系失败只生成 issue，不阻断 prompt。

## 11. Inspector 与输出

Inspector 只读检查空 prompt、质量协议、权重、wildcard、trigger、正负冲突、多主体归属、锁定片段、重复和 token 估算，结果均为 info/warning/conflict advisory。

Anima 必须检查：

1. 正向含当前变体全部强制质量词；
2. Base 含 `score_7`，负向含三个低分 score；
3. Aesthetic/Turbo 未无请求加入 `score_*`；
4. 强制项来自 official exact/alias provenance；
5. 质量/meta/safety 位于正向前部；
6. 假设和缺失 provenance 被记录，未被静默修复。

机器输出固定为：

```json
{
  "positive": "...",
  "negative": "...",
  "notes": [],
  "assumptions": [],
  "advisories": []
}
```

人类输出固定为：

```text
POSITIVE:
...

NEGATIVE:
...
```

说明、ID、诊断和关系状态不得混入 positive/negative。

## 12. 验收不变量

### 保真

- 用户锁定片段、trigger、wildcard、weight 原样保留；
- 用户明确排除项不被移除；
- unknown、inferred、fuzzy 不被静默升级；
- route、模型 profile 和质量协议不改写视觉事实；
- positive/negative 独立；
- Inspector 不修改、不阻断、不把诊断混入 prompt。

### Anima 质量协议

- Plain `Anima` 默认 Base，并记录假设；
- Base 正向固定含 `masterpiece,best quality,score_7`，负向固定含 `worst quality,low quality,score_1,score_2,score_3`；
- Aesthetic/Turbo 正向固定含 `masterpiece,best quality`，负向固定含 `worst quality,low quality`；
- Aesthetic/Turbo 不自动出现 `score_*`；
- mandatory terms 均可回溯到官方 Catalog provenance；
- `highres`/`absurdres` 不被错误当作质量词。

### Catalog 与关系

- exact、alias、prefix、related、fuzzy 命中可解释；
- candidate 不进入默认 related；
- accepted 关系保留 source、model、rationale、evidence；
- 无真实统计 provenance 不生成 cooccurrence；
- 关系提交失败不影响 prompt。

## 13. 实施与切换

实施顺序：

1. 冻结本设计、Skill、references 和入口 metadata；
2. 验证 Catalog schema、官方 Anima 质量项和 manifest；
3. 验证 Brief、Graph、ModelProfile、quality seed、routing、authoring、Draft；
4. 验证 Inspector、输出和关系提交；
5. 执行端到端回归、链接扫描和 stale-reference 扫描；
6. 全部通过后只保留 `anima-prompt-v1` 新接口，删除旧兼容实现。

不提前建立兼容层，不保留旧 schema，不把文档完成声明当作生产证明。pytest 或工具依赖缺失时必须明确记录环境限制，并用可复现的 compile、smoke、Catalog verify 和静态检查补足证据。

## 14. 风险与处理

- 变体未知：按 Base，记录 assumption；
- 强制词无 Catalog provenance：不伪造证据，保留字面并发 advisory；
- 用户与 profile 质量项冲突：保留用户事实，报告协议冲突；
- fuzzy 误命中：只作候选，不自动替换；
- negative 冲突：优先用户排除，报告 profile 缺口；
- 关系污染：只接收本次 exact 命中 ID，candidate 与基础 Catalog 隔离；
- cooccurrence 滥用：只接受真实统计来源；
- 脚本失败：输出 issue，不阻断已生成的 prompt。

## 15. 冻结依据

- Anima 官方模型卡：质量词、score 词、tag 形式、tag 顺序和变体提示；
- 本技能的 `references/`：运行时契约、Catalog、authoring、inspection、evaluation；
- `anima_prompt_v1/`：typed domain、workflow、Catalog、inspection 和 relation submission 实现；
- `knowledge/manifest.json`：Catalog 构建与校验事实。
