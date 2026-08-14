# Anima Prompt v1 B+ 生产实施计划

> 本计划对应设计文档：`docs/superpowers/specs/2026-08-14-anima-prompt-v1-bplus-design.md`。
> 它描述当前唯一实现，不保留旧 `anima-prompt` / `prompt-forge` 兼容语义。

## 目标与边界

交付一条可验证的 Anima 提示词生产链：

```text
用户请求/变体 -> PromptBrief -> 必需质量词种子 -> Catalog 检索
-> VisualRelationGraph -> RouteDecision -> 独立正负向作者
-> PromptPlan -> 不可变 PromptDraft -> 只读 InspectionReport
-> PromptOutput -> LLM 决定关系 -> submit_relation_payload
```

- LLM 是语义作者：解析事实、补充明确标注的创意事实、判断是否值得建立关系。
- Python 运行时负责结构化、Catalog 检索、质量词注入、渲染、审计和关系提交校验。
- Catalog 主库只读；关系写入只进入独立 overlay，候选不自动晋升。
- 正负向提示词只包含可复制文本；来源、假设、关系和诊断进入机器字段。
- 不建立 provider 注入、旧入口、旧目录、通用模型 fallback 或向后兼容层。

## 当前实施状态

| 编号 | 任务 | 状态 | 验收证据 |
|---|---|---|---|
| R1 | Anima v1 运行时与质量词协议 | 已完成 | `anima_prompt_v1/authoring/routing.py`、`workflow.py`、`inspection/checks.py` |
| R2 | Catalog provenance 贯穿 Draft/Output | 已完成 | `draft.py`、`positive.py`、`output.py` |
| R3 | 质量词旧 opt-in/suggest/custom 语义清理 | 已完成 | `tests/test_routing.py`、`tests/test_authoring.py`、`tests/test_cleanroom.py` |
| R4 | 发布、安装、验证链路切换到 `anima-prompt-v1` | 已完成 | `scripts/stage_release.py`、`install.ps1`、`install.sh`、`verify_release.py` |
| R5 | 根插件元数据和活动文档路径统一 | 已完成 | `.codex-plugin/plugin.json`、README、USAGE、AGENTS |
| R6 | 删除旧 `skills/prompt-forge` | 待执行 | 删除后路径检查、目录清单检查 |
| R7 | 端到端回归与交付证据 | 进行中 | compileall、运行时 smoke、release verify、旧引用审计 |

## 设计不变量

### 1. 质量词是生产协议，不是建议

支持变体只有 `base`、`aesthetic`、`turbo`。未指定变体时使用 `base`，并在
`assumptions` 写入 `variant_unspecified: using Anima-Base default`。

| 变体 | positive 必须项 | negative 必须项 |
|---|---|---|
| base | `masterpiece`, `best quality`, `score_7` | `worst quality`, `low quality`, `score_1`, `score_2`, `score_3` |
| aesthetic | `masterpiece`, `best quality` | `worst quality`, `low quality` |
| turbo | `masterpiece`, `best quality` | `worst quality`, `low quality` |

所有必需项先成为 `official` typed facts，再通过 exact canonical/alias Catalog
命中冻结。缺少官方 provenance 必须产生 conflict advisory；不能用 fuzzy 命中冒充合规。
`safe` 是独立安全/meta 事实，不计入质量词；是否加入由 brief 的普通/敏感内容判定决定。

### 2. 关系建立发生在提示词完成之后

运行时不注入关系分析 provider。技能调用方（LLM）在 `PromptOutput` 完成后自行判断：

1. 没有稳定复用价值：提交空关系数组；
2. 有价值：只提交当前 exact Catalog record ID、`parent|child|related`、confidence、rationale、evidence；
3. 脚本只做 schema、record、证据和状态校验，把合法项写入 overlay 的 `candidate`；
4. `cooccurrence` 不能由本技能创建；候选不参与默认 `auto/related` 检索。

### 3. 检索与作者职责分离

`exact canonical -> exact alias -> prefix -> category/facet -> accepted related -> fuzzy`
是检索解释顺序。alias 只是名称映射，fuzzy 只是候选。作者保留用户原文、fact source、
matched text、match type、score 和完整 provenance，不静默改写用户事实。

## 生产文件边界

发布只包含运行所需文件：

- `skills/anima-prompt-v1/SKILL.md`、`agents/`、`references/`、`anima_prompt_v1/`；
- `knowledge/source/`、`manifest.json`、`tags.sqlite`、`tag-catalog.sqlite`；
- `prompt-core`、H3、camera 技能、`mcp_server` 及其活动文档/脚本；
- `.codex-plugin/plugin.json`。

发布器必须排除 `.venv`、`.codegraph`、`__pycache__`、pytest 缓存、测试 fixture、
备份文件和 `.superpowers` 工作记录。源码测试仍在源码树运行，不进入生产 release。

## 回归门禁

完成 R6 前后均执行：

```powershell
$py = 'C:\Users\11245\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m compileall -q skills/anima-prompt-v1/anima_prompt_v1
& $py scripts/verify_release.py --source-root .
& $py scripts/stage_release.py --source-root . --destination-root <temporary-release>
rg -n --hidden --glob '!*.sqlite' --glob '!*.pyc' 'skills/anima-prompt/|skills/prompt-forge/|anima_prompt\b' scripts docs README.md README.en.md AGENTS.md .codex-plugin mcp_server
```

运行时 smoke 必须证明：

- 默认 Anima 产生 base 全部 positive/negative 质量词；
- Aesthetic/Turbo 不产生 `score_*`，但仍产生各自必需词；
- 所有质量片段有官方 Catalog provenance；
- `notes` 保留 provenance，`assumptions` 保留未指定变体；
- inspection 无质量协议冲突；
- prompt 字段不含 ID、诊断或关系状态。

若本地环境没有 pytest，必须明确记录环境限制；不得用未执行测试的结论替代证据。

## 完成标准

- 活动文档、安装脚本、发布脚本、验证脚本均只引用 `anima-prompt-v1`；
- `skills/prompt-forge` 已删除且不存在 reparse/link 越界；
- `verify_release` 通过，stage 结果不含开发缓存、测试和旧副本；
- compileall 和可执行 runtime smoke 通过；
- 旧引用审计逐条区分活动引用与历史记录；
- 不执行 git commit/push，不修改外部 ComfyUI 工作流和用户数据。
