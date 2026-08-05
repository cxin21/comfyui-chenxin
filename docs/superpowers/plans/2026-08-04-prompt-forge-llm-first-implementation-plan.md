# Prompt Forge LLM-first Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Prompt Forge 重建为只负责 Claude/Codex 提示词创作与质量审查的多模型、多风格技能，不依赖模型安装、ComfyUI、MCP 或工作流状态。

**Architecture:** 将现有混合 recipe 目录拆为纯提示词方言注册表和独立风格语言库。LLM 负责写最终提示词，Python 只负责证据归一化、方言检查、tag 精确校验、时间线解析和质量审查；执行层只消费 PromptPackage，不再成为 Prompt Forge 的依赖。

**Tech Stack:** Python 3.11+ 标准库、JSON、Markdown、pytest；不新增模型服务、MCP 客户端或运行时依赖。

## Global Constraints

- Prompt Forge 不检查模型、工作流、ComfyUI、MCP、节点、显存、哈希或执行状态。
- 最终提示词必须由 Claude/Codex 生成；没有 LLM 草稿时，生产校验必须失败，禁止静默 prose fallback。
- 明确事实优先于合理推断，合理推断优先于模型发明；未知信息必须保留为假设或不确定性。
- 模型 profile 只描述提示词方言；风格 profile 只描述视觉语言；两者不得包含执行配置。
- 图像、视频和方言字段按目标条件出现，未使用字段不得填充占位文本。
- ComfyUI 实际执行测试属于 `skills/character-video-pipeline/`，不属于本计划的验收标准。
- 不执行 Git commit 或 push，除非用户在执行阶段明确授权。

## 文件结构与职责

### 新建

- `skills/prompt-forge/dialects/index.json`：纯提示词方言注册表索引。
- `skills/prompt-forge/dialects/image.json`：Anima、Flux、Qwen、SD、Seedream、GPT Image 等图像方言。
- `skills/prompt-forge/dialects/video.json`：LTX、Wan、Kling、Seedance、Sora 等视频方言。
- `skills/prompt-forge/styles/index.json`：风格包索引和可用视觉轴。
- `skills/prompt-forge/styles/visual-language.json`：medium、lighting、composition、color、material、grain、depth、motion 词汇。
- `skills/prompt-forge/internals/dialect_lookup.py`：精确方言 ID/别名解析，不做模糊执行匹配。
- `skills/prompt-forge/internals/style_lookup.py`：显式风格匹配和建议，不自动注入风格事实。
- `skills/prompt-forge/internals/prompt_package.py`：PromptPackage schema、字段条件和质量结果。
- `skills/prompt-forge/internals/tests/fixtures/`：按方言和风格组织的新黄金样例。

### 修改

- `skills/prompt-forge/SKILL.md`：改为 LLM-first 生成协议。
- `skills/prompt-forge/SPEC.md`：改为 PromptPackage 和四象限证据合同。
- `skills/prompt-forge/references/prompt-contracts.md`：删除执行字段，补充条件字段和 LLM provenance。
- `skills/prompt-forge/references/image-dialects.md`：引用新方言注册表。
- `skills/prompt-forge/references/video-dialects.md`：拆分通用视频原则和 LTX/其他模型专属规则。
- `skills/prompt-forge/internals/intent_normalize.py`：输出 CreativeEvidence 和四象限账本。
- `skills/prompt-forge/internals/prompt_compile.py`：保留模块名供当前导入使用，但改成只验证 LLM 草稿并输出 PromptPackage。
- `skills/prompt-forge/internals/tag_lookup.py`：只保留 exact/approved-alias 校验。
- `skills/prompt-forge/internals/evaluate.py`：改为纯提示词质量评测。
- `skills/prompt-forge/internals/tests/`：替换旧 recipe、工作流和通用视频测试。
- `application-inventory.md`、`docs/architecture.md`、`docs/USAGE.md`：修正 Prompt Forge 的边界说明。

### 删除或移出技能运行时

- `skills/prompt-forge/recipes/MODELS.md`
- `skills/prompt-forge/internals/recipe_lookup.py`
- `skills/prompt-forge/internals/recipe_yaml.py`
- `skills/prompt-forge/internals/scene_match.py`
- `skills/prompt-forge/aesthetics/concept-archetypes.md`
- `skills/prompt-forge/aesthetics/video-archetypes.md`
- `skills/prompt-forge/negative/negative-prompts.md`
- `skills/prompt-forge/hardware/8gb.json`
- `skills/prompt-forge/dictionary/danbooru.csv`
- `skills/prompt-forge/dictionary/wd14-tags.csv`
- `skills/prompt-forge/internals/build_tag_index.py`
- `skills/prompt-forge/.pytest_cache/`
- `skills/prompt-forge/.ruff_cache/`
- `skills/prompt-forge/internals/__pycache__/`

