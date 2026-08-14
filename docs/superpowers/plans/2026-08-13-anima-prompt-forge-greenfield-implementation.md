# Anima Prompt Forge Greenfield Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零重写 Prompt Forge 的 Anima 方法论、确定性编译和 camera-image 交付接缝，以视觉意图遵循和最终图像质量为首要目标，彻底删除旧固定槽位、固定标签预算和单句桥接体系。

**Architecture:** LLM 通过精简 Skill 将用户意图形成 `VisualBrief`、选择 `tag | hybrid | natural_language` 路线并提交完整提示词块；一个深模块 `compile_anima_prompt(submission)` 在单一接缝后完成 profile 解析、词法验证、事实覆盖、主体绑定、render-context 校验、token 计数和制品签名。`camera-image` 只接受 Anima v2 BuildLog 引用，并在任何 GPU 操作前重建真实工作流上下文、比较 SHA-256 后注入提示词。

**Tech Stack:** Python 3.10+、标准库 dataclasses/json/hashlib/sqlite3/re、`tokenizers==0.22.2`、pytest 9、Markdown Skill references、JSON/JSONL benchmark fixtures、固定本地 ComfyUI 工作流和 stdio MCP。

**Spec:** `docs/superpowers/specs/2026-08-13-anima-prompt-forge-greenfield-design.md`

## Global Constraints

- 本计划只实现上述 Spec；此前的 Anima 分析、spec 和 plan 不作为实现依据。
- 采用破坏式重写：不保留旧 `AnimaAuthoringRequest`、`author_anima_prompt`、旧字段、转换器、别名、feature flag、双轨入口或迁移代码。
- Anima 新制品固定为 `artifact_version = 2`；H3 制品固定为 `artifact_version = 1`。
- `prompt-forge` 只创作和验证文本，不执行 ComfyUI、不发现工作流、不选择或安装 LoRA。
- LLM 负责审美、构图、场景和语言创作；代码只执行确定性验证、查询、计数、规范化、哈希和报告。
- 不设固定标签数量，不强制审美五层，不自动插入质量词，不自动压缩、删减或改写提示词。
- `camera-image` 的固定 release asset 仍是唯一生产工作流；不得改成运行时搜索工作流。
- 保持 `MiniMax-H3` 的提示词语义和运行行为不变；所有 H3 测试必须通过。
- Python 运行命令统一使用：`C:\Users\11245\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。
- 修改真实关键文件前，按 Task 0 创建 TEMP 精确备份并记录 SHA-256；备份不是兼容层，不进入仓库。
- 使用 `apply_patch` 修改源码和文档；格式化器或官方生成器可直接运行。
- 工作树中现有 `.claude/`、`skills/.claude/`、`skills/prompt-forge/.claude/` 属于用户，不读取、不修改、不暂存。
- 未获用户明确授权时不执行 commit；每个 Task 的 commit 步骤保留为授权后的检查点，未授权则在进度表记录 `commit: not authorized`。
- 修改技能源后必须运行 `powershell -ExecutionPolicy Bypass -File scripts\install.ps1`，再验证源码与插件缓存 SHA-256 一致。
- 离线测试全绿只证明协议正确；第 19 节图像盲评门槛通过后才能声明“质量重写完成”。

---

## 1. Locked File Structure

### 1.1 Create

| Path | Single responsibility |
|---|---|
| `skills/prompt-forge/prompt_forge/anima/contracts.py` | Anima v2 的视觉意图、提示词块和运行上下文不可变类型 |
| `skills/prompt-forge/prompt_forge/anima/profiles.py` | 加载模型 profile、规范化 render context、计算 context SHA-256 |
| `skills/prompt-forge/prompt_forge/anima/tag_parser.py` | 拆分标签块、解析权重、形成确定性语义形式 |
| `skills/prompt-forge/prompt_forge/anima/validation.py` | Visual Brief、route、绑定、安全和模型协议 hard gate |
| `skills/prompt-forge/prompt_forge/anima/rendering.py` | 按 LLM 原始 block 顺序形成 positive/negative 节点文本 |
| `skills/prompt-forge/prompt_forge/anima/compiler.py` | 唯一深模块 interface：`compile_anima_prompt` |
| `skills/prompt-forge/prompt_forge/anima/report.py` | 结构化 finding、claim coverage 和审计序列化 |
| `skills/prompt-forge/knowledge/anima/model-profiles.json` | Base/Aesthetic/Turbo 的受控确定性规则 |
| `skills/prompt-forge/references/anima/visual-brief.md` | 从用户意图构建 claims 和 subjects |
| `skills/prompt-forge/references/anima/route-selection.md` | 三条 route 的选择和升级条件 |
| `skills/prompt-forge/references/anima/model-profiles.md` | 模型版本的人类可读策略 |
| `skills/prompt-forge/references/anima/multi-subject-spatial.md` | 多主体绑定、坐标系和关系语言 |
| `skills/prompt-forge/references/anima/negative-and-weights.md` | 精简 negative 与单变量权重实验 |
| `skills/prompt-forge/references/anima/failure-recovery.md` | 按失败类型做最小改写或升级工具 |
| `skills/prompt-forge/references/anima/examples.md` | 安全的 Tag/Hybrid/NL 完整示例 |
| `skills/prompt-forge/references/anima/evaluation.md` | 低成本固定 seed 盲评方法 |
| `skills/prompt-forge/references/artifact-delivery.md` | BuildLog 和 camera render-context 交付契约 |
| `skills/camera-image/camera_image/runtime/prompt_context.py` | 从真实 camera 配置构建 Anima render context |
| `skills/prompt-forge/scripts/anima_tag_lookup.py` | 只读词典查询 CLI |
| `skills/prompt-forge/scripts/build_anima_eval_manifest.py` | 将候选制品与固定 seeds 展开为渲染清单 |
| `skills/prompt-forge/scripts/score_anima_eval.py` | 校验盲评并计算门槛指标 |
| `skills/prompt-forge/benchmarks/anima/briefs.jsonl` | 六个固定图像质量 brief |
| `skills/prompt-forge/benchmarks/anima/candidates.schema.json` | 候选制品记录 schema |
| `skills/prompt-forge/benchmarks/anima/ratings.schema.json` | 盲评输入 schema |
| `skills/prompt-forge/benchmarks/anima/README.md` | 只描述评测运行契约和成本上限 |

### 1.2 Rewrite or modify

| Path | Required change |
|---|---|
| `skills/prompt-forge/SKILL.md` | 改成方法论核心和一层 references 路由，少于 500 行 |
| `skills/prompt-forge/agents/openai.yaml` | 重新生成可读元数据 |
| `skills/prompt-forge/prompt_forge/__init__.py` | 公共 Anima symbol 改为 `compile_anima_prompt` |
| `skills/prompt-forge/prompt_forge/contracts.py` | 只保留共享 Fact/H3 类型，移除旧 Anima 类型 |
| `skills/prompt-forge/prompt_forge/artifacts.py` | 构造函数显式接收 artifact version，并允许 Anima claims |
| `skills/prompt-forge/prompt_forge/budgets.py` | 删除 Anima 预算，仅保留 H3 |
| `skills/prompt-forge/prompt_forge/compression.py` | 删除 Anima structure，仅保留 H3 |
| `skills/prompt-forge/prompt_forge/anima/dictionary.py` | 保留只读 SQLite 能力，改为新 parser/report 类型 |
| `skills/prompt-forge/prompt_forge/h3/t2va.py` | 显式写入 artifact version 1 |
| `skills/prompt-forge/prompt_forge/h3/ref2va.py` | 显式写入 artifact version 1 |
| `skills/prompt-forge/knowledge/anima/protocol.json` | 只保存词法命名空间、权重防御范围和 rating 映射 |
| `skills/prompt-forge/knowledge/anima/manifest.json` | 记录新 profile/protocol/hash |
| `skills/prompt-forge/knowledge/anima/sources.lock.json` | 记录官方资料与许可，不记录社区点赞为硬规则 |
| `mcp_server/src/comfyui_chenxin_mcp/server.py` | JSON → `AnimaPromptSubmission` 强类型构造 |
| `mcp_server/src/comfyui_chenxin_mcp/engine/prompt_forge.py` | Anima v2 author dispatch 和制品门禁 |
| `mcp_server/src/comfyui_chenxin_mcp/engine/build_log.py` | v2 metadata 与嵌套 token report 摘要 |
| `mcp_server/src/comfyui_chenxin_mcp/engine/execute.py` | gate 结果写回内部 RunConfig 后再准备工作流 |
| `skills/camera-image/camera_image/skill_data.py` | 只接受 prompt_ref，并比较实际 render context |
| `skills/camera-image/camera_image/runtime/config_schema.py` | envelope 只接受 prompt_ref；prompt 变为内部字段 |
| `skills/camera-image/camera_image/runtime/graph_patcher.py` | 删除重复制品解析，只消费 gate 后的内部 prompt |
| `skills/camera-image/camera_image/runtime/lora_resolver.py` | 精确名称解析并暴露实际 trigger terms |
| `skills/camera-image/camera_image/runtime/__init__.py` | 导出新 prompt-context helper，移除失效导出 |
| `skills/camera-image/camera_image/runtime/profiles/camera-anima.json` | profile id 升级为 `camera-anima-v2` 并声明模型上下文 |
| `skills/prompt-forge/scripts/verify_release.py` | 新文件集、版本和禁止旧体系的 release gate |
| `skills/prompt-forge/scripts/stage_release.py` | 确保新 references/benchmarks 被显式打包 |
| `skills/prompt-forge/scripts/run_benchmarks.py` | 删除旧 Anima segment runner，保留 H3 runner |
| `skills/prompt-forge/scripts/build_benchmark_corpus.py` | 删除旧 Anima corpus builder，保留 H3 builder |
| `scripts/install.ps1` / `scripts/install.sh` | 新必需文件和 0.3.0 release 验证 |
| `.codex-plugin/plugin.json` | 版本与产品说明升级到 0.3.0 |
| 全部 5 个 `pyproject.toml` | 项目版本统一为 0.3.0 |
| `docs/USAGE.md`、`docs/architecture.md`、`docs/camera-image-flow.md`、`docs/TROUBLESHOOTING.md` | 新 submission、v2 BuildLog 和只收 prompt_ref 的真实流程 |

### 1.3 Delete

```text
skills/prompt-forge/prompt_forge/anima/author.py
skills/prompt-forge/prompt_forge/anima/audit.py
skills/prompt-forge/prompt_forge/anima/protocol.py
skills/prompt-forge/knowledge/anima/budget-policy.json
skills/prompt-forge/references/dialects/anima/dialect.md
skills/prompt-forge/references/dialects/anima/vocabulary/README.md
skills/prompt-forge/references/dialects/anima/vocabulary/count-identity.md
skills/prompt-forge/references/dialects/anima/vocabulary/appearance.md
skills/prompt-forge/references/dialects/anima/vocabulary/clothing.md
skills/prompt-forge/references/dialects/anima/vocabulary/pose-action.md
skills/prompt-forge/references/dialects/anima/vocabulary/expression.md
skills/prompt-forge/references/dialects/anima/vocabulary/camera-shot.md
skills/prompt-forge/references/dialects/anima/vocabulary/scene-environment.md
skills/prompt-forge/references/dialects/anima/vocabulary/detail-mood.md
skills/prompt-forge/references/dialects/anima/vocabulary/special-themes.md
skills/prompt-forge/references/dialects/anima/recipes/cyberpunk-neon.md
skills/prompt-forge/references/dialects/anima/recipes/film-noir.md
skills/prompt-forge/references/dialects/anima/recipes/ghibli-aesthetic.md
skills/prompt-forge/references/dialects/anima/recipes/helmut-newton-bw.md
skills/prompt-forge/references/dialects/anima/recipes/wes-anderson-pastel.md
skills/prompt-forge/references/dialects/anima/recipes/wuxia-ink.md
skills/prompt-forge/references/shared/authoring-contract.md
skills/prompt-forge/references/shared/method.md
skills/prompt-forge/references/shared/aesthetic-coverage.md
skills/prompt-forge/references/shared/decision-tree.md
skills/prompt-forge/references/shared/self-check.md
skills/prompt-forge/references/shared/output-protocol.md
skills/prompt-forge/references/shared/natural-language.md
skills/prompt-forge/references/quality/conflict-table.md
skills/prompt-forge/references/quality/tag-count-ruler.md
skills/prompt-forge/references/quality/style-consistency.md
skills/prompt-forge/references/quality/budget-ruler.md
skills/prompt-forge/references/quality/audit-and-recovery.md
skills/prompt-forge/references/quality/dictionary-preflight.md
skills/prompt-forge/knowledge/aesthetics/anti-patterns.md
skills/prompt-forge/knowledge/aesthetics/camera.md
skills/prompt-forge/knowledge/aesthetics/composition.md
skills/prompt-forge/knowledge/aesthetics/lighting.md
skills/prompt-forge/knowledge/aesthetics/manifest.json
skills/prompt-forge/knowledge/aesthetics/mood-texture.md
skills/prompt-forge/knowledge/aesthetics/palette.md
skills/prompt-forge/knowledge/aesthetics/sources.lock.json
skills/prompt-forge/knowledge/aesthetics/style-signatures.md
skills/prompt-forge/scripts/preflight.py
skills/prompt-forge/scripts/tag_validate.py
skills/prompt-forge/benchmarks/cases/anima.jsonl
skills/prompt-forge/tests/test_anima_author.py
skills/prompt-forge/tests/test_preflight.py
```

## 2. Interface Ledger

后续任务只能使用这里登记的 interface 名称；如需改变，先修改 Spec 和本表，再继续代码。

```python
# prompt_forge public surface
def compile_anima_prompt(submission: AnimaPromptSubmission) -> PromptArtifact: ...
def author_h3_t2va_prompt(request: H3T2VAAuthoringRequest) -> PromptArtifact: ...
def author_h3_ref2va_prompt(request: H3Ref2VAAuthoringRequest) -> PromptArtifact: ...

