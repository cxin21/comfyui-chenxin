---
title: prompt-forge v2.0 redesign — clean refactor, full vocabulary, multi-model ready
date: 2026-08-13
status: draft
author: claude
related:
  - D:\Projects\提示词模版.txt (NSFW template — methodology source)
  - D:\Projects\comfyui-chenxin\skills\prompt-forge\SKILL.md (current state, to be replaced)
  - D:\Projects\comfyui-chenxin\CHANGELOG.md (entry will be added)
  - D:\Projects\comfyui-chenxin\.claude-plugin\plugin.json (version will be bumped)
---

# prompt-forge v2.0 — design spec

## 1. Background

prompt-forge is the prompt authoring skill inside the `comfyui-chenxin` plugin. Today it ships three production tasks: `anima` (still image), `h3_t2va` (text-to-video-with-audio), `h3_ref2va` (reference-to-video-with-audio). Its current state has three weaknesses:

1. **SKILL.md carries Anima-specific content** (e.g., "For every Anima prompt..."), polluting a file that should be brief.
2. **No pre-flight gates** — most errors surface only in the audit, after `compile_prompt_artifact`.
3. **Anima vocabulary is sparse** — the skill has no full enumeration of tags the model knows.

A reference NSFW authoring template at `D:\Projects\提示词模版.txt` contains a complete methodology (slot order, conflict table, self-check, output protocol, tag-count statistics, decision tree, 5-segment doc structure, special themes, forbidden list). We will fully absorb that methodology into prompt-forge.

**Constraints** (locked with the user):
- Single growing skill, multi-model (option C in the comparison)
- SKILL.md ≤ 60 lines: 3 scenario briefs + ref index
- Existing 5 aesthetics files fully rewritten to 5-segment structure
- Full tag library migration
- No SFW/NSFW boundary statement
- Plugin shell changes in scope (version, CHANGELOG, marketplace)
- **Virgin rewrite** — no patches, no compat shims, no legacy aliases
- Future model extension via the same `references/dialects/<model>/` pattern

---

## 2. Design philosophy

### 2.1 Namespace hierarchy

```
references/        # how to author (concepts, methods, gates)
knowledge/         # what is true about the craft (aesthetics)
prompt_forge/      # runtime (Python package, untouched)
```

Three roles, no overlap. `references/` carries procedural knowledge; `knowledge/` carries descriptive knowledge; `prompt_forge/` is the executing code.

### 2.2 Within `references/`

Three namespaces, each a subdirectory:

- `references/shared/` — cross-model concepts (contract, method, decision tree, self-check, output protocol, natural language bridge, aesthetic coverage)
- `references/quality/` — quality gates (conflict table, tag-count ruler, style consistency, budget ruler, audit, dictionary preflight)
- `references/dialects/<model>/` — per-model content (dialect description + vocabulary + recipes)

Adding a new model = adding `references/dialects/<model>/`. No top-level surgery.

### 2.3 Within `knowledge/`

Single top-level namespace `aesthetics/` holds cross-model aesthetic concepts. Recipes move under `references/dialects/anima/recipes/` because recipes are model-specific compositions, not universal aesthetics.

### 2.4 The 5-segment template

Every vocabulary file, every recipe, every aesthetics cluster follows one template:

1. **核心公式** — one-sentence punch line
2. **变体维度表** — dimensions × tags matrix
3. **氛围链** — light-to-heavy progression (skip if no continuum)
4. **使用提示** — pitfalls and "when not to use"
5. **法典验证场景** — 2-4 proven tag combinations

This template is the format of every cluster doc. Recipes get one additional section (五层组合, see §4.18) because recipes are pre-composed 5-layer solutions — vocabulary files don't have this because they're tag libraries, not compositions. Other files (decision tree, self-check, output protocol) use their own natural format but stay ≤ 300 lines.

---

## 3. Target tree (final state)