`dictionary/tag-index.json` 和 `dictionary/zh-en.json` 继续作为运行时语言资料；原始 CSV 与构建脚本移到维护工具目录或从插件包移除。

---

### Task 1: 建立方言和风格注册表

**Files:**
- Create: `skills/prompt-forge/dialects/index.json`
- Create: `skills/prompt-forge/dialects/image.json`
- Create: `skills/prompt-forge/dialects/video.json`
- Create: `skills/prompt-forge/styles/index.json`
- Create: `skills/prompt-forge/styles/visual-language.json`
- Test: `skills/prompt-forge/internals/tests/test_dialect_registry.py`
- Test: `skills/prompt-forge/internals/tests/test_style_registry.py`

**Interfaces:**
- `dialects/index.json` exposes canonical IDs and aliases for every supported image/video prompt dialect.
- Each dialect entry contains `id`, `modality`, `prompt_form`, `ordering`, `negative_policy`, `reference_rules`, `required_dimensions`, `forbidden_patterns`, and `source_notes`.
- Each style entry contains `id`, `axes`, `visual_fingerprint`, `renderings`, and `incompatible_styles`.

- [ ] **Step 1: Write failing registry tests.** Assert that `anima`, `flux`, `ltx_2_3`, `wan_2_7`, `kling_kuaishou`, and `sora_2_sora_2_pro` resolve to the expected modality and prompt form. Assert that `xianxia_cinematic` exposes lighting, color, composition, material and rendering data.
- [ ] **Step 2: Run the focused tests.** Run `pytest skills/prompt-forge/internals/tests/test_dialect_registry.py skills/prompt-forge/internals/tests/test_style_registry.py -q`. Expected: FAIL because registries do not exist.
- [ ] **Step 3: Add compact JSON registries.** Migrate only prompt-language knowledge from the current 81 recipe entries; exclude audio, 3D, upscale, segmentation and workflow metadata. Preserve broad image/video model coverage without making installation status part of the schema.
- [ ] **Step 4: Run the focused tests again.** Expected: PASS, including duplicate-ID, missing-field and forbidden execution-field checks.

### Task 2: Implement exact dialect and style lookup

**Files:**
- Create: `skills/prompt-forge/internals/dialect_lookup.py`
- Create: `skills/prompt-forge/internals/style_lookup.py`
- Modify: `skills/prompt-forge/internals/tests/test_dialect_registry.py`
- Modify: `skills/prompt-forge/internals/tests/test_style_registry.py`

**Interfaces:**
- `lookup_dialect(query: str, modality: str | None = None) -> dict` returns an exact canonical or approved-alias match and raises `ValueError` for an ambiguous or unknown query.
- `suggest_styles(query: str, limit: int = 3) -> list[dict]` returns explicit suggestions with scores and evidence; it never selects or injects a style.
- `render_style(style: dict, dialect: dict) -> dict` returns dialect-specific visual language without changing facts.

- [ ] **Step 1: Write failing tests.** Cover exact IDs, aliases, ambiguous substrings, modality mismatch, explicit style matches, and the rule that style suggestions do not mutate input evidence.
- [ ] **Step 2: Run focused tests.** Expected: FAIL because lookup modules do not exist.
- [ ] **Step 3: Implement exact lookup and advisory style suggestion.** Remove fuzzy execution matching and random style fallback. A fuzzy query may return suggestions only; it cannot produce a final dialect.
- [ ] **Step 4: Run focused tests.** Expected: PASS.

### Task 3: Replace PromptIntent normalization with CreativeEvidence

**Files:**
- Modify: `skills/prompt-forge/internals/intent_normalize.py`
- Create: `skills/prompt-forge/internals/tests/test_creative_evidence.py`
- Modify: `skills/prompt-forge/internals/tests/fixtures/anima-intent.json`
- Modify: `skills/prompt-forge/internals/tests/fixtures/flux-intent.json`
- Modify: `skills/prompt-forge/internals/tests/fixtures/wan-video-intent.json`