# anima internal seams
def load_model_profile(profile_id: ModelProfileId) -> ModelProfile: ...
def render_context_payload(context: AnimaRenderContext) -> dict[str, object]: ...
def render_context_sha256(context: AnimaRenderContext) -> str: ...
def split_tag_block(text: str) -> tuple[str, ...]: ...
def parse_tag(raw: str) -> ParsedTag: ...
def validate_submission(submission: AnimaPromptSubmission, profile: ModelProfile) -> ValidationReport: ...
def validate_prompt_protocol(submission: AnimaPromptSubmission, profile: ModelProfile, dictionary: AnimaTagDictionary) -> ValidationReport: ...
def render_submission(submission: AnimaPromptSubmission) -> RenderedPrompt: ...

# MCP/camera seam
def validate_prompt_artifact(ref_id: str, *, expected_task: str, expected_render_context: dict[str, object] | None = None, expected_reference_count: int | None = None, expected_duration: float | None = None) -> dict[str, str]: ...
def build_anima_render_context(lora: dict | None) -> dict[str, object]: ...
```

## 3. Progress Record

执行者必须在每个 Task 完成后更新本表；`Evidence` 写测试命令和结果摘要，`Commit` 写 hash 或 `not authorized`。

| ID | Deliverable | Status | Evidence | Commit |
|---:|---|---|---|---|
| 0 | 基线、精确备份和环境证据 | not_started | — | n/a |
| 1 | Anima v2 领域契约与显式 artifact version | not_started | — | — |
| 2 | 模型 profile 与 render-context hash | not_started | — | — |
| 3 | 标签解析和只读词典接缝 | not_started | — | — |
| 4 | Visual Brief、route、绑定和安全门禁 | not_started | — | — |
| 5 | 模型协议、effective prompt 和 warning 审计 | not_started | — | — |
| 6 | 顺序保持渲染器与 `compile_anima_prompt` | not_started | — | — |
| 7 | MCP JSON coercion、BuildLog v2 和公共 surface | not_started | — | — |
| 8 | camera-image prompt_ref-only 与 context gate | not_started | — | — |
| 9 | 方法论 Skill 与渐进式 references | not_started | — | — |
| 10 | 词典 CLI、固定 brief 和盲评工具 | not_started | — | — |
| 11 | 删除旧体系、版本升级与 release gate | not_started | — | — |
| 12 | 全量离线验证、diff 审查和 CodeGraph 同步 | not_started | — | — |
| 13 | 插件缓存同步和低成本图像盲评 | not_started | — | — |

允许的状态只有：`not_started`、`in_progress`、`blocked`、`complete`。同一时刻只能有一个 `in_progress`。

---

### Task 0: Capture Baseline and Recoverable Backups

**Files:**
- Modify during execution tracking only: `docs/superpowers/plans/2026-08-13-anima-prompt-forge-greenfield-implementation.md`
- Backup outside repository: `%TEMP%\comfyui-chenxin-anima-greenfield-20260813\`

**Interfaces:**
- Consumes: current Git worktree, current CodeGraph index, bundled Python path.
- Produces: baseline test log, precise SHA-256 ledger, recoverable copies of critical files.

- [ ] **Step 1: Mark Task 0 in progress**

Use `apply_patch` to set row 0 to `in_progress`. Do not change any other row.

- [ ] **Step 2: Verify exact repository and user-owned changes**

Run:

```powershell
git rev-parse --show-toplevel
git status --short
codegraph.cmd status
```

Expected: repository root is `D:\Projects\comfyui-chenxin`; CodeGraph reports up to date; only the three pre-existing `.claude` paths plus this turn's two new docs may appear.

- [ ] **Step 3: Create the exact TEMP backup root and verify its boundary**

Run:

```powershell
$backupRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'comfyui-chenxin-anima-greenfield-20260813'
$resolvedTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$resolvedBackup = [System.IO.Path]::GetFullPath($backupRoot)
if (-not $resolvedBackup.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Backup target escaped TEMP' }
New-Item -ItemType Directory -Path $resolvedBackup -Force | Out-Null
$resolvedBackup
```

Expected: printed path is inside the current Windows TEMP directory.

- [ ] **Step 4: Copy critical files without broad directory recursion**

Run:

```powershell
$repo = 'D:\Projects\comfyui-chenxin'
$backupRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'comfyui-chenxin-anima-greenfield-20260813'
$critical = @(
  'skills\prompt-forge\SKILL.md',
  'skills\prompt-forge\prompt_forge\contracts.py',
  'skills\prompt-forge\prompt_forge\artifacts.py',
  'skills\prompt-forge\prompt_forge\budgets.py',
  'skills\prompt-forge\prompt_forge\compression.py',
  'skills\prompt-forge\prompt_forge\anima\author.py',
  'mcp_server\src\comfyui_chenxin_mcp\server.py',
  'mcp_server\src\comfyui_chenxin_mcp\engine\prompt_forge.py',
  'skills\camera-image\camera_image\skill_data.py',
  'skills\camera-image\camera_image\runtime\config_schema.py',
  'skills\camera-image\camera_image\runtime\graph_patcher.py',
  'skills\camera-image\camera_image\runtime\lora_resolver.py',
  '.codex-plugin\plugin.json',
  'scripts\install.ps1'
)
$ledger = foreach ($relative in $critical) {
  $source = Join-Path $repo $relative
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing critical file: $relative" }
  $destination = Join-Path $backupRoot $relative
  New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
  Copy-Item -LiteralPath $source -Destination $destination
  [pscustomobject]@{ Path = $relative; SHA256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash }
}
$ledger | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backupRoot 'sha256-ledger.json') -Encoding utf8
```

Expected: 14 copied files and one `sha256-ledger.json`; no repository file changes.

- [ ] **Step 5: Run the complete pre-change offline suite**

Run:

```powershell
$py = 'C:\Users\11245\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m pytest skills/prompt-forge/tests mcp_server/tests skills/camera-image/tests -q
```

Expected: PASS. If it fails, record exact pre-existing failures in row 0 and stop before source edits.

- [ ] **Step 6: Mark Task 0 complete**

Record the pytest summary, backup root and SHA ledger path in row 0.

---

### Task 1: Define Anima v2 Contracts and Explicit Artifact Versions

**Files:**
- Create: `skills/prompt-forge/prompt_forge/anima/contracts.py`
- Create: `skills/prompt-forge/tests/test_anima_contracts_v2.py`
- Modify: `skills/prompt-forge/prompt_forge/artifacts.py`
- Modify: `skills/prompt-forge/prompt_forge/h3/t2va.py`
- Modify: `skills/prompt-forge/prompt_forge/h3/ref2va.py`
- Modify: `skills/prompt-forge/tests/test_artifacts.py`

**Interfaces:**
- Consumes: shared `PromptArtifact` hashing behavior.
- Produces: every dataclass in Spec §7.1; `create_prompt_artifact(..., artifact_version: int)`.

- [ ] **Step 1: Write the failing contract shape tests**

Add these assertions to `test_anima_contracts_v2.py`:

```python
from dataclasses import FrozenInstanceError, fields

import pytest