```
prompt-forge/
├── SKILL.md                              [≤60 lines] 3-scenario brief + refs index
│
├── references/
│   ├── shared/
│   │   ├── authoring-contract.md         [≤150]  field enums + namespaces + slot weight table
│   │   ├── method.md                     [≤200]  5-step process + quality hierarchy + boundaries
│   │   ├── aesthetic-coverage.md         [≤150]  5-source retrieval flow + coverage check
│   │   ├── decision-tree.md              [≤200]  7 route branches
│   │   ├── self-check.md                 [≤120]  6 pre-flight checks
│   │   ├── output-protocol.md            [≤80]   output hard rules
│   │   └── natural-language.md           [≤100]  bridge rules
│   │
│   ├── quality/
│   │   ├── conflict-table.md             [≤150]  5 conflict categories
│   │   ├── tag-count-ruler.md            [≤120]  count percentiles + slot targets
│   │   ├── style-consistency.md          [≤100]  cross-slot worldview check + recipes
│   │   ├── budget-ruler.md               [≤100]  token formulas (existing content rewritten)
│   │   ├── audit-and-recovery.md         [≤120]  hard-gate table (existing content preserved)
│   │   └── dictionary-preflight.md       [≤80]   preflight command (existing content preserved)
│   │
│   └── dialects/
│       ├── anima/
│       │   ├── dialect.md                [≤120]  native form + dictionary + vocabulary pointer
│       │   ├── vocabulary/
│       │   │   ├── README.md             [≤100]  positioning + field mapping + constraints
│       │   │   ├── count-identity.md     [5-segment] §6 of NSFW template
│       │   │   ├── appearance.md         [5-segment] §7
│       │   │   ├── clothing.md           [5-segment] §8 + 7-dim modifications + contrast formulas
│       │   │   ├── pose-action.md        [5-segment] §9
│       │   │   ├── expression.md         [5-segment] §10 + intensity mapping
│       │   │   ├── camera-shot.md        [5-segment] §11
│       │   │   ├── scene-environment.md  [5-segment] §12
│       │   │   ├── detail-mood.md        [5-segment] §13 + tag blacklist
│       │   │   └── special-themes.md     [5-segment] §14 (cross-slot themes)
│       │   └── recipes/
│       │       ├── film-noir.md          [5-segment + 五层组合]
│       │       ├── cyberpunk-neon.md     [5-segment + 五层组合]
│       │       ├── wes-anderson-pastel.md [5-segment + 五层组合]
│       │       ├── helmut-newton-bw.md   [5-segment + 五层组合]
│       │       ├── ghibli-aesthetic.md   [5-segment + 五层组合]
│       │       └── wuxia-ink.md          [5-segment + 五层组合]
│       │
│       └── minimax-h3/
│           ├── dialect.md                [≤120]  H3 dialect (existing minimax-h3.md content)
│           └── budget-policy.json        merged from existing h3-t2va + h3-ref2va policies
│
├── knowledge/
│   └── aesthetics/
│       ├── composition.md                [5-segment] (rewritten)
│       ├── lighting.md                   [5-segment] (rewritten)
│       ├── palette.md                    [5-segment] (rewritten)
│       ├── camera.md                     [5-segment] (rewritten)
│       ├── mood-texture.md               [5-segment] (rewritten)
│       └── anti-patterns.md              [5-segment + tag blacklist] (rewritten)
│
├── scripts/
│   ├── preflight.py                      [≤200]  conflict + tag-count + style-consistency
│   ├── tag-validate.py                   [≤150]  dictionary lookup + frequency warnings
│   ├── build_anima_dictionary.py         existing
│   ├── run_benchmarks.py                 existing
│   ├── stage_release.py                  existing
│   └── verify_release.py                 existing
│
├── tests/
│   ├── test_preflight.py                 NEW
│   ├── test_tag_validate.py              NEW
│   └── ... (existing tests preserved)
│
├── prompt_forge/                         Python runtime package (UNCHANGED)
│
├── knowledge/anima/                      Dictionary assets (UNCHANGED)
│   ├── tags.sqlite
│   ├── manifest.json
│   ├── protocol.json
│   ├── budget-policy.json
│   └── sources.lock.json
│
└── (other existing: agents/, benchmarks/, pyproject.toml, AGENTS.md, README.md)
```

### Files deleted (no compat shim)

- `references/anima.md` → content + position migrated to `references/dialects/anima/dialect.md`
- `references/minimax-h3.md` → migrated to `references/dialects/minimax-h3/dialect.md`
- `references/authoring-contract.md` → moved to `references/shared/`
- `references/budget-ruler.md` → moved to `references/quality/`
- `references/audit-and-recovery.md` → moved to `references/quality/`
- `references/dictionary-preflight.md` → moved to `references/quality/`
- `references/artifact-and-budgets.md` → content subsumed by other files (no replacement needed)
- `knowledge/aesthetics/recipes/` → moved to `references/dialects/anima/recipes/`
- `knowledge/h3-t2va-budget-policy.json` → merged into `references/dialects/minimax-h3/budget-policy.json`
- `knowledge/h3-ref2va-budget-policy.json` → merged into `references/dialects/minimax-h3/budget-policy.json`

After deletion, these paths **must not exist** anywhere — verified by `find . -path '*old-path*'` returning empty.

---

## 4. File-by-file content spec

### 4.1 SKILL.md (≤ 60 lines)