**Interfaces:**
- `normalize_evidence(payload: dict) -> dict` returns a canonical `CreativeEvidence` object.
- `CreativeEvidence` contains `shared_known`, `user_known_agent_unknown`, `assistant_known_user_unknown`, `joint_unknown`, `locked_facts`, `continuity_locks`, `style_evidence`, `asset_refs`, and `uncertainty`.
- Existing dimension values retain `origin` and `source_text`, but no dimension is promoted to fact merely because a style or dialect suggests it.

- [ ] **Step 1: Write failing tests.** Assert explicit facts survive normalization, reasonable inference remains separate, prohibited expansion cannot overlap with locks, and joint unknowns preserve a single-variable experiment.
- [ ] **Step 2: Run focused tests.** Expected: FAIL against the old `PromptIntent`-only shape.
- [ ] **Step 3: Implement the new evidence object.** Keep SHA-256 validation only for source provenance; remove workflow-specific fields and execution mode.
- [ ] **Step 4: Run focused tests.** Expected: PASS.

### Task 4: Implement PromptPackage and LLM-only validation

**Files:**
- Create: `skills/prompt-forge/internals/prompt_package.py`
- Modify: `skills/prompt-forge/internals/prompt_compile.py`
- Create: `skills/prompt-forge/internals/tests/test_prompt_package.py`
- Modify: `skills/prompt-forge/internals/tests/test_prompt_compile.py`

**Interfaces:**
- `validate_draft(draft: dict, evidence: dict, dialect: dict) -> dict` returns a `PromptPackage` with `quality` flags and `warnings`.
- `compile_prompt(evidence: dict, draft: dict | None = None, dialect_id: str | None = None) -> dict` requires `draft` in normal mode and never invents final prose.
- `lint_prompt_text(text: str, forbidden_patterns: list[str]) -> list[str]` returns deterministic text errors.

- [ ] **Step 1: Write failing tests.** Assert missing LLM draft fails, execution fields are rejected, target-specific fields are conditional, placeholders fail, and explicit facts missing from the draft are reported.
- [ ] **Step 2: Run focused tests.** Expected: FAIL because the current compiler creates fallback prose and emits execution fields.
- [ ] **Step 3: Rewrite the compiler.** Remove `recipe_lookup`, `_derived_dialect`, prose fallback and execution metadata. Resolve only the explicit dialect registry and validate the caller-supplied draft.
- [ ] **Step 4: Add image/video conditional validation.** Image dialects validate positive/negative policy; video timeline dialects validate bilingual ranges, dialogue attribution, continuity and global prompt without requiring a workflow.
- [ ] **Step 5: Run focused tests.** Expected: PASS.

### Task 5: Rebuild tag validation as a dialect utility

**Files:**
- Modify: `skills/prompt-forge/internals/tag_lookup.py`
- Modify: `skills/prompt-forge/internals/intent_normalize.py`
- Create: `skills/prompt-forge/internals/tests/test_tag_dialect.py`

**Interfaces:**
- `validate_tags(tags: list[str], index: dict, aliases: dict | None = None) -> dict` returns `validated`, `rejected`, and `duplicates`.
- Unknown tags never become canonical tags automatically.
- `tag-index.json` remains a runtime index; raw CSVs are not imported by the skill.

- [ ] **Step 1: Write failing tests.** Cover exact canonical tags, approved aliases, unknown candidates, duplicate tags, and separation of recipe control tokens from semantic tags.
- [ ] **Step 2: Run focused tests.** Expected: FAIL until the new function exists.
- [ ] **Step 3: Implement exact validation.** Keep lookup deterministic and independent from model installation or workflow state.
- [ ] **Step 4: Run focused tests.** Expected: PASS.

### Task 6: Convert style references and external documents into prompt guidance

**Files:**
- Modify: `skills/prompt-forge/aesthetics/INDEX.md`
- Modify: `skills/prompt-forge/aesthetics/style-presets.md`
- Modify: `skills/prompt-forge/aesthetics/medium-glossary.md`
- Modify: `skills/prompt-forge/aesthetics/motion-glossary.md`
- Modify: `skills/prompt-forge/references/image-dialects.md`
- Modify: `skills/prompt-forge/references/video-dialects.md`
- Modify: `skills/prompt-forge/references/prompt-contracts.md`
- Create: `skills/prompt-forge/references/creative-evidence.md`
- Create: `skills/prompt-forge/internals/tests/test_style_invariance.py`