from prompt_forge.anima.contracts import (
    AnimaPromptSubmission,
    AnimaRenderContext,
    IntentClaim,
    PromptBlock,
    StyleAdapter,
    SubjectBrief,
    VisualBrief,
)


def test_submission_contract_has_only_greenfield_fields() -> None:
    assert [field.name for field in fields(AnimaPromptSubmission)] == [
        "route", "brief", "render_context", "positive_blocks", "negative_blocks"
    ]
    assert [field.name for field in fields(VisualBrief)] == [
        "subjects", "claims", "content_rating", "consensual",
        "coordinate_frame", "control_needs",
    ]
    assert [field.name for field in fields(PromptBlock)] == [
        "block_id", "role", "form", "text", "claim_ids", "owner_ids"
    ]


def test_anima_contracts_are_frozen() -> None:
    claim = IntentClaim("c1", "blue hair", "appearance", ("s1",), "user_explicit", True)
    with pytest.raises(FrozenInstanceError):
        claim.text = "red hair"  # type: ignore[misc]


def test_render_context_records_exact_adapter_order() -> None:
    first = StyleAdapter("style-a", 1.0, 1.0, ("@style-a",))
    second = StyleAdapter("style-b", 0.7, 0.6, ())
    context = AnimaRenderContext("anima-base-v1", "camera-anima-v2", (first, second))
    assert tuple(item.model_name for item in context.style_adapters) == ("style-a", "style-b")
```

- [ ] **Step 2: Write the failing explicit artifact-version test**

In `test_artifacts.py`, add:

```python
def test_artifact_version_is_explicit_and_hashed() -> None:
    first = create_prompt_artifact(
        artifact_version=1,
        status="production_ready",
        task="anima",
        model="circlestone-labs/Anima",
        prompt={"positive": "1girl", "negative": ""},
        facts=(), trace={}, token_report={}, audit={}, compression=(),
        conflict=None, token_count_verified=True,
        knowledge_manifest_sha256="a" * 64,
    )
    second = create_prompt_artifact(
        artifact_version=2,
        status="production_ready",
        task="anima",
        model="circlestone-labs/Anima",
        prompt={"positive": "1girl", "negative": ""},
        facts=(), trace={}, token_report={}, audit={}, compression=(),
        conflict=None, token_count_verified=True,
        knowledge_manifest_sha256="a" * 64,
    )
    assert first.artifact_version == 1
    assert second.artifact_version == 2
    assert first.artifact_sha256 != second.artifact_sha256
```

- [ ] **Step 3: Run the focused tests and confirm the expected failures**

Run:

```powershell
$py = 'C:\Users\11245\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m pytest skills/prompt-forge/tests/test_anima_contracts_v2.py skills/prompt-forge/tests/test_artifacts.py -q
```

Expected: collection fails because `prompt_forge.anima.contracts` does not exist, and the artifact constructor rejects `artifact_version`.

- [ ] **Step 4: Implement the exact Spec §7.1 dataclasses**

Create `contracts.py` with `from __future__ import annotations`, the ten Literal aliases and seven frozen dataclasses exactly named in Spec §7.1. Use tuple defaults, never mutable list or dict defaults.

- [ ] **Step 5: Make artifact version an explicit required constructor argument**

Change `create_prompt_artifact` so its first keyword-only argument is `artifact_version: int`, reject booleans/non-positive integers, place the value in the hash base, and construct `PromptArtifact` from that value:

```python
if isinstance(artifact_version, bool) or not isinstance(artifact_version, int) or artifact_version <= 0:
    raise ValueError("artifact_version must be a positive integer")
```

Change `PromptArtifact.facts` and `create_prompt_artifact(... facts=...)` to `tuple[Any, ...]`; this lets H3 store `Fact` and Anima v2 store `IntentClaim` without a fake adapter type.

- [ ] **Step 6: Pin both H3 authors to version 1**

Add `artifact_version=1` to the two H3 `create_prompt_artifact` calls. Do not change any other H3 field or behavior.

- [ ] **Step 7: Run focused and H3 regression tests**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_contracts_v2.py skills/prompt-forge/tests/test_artifacts.py skills/prompt-forge/tests/test_h3_t2va.py skills/prompt-forge/tests/test_h3_ref2va.py -q
```

Expected: PASS.

- [ ] **Step 8: Record evidence and checkpoint**

Update row 1. If commits are authorized:

```powershell
git add skills/prompt-forge/prompt_forge/anima/contracts.py skills/prompt-forge/prompt_forge/artifacts.py skills/prompt-forge/prompt_forge/h3/t2va.py skills/prompt-forge/prompt_forge/h3/ref2va.py skills/prompt-forge/tests/test_anima_contracts_v2.py skills/prompt-forge/tests/test_artifacts.py
git commit -m "feat: define Anima v2 authoring contracts"
```

---

### Task 2: Implement Model Profiles and Render-Context Hashing

**Files:**
- Create: `skills/prompt-forge/knowledge/anima/model-profiles.json`
- Create: `skills/prompt-forge/prompt_forge/anima/profiles.py`
- Create: `skills/prompt-forge/tests/test_anima_profiles.py`
- Modify: `skills/prompt-forge/knowledge/anima/protocol.json`

**Interfaces:**
- Consumes: `ModelProfileId`, `AnimaRenderContext`.
- Produces: `ModelProfile`, `load_model_profile`, `render_context_payload`, `render_context_sha256`.

- [ ] **Step 1: Write failing profile and hash tests**

```python
from prompt_forge.anima.contracts import AnimaRenderContext, StyleAdapter
from prompt_forge.anima.profiles import (
    load_model_profile,
    render_context_payload,
    render_context_sha256,
)


def test_profiles_encode_variant_differences() -> None:
    base = load_model_profile("anima-base-v1")
    aesthetic = load_model_profile("anima-aesthetic-v1")
    turbo = load_model_profile("anima-turbo-v1")
    assert base.score_tags == "allowed"
    assert aesthetic.score_tags == "forbidden"
    assert turbo.score_tags == "allowed"
    assert set(base.routes) == {"tag", "hybrid", "natural_language"}
    assert base.physical_token_limit == 32768


def test_render_context_hash_is_canonical_but_order_sensitive() -> None:
    a = StyleAdapter("a", 1.0, 1.0, ("alpha",))
    b = StyleAdapter("b", 1.0, 1.0, ("beta",))
    left = AnimaRenderContext("anima-base-v1", "camera-anima-v2", (a, b), ("alpha", "beta"))
    right = AnimaRenderContext("anima-base-v1", "camera-anima-v2", (b, a), ("beta", "alpha"))
    assert render_context_payload(left)["style_adapters"][0]["model_name"] == "a"
    assert len(render_context_sha256(left)) == 64
    assert render_context_sha256(left) != render_context_sha256(right)
```

- [ ] **Step 2: Run and confirm missing-module failure**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_profiles.py -q
```

Expected: FAIL because `prompt_forge.anima.profiles` does not exist.

- [ ] **Step 3: Write the complete model profile data**

Use this top-level shape in `model-profiles.json`:

```json
{
  "schema_version": "1.0",
  "profiles": [
    {
      "profile_id": "anima-base-v1",
      "model": "circlestone-labs/Anima",
      "routes": ["tag", "hybrid", "natural_language"],
      "score_tags": "allowed",
      "suggested_positive": ["masterpiece", "best quality", "score_7", "safe"],
      "suggested_negative": ["worst quality", "low quality", "score_1", "score_2", "score_3", "artist name", "blurry", "jpeg artifacts", "chromatic aberration"],
      "physical_token_limit": 32768
    },
    {
      "profile_id": "anima-aesthetic-v1",
      "model": "circlestone-labs/Anima",
      "routes": ["tag", "hybrid", "natural_language"],
      "score_tags": "forbidden",
      "suggested_positive": ["masterpiece", "best quality", "safe"],
      "suggested_negative": ["worst quality", "low quality", "artist name", "blurry", "jpeg artifacts", "chromatic aberration"],
      "physical_token_limit": 32768
    },
    {
      "profile_id": "anima-turbo-v1",
      "model": "circlestone-labs/Anima",
      "routes": ["tag", "hybrid", "natural_language"],
      "score_tags": "allowed",
      "suggested_positive": ["masterpiece", "best quality", "score_7", "safe"],
      "suggested_negative": ["worst quality", "low quality", "score_1", "score_2", "score_3", "artist name", "blurry", "jpeg artifacts", "chromatic aberration"],
      "physical_token_limit": 32768
    }
  ]
}
```

- [ ] **Step 4: Rewrite deterministic protocol data**

Keep only lexical facts in `protocol.json`: ordinary tag form, score namespace, artist prefix, year pattern, weight min/max `0.01/10.0`, and rating-to-tag mapping. Remove tag-order and slot-allocation claims.

- [ ] **Step 5: Implement strict profile loading and canonical hashing**

`profiles.py` must:

- define frozen `ModelProfile(profile_id, model, routes, score_tags, suggested_positive, suggested_negative, physical_token_limit)`;
- validate exact top-level and profile keys, unique IDs and `schema_version == "1.0"`;
- preserve adapter/injection order;
- serialize with `json.dumps(... ensure_ascii=False, sort_keys=True, separators=(",", ":"))`;
- hash UTF-8 bytes with SHA-256;
- reject non-finite adapter strengths using `math.isfinite`.

- [ ] **Step 6: Run profile tests**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_profiles.py -q
```

Expected: PASS.

- [ ] **Step 7: Record evidence and checkpoint**

If authorized:

```powershell
git add skills/prompt-forge/knowledge/anima/model-profiles.json skills/prompt-forge/knowledge/anima/protocol.json skills/prompt-forge/prompt_forge/anima/profiles.py skills/prompt-forge/tests/test_anima_profiles.py
git commit -m "feat: add Anima model profiles and render context"
```

---

### Task 3: Replace Tag Parsing and Dictionary Integration

**Files:**
- Create: `skills/prompt-forge/prompt_forge/anima/tag_parser.py`
- Rewrite: `skills/prompt-forge/prompt_forge/anima/dictionary.py`
- Rewrite: `skills/prompt-forge/tests/test_anima_dictionary.py`
- Create: `skills/prompt-forge/tests/test_anima_tag_parser.py`

**Interfaces:**
- Consumes: tag block strings and bundled `tags.sqlite`.
- Produces: `ParsedTag`, `TagSyntaxError`, `split_tag_block`, `parse_tag`, exact `AnimaTagDictionary.resolve_many`.

- [ ] **Step 1: Write failing parser tests**