```markdown
---
name: prompt-forge
description: <one-line — what the skill does, when to invoke, what models it covers>
---

# Prompt Forge

<one paragraph — method first, code second; tools verify but the LLM authors>

## Scenarios

| Task | Model | Dialect |
|---|---|---|
| anima | Anima still image | [references/dialects/anima/dialect.md](references/dialects/anima/dialect.md) |
| h3_t2va | MiniMax-H3 text-to-video-with-audio | [references/dialects/minimax-h3/dialect.md](references/dialects/minimax-h3/dialect.md) |
| h3_ref2va | MiniMax-H3 reference-to-video-with-audio | [references/dialects/minimax-h3/dialect.md](references/dialects/minimax-h3/dialect.md) |

## Method

The 5-step authoring process lives in [references/shared/method.md](references/shared/method.md).
Apply aesthetic coverage from [references/shared/aesthetic-coverage.md](references/shared/aesthetic-coverage.md).
Pre-compile check via [references/shared/self-check.md](references/shared/self-check.md).

## References index

### Shared (cross-model)
- authoring-contract · method · aesthetic-coverage · decision-tree · self-check · output-protocol · natural-language

### Quality (gates)
- conflict-table · tag-count-ruler · style-consistency · budget-ruler · audit-and-recovery · dictionary-preflight

### Dialects (per model)
- anima/dialect · anima/vocabulary · anima/recipes
- minimax-h3/dialect · minimax-h3/budget-policy

## Tool

`compile_prompt_artifact(task, request)` → `{ref_id, prompt, metadata}`.
Audit via `get_build_audit(ref_id)` if status is `quality_rejected` or `budget_conflict`.

## Scripts

- `scripts/preflight.py` — pre-compile quality gates
- `scripts/tag-validate.py` — tag dictionary lookup
```

No content beyond this. Any drift (Anima-specific instructions, "how to write a wasteland prompt") is a violation.

### 4.2 `references/shared/authoring-contract.md`

Source: rewrites existing `references/authoring-contract.md`, adds the **前重后轻** (front-weighted) declaration explicitly, adds a field × slot weight table.

Sections:
- Request shape (fact / segment / complexity / exclusion_groups)
- Positive field enums (14 fields, one per row)
- Negative field enums (5 fields)
- Reserved namespaces (score_N, year, @artist)
- Tag form (spaces, underscores only for reserved)
- One tag per segment rule (re-emphasized)
- **Slot weight table** — explicit priority of each field
- Segment compressibility (mandatory vs compressible)
- Bridge rules (dimension whitelist)

### 4.3 `references/shared/method.md`

Source: derived from existing SKILL.md "The authoring method" + "Quality hierarchy" + "Output boundary" + "Script boundary" sections.

Sections:
- 5-step process (each step: 1-paragraph "what to do" + 1-link "details in <ref>")
- Quality hierarchy (5 layers, ordered)
- Output boundary (how `prompt` dict flows to camera-image / camera-video)
- Script boundary (what scripts may do; what they must not)

### 4.4 `references/shared/aesthetic-coverage.md`

Source: derived from existing SKILL.md "Aesthetic coverage (mandatory retrieval)" section.

Sections:
- The five required sources (5 links to `knowledge/aesthetics/*.md` + 1 line each)
- How to apply (6 numbered steps)
- Coverage check (each layer ≥ 1 agent_embellishment fact)
- When to ignore (text-only, sticker, schematic)

### 4.5 `references/shared/decision-tree.md`

Source: derived from NSFW template §5 ASSEMBLY DECISION TREE, but with all NSFW-specific naming renamed to generic.

Branches (7):
1. `single_subject` — 1 subject, subject is focus
2. `two_subject_soft_interaction` — 2 subjects, low-intensity interaction
3. `two_subject_full_interaction` — 2 subjects, high-intensity interaction
4. `two_subject_special_position` — 2 subjects + unconventional framing
5. `multi_subject` — 3+ subjects
6. `two_subject_same_type` — same-type pair (双女 / 双男)
7. `cross_slot_theme` — cross-slot themes (围困 / 战后 / 仪式 / etc.)

Each branch (4 lines): typical brief · slot emphasis · camera recommendation · skipped slots.

### 4.6 `references/shared/self-check.md`

Source: derived from NSFW template §3 FINAL SELF-CHECK.

6 checks:
1. 人数一致 — `count` matches actual characters
2. 互斥冲突 — see `quality/conflict-table.md`
3. 重复标签 — same tag not twice
4. 场景物理合理 — scene × action compatibility
5. 风格一致 — see `quality/style-consistency.md`
6. 标签总数 — see `quality/tag-count-ruler.md`

Each check: 1-line pass criterion + link to detailed table.

### 4.7 `references/shared/output-protocol.md`

Source: derived from NSFW template §2 OUTPUT PROTOCOL.

Hard rules:
1. Single line, no newlines
2. Separator `", "` (comma + space)
3. Lowercase only (score_* keeps underscore)
4. No `(tag:1.2)` weight syntax
5. No markdown / code fences / preamble
6. Bridge at end (if used)

### 4.8 `references/shared/natural-language.md`