**Interfaces:**
- `creative-evidence.md` maps the three user documents to evidence fields, without copying their report templates into final prompts.
- Style references provide language suggestions and provenance, never silent prompt injection.

- [ ] **Step 1: Write failing style-invariance tests.** Generate two style variants from the same evidence and assert identity, plot facts, props and continuity locks are unchanged.
- [ ] **Step 2: Run focused tests.** Expected: FAIL because current style matching can inject scene assumptions.
- [ ] **Step 3: Rewrite style documentation.** Remove random style selection, token-position claims, 50% motion quota and generic unsupported claims. Keep concrete visual vocabulary and model-specific rendering hints.
- [ ] **Step 4: Add evidence mapping.** Encode art bible, character asset, environment asset, prop asset, shot plan, dialogue and uncertainty fields from the three user documents.
- [ ] **Step 5: Run focused tests.** Expected: PASS.

### Task 7: Replace the old recipe/test surface

**Files:**
- Delete: `skills/prompt-forge/recipes/MODELS.md`
- Delete: `skills/prompt-forge/internals/recipe_lookup.py`
- Delete: `skills/prompt-forge/internals/recipe_yaml.py`
- Delete: `skills/prompt-forge/internals/scene_match.py`
- Delete: `skills/prompt-forge/aesthetics/concept-archetypes.md`
- Delete: `skills/prompt-forge/aesthetics/video-archetypes.md`
- Delete: `skills/prompt-forge/negative/negative-prompts.md`
- Delete: `skills/prompt-forge/hardware/8gb.json`
- Delete: `skills/prompt-forge/internals/build_tag_index.py`
- Replace: `skills/prompt-forge/internals/tests/test_recipe_lookup.py`
- Replace: `skills/prompt-forge/internals/tests/test_recipe_yaml.py`
- Replace: `skills/prompt-forge/internals/tests/test_scene_match.py`
- Replace: `skills/prompt-forge/internals/tests/test_eval_corpus.py`

- [ ] **Step 1: Add registry/evaluation coverage for every retained image/video dialect ID.** Each retained entry must have one valid and one invalid draft case.
- [ ] **Step 2: Run the old tests before deletion.** Record which tests cover removed recipe behavior; expected failures are only the cases intentionally removed by the virgin redesign.
- [ ] **Step 3: Remove obsolete source, parsers and generated caches.** Do not remove `tag-index.json` or `zh-en.json`.
- [ ] **Step 4: Run the new test matrix.** Run `pytest skills/prompt-forge/internals/tests -q`. Expected: all retained dialect, style, tag and PromptPackage tests pass.

### Task 8: Update documentation and boundary assertions

**Files:**
- Modify: `skills/prompt-forge/SKILL.md`
- Modify: `skills/prompt-forge/SPEC.md`
- Modify: `application-inventory.md`
- Modify: `docs/architecture.md`
- Modify: `docs/USAGE.md`
- Create: `skills/prompt-forge/internals/tests/test_skill_boundaries.py`

- [ ] **Step 1: Write failing boundary tests.** Assert Prompt Forge source does not import ComfyUI/MCP, does not inspect workflow profile directories, does not emit execution fields, and does not create prose without an LLM draft.
- [ ] **Step 2: Run focused boundary tests.** Expected: FAIL against current documentation and compiler imports.
- [ ] **Step 3: Rewrite public skill docs.** State that Claude/Codex author prompts, Python audits, model knowledge is dialect-only, and execution is outside scope.
- [ ] **Step 4: Update project inventory and architecture docs.** Keep the pipeline as a consumer, not a Prompt Forge dependency.
- [ ] **Step 5: Run the full Prompt Forge test suite and `git diff --check`.** Expected: PASS and clean diff.

## Self-review checklist

- Spec coverage: Tasks 1–2 cover model/style separation; Task 3 covers four-quadrant evidence; Task 4 covers LLM-only PromptPackage; Task 5 covers tag validation; Task 6 covers the three external documents and style rules; Task 7 covers virgin cleanup; Task 8 covers public boundaries.
- Placeholder scan: no task uses `TODO`, `TBD`, or unspecified implementation language; every task names exact files, interfaces, tests and expected outcomes.
- Type consistency: `normalize_evidence` feeds `validate_draft`; `lookup_dialect` supplies the dialect object; `compile_prompt` returns the PromptPackage consumed by evaluation and downstream adapters.
- Scope: the plan modifies Prompt Forge and its documentation boundary only; it does not add a model provider, MCP server or ComfyUI execution feature.