```python
import math
import pytest

from prompt_forge.anima.tag_parser import TagSyntaxError, parse_tag, split_tag_block


def test_split_and_parse_weighted_tags() -> None:
    assert split_tag_block("1girl, blue hair, (@kantoku:2.5)") == (
        "1girl", "blue hair", "(@kantoku:2.5)"
    )
    parsed = parse_tag("(@kantoku:2.5)")
    assert parsed.term == "@kantoku"
    assert parsed.semantic == "kantoku"
    assert parsed.weight == 2.5


@pytest.mark.parametrize("raw", ["(smile:nan)", "(smile:inf)", "(smile:0)", "(smile:10.1)"])
def test_invalid_weight_is_rejected(raw: str) -> None:
    with pytest.raises(TagSyntaxError, match="invalid_weight"):
        parse_tag(raw)


def test_empty_tag_member_is_rejected() -> None:
    with pytest.raises(TagSyntaxError, match="invalid_tag_syntax"):
        split_tag_block("1girl,,smile")
```

- [ ] **Step 2: Write failing exact dictionary tests**

```python
from prompt_forge.anima.dictionary import AnimaTagDictionary


def test_dictionary_resolves_exact_space_form_and_score_form() -> None:
    dictionary = AnimaTagDictionary()
    results = dictionary.resolve_many(("best quality", "score_7"))
    assert results[0] is not None and results[0].canonical == "best_quality"
    assert results[1] is not None and results[1].canonical == "score_7"


def test_dictionary_does_not_use_concept_scan_for_resolve() -> None:
    dictionary = AnimaTagDictionary()
    assert dictionary.resolve("words that merely resemble a tag") is None
```

- [ ] **Step 3: Run and confirm parser import failure**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_tag_parser.py skills/prompt-forge/tests/test_anima_dictionary.py -q
```

Expected: FAIL because `tag_parser.py` is missing.

- [ ] **Step 4: Implement the complete parser**

Define:

```python
@dataclass(frozen=True)
class ParsedTag:
    raw: str
    term: str
    semantic: str
    weight: float | None


class TagSyntaxError(ValueError):
    def __init__(self, code: str, raw: str) -> None:
        self.code = code
        self.raw = raw
        super().__init__(f"{code}: {raw}")
```

Use a full-string weighted regex, finite-number check and the Spec range. `semantic` removes a leading `@`, converts underscores to spaces and collapses whitespace. `split_tag_block` only splits commas and rejects empty members; quoted prose never enters this function.

- [ ] **Step 5: Rewrite dictionary.py behind the exact lookup seam**

Retain read-only immutable SQLite URI, bounded cache and exact canonical/form/alias resolution. Keep `lookup()` for the CLI, but `resolve()` and `resolve_many()` must never fall back to LIKE/concept search. The new dictionary module imports only `parse_tag(...).term` for deweighting.

- [ ] **Step 6: Run parser and dictionary tests**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_tag_parser.py skills/prompt-forge/tests/test_anima_dictionary.py -q
```

Expected: PASS.

- [ ] **Step 7: Record evidence and checkpoint**

If authorized:

```powershell
git add skills/prompt-forge/prompt_forge/anima/tag_parser.py skills/prompt-forge/prompt_forge/anima/dictionary.py skills/prompt-forge/tests/test_anima_tag_parser.py skills/prompt-forge/tests/test_anima_dictionary.py
git commit -m "feat: implement deterministic Anima tag parsing"
```

---

### Task 4: Validate Visual Briefs, Routes, Bindings, Controls, and Safety

**Files:**
- Create: `skills/prompt-forge/prompt_forge/anima/report.py`
- Create: `skills/prompt-forge/prompt_forge/anima/validation.py`
- Create: `skills/prompt-forge/tests/test_anima_submission_validation.py`

**Interfaces:**
- Consumes: `AnimaPromptSubmission`, `ModelProfile`.
- Produces: `Finding`, `ValidationReport`, `validate_submission`.

- [ ] **Step 1: Write a shared valid-submission fixture in the test file**

The fixture must construct one adult subject, required count/appearance claims, a Base render context, one tag block and no negative block. Keep it inside `test_anima_submission_validation.py` so production code never depends on test builders.

- [ ] **Step 2: Write failing route, coverage and binding tests**

```python
def test_hybrid_requires_both_block_forms(valid_submission) -> None:
    broken = replace(valid_submission, route="hybrid")
    report = validate_submission(broken, load_model_profile("anima-base-v1"))
    assert "route_shape_mismatch" in report.hard_codes


def test_required_claim_must_be_covered_by_the_correct_stream(valid_submission) -> None:
    broken = replace(valid_submission, positive_blocks=())
    report = validate_submission(broken, load_model_profile("anima-base-v1"))
    assert "required_claim_uncovered" in report.hard_codes


def test_subject_block_cannot_claim_another_subject_attribute(two_subject_submission) -> None:
    report = validate_submission(two_subject_submission, load_model_profile("anima-base-v1"))
    assert "owner_binding_missing" in report.hard_codes
```

- [ ] **Step 3: Write failing relation, coordinate and control tests**

```python
def test_relation_claim_requires_prose_and_two_owners(relation_as_tag_submission) -> None:
    report = validate_submission(relation_as_tag_submission, load_model_profile("anima-base-v1"))
    assert "relation_requires_prose" in report.hard_codes


def test_multisubject_spatial_claim_requires_coordinate_frame(spatial_submission) -> None:
    report = validate_submission(spatial_submission, load_model_profile("anima-base-v1"))
    assert "coordinate_frame_missing" in report.hard_codes


def test_unavailable_external_control_is_blocking(control_submission) -> None:
    report = validate_submission(control_submission, load_model_profile("anima-base-v1"))
    assert "unsupported_control_need" in report.hard_codes
```

- [ ] **Step 4: Write failing structured safety tests**

```python
@pytest.mark.parametrize("age_class", ["minor", "unknown"])
def test_sexual_content_requires_known_adults(explicit_submission, age_class: str) -> None:
    subject = replace(explicit_submission.brief.subjects[0], age_class=age_class)
    brief = replace(explicit_submission.brief, subjects=(subject,))
    report = validate_submission(replace(explicit_submission, brief=brief), load_model_profile("anima-base-v1"))
    assert "sexual_minor_or_unknown_age" in report.hard_codes


def test_multisubject_explicit_content_requires_affirmative_consent(explicit_pair_submission) -> None:
    report = validate_submission(explicit_pair_submission, load_model_profile("anima-base-v1"))
    assert "nonconsensual_explicit_content" in report.hard_codes
```

- [ ] **Step 5: Run and confirm missing validation module**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_submission_validation.py -q
```

Expected: FAIL because `report.py` and `validation.py` do not exist.

- [ ] **Step 6: Implement report.py**

Define immutable `Finding(code: str, severity: Literal["error", "warning"], message: str, block_id: str | None, claim_ids: tuple[str, ...])` and `ValidationReport(findings, claim_coverage)`. `hard_codes` and `warning_codes` return insertion-order de-duplicated tuples. Add `merge(*reports)` to combine findings and claim coverage without mutating inputs.

- [ ] **Step 7: Implement validate_submission as one-pass aggregation**

Implement every invariant in Spec §§7.2, 8, 12 and 13. Do not raise for a normal rejected submission; append findings and return the full report. Only Python type misuse at the outer function boundary may raise `TypeError`.

Use exact set relationships:

```python
covered = {
    claim_id: tuple(block.block_id for block in all_blocks if claim_id in block.claim_ids)
    for claim_id in claims_by_id
}
missing_controls = set(submission.brief.control_needs) - set(submission.render_context.control_capabilities)
```

For claim-stream correctness, `kind == "exclusion"` belongs only to negative blocks; every other required kind belongs to positive blocks.

- [ ] **Step 8: Run focused validation tests**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_submission_validation.py -q
```

Expected: PASS and every rejected fixture returns all applicable codes in one report.

- [ ] **Step 9: Record evidence and checkpoint**

If authorized:

```powershell
git add skills/prompt-forge/prompt_forge/anima/report.py skills/prompt-forge/prompt_forge/anima/validation.py skills/prompt-forge/tests/test_anima_submission_validation.py
git commit -m "feat: validate Anima visual briefs and safety"
```

---

### Task 5: Audit Model Protocol and the Effective Prompt

**Files:**
- Modify: `skills/prompt-forge/prompt_forge/anima/validation.py`
- Create: `skills/prompt-forge/tests/test_anima_protocol_validation.py`

**Interfaces:**
- Consumes: parsed tag blocks, model profile, exact dictionary, render-context injections.
- Produces: `validate_prompt_protocol` and deterministic error/warning findings.

- [ ] **Step 1: Write failing Base/Aesthetic tests**

```python
def test_aesthetic_rejects_score_tags_in_blocks_or_injections(aesthetic_submission) -> None:
    report = validate_prompt_protocol(
        aesthetic_submission,
        load_model_profile("anima-aesthetic-v1"),
        AnimaTagDictionary(),
    )
    assert "aesthetic_score_tag_forbidden" in report.hard_codes


def test_base_missing_quality_prefix_is_warning_not_error(base_without_quality) -> None:
    report = validate_prompt_protocol(base_without_quality, load_model_profile("anima-base-v1"), AnimaTagDictionary())
    assert "quality_prefix_absent" in report.warning_codes
    assert "quality_prefix_absent" not in report.hard_codes
```

- [ ] **Step 2: Write failing effective-prompt collision tests**

```python
def test_external_injection_cannot_duplicate_authored_semantics(injected_duplicate_submission) -> None:
    report = validate_prompt_protocol(injected_duplicate_submission, load_model_profile("anima-base-v1"), AnimaTagDictionary())
    assert "prompt_injection_collision" in report.hard_codes


def test_positive_and_negative_exact_semantics_conflict(positive_negative_collision) -> None:
    report = validate_prompt_protocol(positive_negative_collision, load_model_profile("anima-base-v1"), AnimaTagDictionary())
    assert "positive_negative_contradiction" in report.hard_codes
```

- [ ] **Step 3: Write failing tag and warning tests**

Cover all of these observable outcomes:

```python
assert "invalid_tag_syntax" in report_for("blue_hair").hard_codes
assert "artist_prefix_missing" in report_for("kantoku").hard_codes
assert "unverified_tag" in report_for("invented visual token").warning_codes
assert "weight_requires_experiment" in report_for("(chibi:2)").warning_codes
assert "artist_mix_experimental" in report_for("@kantoku, @wlop").warning_codes
```

Use a small fake dictionary for artist category tests so the result does not depend on a particular community database row.

- [ ] **Step 4: Write failing natural-language shape tests**