Source: derived from NSFW template §4.4 NATURAL LANGUAGE USAGE.

Sections:
- When required (multi-char attribution, spatial relations, special pose combos, storyboard contrast)
- Rules (≤1 bridge, end position, fact dimension whitelist: ownership/spatial/causal/result/relation, no tag-bridge overlap)

### 4.9 `references/quality/conflict-table.md`

Source: derived from NSFW template §3.1 CONFLICT TABLE.

5 categories:
- 视角冲突 (view conflict) — 4 rows
- 身份冲突 (identity conflict) — 4 rows
- 服装状态冲突 (clothing state conflict) — 3 rows
- 动作体位冲突 (action conflict) — 3 rows
- 细节过度 (detail excess) — 3 rows + the "≤2 state tags per body part" rule

### 4.10 `references/quality/tag-count-ruler.md`

Source: derived from NSFW template §4.2 (percentile stats).

Two tables:
- Total count percentiles (simple/standard/complex × p50/p75/p90/hard cap)
- Per-slot targets (8 rows: count/gender, character/series, appearance, clothing/state, pose/action, expression, camera/shot, scene/environment; each with min/max)

### 4.11 `references/quality/style-consistency.md`

Source: derived from NSFW template §4.1 STYLE CONSISTENCY.

Sections:
- Check list (3 items)
- Common worldview recipes (古风 / 赛博 / 末世 / 日常 / 中世纪 / 当代奇幻 — each 2-3 lines)

### 4.12 `references/quality/budget-ruler.md`

Source: existing content rewritten with link to `tag-count-ruler.md`.

Sections:
- token formula
- relationship to tag count
- soft / quality boundaries

### 4.13 `references/quality/audit-and-recovery.md`

Source: existing content preserved; added header note: "Preflight catches common errors. Audit catches schema errors. Together they form the quality gate."

### 4.14 `references/quality/dictionary-preflight.md`

Source: existing content preserved; added header note: "Python implementation: `scripts/tag-validate.py`."

### 4.15 `references/dialects/anima/dialect.md`

Source: replaces existing `references/anima.md`.

Sections:
- Native form (positive order: quality/meta/year/safety → count → character → copyright → artist → general → bridge)
- Built-in dictionary (points to `knowledge/anima/`)
- Vocabulary (points to `vocabulary/README.md`)
- Token limit (32,768 physical + calibrated quality)

### 4.16 `references/dialects/anima/vocabulary/README.md`