```python
def test_natural_language_route_requires_two_complete_sentences(nl_one_sentence) -> None:
    report = validate_prompt_protocol(nl_one_sentence, load_model_profile("anima-base-v1"), AnimaTagDictionary())
    assert "route_shape_mismatch" in report.hard_codes


def test_visible_text_and_prompt_only_limits_are_warnings(visible_text_submission) -> None:
    report = validate_prompt_protocol(visible_text_submission, load_model_profile("anima-base-v1"), AnimaTagDictionary())
    assert "visible_text_is_weak" in report.warning_codes
```

- [ ] **Step 5: Run and confirm behavior is absent**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_protocol_validation.py -q
```

Expected: FAIL because `validate_prompt_protocol` is absent.

- [ ] **Step 6: Implement effective positive/negative token collection**

For tag blocks, parse every comma member. Append render-context injections after authored tags only for auditing. Track `source = block_id | positive_injection | negative_injection | adapter:<name>` so collision messages identify both sources. Never append injections to the node prompt.

- [ ] **Step 7: Implement deterministic protocol gates**

Enforce lowercase-space ordinary tags, reserved `score_1..score_9`, `@artist`, Aesthetic score prohibition, finite weights, exact duplicate semantics, cross-stream equality and injection collisions. Prose participates only in exact whole-claim overlap checks; do not reject arbitrary substring similarity.

- [ ] **Step 8: Implement warnings without changing content**

Emit the seven warning codes from Spec §12.2. Multiple warnings of the same code may retain distinct block IDs in `findings`, while `warning_codes` remains de-duplicated.

- [ ] **Step 9: Run protocol and prior validation tests**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_protocol_validation.py skills/prompt-forge/tests/test_anima_submission_validation.py -q
```

Expected: PASS.

- [ ] **Step 10: Record evidence and checkpoint**

If authorized:

```powershell
git add skills/prompt-forge/prompt_forge/anima/validation.py skills/prompt-forge/tests/test_anima_protocol_validation.py
git commit -m "feat: audit Anima effective prompt semantics"
```

---

### Task 6: Render in Author Order and Compile PromptArtifact v2

**Files:**
- Create: `skills/prompt-forge/prompt_forge/anima/rendering.py`
- Create: `skills/prompt-forge/prompt_forge/anima/compiler.py`
- Create: `skills/prompt-forge/tests/test_anima_compiler_v2.py`
- Modify: `skills/prompt-forge/prompt_forge/anima/__init__.py`

**Interfaces:**
- Consumes: complete v2 submission, profiles, validation reports, tokenizer, artifact constructor.
- Produces: `RenderedPrompt`, `render_submission`, `compile_anima_prompt`.

- [ ] **Step 1: Write failing order-preservation and route tests**

```python
def test_tag_route_preserves_block_and_tag_order(tag_submission) -> None:
    artifact = compile_anima_prompt(tag_submission)
    assert artifact.status == "production_ready"
    assert artifact.prompt == {
        "positive": "masterpiece, best quality, 1girl, blue hair, smile",
        "negative": "blurry",
    }


def test_hybrid_joins_tags_and_prose_without_reordering(hybrid_submission) -> None:
    artifact = compile_anima_prompt(hybrid_submission)
    assert artifact.prompt["positive"] == (
        "1girl, red coat. She stands at frame left while wind lifts the coat hem. "
        "A quiet station recedes behind her."
    )


def test_natural_language_preserves_capitalization(nl_submission) -> None:
    artifact = compile_anima_prompt(nl_submission)
    assert artifact.prompt["positive"].startswith("A paper theatre opens")
```

- [ ] **Step 2: Write failing rejected-artifact and audit tests**

```python
def test_all_hard_gates_return_one_rejected_artifact(broken_submission) -> None:
    artifact = compile_anima_prompt(broken_submission)
    assert artifact.artifact_version == 2
    assert artifact.status == "quality_rejected"
    assert artifact.prompt is None
    assert len(artifact.audit["hard_gate_codes"]) >= 2
    assert artifact.compression == ()
    assert artifact.conflict is None


def test_success_artifact_binds_context_and_claim_coverage(valid_submission) -> None:
    artifact = compile_anima_prompt(valid_submission)
    contract = artifact.audit["execution_contract"]
    assert contract["render_context"] == render_context_payload(valid_submission.render_context)
    assert contract["render_context_sha256"] == render_context_sha256(valid_submission.render_context)
    assert artifact.trace["appearance"] == ("subject-style",)
```

- [ ] **Step 3: Write failing physical-limit test**

Build one prose block longer than 32,768 exact tokenizer tokens and assert `physical_token_limit` appears, `prompt is None`, and `sacrificed_facts == ()`.

- [ ] **Step 4: Run and confirm compiler import failure**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_compiler_v2.py -q
```

Expected: FAIL because `compiler.py` and `rendering.py` do not exist.

- [ ] **Step 5: Implement deterministic rendering**

`RenderedPrompt` has `positive: str` and `negative: str`. Render each tag block by parsing and joining members with `, `. Preserve prose text except leading/trailing and repeated boundary whitespace. Join consecutive tag blocks with `, `; when either side is prose, use one space if the prior block ends in `.?!`, otherwise use `. `. Never sort blocks.

- [ ] **Step 6: Implement compile_anima_prompt**

Follow Spec §14 exactly. Load the fixed tokenizer from `knowledge/tokenizers/anima-qwen3-0.6b`; merge structure and protocol reports; render once; count positive, negative and effective streams; append `physical_token_limit` if required; create artifact v2 with:

```python
create_prompt_artifact(
    artifact_version=2,
    status=status,
    task="anima",
    model=profile.model,
    prompt=prompt,
    facts=submission.brief.claims,
    trace=report.claim_coverage,
    token_report=token_report,
    audit=audit_payload,
    compression=(),
    conflict=None,
    token_count_verified=True,
    knowledge_manifest_sha256=knowledge_hash,
)
```

Do not catch unexpected programmer errors and turn them into quality findings.

- [ ] **Step 7: Run compiler and artifact tests**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_compiler_v2.py skills/prompt-forge/tests/test_artifacts.py -q
```

Expected: PASS.

- [ ] **Step 8: Run all new Anima v2 tests**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_contracts_v2.py skills/prompt-forge/tests/test_anima_profiles.py skills/prompt-forge/tests/test_anima_tag_parser.py skills/prompt-forge/tests/test_anima_dictionary.py skills/prompt-forge/tests/test_anima_submission_validation.py skills/prompt-forge/tests/test_anima_protocol_validation.py skills/prompt-forge/tests/test_anima_compiler_v2.py -q
```

Expected: PASS.

- [ ] **Step 9: Record evidence and checkpoint**

If authorized:

```powershell
git add skills/prompt-forge/prompt_forge/anima skills/prompt-forge/tests/test_anima_compiler_v2.py
git commit -m "feat: compile Anima v2 prompt artifacts"
```

---

### Task 7: Switch Public Surface and MCP to Anima v2

**Files:**
- Modify: `skills/prompt-forge/prompt_forge/__init__.py`
- Modify: `skills/prompt-forge/tests/test_public_surface.py`
- Modify: `mcp_server/src/comfyui_chenxin_mcp/server.py`
- Modify: `mcp_server/src/comfyui_chenxin_mcp/engine/prompt_forge.py`
- Modify: `mcp_server/src/comfyui_chenxin_mcp/engine/build_log.py`
- Create: `mcp_server/tests/test_anima_compile_v2.py`
- Modify: `mcp_server/tests/test_prompt_artifact_contract.py`
- Modify: `mcp_server/tests/test_real_artifact_consumption.py`

**Interfaces:**
- Consumes: JSON v2 submission and `compile_anima_prompt`.
- Produces: MCP `{ref_id, prompt, metadata}`, artifact-version-aware validation, context comparison option.

- [ ] **Step 1: Write the failing public-surface test**

```python
def test_only_greenfield_anima_and_existing_h3_authors_are_public() -> None:
    import prompt_forge
    assert prompt_forge.__all__ == [
        "compile_anima_prompt",
        "author_h3_t2va_prompt",
        "author_h3_ref2va_prompt",
    ]
    assert not hasattr(prompt_forge, "author_anima_prompt")
```

- [ ] **Step 2: Write the failing JSON coercion test**

Construct a complete JSON request with keys `route`, `brief`, `render_context`, `positive_blocks`, `negative_blocks`. Call `_coerce_anima_submission` and assert nested dataclass types and exact values. Assert a legacy request containing `positive_segments` is rejected with `anima submission requires`.

- [ ] **Step 3: Write the failing artifact-v2 validation test**

Register one Anima BuildLog with `artifact_version=2` and an execution contract; call:

```python
prompt = validate_prompt_artifact(
    ref_id,
    expected_task="anima",
    expected_render_context=context,
)
assert prompt["positive"] == "1girl"
```

Then register version 1 and assert rejection contains `artifact_version`. Change one adapter strength and assert rejection contains `render context`.

- [ ] **Step 4: Run focused MCP tests and confirm failures**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_public_surface.py mcp_server/tests/test_anima_compile_v2.py mcp_server/tests/test_prompt_artifact_contract.py -q
```

Expected: FAIL on old public symbol, missing v2 coercer and missing context validation.

- [ ] **Step 5: Switch the prompt_forge public surface**

Replace the Anima wrapper with:

```python
def compile_anima_prompt(submission: _anima_contracts.AnimaPromptSubmission) -> PromptArtifact:
    from .anima.compiler import compile_anima_prompt as _compile
    return _compile(submission)
```

Do not keep an alias for the old name.

- [ ] **Step 6: Implement strict nested MCP coercion**

Add one constructor helper per nested type: `_coerce_intent_claims`, `_coerce_subjects`, `_coerce_visual_brief`, `_coerce_style_adapters`, `_coerce_render_context`, `_coerce_prompt_blocks`, `_coerce_anima_submission`. Reject unknown top-level or nested keys, missing fields and scalar/list confusion. Never default claim IDs to all facts and never infer owners in code.

- [ ] **Step 7: Make the task registry version-aware**

Set the Anima entry to:

```python
"anima": {
    "model": "circlestone-labs/Anima",
    "prompt_keys": frozenset({"positive", "negative"}),
    "author": "compile_anima_prompt",
    "artifact_version": 2,
}
```

Set both H3 entries to `artifact_version: 1`.

- [ ] **Step 8: Validate the render-context execution contract**

For Anima, `validate_prompt_artifact` must verify exact artifact version, `audit.schema_version == "2.0"`, context object, 64-character context hash and canonical SHA-256 equality. If `expected_render_context` is supplied, compare both canonical objects and hashes. H3 logic remains unchanged.

- [ ] **Step 9: Update BuildLog metadata**

For Anima token reports, set metadata `token_count` to `positive.actual + negative.actual`; retain the current H3 `actual` behavior. Add `artifact_version` and `render_context_sha256` to metadata.

- [ ] **Step 10: Run focused and MCP regression tests**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_public_surface.py mcp_server/tests/test_anima_compile_v2.py mcp_server/tests/test_prompt_artifact_contract.py mcp_server/tests/test_real_artifact_consumption.py -q
```

Expected: PASS.

- [ ] **Step 11: Record evidence and checkpoint**

If authorized:

```powershell
git add skills/prompt-forge/prompt_forge/__init__.py skills/prompt-forge/tests/test_public_surface.py mcp_server/src/comfyui_chenxin_mcp/server.py mcp_server/src/comfyui_chenxin_mcp/engine/prompt_forge.py mcp_server/src/comfyui_chenxin_mcp/engine/build_log.py mcp_server/tests
git commit -m "feat: expose Anima v2 through MCP"
```

---

### Task 8: Enforce prompt_ref-only Camera Delivery and Context Matching

**Files:**
- Create: `skills/camera-image/camera_image/runtime/prompt_context.py`
- Create: `skills/camera-image/tests/test_prompt_context.py`
- Modify: `skills/camera-image/camera_image/skill_data.py`
- Modify: `skills/camera-image/camera_image/runtime/config_schema.py`
- Modify: `skills/camera-image/camera_image/runtime/graph_patcher.py`
- Modify: `skills/camera-image/camera_image/runtime/lora_resolver.py`
- Modify: `skills/camera-image/camera_image/runtime/__init__.py`
- Modify: `skills/camera-image/camera_image/runtime/profiles/camera-anima.json`
- Rewrite: `skills/camera-image/tests/test_image_artifact_input.py`
- Modify: `mcp_server/src/comfyui_chenxin_mcp/engine/execute.py`
- Modify: `mcp_server/tests/test_real_artifact_consumption.py`

**Interfaces:**
- Consumes: `prompt_ref`, actual camera LoRA config, validated BuildLog.
- Produces: exact camera render-context dict, internally hydrated `RunConfig.prompt`, fail-closed pre-GPU gate.

- [ ] **Step 1: Write failing envelope tests**

```python
def test_camera_image_requires_only_prompt_ref() -> None:
    config = RunConfig.from_envelope({"prompt_ref": "a" * 32})
    assert config.prompt_ref == "a" * 32
    assert config.prompt == {}
    with pytest.raises(TypeError, match="prompt_ref"):
        RunConfig.from_envelope({"prompt": {"positive": "1girl", "negative": ""}})
    with pytest.raises(TypeError, match="unsupported envelope"):
        RunConfig.from_envelope({"prompt_ref": "a" * 32, "prompt": {}})
```

- [ ] **Step 2: Write failing default and custom context tests**

```python
def test_default_context_matches_fixed_workflow() -> None:
    context = build_anima_render_context(None)
    assert context["model_profile_id"] == "anima-base-v1"
    assert context["workflow_profile_id"] == "camera-anima-v2"
    assert context["positive_injections"] == ["masterpiece", "very aesthetic", "@gpt-image-2"]


def test_custom_lora_context_preserves_exact_order_and_strengths() -> None:
    lora = {"selections": [
        {"name": "style-a", "strength_model": 0.8, "strength_clip": 0.7, "trigger_words": ["@style-a"]},
        {"name": "detail-b", "strength_model": 0.4, "trigger_words": ["detail"]},
    ]}
    context = build_anima_render_context(lora)
    assert [item["model_name"] for item in context["style_adapters"]] == ["style-a", "detail-b"]
    assert context["positive_injections"] == ["@style-a", "detail"]


def test_explicit_empty_lora_selection_means_no_adapters() -> None:
    context = build_anima_render_context({"selections": []})
    assert context["style_adapters"] == []
    assert context["positive_injections"] == []
```

- [ ] **Step 3: Write failing exact-name and pre-GPU tests**

Assert `resolve_lora_names([{"name": "style"}], ["anima\\style-one.safetensors"])` raises not found instead of substring matching. In the MCP execution fake, register a context-mismatched BuildLog and assert `health`, `upload_image`, `validate_workflow` and `enqueue` call counts all remain zero.

- [ ] **Step 4: Run focused tests and confirm old direct-prompt behavior fails expectations**

Run:

```powershell
& $py -m pytest skills/camera-image/tests/test_image_artifact_input.py skills/camera-image/tests/test_prompt_context.py mcp_server/tests/test_real_artifact_consumption.py -q
```

Expected: FAIL because direct prompt is still accepted and prompt context helper is absent.

- [ ] **Step 5: Implement prompt_context.py**

Return plain JSON-compatible data with exact keys from `AnimaRenderContext`. Default data must match Spec §11. For custom LoRAs, normalize only folder and `.safetensors` suffix; never perform substring matching. Delete the old `active` field: every listed selection is loaded and contributes its trigger terms. Missing `lora` selects the fixed default stack; an explicit empty `selections` array selects no adapters.

- [ ] **Step 6: Make RunConfig prompt_ref-only at the public boundary**

Keep `prompt: dict[str, str]` as an internal field with `default_factory=dict`; make `prompt_ref: str` required. `from_envelope` accepts exactly `{"prompt_ref"}` and rejects every direct prompt. Preserve all existing camera tunables.

- [ ] **Step 7: Make the gate hydrate internal prompt before workflow preparation**

In `execute.run_skill`, after `prompt_gate_result` succeeds:

```python
patch_config = config
if prompt_gate_result is not None and hasattr(config, "prompt"):
    patch_config = replace(config, prompt=dict(prompt_gate_result))
```

Use `patch_config` for uploads and `prepare_fn`. Keep `config` for the immutable original run record, and keep `prompt_gate_result` as the reproducibility prompt.

- [ ] **Step 8: Compare actual context in compile_prompt_gate**

Build expected context from `config.lora`, pass it to `validate_prompt_artifact`, and return the resolved prompt. Remove the graph patcher's second BuildLog lookup; it must only read `config.prompt` after the gate.

- [ ] **Step 9: Remove fuzzy LoRA resolution**

Resolution order becomes exact normalized name, then exact full inventory name, case-insensitively. Delete substring matching, ambiguity branches and the `active` field. Preserve inventory filtering and error messages with the requested exact name. Change `build_lora_patch` so missing `lora` selects the default stack while explicit `{"selections": []}` produces an empty stack and empty trigger message.

- [ ] **Step 10: Update workflow profile and describe output**

Set `profile_id` to `camera-anima-v2`; add `model_profile_id`, default style adapters, injections and control capabilities. `describe_config` must expose a `prompt_context` object callers can copy into an Anima submission before compilation.

- [ ] **Step 11: Run camera and MCP tests**

Run:

```powershell
& $py -m pytest skills/camera-image/tests mcp_server/tests/test_real_artifact_consumption.py mcp_server/tests/test_prompt_artifact_contract.py -q
```

Expected: PASS; direct prompt and context mismatch both fail before GPU-adjacent calls.

- [ ] **Step 12: Record evidence and checkpoint**

If authorized:

```powershell
git add skills/camera-image mcp_server/src/comfyui_chenxin_mcp/engine/execute.py mcp_server/tests/test_real_artifact_consumption.py
git commit -m "feat: bind camera runs to Anima render context"
```

---

### Task 9: Rewrite the Skill as a Methodology-First Guide

**Files:**
- Rewrite: `skills/prompt-forge/SKILL.md`
- Regenerate: `skills/prompt-forge/agents/openai.yaml`
- Create: all nine reference files listed in §1.1
- Move/rewrite: `skills/prompt-forge/references/dialects/minimax-h3/dialect.md` → `skills/prompt-forge/references/minimax-h3/dialect.md`
- Move: `skills/prompt-forge/references/dialects/minimax-h3/budget-policy.json` → `skills/prompt-forge/references/minimax-h3/budget-policy.json`
- Rewrite: `skills/prompt-forge/tests/test_documentation_contract.py`

**Interfaces:**
- Consumes: Design Spec and implemented v2 JSON contract.
- Produces: a zero-context Agent can author a valid, high-quality submission without loading irrelevant references.

- [ ] **Step 1: Write failing documentation contract tests**

```python
def test_skill_is_concise_and_routes_references_one_level_deep() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    assert len(skill.splitlines()) < 500
    for name in (
        "visual-brief.md", "route-selection.md", "model-profiles.md",
        "multi-subject-spatial.md", "negative-and-weights.md",
        "failure-recovery.md", "examples.md", "evaluation.md",
        "artifact-delivery.md", "minimax-h3/dialect.md",
    ):
        assert name in skill


def test_anima_method_contains_no_removed_rules() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in ANIMA_DOCS)
    forbidden = (
        "fixed tag count", "mandatory five layers", "scene_description_count",
        "direct eye contact", "natural language bridge", "author_anima_prompt",
    )
    assert [token for token in forbidden if token in combined.casefold()] == []


def test_every_markdown_link_resolves() -> None:
    assert unresolved_relative_links(SKILL.parent) == []
```

- [ ] **Step 2: Run and confirm current documents violate the new contract**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_documentation_contract.py -q
```

Expected: FAIL on missing references and removed-rule text.

- [ ] **Step 3: Rewrite SKILL.md**

Use this exact section order:

1. `# Prompt Forge`
2. `## Responsibility split`
3. `## Choose the task`
4. `## Anima workflow` with seven imperative steps: gather context, build brief, choose route, author blocks, run self-review, compile, inspect warnings.
5. `## When to load each Anima reference`
6. `## MiniMax-H3 workflow`
7. `## Tool contract`
8. `## Production delivery`
9. `## Non-negotiable boundaries`

State explicitly that code does not choose aesthetics and that image evaluation, not prompt length, decides quality.

- [ ] **Step 4: Write visual-brief.md and route-selection.md**

`visual-brief.md` must define the claim inventory, owners, required/origin distinction, content rating, coordinate frame and control needs. `route-selection.md` must provide the Tag/Hybrid/NL decision table and the prompt-only escalation test. Do not include fixed tag counts.

- [ ] **Step 5: Write model-profiles.md and multi-subject-spatial.md**

Record Base/Aesthetic/Turbo differences, official quality suggestions, Aesthetic score prohibition, viewer/scene coordinate frames, subject-block binding, causal action order and regional prompting escalation.

- [ ] **Step 6: Write negative-and-weights.md and failure-recovery.md**

Negative method: official minimal baseline plus observed-failure terms; no generic anatomy dump by default. Weight method: off by default, one variable, fixed seed comparison, no universal artist range. Failure recovery must follow Spec §20 exactly.