Sections:
- Positioning (Anima's full tag vocabulary; dictionary ≠ creation instruction)
- Field mapping (each vocabulary file → authoring-contract field)
- Usage constraints (must pass self-check + style-consistency + tag-count; frequency warnings from tag-validate.py)
- Cross-reference (links to each of the 9 vocabulary files)

### 4.17 `references/dialects/anima/vocabulary/*.md` (9 files, 5-segment)

Each file follows the canonical 5-segment template (§2.4). Mapping:

| File | NSFW template section | Tag count est. |
|---|---|---|
| count-identity.md | §6 | ~30 |
| appearance.md | §7 (hair/eyes/body/non-human/marks) | ~150 |
| clothing.md | §8 + 7-dim modifications + contrast formulas | ~250 |
| pose-action.md | §9 (single/dual/multi/storyboard) | ~100 |
| expression.md | §10 + intensity mapping | ~80 |
| camera-shot.md | §11 | ~60 |
| scene-environment.md | §12 | ~120 |
| detail-mood.md | §13 + tag blacklist | ~80 |
| special-themes.md | §14 (cross-slot) | ~150 |

### 4.18 `references/dialects/anima/recipes/*.md` (6 files, 5-segment + 五层组合)

Each recipe follows the 5-segment template PLUS an additional 五层组合 section (composition/lighting/palette/camera/mood-texture) extracted from existing recipes/.

Recipes: film-noir · cyberpunk-neon · wes-anderson-pastel · helmut-newton-bw · ghibli-aesthetic · wuxia-ink.

### 4.19 `references/dialects/minimax-h3/dialect.md`

Source: existing `references/minimax-h3.md` content, moved verbatim. Added pointer to `budget-policy.json`.

### 4.20 `references/dialects/minimax-h3/budget-policy.json`

Source: merged from existing `knowledge/h3-t2va-budget-policy.json` + `knowledge/h3-ref2va-budget-policy.json`.

Schema: `{ "t2va": {...}, "ref2va": {...} }`. If schemas conflict, raise during merge.

### 4.21 `knowledge/aesthetics/*.md` (6 files, 5-segment)

Each file rewritten to 5-segment template. Each cluster (framing / angle / layout for composition; quality / direction / source for lighting; etc.) is one entry inside its file.

### 4.22 `knowledge/aesthetics/anti-patterns.md`

Source: existing content rewritten + new "tag blacklist" section.

Structure:
- 核心公式 — "this file is the override layer"
- 变体维度表 — table of (category | wrong pattern | correct replacement)
  - Replaces existing A-G sections with concrete tag pairs
  - Includes all items from NSFW template §13.6 forbidden list
- 使用提示 — blackandwhite → monochrome; 等
- 法典验证场景 — 2 examples: compliant prompt + violation prompt + fixed version

### 4.23 `scripts/preflight.py`

```python
def preflight_check(segments: list[dict], complexity: dict) -> dict:
    """Returns {ok: bool, errors: list[str], warnings: list[str]}."""
    # 1. Conflict check (delegates to references/quality/conflict-table.md logic)
    # 2. Tag count check (delegates to references/quality/tag-count-ruler.md)
    # 3. Style consistency check (delegates to references/quality/style-consistency.md)
```

The script encodes the rules in those three files. If the rules change, the script changes; the script is the canonical implementation of those rules.

### 4.24 `scripts/tag-validate.py`

```python
def validate_tag(tag: str) -> dict:
    """Returns {canonical: str, frequency: int, verified: bool, alias: bool}."""
    # 1. Look up in knowledge/anima/tags.sqlite
    # 2. Return canonical form if alias
    # 3. Return frequency from manifest
    # 4. Mark unverified if not in dictionary
```

### 4.25 Tests (2 files)

`tests/test_preflight.py`:
- Test conflict detection: `pov` + `full body` → error
- Test tag count: too many tags → warning
- Test style consistency: hanfu + cyberpunk city → error

`tests/test_tag_validate.py`:
- Test canonical lookup: `male` → `male_focus`
- Test alias: `holding katana` → `holding_sword`
- Test unverified: `quantum chrome` → unverified: True

---

## 5. The 5-segment template (canonical form)

```markdown
# <主题>

## 核心公式
> 一句话点睛 — 这一类内容在视觉/语义上"做什么"。

## 变体维度表
| 维度 | 可选标签 |
|---|---|
| <维度名> | `tag_a` / `tag_b` / `tag_c` |
| <维度名> | `tag_d` / `tag_e` |

## 氛围链
<起点> → <中段> → <极端>

(omit if no continuum)

## 使用提示
- 避坑 1
- 避坑 2

## 法典验证场景
### 场景 A
tags: `tag1, tag2, ...`
备注：何时使用

### 场景 B
tags: `tag1, tag2, ...`
备注：...
```

**Rules**:
- `法典验证场景` tags MUST be drawn from the same file's `变体维度表` (no cross-file borrowing)
- `氛围链` is omitted only when no continuum exists (e.g., discrete counts)
- `使用提示` is never omitted
- Minimum 2 scenarios; maximum 4 scenarios

---

## 6. Reference map (who cites whom)

| File | Cites |
|---|---|
| `SKILL.md` | `shared/method.md`, `shared/aesthetic-coverage.md`, `shared/self-check.md`, `dialects/anima/dialect.md`, `dialects/minimax-h3/dialect.md` |
| `shared/method.md` | `shared/authoring-contract.md`, `shared/aesthetic-coverage.md`, `shared/self-check.md`, `quality/audit-and-recovery.md`, `quality/budget-ruler.md` |
| `shared/aesthetic-coverage.md` | `knowledge/aesthetics/*.md` (6 files) |
| `shared/decision-tree.md` | `shared/natural-language.md`, `shared/output-protocol.md` |
| `shared/self-check.md` | `quality/conflict-table.md`, `quality/tag-count-ruler.md`, `quality/style-consistency.md` |
| `shared/natural-language.md` | `shared/output-protocol.md` |
| `shared/authoring-contract.md` | (terminal — defines the schema) |
| `quality/budget-ruler.md` | `quality/tag-count-ruler.md` |
| `quality/audit-and-recovery.md` | (terminal — error codes) |
| `quality/dictionary-preflight.md` | `scripts/tag-validate.py` |
| `quality/conflict-table.md` | (terminal — conflict data) |
| `quality/tag-count-ruler.md` | (terminal — count data) |
| `quality/style-consistency.md` | (terminal — worldview recipes) |
| `dialects/anima/dialect.md` | `dialects/anima/vocabulary/README.md`, `knowledge/anima/` |
| `dialects/anima/vocabulary/README.md` | `shared/authoring-contract.md` (fields), `dialects/anima/vocabulary/*.md` (9 files) |
| `dialects/anima/vocabulary/*.md` | (mostly terminal — vocabulary data; cite `scripts/tag-validate.py`) |
| `dialects/anima/recipes/*.md` | `knowledge/aesthetics/*.md` (5 layers) |
| `dialects/minimax-h3/dialect.md` | `dialects/minimax-h3/budget-policy.json` |
| `knowledge/aesthetics/*.md` | (terminal — concept data) |

**Cited by** (reverse map):

| Cited file | Cited by |
|---|---|
| `shared/authoring-contract.md` | `SKILL.md`, `shared/method.md`, `dialects/anima/vocabulary/README.md` |
| `shared/method.md` | `SKILL.md` |
| `shared/aesthetic-coverage.md` | `SKILL.md`, `shared/method.md` |
| `shared/decision-tree.md` | `SKILL.md` |
| `shared/self-check.md` | `SKILL.md`, `shared/method.md` |
| `shared/natural-language.md` | `shared/decision-tree.md` |
| `shared/output-protocol.md` | `shared/decision-tree.md`, `shared/natural-language.md` |
| `quality/conflict-table.md` | `shared/self-check.md`, `scripts/preflight.py` |
| `quality/tag-count-ruler.md` | `shared/self-check.md`, `quality/budget-ruler.md`, `scripts/preflight.py` |
| `quality/style-consistency.md` | `shared/self-check.md`, `scripts/preflight.py` |
| `quality/budget-ruler.md` | `shared/method.md` |
| `quality/audit-and-recovery.md` | `shared/method.md` |
| `quality/dictionary-preflight.md` | (referenced from SKILL index) |
| `dialects/anima/dialect.md` | `SKILL.md` |
| `dialects/anima/vocabulary/README.md` | `dialects/anima/dialect.md` |
| `knowledge/aesthetics/*.md` | `shared/aesthetic-coverage.md`, `dialects/anima/recipes/*.md` |
| `scripts/preflight.py` | `SKILL.md` |
| `scripts/tag-validate.py` | `SKILL.md`, `quality/dictionary-preflight.md` |

If after implementation any reference link is broken (404 / file not found), the implementation is incomplete.

---

## 7. Implementation phases

### Phase 1 — Skeleton + contracts (P0, 1-2 days)

1. Create `references/{shared,quality,dialects}/` directories
2. Write `references/shared/authoring-contract.md` (rewritten)
3. Write `references/shared/method.md` (from SKILL.md 整体下沉)
4. Write `references/shared/aesthetic-coverage.md` (from SKILL.md 整体下沉)
5. Rewrite `SKILL.md` (≤ 60 lines)
6. Delete old `references/{anima,minimax-h3,budget-ruler,audit-and-recovery,dictionary-preflight,artifact-and-budgets}.md`

Exit criteria:
- `find . -path '*references/anima.md'` returns empty
- SKILL.md ≤ 60 lines
- Each new file ≤ line cap (§4)

### Phase 2 — Quality gates + shared process (P0, 1-2 days)

1. `references/quality/conflict-table.md`
2. `references/quality/tag-count-ruler.md`
3. `references/quality/style-consistency.md`
4. `references/quality/budget-ruler.md` (rewritten)
5. `references/quality/audit-and-recovery.md` (preserved + header note)
6. `references/quality/dictionary-preflight.md` (preserved + header note)
7. `references/shared/decision-tree.md`
8. `references/shared/self-check.md`
9. `references/shared/output-protocol.md`
10. `references/shared/natural-language.md`

Exit criteria:
- All 10 files exist, each ≤ line cap
- `references/shared/self-check.md` correctly links to all 3 quality files
- `references/shared/method.md` correctly links to all shared/ files

### Phase 3 — Anima dialect + vocabulary + recipes (P1, 3-5 days)

1. `references/dialects/anima/dialect.md`
2. `references/dialects/anima/vocabulary/README.md`
3. 9 files under `vocabulary/` (5-segment each)
4. 6 files under `recipes/` (5-segment + 五层组合 each)
5. `references/dialects/minimax-h3/dialect.md`
6. `references/dialects/minimax-h3/budget-policy.json` (merge)

Exit criteria:
- 17 new files in `references/dialects/`
- Each vocabulary file: 5 segments present, 法典例 tags all from same-file 变体维度表
- Each recipe: 5 segments + 五层组合 section

### Phase 4 — Aesthetics knowledge (P0, 1-2 days)

1. `knowledge/aesthetics/composition.md` (5-segment)
2. `knowledge/aesthetics/lighting.md` (5-segment)
3. `knowledge/aesthetics/palette.md` (5-segment)
4. `knowledge/aesthetics/camera.md` (5-segment)
5. `knowledge/aesthetics/mood-texture.md` (5-segment)
6. `knowledge/aesthetics/anti-patterns.md` (5-segment + tag blacklist)

Exit criteria:
- All 6 files have all 5 segments
- anti-patterns.md blacklist covers NSFW template §13.6 items

### Phase 5 — Scripts + tests (P1, 1 day)

1. `scripts/preflight.py`
2. `scripts/tag-validate.py`
3. `tests/test_preflight.py`
4. `tests/test_tag_validate.py`

Exit criteria:
- `pytest tests/test_preflight.py tests/test_tag_validate.py` passes
- `preflight_check()` on wasteland prompt returns `ok: true`
- `preflight_check()` on `pov` + `full body` returns `ok: false` with conflict error

### Phase 6 — Validation + plugin shell (P2, 1 day)

1. Compile 5 test prompts (1 single · 1 dual · 1 multi · 1 themed · 1 H3)
2. Compare output before/after for wasteland prompt
3. `find . -path '*old-path*'` returns empty
4. `plugin.json` version 0.2.0
5. `.claude-plugin/marketplace.json` sync
6. `CHANGELOG.md` new entry

---

## 8. Post-implementation self-check

Run **all** of these after implementation. Any failure = block release.

### 8.1 Structural checks

```bash
# No compat shim
grep -rn 'legacy\|deprecated\|backward compat\|migrated from' skills/prompt-forge/
# Expected: no matches

# Old paths gone
find skills/prompt-forge -path '*references/anima.md' -o -path '*references/minimax-h3.md' \
  -o -path '*references/authoring-contract.md' -o -path '*references/budget-ruler.md' \
  -o -path '*references/audit-and-recovery.md' -o -path '*references/dictionary-preflight.md' \
  -o -path '*references/artifact-and-budgets.md' -o -path '*knowledge/aesthetics/recipes/*'
# Expected: no output

# File counts match the target tree (§3)
ls references/shared/ | wc -l    # Expected: 7
ls references/quality/ | wc -l   # Expected: 6
ls references/dialects/anima/vocabulary/ | wc -l  # Expected: 10
ls references/dialects/anima/recipes/ | wc -l     # Expected: 6
ls knowledge/aesthetics/ | wc -l # Expected: 6 (no recipes subdir)

# Line caps respected (references/ ≤ 300, knowledge/ ≤ 350)
find skills/prompt-forge/references -name '*.md' -exec wc -l {} + | awk '$1 > 300 {print}'
# Expected: no output
find skills/prompt-forge/knowledge -name '*.md' -exec wc -l {} + | awk '$1 > 350 {print}'
# Expected: no output

# SKILL.md brief
wc -l skills/prompt-forge/SKILL.md  # Expected: 40-60
```

### 8.2 Reference closure

```bash
# All relative links resolve
find skills/prompt-forge -name '*.md' -exec grep -h -oE '\]\([^)]+\.md[^)]*\)' {} + | \
  sed 's/.*(\(.*\))/\1/' | sort -u | while read f; do
    test -f "skills/prompt-forge/$f" || echo "BROKEN: $f"
done
# Expected: no BROKEN lines

# Recipes/ vocabulary link to right paths
grep -l 'composition.md' references/dialects/anima/recipes/*.md | wc -l  # Expected: 6
grep -l 'lighting.md' references/dialects/anima/recipes/*.md | wc -l     # Expected: 6
```

### 8.3 5-segment structure

```bash
# Every vocabulary/recipe/aesthetics file has all 5 segments
for f in $(ls references/dialects/anima/vocabulary/*.md references/dialects/anima/recipes/*.md \
           knowledge/aesthetics/*.md); do
  for seg in '核心公式' '变体维度表' '使用提示' '法典验证场景'; do
    grep -q "## $seg" "$f" || echo "MISSING $seg in $f"
  done
done
# Expected: no MISSING lines

# Vocabulary/recipe has 氛围链 or explicitly skipped (not missing)
# No automated check — manual review of files where 氛围链 is omitted
```

### 8.4 Functional tests

```bash
# Run pytest
cd skills/prompt-forge
pytest tests/test_preflight.py tests/test_tag_validate.py -v
# Expected: all pass

# Compile 5 test prompts
python -c "
from prompt_forge.api import compile_prompt_artifact
for task in ['anima', 'anima', 'anima', 'anima', 'h3_t2va']:
    request = {...}
    result = compile_prompt_artifact(task, request)
    assert result['metadata']['status'] == 'production_ready', f'Failed: {task}'
print('all 5 compiled')
"
# Expected: all 5 compiled

# Run preflight on wasteland prompt
python -c "
from scripts.preflight import preflight_check
result = preflight_check(wasteland_segments, wasteland_complexity)
assert result['ok'], result
print('wasteland ok')
"
# Expected: wasteland ok

# Negative test: pov + full body should fail preflight
python -c "
from scripts.preflight import preflight_check
result = preflight_check([{'field': 'camera', 'text': 'pov'}, {'field': 'camera', 'text': 'full body'}], {})
assert not result['ok']
assert any('pov' in e for e in result['errors'])
print('conflict caught')
"
# Expected: conflict caught
```

### 8.5 Plugin shell

```bash
# Version bumped
grep '"version"' .claude-plugin/plugin.json
# Expected: "0.2.0"

# Marketplace in sync
diff <(jq -S '.version, .description' .claude-plugin/plugin.json) \
     <(jq -S '.version, .description' .claude-plugin/marketplace.json)
# Expected: no diff

# CHANGELOG entry
head -30 CHANGELOG.md | grep -q '0.2.0'
# Expected: match
```

### 8.6 Drift guard

```bash
# All relative .md links must resolve (already in 8.2)
# All files referenced from SKILL.md exist
grep -oE '\[.*\]\((references/[^)]+)\)' SKILL.md | sed 's/.*(\(.*\))/\1/' | sort -u | while read f; do
  test -f "$f" || echo "MISSING from SKILL: $f"
done
# Expected: no MISSING lines

# Tag forms: no underscores in non-reserved tags
# (manual: scan a few sample prompts to confirm)
```

---

## 9. Document reference index (drift prevention)

This section is the implementer's navigation aid. If you lose context, come back here.

### 9.1 By task

| Task | Read first | Then |
|---|---|---|
| Authoring Anima prompt | `shared/method.md` | `shared/authoring-contract.md` → `shared/aesthetic-coverage.md` → `knowledge/aesthetics/*.md` → `dialects/anima/dialect.md` → `dialects/anima/vocabulary/README.md` |
| Authoring H3 prompt | `shared/method.md` | `dialects/minimax-h3/dialect.md` |
| Diagnosing compile failure | `shared/self-check.md` | `quality/conflict-table.md` → `quality/audit-and-recovery.md` |
| Adding new tag vocabulary | `dialects/anima/vocabulary/README.md` | relevant `vocabulary/*.md` |
| Adding new recipe | any existing `dialects/anima/recipes/*.md` | template structure + `knowledge/aesthetics/*.md` |
| Adding new model | `dialects/anima/dialect.md` (as template) | create `dialects/<model>/{dialect,vocabulary,recipes}/` |

### 9.2 By file type

| Type | Path pattern |
|---|---|
| Skill entry | `SKILL.md` |
| Concept (cross-model) | `references/shared/*.md` |
| Gate (audit/check) | `references/quality/*.md` |
| Per-model | `references/dialects/<model>/*.md` |
| Per-model vocabulary | `references/dialects/<model>/vocabulary/*.md` |
| Per-model recipe | `references/dialects/<model>/recipes/*.md` |
| Aesthetic concept | `knowledge/aesthetics/*.md` |
| Runtime | `prompt_forge/*.py` |
| Dictionary assets | `knowledge/<model>/*.sqlite|json` |
| Tooling | `scripts/*.py` |

### 9.3 Anti-drift signals

If you find yourself doing any of these, STOP and check this spec:

- Adding a "legacy" or "deprecated" comment anywhere
- Adding a backward-compat alias or shim
- Moving a file's content instead of rewriting it
- Keeping an old path alive alongside a new path
- Adding a new top-level directory under `references/` or `knowledge/`
- Naming a file outside the documented pattern
- Adding content to SKILL.md beyond the index structure
- Cross-file tag borrowing in 法典验证场景

Each of these is a signal that the implementation is drifting from this spec.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Vocabulary file is too large to write | Split by sub-cluster (e.g., appearance/hair.md, appearance/eyes.md) — but only if a single file exceeds 500 lines |
| Recipe content lost during 5-segment rewrite | Cross-reference: each new recipe's 变体维度表 must include all original tags |
| Conflict table missing edge case | Add to conflict-table.md as encountered; document additions in CHANGELOG |
| Preflight script too restrictive | Soft warnings (not errors) by default; promote to errors only after observation |
| Min routes in decision tree too generic | Each branch has 4 specific lines (brief / slots / camera / skipped) — fail review if vague |
| H3 budget policy merge loses info | Pre-merge diff; raise during merge if schemas differ |

---

## 11. Acceptance criteria

The redesign is complete when:

1. All 6 phases exit criteria pass
2. All checks in §8 (post-implementation self-check) return expected results
3. 5 test prompts (1 single, 1 dual, 1 multi, 1 themed, 1 H3) compile to `production_ready`
4. Old wasteland battle prompt from this session compiles AND now uses 5-layer aesthetic coverage (verifiable by reading the produced positive prompt)
5. `preflight.py` catches known conflicts
6. `find . -path '*old-path*'` returns empty
7. `CHANGELOG.md` documents v0.2.0
8. `plugin.json` reads `"version": "0.2.0"`

Then user pushes git, reinstalls plugin, and observes no regression in subsequent authoring sessions.

---

## 12. Out of scope

- Adding new tasks beyond anima / h3_t2va / h3_ref2va
- Changing the Python runtime (`prompt_forge/` package)
- Changing the dictionary acquisition (`scripts/build_anima_dictionary.py`)
- Changing benchmark methodology
- Changing mcp_server/ code
- Adding new tests beyond what's needed to verify this redesign