- [ ] **Step 7: Write examples.md, evaluation.md and artifact-delivery.md**

Include three complete safe submissions: simple Tag, two-adult Hybrid interaction, pure NL experimental composition. Include their render context and expected warning behavior. Evaluation must include the 24/12 image cost cap and five 0–4 dimensions. Delivery must show `compile_prompt_artifact` followed by `run_skill` with `{"prompt_ref": "..."}` only.

- [ ] **Step 8: Move H3 references without semantic changes**

Use `apply_patch` to create the new paths with byte-equivalent H3 content, update SKILL links, then delete the old paths. Do not alter H3 field grammar or budget JSON.

- [ ] **Step 9: Regenerate openai.yaml**

Run:

```powershell
& $py 'C:\Users\11245\.codex\skills\.system\skill-creator\scripts\generate_openai_yaml.py' 'skills\prompt-forge' --interface 'display_name=Prompt Forge' --interface 'short_description=Author and audit Anima and MiniMax-H3 prompts' --interface 'default_prompt=Use $prompt-forge to author and audit a model-native production prompt.'
```

Expected: valid UTF-8 YAML with quoted strings and the required `$prompt-forge` mention.

- [ ] **Step 10: Run documentation tests**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_documentation_contract.py -q
```

Expected: PASS.

- [ ] **Step 11: Record evidence and checkpoint**

If authorized:

```powershell
git add skills/prompt-forge/SKILL.md skills/prompt-forge/agents/openai.yaml skills/prompt-forge/references skills/prompt-forge/tests/test_documentation_contract.py
git commit -m "docs: rewrite Prompt Forge around visual intent"
```

---

### Task 10: Add Deterministic Lookup and Evaluation Tools

**Files:**
- Create: `skills/prompt-forge/scripts/anima_tag_lookup.py`
- Create: `skills/prompt-forge/scripts/build_anima_eval_manifest.py`
- Create: `skills/prompt-forge/scripts/score_anima_eval.py`
- Create: `skills/prompt-forge/benchmarks/anima/briefs.jsonl`
- Create: `skills/prompt-forge/benchmarks/anima/candidates.schema.json`
- Create: `skills/prompt-forge/benchmarks/anima/ratings.schema.json`
- Create: `skills/prompt-forge/benchmarks/anima/README.md`
- Create: `skills/prompt-forge/tests/test_anima_eval_tools.py`

**Interfaces:**
- Consumes: exact tag query, candidate JSONL, rating JSONL.
- Produces: deterministic JSON stdout, render manifest, score summary; never authors prompt text.

- [ ] **Step 1: Write failing CLI tests**

Use `subprocess.run([sys.executable, script, ...], capture_output=True, text=True)` and assert:

- `anima_tag_lookup.py --query "best quality" --limit 3` returns JSON with the canonical exact hit first.
- limit 0 exits nonzero with no traceback containing database paths.
- tools do not import ComfyUI or make network calls.

- [ ] **Step 2: Write failing manifest tests**

Given two candidate records and seeds `17,73`, assert four jobs are emitted in candidate order, each with `brief_id`, `candidate_id`, `prompt_ref`, `artifact_sha256`, `render_context_sha256`, `seed`, `status="planned"`.

- [ ] **Step 3: Write failing score tests**

Provide complete paired ratings and assert:

```python
assert summary["median_total"] == 17
assert summary["minimum_fact_adherence"] == 3
assert summary["minimum_subject_binding"] == 3
assert summary["non_tie_preference_rate"] == 0.75
assert summary["release_gate_passed"] is True
```

Also assert missing dimensions, scores outside 0–4 and duplicate `(brief_id, candidate_id, seed)` fail closed.

- [ ] **Step 4: Run and confirm scripts are absent**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_eval_tools.py -q
```

Expected: FAIL because the three scripts and fixtures are absent.

- [ ] **Step 5: Implement the tag lookup CLI**

Arguments are `--query`, optional `--category`, and `--limit` in 1–100. Emit only JSON records from `AnimaTagDictionary.lookup`; error messages go to stderr and exit 2 for bad input.

- [ ] **Step 6: Commit the six fixed briefs**

Use IDs and intents:

```json
{"brief_id":"single-identity","intent":"One adult woman with short blue hair reading beside a train window; identity and quiet composition dominate.","required_dimensions":["identity","appearance","action","composition"],"routes":["tag","hybrid"]}
{"brief_id":"two-subject-binding","intent":"Two adult women, red-haired subject on viewer-left and black-haired subject on viewer-right, exchanging differently colored umbrellas.","required_dimensions":["count","appearance","relation","spatial"],"routes":["hybrid"]}
{"brief_id":"causal-interaction","intent":"An adult swordswoman cuts a falling ribbon; the severed halves visibly drift apart after the strike.","required_dimensions":["identity","action","relation"],"routes":["hybrid"]}
{"brief_id":"layered-space","intent":"An adult courier in foreground, market crowd in midground, hilltop observatory in background, all sharing one viewer coordinate frame.","required_dimensions":["identity","spatial","environment","composition"],"routes":["hybrid","natural_language"]}
{"brief_id":"paper-theatre","intent":"A paper theatre opens into a painted ocean while an adult performer manipulates visible paper waves; prioritize unusual material logic.","required_dimensions":["action","environment","style","composition"],"routes":["natural_language"]}
{"brief_id":"wuxia-cyberpunk","intent":"An adult wuxia traveler crosses a rain-soaked neon megacity; ink-wash motion and cyberpunk architecture are intentionally coherent.","required_dimensions":["identity","environment","style","lighting"],"routes":["hybrid","natural_language"]}
```

- [ ] **Step 7: Implement manifest generation and score calculation**

Manifest CLI: `--candidates`, `--seeds`, `--output`; reject candidate count that would exceed 24 planned jobs unless `--max-jobs` is explicitly lower. Score CLI: `--ratings`, `--output`; compute integer totals, median, minimum adherence/binding, non-tie preference rate and the exact Spec §19.3 release gate.

- [ ] **Step 8: Write the schemas and README contract**

Use JSON Schema draft 2020-12, `additionalProperties: false`, required fields and integer score bounds 0–4. README must state that prompts are authored outside these scripts and failed images may not be silently dropped or re-seeded.

- [ ] **Step 9: Run eval-tool tests**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_anima_eval_tools.py -q
```

Expected: PASS.

- [ ] **Step 10: Record evidence and checkpoint**

If authorized:

```powershell
git add skills/prompt-forge/scripts/anima_tag_lookup.py skills/prompt-forge/scripts/build_anima_eval_manifest.py skills/prompt-forge/scripts/score_anima_eval.py skills/prompt-forge/benchmarks/anima skills/prompt-forge/tests/test_anima_eval_tools.py
git commit -m "test: add reproducible Anima image evaluation"
```

---

### Task 11: Delete the Old Anima System and Lock the 0.3.0 Release Shape

**Files:**
- Delete: every path in §1.3
- Modify: `skills/prompt-forge/prompt_forge/contracts.py`
- Modify: `skills/prompt-forge/prompt_forge/budgets.py`
- Modify: `skills/prompt-forge/prompt_forge/compression.py`
- Modify: `skills/prompt-forge/tests/test_budgets.py`
- Modify: `skills/prompt-forge/tests/test_compression.py`
- Modify: `skills/prompt-forge/tests/test_release_verifier.py`
- Modify: `skills/prompt-forge/scripts/verify_release.py`
- Modify: `skills/prompt-forge/scripts/stage_release.py`
- Modify: `skills/prompt-forge/scripts/run_benchmarks.py`
- Modify: `skills/prompt-forge/scripts/build_benchmark_corpus.py`
- Modify: `.codex-plugin/plugin.json`
- Modify: `mcp_server/pyproject.toml`
- Modify: `skills/prompt-forge/pyproject.toml`
- Modify: `skills/camera-image/pyproject.toml`
- Modify: `skills/camera-multiview/pyproject.toml`
- Modify: `skills/camera-video/pyproject.toml`
- Modify: `scripts/install.ps1`
- Modify: `scripts/install.sh`
- Modify: `docs/USAGE.md`
- Modify: `docs/architecture.md`
- Modify: `docs/camera-image-flow.md`
- Modify: `docs/TROUBLESHOOTING.md`

**Interfaces:**
- Consumes: fully working Anima v2 and unchanged H3.
- Produces: no reachable or packaged legacy Anima implementation; release verifier proves the new shape.

- [ ] **Step 1: Write the failing deletion and public-shape tests**

Extend `test_release_verifier.py` so `verify_greenfield_shape` rejects:

```text
prompt_forge/anima/author.py
prompt_forge/anima/audit.py
knowledge/anima/budget-policy.json
references/shared/aesthetic-coverage.md
references/quality/tag-count-ruler.md
references/dialects/anima/recipes/film-noir.md
knowledge/aesthetics/lighting.md
scripts/preflight.py
```

Scan production `.py` and active skill references for `AnimaAuthoringRequest`, `author_anima_prompt`, `plan_anima_budget`, `scene_description_count`, `tag_bridge_fact_overlap`, and `mandatory aesthetic retrieval`; assert no matches.

- [ ] **Step 2: Run and confirm old files make the test fail**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_release_verifier.py -q
```

Expected: FAIL and list existing legacy paths/symbols.

- [ ] **Step 3: Remove old shared Anima contracts**

Delete `Complexity` and `AnimaAuthoringRequest` from shared `contracts.py`. Keep `Fact`, `AuthoredSegment`, `H3ReferenceImage`, `H3T2VAAuthoringRequest`, `H3Ref2VAAuthoringRequest`, status and task literals.

- [ ] **Step 4: Remove Anima budgeting and compression**

Delete `AnimaBudgetPlan`, `_ANIMA_POLICY`, `plan_anima_budget`, Anima imports and the `"anima"` compression structure. Rewrite budget/compression tests so they cover only the two H3 paths and shared utility-density behavior.

- [ ] **Step 5: Delete exact legacy files with apply_patch**

Delete every §1.3 file. Do not delete `tags.sqlite`, its builder, tokenizer snapshots, H3 references or shared artifact/fact modules.

- [ ] **Step 6: Remove old Anima branches from generic benchmark scripts**

`run_benchmarks.py` and `build_benchmark_corpus.py` become H3-only. Remove the old `benchmarks/cases/anima.jsonl` and any Anima keys from `benchmarks/baselines/prompt_metrics.json`; use the Task 10 harness for Anima.

- [ ] **Step 7: Upgrade all package and plugin versions**

Set every Python project to `0.3.0`. Set plugin version to `0.3.0+codex.20260813`. Update release verifier exact-version assertions, plugin descriptions and install script checks together.

- [ ] **Step 8: Update release staging and cache key files**

Include new Anima Python files, `model-profiles.json`, rewritten protocol/manifest, all direct references, evaluation schemas and scripts. Remove `budget-policy.json` from required assets. Fail if cache contains a path from §1.3.

- [ ] **Step 9: Rewrite operational docs to the actual v2 flow**

Document: obtain camera prompt context via `describe_config`; author v2 submission; compile; pass only `prompt_ref`; context mismatch fails before GPU; H3 flow unchanged. Remove any statement that camera accepts arbitrary prompt dictionaries.

- [ ] **Step 10: Run release-shape and H3 regressions**

Run:

```powershell
& $py -m pytest skills/prompt-forge/tests/test_release_verifier.py skills/prompt-forge/tests/test_public_surface.py skills/prompt-forge/tests/test_budgets.py skills/prompt-forge/tests/test_compression.py skills/prompt-forge/tests/test_h3_t2va.py skills/prompt-forge/tests/test_h3_ref2va.py -q
```

Expected: PASS.

- [ ] **Step 11: Run a repository-wide forbidden-symbol scan**

Run:

```powershell
rg -n "AnimaAuthoringRequest|author_anima_prompt|plan_anima_budget|scene_description_count|tag_bridge_fact_overlap|mandatory aesthetic retrieval" skills/prompt-forge mcp_server skills/camera-image -g '*.py' -g '*.md' -g '*.json'
```

Expected: no output. Historical docs under `docs/superpowers/specs` and `docs/superpowers/plans` are outside the scan by design.

- [ ] **Step 12: Record evidence and checkpoint**

If authorized:

```powershell
git add -A skills/prompt-forge skills/camera-image mcp_server scripts docs .codex-plugin/plugin.json skills/camera-multiview/pyproject.toml skills/camera-video/pyproject.toml
git commit -m "refactor: replace legacy Anima prompt system"
```

---

### Task 12: Run Full Offline Verification and Independent Diff Review

**Files:**
- Modify only for progress: `docs/superpowers/plans/2026-08-13-anima-prompt-forge-greenfield-implementation.md`
- Modify only if a defect is proven: the owning file from Tasks 1–11, with a new failing regression test first.

**Interfaces:**
- Consumes: complete source rewrite.
- Produces: full offline evidence, clean diff review, synchronized CodeGraph.

- [ ] **Step 1: Run all Prompt Forge tests**

```powershell
& $py -m pytest skills/prompt-forge/tests -q
```

Expected: PASS.

- [ ] **Step 2: Run all MCP tests**

```powershell
& $py -m pytest mcp_server/tests -q
```

Expected: PASS.

- [ ] **Step 3: Run all camera-image tests**

```powershell
& $py -m pytest skills/camera-image/tests -q
```

Expected: PASS.

- [ ] **Step 4: Run unaffected camera regressions**

```powershell
& $py -m pytest skills/camera-multiview/tests skills/camera-video/tests -q
```

Expected: PASS.

- [ ] **Step 5: Run source release verification**

```powershell
& $py skills/prompt-forge/scripts/verify_release.py --source-root 'D:\Projects\comfyui-chenxin'
```

Expected: exit 0 and JSON reporting plugin 0.3.0, new public surface, dictionary/tokenizer integrity and zero forbidden paths.

- [ ] **Step 6: Review the entire diff**

Run:

```powershell
git diff --check
git diff --stat
git diff -- skills/prompt-forge mcp_server skills/camera-image scripts docs .codex-plugin/plugin.json
```

Verify every changed file belongs to §1, no user `.claude` path appears, no generated cache or benchmark output is staged, and no hard rule lacks a test.

- [ ] **Step 7: Re-read the Spec coverage matrix**

Record one Task number beside every Spec section 1–22. Any section without an owning Task is a plan defect; add a failing test and implement it before proceeding.

- [ ] **Step 8: Synchronize CodeGraph**

Run:

```powershell
codegraph.cmd sync
codegraph.cmd status
```

Expected: index up to date and new `compile_anima_prompt` call paths visible.

- [ ] **Step 9: Review the final call paths**

Run:

```powershell
codegraph.cmd explore "compile_anima_prompt AnimaPromptSubmission validate_prompt_artifact camera prompt context" --max-files 20
```

Expected: one Anima public compiler, one MCP coercion path, one camera context gate, no old author call path.

- [ ] **Step 10: Record evidence**

Update row 12 with all five test summaries, release verifier result and CodeGraph status. If a separate reviewer was authorized, add its review identifier; otherwise write `diff self-review complete`.

---

### Task 13: Synchronize Plugin Cache and Run the Low-Cost Image Gate

**Files:**
- Runtime output only: `outputs/anima-eval/20260813/`
- Modify for progress/evidence: `docs/superpowers/plans/2026-08-13-anima-prompt-forge-greenfield-implementation.md`
- Plugin cache written only by: `scripts/install.ps1`

**Interfaces:**
- Consumes: source-verified 0.3.0 plugin, local ComfyUI, required MCP tools and fixed workflow assets.
- Produces: source/cache equality evidence and blind image-quality score meeting Spec §19.3.

- [ ] **Step 1: Verify hard runtime dependencies without mutation**

Confirm Python 3.10+, Node.js, ComfyUI `http://127.0.0.1:8188`, and MCP tools `check_workflow_runtime`, `get_workflow`, `strip_workflow`, `validate_workflow`, `list_local_models`. If one is missing, mark Task 13 blocked; do not simulate it.

- [ ] **Step 2: Synchronize the managed plugin cache**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

Expected: source release verification, clean staging, installation under the 0.3.0 cache path, package installation and source/cache verification all pass.

- [ ] **Step 3: Verify source/cache equality explicitly**

Resolve the exact installed 0.3.0 cache directory printed by the installer, then run:

```powershell
$cachePath = 'PASTE-THE-EXACT-INSTALLED-CACHE-PATH-PRINTED-BY-INSTALLER'
if ($cachePath.StartsWith('PASTE-')) { throw 'Set cachePath from the installer output before verification' }
& $py skills/prompt-forge/scripts/verify_release.py --source-root 'D:\Projects\comfyui-chenxin' --cache-root $cachePath
```

Expected: exit 0 and every key file hash equal. Replace the angle-bracket token with the installer’s exact printed path before running; do not guess or glob a cache target.

- [ ] **Step 4: Author two candidates for each fixed brief**

For each `briefs.jsonl` row, author an official-minimal candidate and a methodology candidate. Use the same `AnimaRenderContext` returned by `describe_config(skill="camera-image", stage="t2i-camera")`. Compile each with `compile_prompt_artifact(task="anima", request=...)`; retain only `production_ready` candidates and record rejected candidates rather than silently rewriting them.

- [ ] **Step 5: Build the bounded render manifest**

If a verified Turbo workflow exists, use seeds `17,73` for 12 candidates, maximum 24 jobs. If only the fixed Base workflow exists, use seed `17`, maximum 12 jobs. Run:

```powershell
& $py skills/prompt-forge/scripts/build_anima_eval_manifest.py --candidates outputs/anima-eval/20260813/candidates.jsonl --seeds 17,73 --max-jobs 24 --output outputs/anima-eval/20260813/render-manifest.json
```

For Base-only evaluation use `--seeds 17 --max-jobs 12`.

- [ ] **Step 6: Render every planned job without seed shopping**

For each manifest row call `run_skill` with:

```json
{
  "skill": "camera-image",
  "stage": "t2i-camera",
  "envelope": {"prompt_ref": "value copied exactly from the current manifest row"},
  "config": {
    "seed": 17,
    "image_size": {"width": 1216, "height": 832}
  },
  "output_dir": "outputs/anima-eval/20260813"
}
```

Use the row seed exactly. Record failures with error category; do not replace failed seeds.

- [ ] **Step 7: Collect blind ratings**

Randomize display labels so the evaluator cannot see candidate type. Record all five 0–4 dimensions plus paired preference in `ratings.jsonl`, conforming to `ratings.schema.json`.

- [ ] **Step 8: Score the release gate**

Run:

```powershell
& $py skills/prompt-forge/scripts/score_anima_eval.py --ratings outputs/anima-eval/20260813/ratings.jsonl --output outputs/anima-eval/20260813/summary.json
```

Expected: `minimum_fact_adherence >= 3`, `minimum_subject_binding >= 3`, `median_total >= 17`, `non_tie_preference_rate >= 0.60`, `release_gate_passed == true`.

- [ ] **Step 9: Handle a failed image gate scientifically**

If the gate fails, classify each failure by Spec §20, change exactly one methodology or validation assumption, add a regression brief or static test, rerun only the affected pair with the same seeds, and keep the original failed evidence. Do not lower thresholds.

- [ ] **Step 10: Final verification and progress closure**

Re-run Task 12 Steps 1–5 after any image-driven change, rerun installer/cache verification, then mark row 13 and every remaining row complete. Record output directory, summary SHA-256 and final source/cache verifier result.

---

## 4. Final Self-Review Checklist

Before declaring the plan executed, verify all boxes:

- [ ] Every Spec section has an owning Task.
- [ ] Every hard gate has at least one failing-then-passing test.
- [ ] Every warning is non-blocking in a test.
- [ ] Anima v2 stores claims directly and never fabricates old Fact/Segment adapters.
- [ ] Anima has no token-based content deletion or budget-conflict path.
- [ ] H3 still uses artifact version 1 and all H3 tests pass.
- [ ] Camera rejects direct prompt dictionaries, Anima v1 and context mismatch before GPU work.
- [ ] Workflow and LoRA injections participate in effective-prompt audit but are not duplicated into node text.
- [ ] Skill references are one level from SKILL.md and SKILL.md remains under 500 lines.
- [ ] No sexualized-minor material from the supplied template enters the new skill or examples.
- [ ] Old Anima source, references, recipes, aesthetic corpus and scripts are absent from source and cache.
- [ ] All package versions are 0.3.0 and plugin cache matches source.
- [ ] Image gate meets the fixed thresholds without discarded failures or changed seeds.
- [ ] User-owned untracked paths remain untouched.

## 5. Execution Handoff

Plan execution must start in an isolated worktree using `superpowers:using-git-worktrees`, then choose exactly one mode:

1. **Subagent-Driven (recommended):** use `superpowers:subagent-driven-development`; dispatch one fresh worker per Task and run two-stage review between Tasks.
2. **Inline Execution:** use `superpowers:executing-plans`; execute Tasks in numbered order with progress-table checkpoints.

Neither mode may parallelize Tasks that modify the same files. Task 13 begins only after Tasks 0–12 are complete.
