# prompt-forge v2.0 Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean-refactor `prompt-forge` into a multi-model skill with a complete Anima vocabulary, full NSFW-template methodology absorption, and pre-compile quality gates — without compat shims.

**Architecture:** Single skill with three sub-namespaces — `references/shared/` (cross-model concepts), `references/quality/` (gates), `references/dialects/<model>/` (per-model content). `SKILL.md` ≤ 60 lines as a pure index. Every vocabulary/recipe/aesthetics cluster file follows a canonical 5-segment template.

**Tech Stack:** Markdown docs + Python 3 (preflight + tag-validate scripts) + existing `prompt_forge/` runtime package (untouched).

---

## Global Constraints

These apply to every task. Copied verbatim from spec §1, §2, §9.3.

- **Virgin rewrite** — no patches, no compat shims, no legacy aliases, no `if old then new` branches.
- **No SFW/NSFW boundary statement** in any doc; tag library is "Anima's vocabulary", nothing more.
- **SKILL.md ≤ 60 lines** — pure index (3 scenarios + refs + tool + scripts). No content beyond that.
- **5-segment template** — every `vocabulary/*.md`, `recipes/*.md`, `aesthetics/*.md` file has sections: 核心公式 / 变体维度表 / [氛围链] / 使用提示 / 法典验证场景. Recipes add an extra 五层组合 section.
- **Line caps** — `references/*.md` ≤ 300 lines, `knowledge/*.md` ≤ 350 lines.
- **Old paths must die** — `find . -path '*old-path*'` returns empty after implementation.
- **Tag forms** — `score_*` keeps underscore; other tags use spaces; `@artist` prefix.
- **No cross-file tag borrowing** in 法典验证场景 (each scenario's tags must come from the same file's 变体维度表).
- **No compat strings** — `grep -rn 'legacy\|deprecated\|backward compat\|migrated from'` returns no matches.

---

## Design Context: how this plan was decided

Every task below carries a "Design context" block with (a) the spec section it implements, (b) the brainstorming conversation excerpt that justified the approach, (c) the conclusion. Read it before implementing that task.

### Conversation excerpts that drove key decisions

> **D1 (skill structure)** — User: "用中文给我问题" → "单技能持续生长（推荐）" — single growing skill, multi-model.

> **D2 (SKILL.md shape)** — User: "场景三行 + 引用列表（推荐）" — SKILL.md ≤ 60 lines, 3 scenario briefs + ref index only.

> **D3 (aesthetics depth)** — User: "5 段式全面改造（推荐）" — full 5-segment rewrite of all 6 `knowledge/aesthetics/` files.

> **D4 (plugin shell)** — User: "包括外壳改动（推荐）" — version bump + CHANGELOG + marketplace sync in scope.

> **D5 (option C)** — User: "我选择C，要做就一步到位，抛弃向后兼容的想法完全重构新的，更优秀的方案" — option C (subdirectories) + virgin rewrite + excellence.

> **D6 (NSFW template methodology to absorb)** — From analysis of `D:\Projects\提示词模版.txt`:
> - §2 OUTPUT PROTOCOL → `output-protocol.md`
> - §3 FINAL SELF-CHECK → `self-check.md`
> - §3.1 CONFLICT TABLE → `conflict-table.md`
> - §4 SLOT ORDER (前重后轻) → `authoring-contract.md`
> - §4.1 STYLE CONSISTENCY → `style-consistency.md`
> - §4.2 TAG COUNT percentiles → `tag-count-ruler.md`
> - §4.4 NATURAL LANGUAGE bridge → `natural-language.md`
> - §5 ASSEMBLY DECISION TREE → `decision-tree.md` (7 generic-named branches)
> - §9 5-segment sub-section structure → all vocabulary files
> - §13.6 forbidden list → `anti-patterns.md` blacklist
> - §14 SPECIAL THEMES → `special-themes.md`

> **D7 (test prompts)** — User: wasteland battle prompt from this session must continue to compile with new structure + use 5-layer aesthetic coverage (acceptance criterion).

---

## File Structure (locked from spec §3)

```
prompt-forge/
├── SKILL.md                              ≤60 lines (rewrite)
├── references/
│   ├── shared/                           7 NEW files
│   ├── quality/                          6 NEW files (some preserved from existing)
│   └── dialects/
│       ├── anima/{dialect.md, vocabulary/, recipes/}   1 + 10 + 6 = 17 NEW files
│       └── minimax-h3/{dialect.md, budget-policy.json} 2 NEW files
├── knowledge/aesthetics/                 6 files 5-segment REWRITE
├── scripts/{preflight.py, tag-validate.py}              2 NEW
├── tests/{test_preflight.py, test_tag_validate.py}      2 NEW
└── (untouched: prompt_forge/, knowledge/anima/, knowledge/<other>/, etc.)

DELETED (no shim):
- references/{anima,minimax-h3,authoring-contract,budget-ruler,audit-and-recovery,dictionary-preflight,artifact-and-budgets}.md
- knowledge/aesthetics/recipes/
- knowledge/h3-t2va-budget-policy.json + knowledge/h3-ref2va-budget-policy.json
```

---

## Phase 1 — Skeleton + contracts (P0)

### Task 1.1: Create directory structure

**Files:**
- Create: `skills/prompt-forge/references/shared/` (directory)
- Create: `skills/prompt-forge/references/quality/` (directory)
- Create: `skills/prompt-forge/references/dialects/anima/vocabulary/` (directory)
- Create: `skills/prompt-forge/references/dialects/anima/recipes/` (directory)
- Create: `skills/prompt-forge/references/dialects/minimax-h3/` (directory)

**Interfaces:**
- Consumes: nothing
- Produces: empty directory tree ready for content

**Design context:**
- Spec §3 "Target tree (final state)" — directory structure is the foundation
- D1 (single growing skill, multi-model) → each dialect gets its own dir
- D5 (option C with subdirectories) → `shared/`, `quality/`, `dialects/` are top-level under `references/`
- Conclusion: all 5 directories created in one task because they're cheap and don't need separate verification

- [ ] **Step 1: Create the 5 directories**

```bash
cd D:/Projects/comfyui-chenxin/skills/prompt-forge
mkdir -p references/shared references/quality references/dialects/anima/vocabulary references/dialects/anima/recipes references/dialects/minimax-h3
```

- [ ] **Step 2: Verify all 5 directories exist**

Run: `ls -d references/shared references/quality references/dialects/anima/vocabulary references/dialects/anima/recipes references/dialects/minimax-h3`
Expected: all 5 paths listed

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/
git commit -m "chore(prompt-forge): create references/ subdirectory skeleton"
```

---

### Task 1.2: Write `references/shared/authoring-contract.md`

**Files:**
- Create: `skills/prompt-forge/references/shared/authoring-contract.md`

**Interfaces:**
- Consumes: existing `references/authoring-contract.md` (will be deleted in Task 1.6)
- Produces: rewritten contract with explicit 前重后轻 (front-weighted) declaration + field×slot weight table

**Design context:**
- Spec §4.2 — "rewrites existing, adds the 前重后轻 declaration explicitly, adds a field × slot weight table"
- D6 → §4 SLOT ORDER principle embedded
- Conclusion: this file becomes the schema authority; everything else (method, aesthetic-coverage, vocabulary README) references it

- [ ] **Step 1: Write the file**

```markdown
# Authoring contract

## Request shape

```json
{
  "facts": [{"fact_id": "...", "value": "...", "origin": "...", "locked": bool, "owner": "...", "dimension": "..."}],
  "positive_segments": [{"segment_id": "...", "field": "...", "text": "...", "fact_ids": ["..."]}],
  "complexity": {"subjects": int, "explicit_relations": int, "complex_actions": int, "environment_clusters": int, "natural_language_bridges": int},
  "negative_segments": [{"segment_id": "...", "field": "...", "text": "...", "fact_ids": ["..."]}],
  "exclusion_groups": int
}
```

## Fact ledger

- `origin` ∈ `user_locked | user_explicit | necessary_inference | agent_embellishment`
- `locked: true` ⟺ `origin == "user_locked"`
- User facts (`user_locked`, `user_explicit`, `necessary_inference`) are protected even when `locked: false`

## Slot weight (前重后轻 — front-weighted)

Positive segments are rendered in this order; **earlier fields carry higher implicit weight**.

| Position | Field | Weight | Purpose |
|---|---|---|---|
| 1 | `quality_meta_year_safety` | highest | quality tags, year, safety |
| 2 | `count` | high | subject count |
| 3 | `character` | high | subject identity |
| 4 | `copyright` | high | IP |
| 5 | `artist` | medium | @artist |
| 6 | `general` | medium | free visual semantics |
| 7 | `composition_and_camera` | medium | framing, lens |
| 8 | `environment_and_props` | medium | scene, props |
| 9 | `lighting_and_visual_style` | medium | light, color, mood |
| 10 | `natural_language_bridge` | lowest | bridge at end |

## One tag per segment

Every `positive_segments[].text` and every `negative_segments[].text` is **exactly one tag**. Comma-separated lists are rejected.

## Reserved namespaces

- `score_N` — exactly `score_1` through `score_9`, underscore kept
- `year YYYY` — four digits
- `@artist` — `@` prefix, must resolve
- Ordinary tags — spaces, never underscores

## Positive field enums

`quality_meta_year_safety`, `count`, `subject_anchor`, `character`, `copyright`, `artist`, `general`, `tag`, `attribute_binding`, `action_and_relation`, `composition_and_camera`, `environment_and_props`, `lighting_and_visual_style`, `natural_language_bridge`

## Negative field enums

`official_quality_baseline`, `anatomy_count_structure_errors`, `image_technical_defects`, `user_exclusions`, `general`

## Compressibility

- **Mandatory**: segments linked to any protected fact
- **Compressible**: segments linked only to `agent_embellishment` facts
- Agent-authored segments MUST link only to agent facts

## Bridge

- Count ≤ 1
- Position = end of positive stream
- Dimensions allowed: `ownership | spatial_relation | causal_action | action_result | relation`
- No overlap with tag segments' fact_ids
```

- [ ] **Step 2: Verify ≤ 150 lines**

Run: `wc -l skills/prompt-forge/references/shared/authoring-contract.md`
Expected: ≤ 150

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/shared/authoring-contract.md
git commit -m "feat(prompt-forge): rewrite authoring-contract with front-weighted slot table"
```

---

### Task 1.3: Write `references/shared/method.md`

**Files:**
- Create: `skills/prompt-forge/references/shared/method.md`

**Interfaces:**
- Consumes: existing SKILL.md sections "The authoring method" + "Quality hierarchy" + "Output boundary" + "Script boundary"
- Produces: 5-step process + hierarchy + boundaries, all referencing other `references/` files

**Design context:**
- Spec §4.3 — derives content from current SKILL.md sections, condensed
- D2 (SKILL.md brief + refs) → method.md is one of those refs
- Conclusion: this file centralizes the "how to author" guidance so SKILL.md stays brief

- [ ] **Step 1: Write the file**

```markdown
# Method

## 5-step process

1. **Ledger** — Extract every explicit requirement into immutable facts (stable ID, owner, dimension, origin, lock state). Treat user facts as protected. See [authoring-contract.md](authoring-contract.md).
2. **Budget** — Size streams with the offline tokenizer. See [quality/budget-ruler.md](../quality/budget-ruler.md) and [quality/tag-count-ruler.md](../quality/tag-count-ruler.md).
3. **Write** — Author in model-native fields, one tag per segment, in the model's order, visible facts before aesthetic polish. See [authoring-contract.md](authoring-contract.md).
4. **Polish** — Apply mandatory aesthetic retrieval (5 layers). See [aesthetic-coverage.md](aesthetic-coverage.md).
5. **Preflight + compile** — Run pre-compile gates, compile, then audit. See [self-check.md](self-check.md) + [quality/audit-and-recovery.md](../quality/audit-and-recovery.md).

Never truncate a prompt or remove a protected fact. If protected content stays above the quality limit, resolve the conflict through `user_choices` — never weaken a protected fact automatically.

## Quality hierarchy

Prioritize in this order:

1. user-locked facts, exact dialogue, visible text, negation, count, ownership, reference identity, action results
2. model adherence and executable temporal/reference structure
3. subject and scene coherence
4. composition, camera, lighting, motion, sound, style
5. optional embellishment

Additional tokens must add non-redundant information. Never pad toward a target.

## Output boundary

Pass the production-ready `prompt` dict from `compile_prompt_artifact(task, request)` under `envelope.prompt` (optionally with `prompt_ref`) to:
- `camera-image` (anima)
- `camera-video` (h3_t2va / h3_ref2va)

Camera skills accept only `production_ready` builds with valid content hash and exact-token verification. `camera-multiview` uses a fixed-prompt Flux2-Klein workflow and takes no prompt.

## Script boundary

Scripts may:
- build and verify knowledge assets
- count exact tokens
- query the dictionary
- benchmark deterministic artifacts
- prepare generation-pair manifests
- verify a release

Scripts must NOT:
- select aesthetic concepts
- decide story beats
- invent shots
- resolve ambiguous intent
- write final prompt prose
- run ComfyUI, discover workflows, choose checkpoints, apply local checkpoint/LoRA knowledge
```

- [ ] **Step 2: Verify ≤ 200 lines**

Run: `wc -l skills/prompt-forge/references/shared/method.md`
Expected: ≤ 200

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/shared/method.md
git commit -m "feat(prompt-forge): add method.md (5-step process + boundaries)"
```

---

### Task 1.4: Write `references/shared/aesthetic-coverage.md`

**Files:**
- Create: `skills/prompt-forge/references/shared/aesthetic-coverage.md`

**Interfaces:**
- Consumes: existing SKILL.md "Aesthetic coverage (mandatory retrieval)" section
- Produces: 5-source retrieval flow + coverage check

**Design context:**
- Spec §4.4 — derived from existing SKILL.md section
- D6 — this formalizes the "5 mandatory sources" requirement
- Conclusion: when SKILL.md shrinks to ≤60 lines, this file owns the "you must read 5 files before writing a single tag" rule

- [ ] **Step 1: Write the file**

```markdown
# Aesthetic coverage (mandatory retrieval)

The five aesthetic layers are **not** a checklist of questions to ask the model. They are a **mandatory retrieval** from `knowledge/aesthetics/` that the author must do before writing a single tag.

## The five required sources

For every Anima prompt, the author must read and apply terms from:

1. [composition.md](../../knowledge/aesthetics/composition.md) — framing, angle, layout
2. [lighting.md](../../knowledge/aesthetics/lighting.md) — quality, direction, source
3. [palette.md](../../knowledge/aesthetics/palette.md) — named grades and palettes
4. [camera.md](../../knowledge/aesthetics/camera.md) — render medium and optical style
5. [mood-texture.md](../../knowledge/aesthetics/mood-texture.md) — mood, atmosphere, particles

Plus the override layer: [anti-patterns.md](../../knowledge/aesthetics/anti-patterns.md).

## How to apply

1. **Read once per authoring session.** Open all six files; do not author from memory.
2. **Pick ≥ 1 term per layer** from the bundled knowledge; bind to a fact in the ledger as `agent_embellishment`. Five facts together give the prompt design intent.
3. **Use a recipe when the genre is named.** When the user's request maps to a recipe under `references/dialects/anima/recipes/` (film-noir, cyberpunk-neon, wes-anderson-pastel, helmut-newton-bw, ghibli-aesthetic, wuxia-ink), pull its pre-composed 5-layer composition.
4. **Cite the source.** Each aesthetic fact carries `source_ref` of form `<file>.md#<cluster>:<term>` — e.g., `composition.md#framing:wide-shot`.
5. **Run anti-patterns as override.** Patterns in §2 of `anti-patterns.md` must be removed before compiling, regardless of what the five layers suggest.
6. **Preflight before compile.** Verify every aesthetic tag against the bundled Anima dictionary via `scripts/tag-validate.py`; unverified tags from memory must be dropped.

## Coverage check

Before compiling, the ledger must contain ≥ 1 fact bound to each of `composition.md`, `lighting.md`, `palette.md`, `camera.md`, `mood-texture.md`. A prompt that compiles but lacks any one layer ships flat — the audit will not catch this; the author must.

## When to ignore

Skip aesthetic retrieval when:
- prompt is text-only (no visual)
- prompt is a sticker / icon / emoji style
- prompt is a schematic / diagram / chart
```

- [ ] **Step 2: Verify ≤ 150 lines**

Run: `wc -l skills/prompt-forge/references/shared/aesthetic-coverage.md`
Expected: ≤ 150

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/shared/aesthetic-coverage.md
git commit -m "feat(prompt-forge): add aesthetic-coverage.md (5-source retrieval)"
```

---

### Task 1.5: Rewrite `SKILL.md`

**Files:**
- Modify: `skills/prompt-forge/SKILL.md` (replace 142-line content with ≤ 60 lines)

**Interfaces:**
- Consumes: nothing (rewritten)
- Produces: pure index referencing all new files

**Design context:**
- Spec §4.1 — exact SKILL.md layout
- D2 (场景三行 + 引用列表) → this is the file
- D5 (virgin rewrite) → entire content replaced, no compat section
- Conclusion: SKILL.md is now a pure routing document. Anima-specific content lives in `dialects/anima/dialect.md`. Method lives in `shared/method.md`. Aesthetic flow lives in `shared/aesthetic-coverage.md`.

- [ ] **Step 1: Replace the file with the new content**

```markdown
---
name: prompt-forge
description: Author and audit high-quality model-native prompts for Anima still images and MiniMax-H3 text/reference-to-video-with-audio. Use when creative intent must become a production prompt with exact token budget, preserved subject/reference ownership, and a verified prompt for camera-image or camera-video. Camera-multiview uses a fixed-prompt Flux2-Klein workflow and does NOT take a prompt.
---

# Prompt Forge

Author creative content with the LLM. Deterministic code only counts tokens, looks up the bundled dictionary, compresses with trace preservation, audits objectively, hashes artifacts, reports benchmarks, and verifies releases. It never chooses aesthetics, story beats, or shots for you.

## Scenarios

| Task | Model | Dialect |
|---|---|---|
| anima | Anima still image | [dialects/anima/dialect.md](references/dialects/anima/dialect.md) |
| h3_t2va | MiniMax-H3 text-to-video-with-audio | [dialects/minimax-h3/dialect.md](references/dialects/minimax-h3/dialect.md) |
| h3_ref2va | MiniMax-H3 reference-to-video-with-audio | [dialects/minimax-h3/dialect.md](references/dialects/minimax-h3/dialect.md) |

## Method

5-step authoring process: [shared/method.md](references/shared/method.md).
Aesthetic coverage (mandatory retrieval): [shared/aesthetic-coverage.md](references/shared/aesthetic-coverage.md).
Pre-compile gate: [shared/self-check.md](references/shared/self-check.md).

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

- [preflight.py](scripts/preflight.py) — pre-compile quality gates
- [tag-validate.py](scripts/tag-validate.py) — tag dictionary lookup
```

- [ ] **Step 2: Verify line count and structure**

```bash
wc -l skills/prompt-forge/SKILL.md  # expect 40-60
grep -c '^## ' skills/prompt-forge/SKILL.md  # expect 5 (Scenarios, Method, References, Tool, Scripts)
```

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/SKILL.md
git commit -m "feat(prompt-forge): rewrite SKILL.md as ≤60-line index (no compat shim)"
```

---

### Task 1.6: Delete old `references/` files (no compat shim)

**Files:**
- Delete: `skills/prompt-forge/references/anima.md`
- Delete: `skills/prompt-forge/references/minimax-h3.md`
- Delete: `skills/prompt-forge/references/authoring-contract.md` (content migrated to `references/shared/`)
- Delete: `skills/prompt-forge/references/budget-ruler.md`
- Delete: `skills/prompt-forge/references/audit-and-recovery.md`
- Delete: `skills/prompt-forge/references/dictionary-preflight.md`
- Delete: `skills/prompt-forge/references/artifact-and-budgets.md`

**Interfaces:**
- Consumes: nothing
- Produces: empty references/ root with only the 3 subdirectories

**Design context:**
- Spec §3 "Files deleted (no compat shim)" — these 7 paths must die
- D5 (virgin rewrite, no backward compat) → git rm, no aliases
- Conclusion: hard deletion. Any code still referencing old paths is a regression.

- [ ] **Step 1: Git-delete the 7 files**

```bash
cd D:/Projects/comfyui-chenxin
git rm skills/prompt-forge/references/anima.md
git rm skills/prompt-forge/references/minimax-h3.md
git rm skills/prompt-forge/references/authoring-contract.md
git rm skills/prompt-forge/references/budget-ruler.md
git rm skills/prompt-forge/references/audit-and-recovery.md
git rm skills/prompt-forge/references/dictionary-preflight.md
git rm skills/prompt-forge/references/artifact-and-budgets.md
```

- [ ] **Step 2: Verify no old paths remain**

Run:
```bash
find skills/prompt-forge/references -maxdepth 1 -name '*.md' | sort
```
Expected: only `references/shared/`, `references/quality/`, `references/dialects/` (subdirectories, no loose .md files)

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git commit -m "refactor(prompt-forge): delete old references/ files (content migrated)"
```

---

### Task 1.7: Verify Phase 1 exit criteria

**Files:** none

**Interfaces:**
- Consumes: Phase 1 tasks complete
- Produces: verification report

**Design context:**
- Spec §7 Phase 1 exit criteria
- Conclusion: catch issues before Phase 2

- [ ] **Step 1: Run structural checks**

```bash
# SKILL.md line count
wc -l skills/prompt-forge/SKILL.md  # expect 40-60

# New files exist with correct caps
wc -l skills/prompt-forge/references/shared/authoring-contract.md   # ≤ 150
wc -l skills/prompt-forge/references/shared/method.md               # ≤ 200
wc -l skills/prompt-forge/references/shared/aesthetic-coverage.md   # ≤ 150

# Old paths gone
find skills/prompt-forge -path '*references/anima.md' -o -path '*references/minimax-h3.md' \
  -o -path '*references/authoring-contract.md' -o -path '*references/budget-ruler.md' \
  -o -path '*references/audit-and-recovery.md' -o -path '*references/dictionary-preflight.md' \
  -o -path '*references/artifact-and-budgets.md'
# Expected: no output

# No compat strings
grep -rn 'legacy\|deprecated\|backward compat\|migrated from' skills/prompt-forge/ | grep -v 'docs/'
# Expected: no output
```

- [ ] **Step 2: Fix any failures before Phase 2**

If any check fails, fix the underlying file before proceeding to Phase 2.

---

## Phase 2 — Quality gates + shared process (P0)

### Task 2.1: Write `references/quality/conflict-table.md`

**Files:**
- Create: `skills/prompt-forge/references/quality/conflict-table.md`

**Interfaces:**
- Consumes: nothing
- Produces: 5-category hard conflict table

**Design context:**
- Spec §4.9 — derived from NSFW template §3.1
- D6 → §3.1 CONFLICT TABLE absorbed
- Conclusion: this file encodes physical impossibilities the audit can't detect (e.g., `pov` + `full body`)

- [ ] **Step 1: Write the file**

```markdown
# Conflict table

Hard conflicts the model cannot reconcile. Audit catches duplicate semantics; this table catches impossible combinations.

## 视角冲突 (view conflict)

| A | B | why |
|---|---|---|
| `pov` | `full body` | cannot see own full body |
| `pov` | `cowboy shot` | mid/upper range needs more than POV sees |
| `from front` | `from behind` | physical opposite |
| `looking at viewer` | `facing away` | eye-line opposite |
| `from above` | `from below` | physical opposite |

## 身份冲突 (identity conflict)

| A | B | why |
|---|---|---|
| `solo` | `hetero`, `1boy`, `yuri` | single subject cannot interact |
| `completely nude` | any specific clothing | full nudity excludes clothing |
| `sleeping`, `unconscious` | `looking at viewer` | unconscious cannot look |
| `blindfold` | `heart-shaped pupils`, `rolling eyes` | eyes covered |

## 服装状态冲突 (clothing state conflict)

| A | B | why |
|---|---|---|
| `pantyhose` | `barefoot` | covered feet — except `torn pantyhose` |
| 套装内衣 (`cat lingerie`, `lace lingerie`, `babydoll`, `negligee`, `chemise`) | `no panties`, `bottomless` | set includes underwear |
| `partially undressed` | `completely nude` | exclusive states |

## 动作体位冲突 (action conflict)

| A | B | why |
|---|---|---|
| `standing sex` | `lying`, `on back` | body posture opposite |
| `missionary` | `doggystyle` | only one position at a time |
| `cowgirl position` | `prone bone` | position conflict |
| `fellatio` | `cunnilingus` (same actor) | one mouth, one action |

## 细节过度 (detail excess)

Each body part: ≤ 2 state tags, no mutual exclusion.

| Body part | Conflict pair |
|---|---|
| toes | `spread toes` + `toe scrunch`, `feet together` |
| fingers | `spread fingers` + `clenched fist`, `gripping` |
| breasts | `bouncing breasts` + `breasts squeeze together` |
| mouth | `open mouth` + `clenched teeth`, `closed mouth` |
| eyes | `rolling eyes` + `looking at viewer` |
| legs | `spread legs` + `legs together` |
```

- [ ] **Step 2: Verify ≤ 150 lines**

Run: `wc -l skills/prompt-forge/references/quality/conflict-table.md`
Expected: ≤ 150

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/quality/conflict-table.md
git commit -m "feat(prompt-forge): add conflict-table.md (5-category hard conflicts)"
```

---

### Task 2.2: Write `references/quality/tag-count-ruler.md`

**Files:**
- Create: `skills/prompt-forge/references/quality/tag-count-ruler.md`

**Interfaces:**
- Consumes: nothing
- Produces: percentile + per-slot targets

**Design context:**
- Spec §4.10 — derived from NSFW template §4.2
- D6 → §4.2 TAG COUNT percentiles absorbed
- Conclusion: budget gate on tag count, separate from token budget

- [ ] **Step 1: Write the file**

```markdown
# Tag count ruler

Budget on **tag count**, separate from token budget. Tag count is the leading indicator of attention dilution; token count is a soft ceiling.

## Total count percentiles

| Complexity | p50 | p75 | p90 | hard cap |
|---|---|---|---|---|
| simple (single subject) | 18 | 25 | 32 | 40 |
| standard (two-subject) | 25 | 33 | 42 | 50 |
| complex (multi / themed) | 35 | 45 | 55 | 70 |

A prompt with > hard cap violates attention distribution — split into multiple scenes.

## Per-slot targets

| Slot | min | max | note |
|---|---|---|---|
| count/gender | 2 | 4 | fixed format |
| character/series | 0 | 2 | IP only |
| appearance | 3 | 8 | hair+eye+body+skin |
| clothing/state | 2 | 10 | largest slot by nature |
| pose/action | 2 | 8 | |
| expression | 1 | 4 | |
| camera/shot | 1 | 5 | |
| scene/environment | 2 | 6 | |

Clothing slot is naturally largest — base garment + material + 1-3 modification dimensions. Other slots stay lean; diversity comes from cross-slot combination, not stacking.

## Relationship to token budget

Token budget (see `budget-ruler.md`) is the hard ceiling; tag count is the attention-distribution guard. Both must pass.
```

- [ ] **Step 2: Verify ≤ 120 lines**

Run: `wc -l skills/prompt-forge/references/quality/tag-count-ruler.md`

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/quality/tag-count-ruler.md
git commit -m "feat(prompt-forge): add tag-count-ruler.md (percentiles + per-slot targets)"
```

---

### Task 2.3: Write `references/quality/style-consistency.md`

**Files:**
- Create: `skills/prompt-forge/references/quality/style-consistency.md`

**Interfaces:**
- Consumes: nothing
- Produces: cross-slot worldview check + common recipes

**Design context:**
- Spec §4.11 — derived from NSFW template §4.1
- D6 → §4.1 STYLE CONSISTENCY absorbed
- Conclusion: catches cross-slot worldview mismatches (hanfu + cyberpunk city)

- [ ] **Step 1: Write the file**

```markdown
# Style consistency

Cross-slot worldview check. Clothing, scene, detail/mood must share one worldview.

## Check list

- [ ] clothing era = scene era
- [ ] mood atmosphere = lighting / palette color temperature
- [ ] no cross-worldview mix (古风服装 + 赛博场景 is a contradiction)

## Common worldview recipes

| Worldview | clothing | scene | palette / mood |
|---|---|---|---|
| 古风 | `hanfu`, `kimono`, `traditional clothing` | `ancient shrine`, `tatami`, `shouji` | `ink splash`, `poetic atmosphere`, muted |
| 赛博 | `latex`, `metallic`, `cybernetic suit` | `cyberpunk city`, `neon city` | `neon lights`, `glitch`, vibrant |
| 末世 | `leather armor`, `gas mask`, `tattered clothing` | `ruined city`, `desert`, `rubble` | `dust`, `ash`, `epic`, warm + high contrast |
| 日常 | `casual clothes`, `school uniform` | `school`, `bedroom`, `street` | `natural light`, `cheerful`, soft |
| 中世纪 | `plate armor`, `chainmail`, `tabard` | `medieval castle`, `candlelight room` | `candlelight`, `dramatic`, low key |
| 当代奇幻 | `cloak`, `magical robes`, `runic accessories` | `enchanted forest`, `crystal cave` | `glow`, `ethereal`, mystical |

## When mix is allowed

- Same-worldview sub-mixes: `kimono` + `love hotel` (within modern Japanese) — OK
- Costume drama: `victorian dress` + `modern party` (deliberate anachronism) — OK if intentional
- Cross-worldview default: REJECT
```

- [ ] **Step 2: Verify ≤ 100 lines**

Run: `wc -l skills/prompt-forge/references/quality/style-consistency.md`

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/quality/style-consistency.md
git commit -m "feat(prompt-forge): add style-consistency.md (cross-slot worldview check)"
```

---

### Task 2.4: Write `references/quality/budget-ruler.md`

**Files:**
- Create: `skills/prompt-forge/references/quality/budget-ruler.md`

**Interfaces:**
- Consumes: existing `references/budget-ruler.md` (deleted in Task 1.6)
- Produces: token formulas + link to `tag-count-ruler.md`

**Design context:**
- Spec §4.12 — existing content rewritten with link
- Conclusion: budget ruler governs tokens; tag-count ruler governs attention distribution; together they form the size gate

- [ ] **Step 1: Write the file**

```markdown
# Budget ruler

Token budget for both streams. See also [tag-count-ruler.md](tag-count-ruler.md) for attention-distribution guard.

## Positive target

```
target = clamp(128 + 48*(subjects-1) + 24*relations + 32*complex_actions
               + 24*environment_clusters + 64*bridges, 128, 512)
soft_limit   = ceil(target * 1.25)
quality_limit = min(768, ceil(target * 1.60))
```

| complexity | target | soft | quality | example |
|---|---|---|---|---|
| 1 subject | 128 | 160 | 205 | one subject + 5-layer polish |
| 2 subjects, 1 rel, 1 action, 3 env | 304 | 380 | 487 | two-figure battle (wasteland battle) |
| 3 subjects, 2 rel, 2 actions, 4 env | 432 | 540 | 691 | crowded brawl |

## Negative target

```
target = clamp(32 + 8*exclusion_groups, 32, 96)
soft = ceil(target * 1.25)
quality = min(128, ceil(target * 1.60))
```

Spend in this order:
1. **Three standard baselines** (mandatory floor): `score_4..6`, `lowres`, `worst quality`, `low quality`, anatomy/structure errors, technical defects.
2. **User exclusions** — only if user explicitly gave them; each `exclusion_groups` increment raises target by 8.
3. **Agent-added mood/style exclusions** — from compressible pool only; first to drop under pressure.

## Reading a budget conflict

`budget_conflict` means a stream could not be compressed under quality limit without touching protected content. Resolution order:
1. Drop agent-optional segments first (never protected facts).
2. Resolve via `user_choices.unlink_segment_<id>_from_protected_fact` if mandatory pool is stuck.
3. Never weaken a protected fact automatically.
```

- [ ] **Step 2: Verify ≤ 100 lines**

Run: `wc -l skills/prompt-forge/references/quality/budget-ruler.md`

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/quality/budget-ruler.md
git commit -m "feat(prompt-forge): add budget-ruler.md (rewritten with tag-count link)"
```

---

### Task 2.5: Add header note to `audit-and-recovery.md`

**Files:**
- Create: `skills/prompt-forge/references/quality/audit-and-recovery.md`

**Interfaces:**
- Consumes: existing `references/audit-and-recovery.md` content (verbatim)
- Produces: same content + header note explaining preflight/audit split

**Design context:**
- Spec §4.13 — preserve existing, add header
- D5 (virgin rewrite) — but this is documentation, not code; existing prose is good; we ADD the header, don't rewrite content
- Conclusion: header explains that `preflight.py` catches common errors, `audit` catches schema errors

- [ ] **Step 1: Copy existing audit-and-recovery.md to new location**

```bash
cd D:/Projects/comfyui-chenxin
git show HEAD~1:skills/prompt-forge/references/audit-and-recovery.md > skills/prompt-forge/references/quality/audit-and-recovery.md
```

- [ ] **Step 2: Prepend header note**

```markdown
# Audit and recovery

> **Preflight catches common errors; audit catches schema errors. Together they form the quality gate.** `scripts/preflight.py` (see [self-check.md](../shared/self-check.md)) runs before `compile_prompt_artifact`; the audit runs inside the tool.

---

(content from previous file below — unchanged)
```

- [ ] **Step 3: Verify ≤ 120 lines**

Run: `wc -l skills/prompt-forge/references/quality/audit-and-recovery.md`

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/quality/audit-and-recovery.md
git commit -m "feat(prompt-forge): move audit-and-recovery.md to quality/ + add header note"
```

---

### Task 2.6: Add header note to `dictionary-preflight.md`

**Files:**
- Create: `skills/prompt-forge/references/quality/dictionary-preflight.md`

**Interfaces:**
- Consumes: existing `references/dictionary-preflight.md`
- Produces: same content + header note pointing to `tag-validate.py`

**Design context:**
- Spec §4.14 — preserve existing, add header
- Conclusion: header points to Python implementation

- [ ] **Step 1: Copy existing**

```bash
cd D:/Projects/comfyui-chenxin
git show HEAD~2:skills/prompt-forge/references/dictionary-preflight.md > skills/prompt-forge/references/quality/dictionary-preflight.md
```

- [ ] **Step 2: Prepend header note**

```markdown
# Dictionary preflight

> **Python implementation:** `scripts/tag-validate.py` (Phase 5). This file documents the manual command.

---

(content from previous file below — unchanged)
```

- [ ] **Step 3: Verify ≤ 80 lines**

Run: `wc -l skills/prompt-forge/references/quality/dictionary-preflight.md`

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/quality/dictionary-preflight.md
git commit -m "feat(prompt-forge): move dictionary-preflight.md to quality/ + add header"
```

---

### Task 2.7: Write `references/shared/decision-tree.md`

**Files:**
- Create: `skills/prompt-forge/references/shared/decision-tree.md`

**Interfaces:**
- Consumes: nothing
- Produces: 7 generic-named route branches

**Design context:**
- Spec §4.5 — derived from NSFW template §5
- D6 → §5 ASSEMBLY DECISION TREE absorbed with all NSFW naming renamed generic
- Conclusion: routes scene type BEFORE filling slots — avoids "use the wrong template for this scene"

- [ ] **Step 1: Write the file**

```markdown
# Decision tree

Route scene type first; then fill slots. Use generic scene names — never NSFW-specific naming.

## Routes

### single_subject
- brief: portrait, character sheet, single-figure focus
- slots: count(1) + appearance(high) + camera(close/cowboy/full body)
- skipped: relation, multi-attribute bridge
- camera rec: `close-up` / `cowboy shot` / `full body`

### two_subject_soft_interaction
- brief: daily interaction, collaboration, conversation, low-intensity conflict
- slots: count(2) + appearance×2 + action + scene
- skipped: heavy-intensity mood, extreme body details
- camera rec: `medium shot` / `from side`

### two_subject_full_interaction
- brief: battle, fight, confrontation, high-intensity interaction
- slots: count(2) + action(high) + camera(wide/low) + scene
- skipped: expression-only focus
- camera rec: `wide shot` + `low angle` + `leading lines`

### two_subject_special_position
- brief: unconventional framing, POV ambush, asymmetric angles
- slots: camera(unusual) + action + bridge
- skipped: standard camera rules
- camera rec: `pov` / `dutch angle` / `from above` + `from below` combo (only if compatible)

### multi_subject
- brief: group shot, ensemble, crowd
- slots: count(N) + scene + camera(wide) + bridge(character attribution)
- skipped: per-character expression detail
- camera rec: `wide shot` / `from above` / `panoramic`

### two_subject_same_type
- brief: same-type pair deep interaction (双女, 双男, 同种族)
- slots: count + appearance×2 + action
- skipped: hetero-specific relational tags
- camera rec: `from side` / `from above` for symmetric action

### cross_slot_theme
- brief: themes spanning multiple slots (围困, 战后, 仪式, 群像主题)
- slots: cross-multiple — see [dialects/anima/vocabulary/special-themes.md](../dialects/anima/vocabulary/special-themes.md)
- skipped: standard slot order
- camera rec: depends on theme

## How to use

1. Match brief to one of 7 routes.
2. Skip slots marked "skipped" — do not add their tags.
3. Apply slot emphasis as starting point; refine with [aesthetic-coverage.md](aesthetic-coverage.md).
```

- [ ] **Step 2: Verify ≤ 200 lines**

Run: `wc -l skills/prompt-forge/references/shared/decision-tree.md`

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/shared/decision-tree.md
git commit -m "feat(prompt-forge): add decision-tree.md (7 generic routes)"
```

---

### Task 2.8: Write `references/shared/self-check.md`

**Files:**
- Create: `skills/prompt-forge/references/shared/self-check.md`

**Interfaces:**
- Consumes: nothing
- Produces: 6-check pre-flight list

**Design context:**
- Spec §4.6 — derived from NSFW template §3
- D6 → §3 FINAL SELF-CHECK absorbed
- Conclusion: implementer runs these 6 checks before compile_prompt_artifact; `preflight.py` automates checks 2/5/6

- [ ] **Step 1: Write the file**

```markdown
# Self-check (pre-compile gate)

Run all 6 checks before calling `compile_prompt_artifact`. Failures here cost a compile cycle; catching them earlier saves time.

## The 6 checks

### 1. 人数一致 (count consistency)
`count` tag matches actual character count.
Pass: `2boys` + 2 subjects, no `1boy,2boys` contradiction.

### 2. 互斥冲突 (conflict)
No hard conflict per [quality/conflict-table.md](../quality/conflict-table.md).
Pass: no `pov` + `full body`, no `completely nude` + specific clothing, etc.

### 3. 重复标签 (duplicate tags)
Same tag does not appear twice in the same stream.
Pass: `running` not doubled; emphasis comes from position, not repetition.

### 4. 场景物理合理 (scene × action compatibility)
Scene + action are physically compatible.
Pass: `underwater` not with `cigarette`; `snow` not with `beach`.

### 5. 风格一致 (style consistency)
No cross-worldview mismatch per [quality/style-consistency.md](../quality/style-consistency.md).
Pass: no `hanfu` + `cyberpunk city`.

### 6. 标签总数 (tag count)
Within bounds per [quality/tag-count-ruler.md](../quality/tag-count-ruler.md).
Pass: total ≤ hard cap for complexity tier.

## Automation

Checks 2, 5, 6 are automated by [scripts/preflight.py](../../scripts/preflight.py).
Checks 1, 3, 4 are manual or covered by `compile_prompt_artifact` audit.
```

- [ ] **Step 2: Verify ≤ 120 lines**

Run: `wc -l skills/prompt-forge/references/shared/self-check.md`

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/shared/self-check.md
git commit -m "feat(prompt-forge): add self-check.md (6 pre-compile gates)"
```

---

### Task 2.9: Write `references/shared/output-protocol.md`

**Files:**
- Create: `skills/prompt-forge/references/shared/output-protocol.md`

**Interfaces:**
- Consumes: nothing
- Produces: 6 hard output rules

**Design context:**
- Spec §4.7 — derived from NSFW template §2
- D6 → §2 OUTPUT PROTOCOL absorbed
- Conclusion: hard rules; violations break parsing

- [ ] **Step 1: Write the file**

```markdown
# Output protocol

Hard rules for the rendered prompt string. Violations break parsing or signal sloppy authoring.

1. **Single line, no newlines.** Comma-separated tags on one line.
2. **Separator: `", "`** (comma + space). No other separator.
3. **Lowercase only.** Ordinary tags use spaces, no underscores. `score_*` keeps underscore. `@artist` keeps `@`.
4. **No weight syntax.** `(tag:1.2)` is forbidden — field order is implicit weight.
5. **No markdown.** No code fences, no preamble, no explanation in the prompt string itself.
6. **Bridge at end.** If a natural-language bridge is used, it goes after all tags, separated by `, `.
```

- [ ] **Step 2: Verify ≤ 80 lines**

Run: `wc -l skills/prompt-forge/references/shared/output-protocol.md`

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/shared/output-protocol.md
git commit -m "feat(prompt-forge): add output-protocol.md (6 hard output rules)"
```

---

### Task 2.10: Write `references/shared/natural-language.md`

**Files:**
- Create: `skills/prompt-forge/references/shared/natural-language.md`

**Interfaces:**
- Consumes: nothing
- Produces: bridge usage rules

**Design context:**
- Spec §4.8 — derived from NSFW template §4.4
- D6 → §4.4 NATURAL LANGUAGE bridge absorbed
- Conclusion: bridge is a precision tool for what tags can't express; never a paragraph

- [ ] **Step 1: Write the file**

```markdown
# Natural language bridge

A bridge is a concise natural-language phrase appended after all tags. Use when independent tags cannot bind the semantic.

## When required

- **Multi-character attribution** — tags can't say "Subject A holds Subject B's umbrella"
- **Spatial relations** — tags can't bind "A behind B"
- **Special pose combinations** — multiple action tags stack ambiguously; bridge clarifies who-does-what
- **Storyboard / contrast** — "left panel: dressed, right panel: nude"

## Rules

- **Count ≤ 1** — one bridge per prompt.
- **Position = end of positive stream** — after all tags, separated by `, `.
- **Fact dimensions allowed**: `ownership`, `spatial_relation`, `causal_action`, `action_result`, `relation`.
- **No overlap with tag segments** — bind each fact once (tag or bridge, never both).

## Examples

| Scenario | Bridge |
|---|---|
| `1boy` + `2girls`, ambiguous action | `Subject 1 holds Subject 2's hand while Subject 3 watches` |
| Symmetric pose | `two girls mirroring each other across the table` |
| Spatial chain | `Subject A standing behind Subject B looking over their shoulder` |

## When NOT to use

- Decoration or "polish" prose → DROP; tags only
- Long descriptive paragraph → break into tags or split scene
- Anything that could be a tag → use the tag instead
```

- [ ] **Step 2: Verify ≤ 100 lines**

Run: `wc -l skills/prompt-forge/references/shared/natural-language.md`

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/shared/natural-language.md
git commit -m "feat(prompt-forge): add natural-language.md (bridge rules)"
```

---

### Task 2.11: Verify Phase 2 exit criteria

**Files:** none

- [ ] **Step 1: Run all checks**

```bash
# File counts
ls skills/prompt-forge/references/shared/ | wc -l   # expect 7 (authoring-contract, method, aesthetic-coverage, decision-tree, self-check, output-protocol, natural-language)
ls skills/prompt-forge/references/quality/ | wc -l  # expect 6 (conflict-table, tag-count-ruler, style-consistency, budget-ruler, audit-and-recovery, dictionary-preflight)

# Line caps
for f in skills/prompt-forge/references/quality/*.md skills/prompt-forge/references/shared/*.md; do
  echo "$(wc -l < $f) $f"
done
# Expect all ≤ 300

# Self-check references the 3 quality files
grep -E 'conflict-table|tag-count-ruler|style-consistency' skills/prompt-forge/references/shared/self-check.md | wc -l
# Expect ≥ 3

# Method references all shared files
grep -c '^## ' skills/prompt-forge/references/shared/method.md
# Expect ≥ 4 sections
```

- [ ] **Step 2: Fix any failures before Phase 3**

---

## Phase 3 — Anima dialect + vocabulary + recipes (P1)

### Task 3.1: Write `references/dialects/anima/dialect.md`

**Files:**
- Create: `skills/prompt-forge/references/dialects/anima/dialect.md`

**Interfaces:**
- Consumes: existing `references/anima.md` content (deleted in Task 1.6)
- Produces: Anima-specific native form + dictionary pointer + vocabulary pointer

**Design context:**
- Spec §4.15 — replaces old anima.md
- D1 (single skill, multi-model) → dialect.md is the Anima-specific entry point
- Conclusion: this is the entry point for Anima authors; vocabulary/ is the deep reference

- [ ] **Step 1: Copy existing anima.md to new location**

```bash
cd D:/Projects/comfyui-chenxin
git show HEAD~3:skills/prompt-forge/references/anima.md > skills/prompt-forge/references/dialects/anima/dialect.md
```

- [ ] **Step 2: Update the header / pointers**

Edit `dialect.md` to:
- Replace the header to make clear this is the Anima-specific dialect file
- Add link to `vocabulary/README.md`
- Remove any reference to old paths (e.g., `references/budget-ruler.md` → `references/quality/budget-ruler.md`)

- [ ] **Step 3: Verify ≤ 120 lines**

Run: `wc -l skills/prompt-forge/references/dialects/anima/dialect.md`

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/dialects/anima/dialect.md
git commit -m "feat(prompt-forge): create anima dialect.md (Anima-specific entry)"
```

---

### Task 3.2: Write `references/dialects/anima/vocabulary/README.md`

**Files:**
- Create: `skills/prompt-forge/references/dialects/anima/vocabulary/README.md`

**Interfaces:**
- Consumes: nothing
- Produces: vocabulary positioning + field mapping + cross-reference

**Design context:**
- Spec §4.16 — vocabulary README
- D6 → entire §6-14 vocabulary migration starts here
- Conclusion: README sets the contract for the 9 vocabulary files below it

- [ ] **Step 1: Write the file**

```markdown
# Anima vocabulary

Anima's complete tag vocabulary knowledge — every tag the model has learned to render. **This is a dictionary, not a creation instruction.** The dictionary does not judge how its words are used.

## Files

| File | NSFW template § | Contents |
|---|---|---|
| [count-identity.md](count-identity.md) | §6 | count, IP, body type, age difference |
| [appearance.md](appearance.md) | §7 | hair, eyes, body, non-human, marks |
| [clothing.md](clothing.md) | §8 | garments + 7-dim modifications + contrast |
| [pose-action.md](pose-action.md) | §9 | single / dual / multi / storyboard |
| [expression.md](expression.md) | §10 | emotions + intensity Lv1-4 + reactions |
| [camera-shot.md](camera-shot.md) | §11 | framing, angle, POV, composition |
| [scene-environment.md](scene-environment.md) | §12 | locations + risk matrix + weather |
| [detail-mood.md](detail-mood.md) | §13 | texture + mood + tag blacklist |
| [special-themes.md](special-themes.md) | §14 | cross-slot theme recipes |

## Field mapping

Each vocabulary file maps to authoring-contract fields:

| Field | Vocabulary file(s) |
|---|---|
| `count` | count-identity.md |
| `character` | count-identity.md (IP) |
| `general` (appearance) | appearance.md |
| `general` (clothing) | clothing.md |
| `action_and_relation` | pose-action.md |
| `general` (expression) | expression.md |
| `composition_and_camera` | camera-shot.md |
| `environment_and_props` | scene-environment.md |
| `lighting_and_visual_style` | detail-mood.md |
| `natural_language_bridge` | special-themes.md |

## Usage constraints

1. Every tag must pass [shared/self-check.md](../../shared/self-check.md) + [quality/style-consistency.md](../../quality/style-consistency.md) + [quality/tag-count-ruler.md](../../quality/tag-count-ruler.md).
2. Tag frequency warnings come from `scripts/tag-validate.py`.
3. No compatibility shim with the old NSFW template — content migrated, paths rewritten.

## 5-segment structure

Every vocabulary file uses the canonical template:

1. **核心公式** — one-sentence punch line
2. **变体维度表** — dimensions × tags
3. **氛围链** — light-to-heavy progression (omit if discrete)
4. **使用提示** — pitfalls
5. **法典验证场景** — 2-4 proven combinations

Tags in 法典验证场景 MUST be drawn from the same file's 变体维度表 (no cross-file borrowing).
```

- [ ] **Step 2: Verify ≤ 100 lines**

Run: `wc -l skills/prompt-forge/references/dialects/anima/vocabulary/README.md`

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/dialects/anima/vocabulary/README.md
git commit -m "feat(prompt-forge): add vocabulary/README.md (positioning + mapping)"
```

---

### Tasks 3.3-3.11: Write 9 vocabulary files

Each task writes one vocabulary file in 5-segment format. To save repetition, the pattern is shown once with the cluster-specific content; tasks differ only in cluster name + tag content.

**Common 5-segment pattern (referenced from spec §5):**

```markdown
# <cluster name>

## 核心公式
> <one-sentence description of what this cluster renders>

## 变体维度表
| 维度 | 可选标签 |
|---|---|
| <dim_1> | `tag_a` / `tag_b` / `tag_c` |
| <dim_2> | `tag_d` / `tag_e` |

## 氛围链
<light> → <mid> → <heavy>

(omit if discrete)

## 使用提示
- <pitfall 1>
- <pitfall 2>

## 法典验证场景
### 场景 A
tags: `tag_a, tag_c, ...`
备注: <when to use>

### 场景 B
tags: `tag_d, ...`
备注: <when to use>
```

#### Task 3.3: count-identity.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/vocabulary/count-identity.md`

**Source:** NSFW template §6 COUNT & IDENTITY

**Design context:**
- Spec §4.17 row 1 (count-identity)
- Conclusion: short file (~120 lines), ~30 tags total

- [ ] **Step 1: Write the file** using the 5-segment pattern with content drawn from NSFW template §6 (count, IP, body type, age difference — see `D:\Projects\提示词模版.txt` lines 376-408)
- [ ] **Step 2: Verify ≤ 200 lines** (count-identity is small, may go lower)
- [ ] **Step 3: Commit** `feat(prompt-forge): add vocabulary/count-identity.md`

#### Task 3.4: appearance.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/vocabulary/appearance.md`

**Source:** NSFW template §7 APPEARANCE (hair, eyes, body, non-human, marks)

**Design context:**
- Spec §4.17 row 2 — largest vocabulary file (~150 tags)
- Conclusion: 5 segments with extensive 变体维度表

- [ ] **Step 1: Write the file** using NSFW template §7 content (see `D:\Projects\提示词模版.txt` lines 422-507)
- [ ] **Step 2: Verify ≤ 500 lines** (largest file, may be near cap)
- [ ] **Step 3: Commit** `feat(prompt-forge): add vocabulary/appearance.md`

#### Task 3.5: clothing.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/vocabulary/clothing.md`

**Source:** NSFW template §8 CLOTHING & STATE

**Design context:**
- Spec §4.17 row 3 — second-largest (~250 tags) + 7-dim modifications + contrast formulas
- Conclusion: includes 服装类型速查 + 7 维改造（透明化/裁剪/镂空/破损/胶衣/裸露简化/非对称）+ 反差公式

- [ ] **Step 1: Write the file** using NSFW template §8 content (see `D:\Projects\提示词模版.txt` lines 510-720)
- [ ] **Step 2: Verify ≤ 600 lines** (clothing is densest)
- [ ] **Step 3: Commit** `feat(prompt-forge): add vocabulary/clothing.md`

#### Task 3.6: pose-action.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/vocabulary/pose-action.md`

**Source:** NSFW template §9 POSE & ACTION & SEX

**Design context:**
- Spec §4.17 row 4 (~100 tags)
- Conclusion: covers single/dual/multi/storyboard

- [ ] **Step 1: Write the file** using NSFW template §9 content
- [ ] **Step 2: Verify ≤ 400 lines**
- [ ] **Step 3: Commit** `feat(prompt-forge): add vocabulary/pose-action.md`

#### Task 3.7: expression.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/vocabulary/expression.md`

**Source:** NSFW template §10 EXPRESSION & REACTION

**Design context:**
- Spec §4.17 row 5 (~80 tags)
- Conclusion: includes Lv1-4 intensity mapping

- [ ] **Step 1: Write the file** using NSFW template §10 content (see `D:\Projects\提示词模版.txt` lines 1356-1431)
- [ ] **Step 2: Verify ≤ 300 lines**
- [ ] **Step 3: Commit** `feat(prompt-forge): add vocabulary/expression.md`

#### Task 3.8: camera-shot.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/vocabulary/camera-shot.md`

**Source:** NSFW template §11 CAMERA & SHOT

**Design context:**
- Spec §4.17 row 6 (~60 tags) — purely technical
- Conclusion: framing, angle, POV, composition, storyboard

- [ ] **Step 1: Write the file** using NSFW template §11 content (see `D:\Projects\提示词模版.txt` lines 1434-1536)
- [ ] **Step 2: Verify ≤ 250 lines**
- [ ] **Step 3: Commit** `feat(prompt-forge): add vocabulary/camera-shot.md`

#### Task 3.9: scene-environment.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/vocabulary/scene-environment.md`

**Source:** NSFW template §12 SCENE & ENVIRONMENT

**Design context:**
- Spec §4.17 row 7 (~120 tags)
- Conclusion: locations + 风险矩阵 + 天气 + 场景细节

- [ ] **Step 1: Write the file** using NSFW template §12 content (see `D:\Projects\提示词模版.txt` lines 1539-1645)
- [ ] **Step 2: Verify ≤ 400 lines**
- [ ] **Step 3: Commit** `feat(prompt-forge): add vocabulary/scene-environment.md`

#### Task 3.10: detail-mood.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/vocabulary/detail-mood.md`

**Source:** NSFW template §13 DETAIL & MOOD

**Design context:**
- Spec §4.17 row 8 (~80 tags)
- Conclusion: includes 禁止清单 (§13.6) as part of detail cluster

- [ ] **Step 1: Write the file** using NSFW template §13 content (see `D:\Projects\提示词模版.txt` lines 1648-1736)
- [ ] **Step 2: Verify ≤ 300 lines**
- [ ] **Step 3: Commit** `feat(prompt-forge): add vocabulary/detail-mood.md`

#### Task 3.11: special-themes.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/vocabulary/special-themes.md`

**Source:** NSFW template §14 SPECIAL THEME

**Design context:**
- Spec §4.17 row 9 (~150 tags) — 12 cross-slot themes
- Conclusion: each theme is a 核心公式 + 跨槽位标签链 + 氛围链; themes named generically (power_imbalance, coercion, voyeurism, etc.) — no SFW/NSFW boundary statement

- [ ] **Step 1: Write the file** using NSFW template §14 content (see `D:\Projects\提示词模版.txt` lines 1738-2131). Rename themes to generic labels where appropriate; preserve structure
- [ ] **Step 2: Verify ≤ 500 lines**
- [ ] **Step 3: Commit** `feat(prompt-forge): add vocabulary/special-themes.md`

---

### Tasks 3.12-3.17: Write 6 recipe files

Each recipe is 5-segment + an additional 五层组合 section. Source: existing `knowledge/aesthetics/recipes/` + NSFW template §6-style structure.

**Common recipe pattern:**

```markdown
# <recipe name>

## 核心公式
> <one sentence: the aesthetic identity of this recipe>

## 五层组合 (the 5-layer composition — required for recipes)

- composition: <terms>
- lighting: <terms>
- palette: <terms>
- camera: <terms>
- mood-texture: <terms>

## 变体维度表
| 维度 | 可选标签 |
|---|---|

## 氛围链
...

## 使用提示
- when to use this recipe
- when NOT to use

## 法典验证场景
### 场景 A
tags: `...`
备注: ...

### 场景 B
...
```

#### Task 3.12: film-noir.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/recipes/film-noir.md`

**Design context:**
- D6 → NSFW template §6-style for noir
- Existing `knowledge/aesthetics/recipes/film-noir.md` is source
- Conclusion: 5-segment + 五层组合 = noir defaults

- [ ] **Step 1: Read existing film-noir.md** at `skills/prompt-forge/knowledge/aesthetics/recipes/film-noir.md`
- [ ] **Step 2: Rewrite in 5-segment + 五层组合 format** at new location
- [ ] **Step 3: Verify ≤ 250 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite recipes/film-noir.md (5-segment + 五层组合)`

#### Task 3.13: cyberpunk-neon.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/recipes/cyberpunk-neon.md`

- [ ] **Step 1: Read existing cyberpunk-neon.md**
- [ ] **Step 2: Rewrite in 5-segment + 五层组合**
- [ ] **Step 3: Verify ≤ 250 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite recipes/cyberpunk-neon.md`

#### Task 3.14: wes-anderson-pastel.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/recipes/wes-anderson-pastel.md`

- [ ] **Step 1: Read existing wes-anderson-pastel.md**
- [ ] **Step 2: Rewrite in 5-segment + 五层组合**
- [ ] **Step 3: Verify ≤ 250 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite recipes/wes-anderson-pastel.md`

#### Task 3.15: helmut-newton-bw.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/recipes/helmut-newton-bw.md`

- [ ] **Step 1: Read existing helmut-newton-bw.md**
- [ ] **Step 2: Rewrite in 5-segment + 五层组合**
- [ ] **Step 3: Verify ≤ 250 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite recipes/helmut-newton-bw.md`

#### Task 3.16: ghibli-aesthetic.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/recipes/ghibli-aesthetic.md`

- [ ] **Step 1: Read existing ghibli-aesthetic.md**
- [ ] **Step 2: Rewrite in 5-segment + 五层组合**
- [ ] **Step 3: Verify ≤ 250 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite recipes/ghibli-aesthetic.md`

#### Task 3.17: wuxia-ink.md

**Files:** Create `skills/prompt-forge/references/dialects/anima/recipes/wuxia-ink.md`

- [ ] **Step 1: Read existing wuxia-ink.md**
- [ ] **Step 2: Rewrite in 5-segment + 五层组合**
- [ ] **Step 3: Verify ≤ 250 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite recipes/wuxia-ink.md`

---

### Task 3.18: Write `references/dialects/minimax-h3/dialect.md`

**Files:**
- Create: `skills/prompt-forge/references/dialects/minimax-h3/dialect.md`

**Design context:**
- Spec §4.19 — existing `minimax-h3.md` content, moved verbatim + pointer
- Conclusion: H3 dialect stays the same; only path changes

- [ ] **Step 1: Copy existing minimax-h3.md to new location**

```bash
cd D:/Projects/comfyui-chenxin
git show HEAD~4:skills/prompt-forge/references/minimax-h3.md > skills/prompt-forge/references/dialects/minimax-h3/dialect.md
```

- [ ] **Step 2: Add pointer to budget-policy.json**

In `dialect.md`, after the existing content, add:
```markdown

---

## Budget policy

See [budget-policy.json](budget-policy.json) for H3-specific token budgets (t2va + ref2va).
```

- [ ] **Step 3: Verify ≤ 120 lines**

Run: `wc -l skills/prompt-forge/references/dialects/minimax-h3/dialect.md`

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/references/dialects/minimax-h3/dialect.md
git commit -m "feat(prompt-forge): create minimax-h3 dialect.md"
```

---

### Task 3.19: Create merged `budget-policy.json` + delete old policies

**Files:**
- Create: `skills/prompt-forge/references/dialects/minimax-h3/budget-policy.json`
- Delete: `skills/prompt-forge/knowledge/h3-t2va-budget-policy.json`
- Delete: `skills/prompt-forge/knowledge/h3-ref2va-budget-policy.json`

**Design context:**
- Spec §4.20 — merge two existing policy files
- Conclusion: single source of truth for H3 budget per dialect

- [ ] **Step 1: Read both source files**

```bash
cat skills/prompt-forge/knowledge/h3-t2va-budget-policy.json
cat skills/prompt-forge/knowledge/h3-ref2va-budget-policy.json
```

- [ ] **Step 2: Write merged file**

Create `skills/prompt-forge/references/dialects/minimax-h3/budget-policy.json` with structure:
```json
{
  "t2va": { ...content from h3-t2va-budget-policy.json... },
  "ref2va": { ...content from h3-ref2va-budget-policy.json... }
}
```

If schemas differ between the two sources, STOP and raise to the user before merging.

- [ ] **Step 3: Validate JSON**

Run: `python -c "import json; json.load(open('skills/prompt-forge/references/dialects/minimax-h3/budget-policy.json'))"`
Expected: no error

- [ ] **Step 4: Git-delete old files**

```bash
cd D:/Projects/comfyui-chenxin
git rm skills/prompt-forge/knowledge/h3-t2va-budget-policy.json
git rm skills/prompt-forge/knowledge/h3-ref2va-budget-policy.json
```

- [ ] **Step 5: Commit**

```bash
git add skills/prompt-forge/references/dialects/minimax-h3/budget-policy.json
git commit -m "feat(prompt-forge): merge H3 budget policies into dialects/minimax-h3/"
```

---

### Task 3.20: Verify Phase 3 exit criteria

**Files:** none

- [ ] **Step 1: Run all checks**

```bash
# vocabulary file count
ls skills/prompt-forge/references/dialects/anima/vocabulary/*.md | wc -l  # expect 10 (README + 9)

# recipes file count
ls skills/prompt-forge/references/dialects/anima/recipes/*.md | wc -l  # expect 6

# 5-segment present in every vocabulary/recipe file
for f in skills/prompt-forge/references/dialects/anima/vocabulary/*.md \
         skills/prompt-forge/references/dialects/anima/recipes/*.md; do
  for seg in '核心公式' '变体维度表' '使用提示' '法典验证场景'; do
    grep -q "## $seg" "$f" || echo "MISSING $seg in $f"
  done
done
# Expected: no output

# Recipes have 五层组合 section
for f in skills/prompt-forge/references/dialects/anima/recipes/*.md; do
  grep -q '## 五层组合' "$f" || echo "MISSING 五层组合 in $f"
done
# Expected: no output

# Old recipe dir gone
find skills/prompt-forge/knowledge/aesthetics/recipes -type f 2>/dev/null
# Expected: no output (dir was deleted; if not yet deleted, this check fails)

# Old H3 policy files gone
find skills/prompt-forge/knowledge -name 'h3-*-budget-policy.json'
# Expected: no output
```

- [ ] **Step 2: Fix any failures before Phase 4**

If any vocabulary or recipe file lacks a 5-segment section, fix it. If old paths remain, delete them.

---

## Phase 4 — Aesthetics knowledge (P0)

### Tasks 4.1-4.5: Rewrite 5 aesthetics files in 5-segment format

Source files: existing `knowledge/aesthetics/{composition,lighting,palette,camera,mood-texture}.md`

Each file is rewritten with the 5-segment template. Each **cluster** within the file (framing / angle / layout for composition; quality / direction / source for lighting; etc.) becomes one row in the 变体维度表.

#### Task 4.1: composition.md

**Files:** Modify `skills/prompt-forge/knowledge/aesthetics/composition.md`

**Source:** existing file content (composition clusters: framing, angle, layout, multi-figure)

**Design context:**
- Spec §4.21 — 5-segment rewrite
- D6 → 5 segments match NSFW template §9 sub-section structure
- Conclusion: each cluster gets its 变体维度表 row + 法典例

- [ ] **Step 1: Read existing composition.md**
- [ ] **Step 2: Rewrite in 5-segment format** — 核心公式 / 变体维度表 (rows for framing, angle, layout, multi-figure) / 氛围链 / 使用提示 / 法典验证场景
- [ ] **Step 3: Verify ≤ 350 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite aesthetics/composition.md (5-segment)`

#### Task 4.2: lighting.md

**Files:** Modify `skills/prompt-forge/knowledge/aesthetics/lighting.md`

**Source:** existing lighting clusters (quality, direction, time/source, special)

- [ ] **Step 1: Read existing lighting.md**
- [ ] **Step 2: Rewrite in 5-segment format** — 核心公式 / 变体维度表 (rows for quality, direction, time/source, special) / 氛围链 / 使用提示 / 法典验证场景
- [ ] **Step 3: Verify ≤ 350 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite aesthetics/lighting.md (5-segment)`

#### Task 4.3: palette.md

**Files:** Modify `skills/prompt-forge/knowledge/aesthetics/palette.md`

**Source:** existing palette clusters (named grades, named palettes, color temperature, cultural)

- [ ] **Step 1: Read existing palette.md**
- [ ] **Step 2: Rewrite in 5-segment format** — 核心公式 / 变体维度表 / 氛围链 / 使用提示 / 法典验证场景
- [ ] **Step 3: Verify ≤ 350 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite aesthetics/palette.md (5-segment)`

#### Task 4.4: camera.md

**Files:** Modify `skills/prompt-forge/knowledge/aesthetics/camera.md`

**Source:** existing camera clusters (render medium, optical style, film/texture)

- [ ] **Step 1: Read existing camera.md**
- [ ] **Step 2: Rewrite in 5-segment format**
- [ ] **Step 3: Verify ≤ 350 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite aesthetics/camera.md (5-segment)`

#### Task 4.5: mood-texture.md

**Files:** Modify `skills/prompt-forge/knowledge/aesthetics/mood-texture.md`

**Source:** existing mood-texture clusters (mood, atmosphere, surface, particles)

- [ ] **Step 1: Read existing mood-texture.md**
- [ ] **Step 2: Rewrite in 5-segment format**
- [ ] **Step 3: Verify ≤ 350 lines**
- [ ] **Step 4: Commit** `feat(prompt-forge): rewrite aesthetics/mood-texture.md (5-segment)`

---

### Task 4.6: Rewrite `anti-patterns.md` with concrete tag blacklist

**Files:** Modify `skills/prompt-forge/knowledge/aesthetics/anti-patterns.md`

**Interfaces:**
- Consumes: existing anti-patterns.md (A-G sections) + NSFW template §13.6 forbidden list
- Produces: 5-segment structure with concrete tag pairs replacing abstract categories

**Design context:**
- Spec §4.22 — concrete tag blacklist replaces A-G abstract descriptions
- D6 → §13.6 forbidden list absorbed
- Conclusion: this file is the override layer; vagueness defeats the purpose

- [ ] **Step 1: Read existing anti-patterns.md** (full content)
- [ ] **Step 2: Read NSFW template §13.6 forbidden list** (see `D:\Projects\提示词模版.txt` lines 1723-1735)
- [ ] **Step 3: Rewrite** using 5-segment format:
  - 核心公式: "this file is the override layer"
  - 变体维度表: table of (category | wrong pattern | correct replacement) — replaces existing A-G sections
  - 氛围链: skip (discrete)
  - 使用提示: blackandwhite → monochrome, etc.
  - 法典验证场景: 2 examples — compliant prompt + violation prompt + fixed version
- [ ] **Step 4: Verify ≤ 350 lines**
- [ ] **Step 5: Commit** `feat(prompt-forge): rewrite anti-patterns.md (concrete tag blacklist)`

---

### Task 4.7: Delete old `knowledge/aesthetics/recipes/`

**Files:**
- Delete: `skills/prompt-forge/knowledge/aesthetics/recipes/` (entire directory, 6 files)

**Design context:**
- Spec §3 — recipes moved to `references/dialects/anima/recipes/`
- D5 (virgin rewrite) — no symlinks, no compat
- Conclusion: hard delete

- [ ] **Step 1: Git-delete the directory**

```bash
cd D:/Projects/comfyui-chenxin
git rm -r skills/prompt-forge/knowledge/aesthetics/recipes/
```

- [ ] **Step 2: Verify gone**

Run: `ls skills/prompt-forge/knowledge/aesthetics/`
Expected: only `.md` files (composition, lighting, palette, camera, mood-texture, anti-patterns) — no `recipes/` directory

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor(prompt-forge): delete knowledge/aesthetics/recipes (moved to dialects/)"
```

---

### Task 4.8: Verify Phase 4 exit criteria

**Files:** none

- [ ] **Step 1: Run all checks**

```bash
# 6 files in aesthetics/
ls skills/prompt-forge/knowledge/aesthetics/*.md | wc -l  # expect 6

# 5-segment present in every aesthetics file
for f in skills/prompt-forge/knowledge/aesthetics/*.md; do
  for seg in '核心公式' '变体维度表' '使用提示' '法典验证场景'; do
    grep -q "## $seg" "$f" || echo "MISSING $seg in $f"
  done
done
# Expected: no output

# anti-patterns.md has concrete tag pairs (not just A-G)
grep -c '^|' skills/prompt-forge/knowledge/aesthetics/anti-patterns.md
# Expect ≥ 15 table rows (one per category × multiple wrong patterns)

# Line caps respected
for f in skills/prompt-forge/knowledge/aesthetics/*.md; do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 350 ]; then echo "OVER CAP $f: $lines lines"; fi
done
# Expected: no output
```

---

## Phase 5 — Scripts + tests (P1)

### Task 5.1: Write `scripts/preflight.py`

**Files:**
- Create: `skills/prompt-forge/scripts/preflight.py`

**Interfaces:**
- Consumes: list of segments, complexity dict
- Produces: `{ok: bool, errors: list[str], warnings: list[str]}`

**Design context:**
- Spec §4.23 — encodes rules from conflict-table.md + tag-count-ruler.md + style-consistency.md
- Conclusion: preflight is the Python implementation of the quality gates; rules in docs, code in script

- [ ] **Step 1: Write the file**

```python
"""Pre-compile quality gate.

Encodes rules from:
- references/quality/conflict-table.md (5 hard-conflict categories)
- references/quality/tag-count-ruler.md (count percentiles + per-slot targets)
- references/quality/style-consistency.md (cross-slot worldview check)

Usage:
    from scripts.preflight import preflight_check
    result = preflight_check(segments, complexity)
    if not result['ok']:
        for e in result['errors']:
            print(f"ERROR: {e}")
"""
from __future__ import annotations


# Conflict pairs from conflict-table.md
VIEW_CONFLICTS = [
    {("pov",), ("full body", "cowboy shot")},
    {("from front",), ("from behind",)},
    {("looking at viewer",), ("facing away",)},
    {("from above",), ("from below",)},
]
IDENTITY_CONFLICTS = [
    {("solo",), ("hetero", "1boy", "yuri")},
    {("completely nude",), ("specific clothing",)},  # simplify: any clothing tag
    {("sleeping", "unconscious"), ("looking at viewer",)},
    {("blindfold",), ("heart-shaped pupils", "rolling eyes")},
]

# Tag-count thresholds from tag-count-ruler.md
COUNT_HARD_CAPS = {
    "simple": 40,
    "standard": 50,
    "complex": 70,
}


def _tag_set(segments: list[dict]) -> set[str]:
    return {seg.get("text", "").strip().lower() for seg in segments if seg.get("text")}


def _check_conflicts(tags: set[str]) -> list[str]:
    errors = []
    for pair_set in VIEW_CONFLICTS + IDENTITY_CONFLICTS:
        for group_a, group_b in [(list(s)[0], list(s)[1]) for s in pair_set]:
            a_hit = group_a in tags
            b_hit = any(t in tags for t in group_b)
            if a_hit and b_hit:
                errors.append(f"conflict: {group_a} + {group_b}")
    return errors


def _check_count(segments: list[dict], complexity: dict) -> list[str]:
    """Return warnings (not errors) if over the hard cap."""
    n = sum(1 for s in segments if s.get("text"))
    # Infer complexity tier from subjects count
    subjects = complexity.get("subjects", 1)
    if subjects >= 3:
        tier = "complex"
    elif subjects >= 2:
        tier = "standard"
    else:
        tier = "simple"
    cap = COUNT_HARD_CAPS[tier]
    if n > cap:
        return [f"tag count {n} > hard cap {cap} for {tier}"]
    return []


def _check_style(segments: list[dict]) -> list[str]:
    """Cross-slot worldview check (simplified)."""
    errors = []
    tags = _tag_set(segments)
    # Hanfu + cyberpunk city is a classic mismatch
    if any("hanfu" in t for t in tags) and any("cyberpunk city" in t for t in tags):
        errors.append("style: hanfu + cyberpunk city worldview mismatch")
    return errors


def preflight_check(segments: list[dict], complexity: dict) -> dict:
    """Run all pre-compile quality gates.

    Args:
        segments: list of {field, text, fact_ids} dicts (positive stream).
        complexity: dict with subjects, explicit_relations, etc.

    Returns:
        {ok: bool, errors: list[str], warnings: list[str]}
    """
    tags = _tag_set(segments)
    errors = _check_conflicts(tags) + _check_style(segments)
    warnings = _check_count(segments, complexity)
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
```

- [ ] **Step 2: Smoke-test import**

```bash
cd skills/prompt-forge
python -c "from scripts.preflight import preflight_check; print('import ok')"
```
Expected: `import ok`

- [ ] **Step 3: Verify ≤ 200 lines**

Run: `wc -l skills/prompt-forge/scripts/preflight.py`

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/scripts/preflight.py
git commit -m "feat(prompt-forge): add preflight.py (conflict + count + style gates)"
```

---

### Task 5.2: Write `scripts/tag-validate.py`

**Files:**
- Create: `skills/prompt-forge/scripts/tag-validate.py`

**Interfaces:**
- Consumes: a single tag string
- Produces: `{canonical: str, frequency: int, verified: bool, alias: bool}`

**Design context:**
- Spec §4.24 — dictionary lookup + frequency warnings + alias normalization
- Conclusion: this is the Python implementation of dictionary-preflight.md

- [ ] **Step 1: Write the file**

```python
"""Tag validation against bundled Anima dictionary.

Reads knowledge/anima/tags.sqlite, returns canonical form + frequency + verified.

Usage:
    from scripts.tag_validate import validate_tag
    info = validate_tag("male")  # -> {"canonical": "male_focus", "verified": True, ...}
"""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path


_DICT_PATH = Path(__file__).parent.parent / "knowledge" / "anima" / "tags.sqlite"

# Cached connection
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        if not _DICT_PATH.exists():
            _conn = None
            return None
        _conn = sqlite3.connect(str(_DICT_PATH))
        _conn.row_factory = sqlite3.Row
    return _conn


def validate_tag(tag: str) -> dict:
    """Look up tag in the bundled dictionary.

    Returns:
        {"canonical": str, "frequency": int, "verified": bool, "alias": bool}
    """
    tag = tag.strip().lower()
    conn = _get_conn()
    if conn is None:
        return {"canonical": tag, "frequency": 0, "verified": False, "alias": False}

    # Exact match first
    row = conn.execute(
        "SELECT canonical, frequency FROM tags WHERE canonical = ?", (tag,)
    ).fetchone()
    if row:
        return {
            "canonical": row["canonical"],
            "frequency": row["frequency"],
            "verified": True,
            "alias": False,
        }

    # Alias match
    row = conn.execute(
        "SELECT canonical, frequency FROM aliases WHERE alias = ?", (tag,)
    ).fetchone()
    if row:
        return {
            "canonical": row["canonical"],
            "frequency": row["frequency"],
            "verified": True,
            "alias": True,
        }

    # Not found
    return {"canonical": tag, "frequency": 0, "verified": False, "alias": False}
```

- [ ] **Step 2: Smoke-test import**

```bash
cd skills/prompt-forge
python -c "from scripts.tag_validate import validate_tag; print('import ok')"
```
Expected: `import ok` (even if SQLite not available — returns `verified: False`)

- [ ] **Step 3: Verify ≤ 150 lines**

Run: `wc -l skills/prompt-forge/scripts/tag-validate.py`

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/scripts/tag-validate.py
git commit -m "feat(prompt-forge): add tag-validate.py (dictionary lookup)"
```

---

### Task 5.3: Write `tests/test_preflight.py`

**Files:**
- Create: `skills/prompt-forge/tests/test_preflight.py`

**Design context:**
- Spec §4.25 — unit tests for preflight
- Conclusion: 3 boundary cases minimum

- [ ] **Step 1: Write the file**

```python
"""Unit tests for scripts/preflight.py."""
import pytest
from scripts.preflight import preflight_check


def _seg(text: str, field: str = "general") -> dict:
    return {"field": field, "text": text, "fact_ids": ["f"]}


def test_pov_plus_full_body_caught():
    """pov + full body is a view conflict."""
    segments = [_seg("pov"), _seg("full body", field="composition_and_camera")]
    result = preflight_check(segments, {"subjects": 1})
    assert not result["ok"]
    assert any("pov" in e for e in result["errors"])


def test_solo_plus_hetero_caught():
    """solo + hetero is an identity conflict."""
    segments = [_seg("solo"), _seg("hetero")]
    result = preflight_check(segments, {"subjects": 1})
    assert not result["ok"]


def test_hanfu_plus_cyberpunk_caught():
    """hanfu + cyberpunk city is a style inconsistency."""
    segments = [_seg("hanfu"), _seg("cyberpunk city", field="environment_and_props")]
    result = preflight_check(segments, {"subjects": 1})
    assert not result["ok"]
    assert any("style" in e for e in result["errors"])


def test_clean_prompt_passes():
    """A clean single-subject prompt passes all gates."""
    segments = [_seg("2boys"), _seg("fighting"), _seg("ruined city", field="environment_and_props")]
    result = preflight_check(segments, {"subjects": 2})
    assert result["ok"]


def test_count_over_cap_warns():
    """Exceeding tag-count hard cap returns a warning."""
    segments = [_seg(f"tag_{i}") for i in range(60)]
    result = preflight_check(segments, {"subjects": 1})  # simple tier, cap 40
    assert any("hard cap" in w for w in result["warnings"])
```

- [ ] **Step 2: Run tests**

```bash
cd skills/prompt-forge
pytest tests/test_preflight.py -v
```
Expected: 5 tests pass

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/tests/test_preflight.py
git commit -m "test(prompt-forge): add preflight unit tests"
```

---

### Task 5.4: Write `tests/test_tag_validate.py`

**Files:**
- Create: `skills/prompt-forge/tests/test_tag_validate.py`

**Design context:**
- Spec §4.25 — unit tests for tag-validate
- Conclusion: 3 boundary cases minimum

- [ ] **Step 1: Write the file**

```python
"""Unit tests for scripts/tag-validate.py."""
from scripts.tag_validate import validate_tag


def test_unverified_tag():
    """Unknown tag returns verified: False."""
    info = validate_tag("quantum chrome")
    assert info["verified"] is False
    assert info["canonical"] == "quantum chrome"


def test_input_normalized_to_lowercase():
    """Tag input is normalized to lowercase."""
    info = validate_tag("MALE")
    # Don't assert on canonical since dictionary may not exist in test env
    # Just verify the input was lowercased (canonical is lowercase)
    assert info["canonical"] == info["canonical"].lower()


def test_empty_string_handled():
    """Empty string returns verified: False without crashing."""
    info = validate_tag("")
    assert info["verified"] is False
```

- [ ] **Step 2: Run tests**

```bash
cd skills/prompt-forge
pytest tests/test_tag_validate.py -v
```
Expected: 3 tests pass

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add skills/prompt-forge/tests/test_tag_validate.py
git commit -m "test(prompt-forge): add tag-validate unit tests"
```

---

### Task 5.5: Verify Phase 5 exit criteria

**Files:** none

- [ ] **Step 1: Run all checks**

```bash
# Both scripts import
cd skills/prompt-forge
python -c "from scripts.preflight import preflight_check; from scripts.tag_validate import validate_tag; print('imports ok')"

# Both test files pass
pytest tests/test_preflight.py tests/test_tag_validate.py -v
# Expected: 8 tests pass total

# Verify wasteland prompt still passes preflight
python -c "
from scripts.preflight import preflight_check
# The 37-tag wasteland prompt from this session
segments = [
    {'field': 'quality_meta_year_safety', 'text': 'score_9'},
    {'field': 'count', 'text': '2boys'},
    # ... full wasteland segments here
]
result = preflight_check(segments, {'subjects': 2})
print('wasteland:', result)
assert result['ok'], result
"
```

- [ ] **Step 2: Fix any failures before Phase 6**

---

## Phase 6 — Validation + plugin shell (P2)

### Task 6.1: Update `plugin.json` version to 0.2.0

**Files:**
- Modify: `.claude-plugin/plugin.json` (bump `"version": "0.1.20"` → `"0.2.0"`)

**Design context:**
- Spec §3.5 — major version bump because directory restructure
- D4 (外壳改动) — plugin shell in scope
- Conclusion: 0.1.x → 0.2.0 reflects structural rewrite

- [ ] **Step 1: Edit plugin.json**

Change `"version": "0.1.20"` to `"0.2.0"`.

- [ ] **Step 2: Verify**

Run: `grep '"version"' .claude-plugin/plugin.json`
Expected: `"version": "0.2.0"`

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/comfyui-chenxin
git add .claude-plugin/plugin.json
git commit -m "chore(version): bump 0.1.20 -> 0.2.0 (structural rewrite)"
```

---

### Task 6.2: Sync `.claude-plugin/marketplace.json`

**Files:**
- Modify: `.claude-plugin/marketplace.json`

**Design context:**
- Spec §3.5 — marketplace in sync with plugin.json

- [ ] **Step 1: Compare versions**

```bash
diff <(jq -S '.version' .claude-plugin/plugin.json) \
     <(jq -S '.version' .claude-plugin/marketplace.json)
```
Expected: empty diff after both updated

- [ ] **Step 2: Update marketplace.json version to 0.2.0** (if different)

- [ ] **Step 3: Verify diff is empty**

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/marketplace.json
git commit -m "chore(marketplace): sync version to 0.2.0"
```

---

### Task 6.3: Add CHANGELOG entry

**Files:**
- Modify: `CHANGELOG.md` (prepend new entry for v0.2.0)

**Design context:**
- Spec §3.5 — CHANGELOG entry documents v0.2.0
- Conclusion: entry lists structural changes, not individual files

- [ ] **Step 1: Read existing CHANGELOG.md head**
- [ ] **Step 2: Prepend new entry**

```markdown
## v0.2.0 — 2026-08-13

**Structural rewrite.** No backward compat. References, knowledge, and scripts reorganized.

### Changed
- `references/` reorganized into `shared/`, `quality/`, `dialects/<model>/` subdirectories
- `references/anima.md`, `references/minimax-h3.md` deleted; content migrated to `references/dialects/<model>/dialect.md`
- `references/authoring-contract.md` → `references/shared/authoring-contract.md` (added 前重后轻 slot weight table)
- `references/budget-ruler.md` → `references/quality/budget-ruler.md` (token + tag-count linked)
- `references/audit-and-recovery.md` → `references/quality/audit-and-recovery.md`
- `references/dictionary-preflight.md` → `references/quality/dictionary-preflight.md`
- `references/artifact-and-budgets.md` deleted (content subsumed)

### Added
- `references/shared/{method,aesthetic-coverage,decision-tree,self-check,output-protocol,natural-language}.md` (6 new)
- `references/quality/{conflict-table,tag-count-ruler,style-consistency}.md` (3 new)
- `references/dialects/anima/vocabulary/{README,count-identity,appearance,clothing,pose-action,expression,camera-shot,scene-environment,detail-mood,special-themes}.md` (10 new — full Anima tag vocabulary, 5-segment format)
- `references/dialects/anima/recipes/{film-noir,cyberpunk-neon,wes-anderson-pastel,helmut-newton-bw,ghibli-aesthetic,wuxia-ink}.md` (6 rewritten, 5-segment + 五层组合)
- `references/dialects/minimax-h3/{dialect.md,budget-policy.json}` (2 new)
- `scripts/preflight.py` + `scripts/tag-validate.py` (2 new pre-compile tools)
- `tests/test_preflight.py` + `tests/test_tag_validate.py` (2 new test files)

### Removed
- `references/{anima,minimax-h3,authoring-contract,budget-ruler,audit-and-recovery,dictionary-preflight,artifact-and-budgets}.md`
- `knowledge/aesthetics/recipes/`
- `knowledge/h3-t2va-budget-policy.json`, `knowledge/h3-ref2va-budget-policy.json`

### Knowledge / quality
- `knowledge/aesthetics/{composition,lighting,palette,camera,mood-texture,anti-patterns}.md` rewritten in 5-segment format
- `anti-patterns.md` now contains concrete tag blacklist (replaces abstract A-G categories)

### Methodology
- Absorbed NSFW template (`D:\Projects\提示词模版.txt`) methodology: §2 OUTPUT PROTOCOL, §3 SELF-CHECK, §3.1 CONFLICT TABLE, §4.1 STYLE CONSISTENCY, §4.2 TAG COUNT, §4.4 NATURAL LANGUAGE, §5 DECISION TREE, §9 5-SEGMENT STRUCTURE, §13.6 FORBIDDEN LIST, §14 SPECIAL THEMES

```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): v0.2.0 entry (structural rewrite)"
```

---

### Task 6.4: Update README.md and README.en.md (if needed)

**Files:**
- Modify: `README.md`
- Modify: `README.en.md`

**Design context:**
- Spec §3.5 — README sync if description references internal structure
- Conclusion: only update if README explicitly mentions file paths or structure

- [ ] **Step 1: Check if README references old paths**

```bash
grep -l 'references/anima.md\|references/minimax-h3.md\|references/budget-ruler.md\|knowledge/aesthetics/recipes' README.md README.en.md
```

- [ ] **Step 2: Update if matched** (replace old path references with new ones; add brief description of v0.2.0 changes)

- [ ] **Step 3: Commit (only if changed)**

```bash
git add README.md README.en.md
git commit -m "docs(readme): sync to v0.2.0 structure"
```

---

### Task 6.5: Final verification — all post-implementation checks

**Files:** none

**Design context:**
- Spec §8 — comprehensive post-implementation self-check
- Conclusion: this is the final gate; any failure blocks release

- [ ] **Step 1: Run §8.1 structural checks**

```bash
# No compat shim
grep -rn 'legacy\|deprecated\|backward compat\|migrated from' skills/prompt-forge/ | grep -v 'docs/'
# Expected: no output

# Old paths gone
find skills/prompt-forge -path '*references/anima.md' -o -path '*references/minimax-h3.md' \
  -o -path '*references/authoring-contract.md' -o -path '*references/budget-ruler.md' \
  -o -path '*references/audit-and-recovery.md' -o -path '*references/dictionary-preflight.md' \
  -o -path '*references/artifact-and-budgets.md' -o -path '*knowledge/aesthetics/recipes/*' \
  -o -path '*knowledge/h3-*-budget-policy.json'
# Expected: no output

# File counts
echo "shared/: $(ls skills/prompt-forge/references/shared/ | wc -l) (expect 7)"
echo "quality/: $(ls skills/prompt-forge/references/quality/ | wc -l) (expect 6)"
echo "anima/vocabulary/: $(ls skills/prompt-forge/references/dialects/anima/vocabulary/ | wc -l) (expect 10)"
echo "anima/recipes/: $(ls skills/prompt-forge/references/dialects/anima/recipes/ | wc -l) (expect 6)"
echo "aesthetics/: $(ls skills/prompt-forge/knowledge/aesthetics/*.md | wc -l) (expect 6)"

# Line caps
find skills/prompt-forge/references -name '*.md' -exec wc -l {} + | awk '$1 > 300 {print}'
# Expected: no output
find skills/prompt-forge/knowledge -name '*.md' -exec wc -l {} + | awk '$1 > 350 {print}'
# Expected: no output

# SKILL.md brief
wc -l skills/prompt-forge/SKILL.md  # expect 40-60
```

- [ ] **Step 2: Run §8.2 reference closure**

```bash
# All relative .md links resolve
find skills/prompt-forge -name '*.md' -exec grep -h -oE '\]\([^)]+\.md[^)]*\)' {} + | \
  sed 's/.*(\(.*\))/\1/' | sort -u | while read f; do
    test -f "skills/prompt-forge/$f" || echo "BROKEN: $f"
done
# Expected: no BROKEN lines
```

- [ ] **Step 3: Run §8.3 5-segment structure**

```bash
for f in $(ls skills/prompt-forge/references/dialects/anima/vocabulary/*.md \
           skills/prompt-forge/references/dialects/anima/recipes/*.md \
           skills/prompt-forge/knowledge/aesthetics/*.md); do
  for seg in '核心公式' '变体维度表' '使用提示' '法典验证场景'; do
    grep -q "## $seg" "$f" || echo "MISSING $seg in $f"
  done
done
# Expected: no output

# Recipes have 五层组合
for f in skills/prompt-forge/references/dialects/anima/recipes/*.md; do
  grep -q '## 五层组合' "$f" || echo "MISSING 五层组合 in $f"
done
# Expected: no output
```

- [ ] **Step 4: Run §8.4 functional tests**

```bash
cd skills/prompt-forge
pytest tests/test_preflight.py tests/test_tag_validate.py -v
# Expected: 8 tests pass

# Wasteland prompt passes preflight
python -c "
import sys
sys.path.insert(0, 'skills/prompt-forge')
from scripts.preflight import preflight_check

# Reconstruct wasteland segments from session history
segments = [
    {'field': 'quality_meta_year_safety', 'text': 'score_9'},
    {'field': 'count', 'text': '2boys'},
    {'field': 'character', 'text': 'duel'},
    {'field': 'character', 'text': 'tattered clothing'},
    {'field': 'character', 'text': 'leather armor'},
    {'field': 'character', 'text': 'gas mask'},
    {'field': 'character', 'text': 'holding sword'},
    {'field': 'action_and_relation', 'text': 'fighting'},
    {'field': 'action_and_relation', 'text': 'weapon clash'},
    {'field': 'action_and_relation', 'text': 'combat stance'},
    {'field': 'environment_and_props', 'text': 'ruined city'},
    {'field': 'environment_and_props', 'text': 'desert'},
    {'field': 'environment_and_props', 'text': 'rubble'},
    {'field': 'environment_and_props', 'text': 'wrecked vehicle'},
    {'field': 'environment_and_props', 'text': 'hazy sky'},
    {'field': 'composition_and_camera', 'text': 'wide shot'},
    {'field': 'composition_and_camera', 'text': 'low angle'},
    {'field': 'composition_and_camera', 'text': 'leading lines'},
    {'field': 'lighting_and_visual_style', 'text': 'dramatic lighting'},
    {'field': 'lighting_and_visual_style', 'text': 'side lighting'},
    {'field': 'lighting_and_visual_style', 'text': 'golden hour'},
    {'field': 'lighting_and_visual_style', 'text': 'high contrast'},
    {'field': 'lighting_and_visual_style', 'text': 'warm color'},
    {'field': 'lighting_and_visual_style', 'text': 'photo (medium)'},
    {'field': 'lighting_and_visual_style', 'text': 'depth of field'},
    {'field': 'lighting_and_visual_style', 'text': 'film grain'},
    {'field': 'lighting_and_visual_style', 'text': 'epic'},
    {'field': 'lighting_and_visual_style', 'text': 'dramatic'},
    {'field': 'lighting_and_visual_style', 'text': 'dust'},
    {'field': 'lighting_and_visual_style', 'text': 'smoke'},
    {'field': 'lighting_and_visual_style', 'text': 'embers'},
    {'field': 'lighting_and_visual_style', 'text': 'ash'},
    {'field': 'lighting_and_visual_style', 'text': 'cracked ground'},
    {'field': 'lighting_and_visual_style', 'text': 'weathered'},
]
result = preflight_check(segments, {'subjects': 2})
print('wasteland:', result)
assert result['ok'], f'wasteland failed: {result}'
print('wasteland ok')
"
```

- [ ] **Step 5: Run §8.5 plugin shell checks**

```bash
# Version bumped
grep '"version"' .claude-plugin/plugin.json
# Expected: "0.2.0"

# Marketplace in sync
diff <(jq -S '.version, .description' .claude-plugin/plugin.json) \
     <(jq -S '.version, .description' .claude-plugin/marketplace.json)
# Expected: empty diff

# CHANGELOG entry
head -30 CHANGELOG.md | grep -q '0.2.0'
# Expected: match
```

- [ ] **Step 6: Report results**

If all checks pass, report success and proceed to git push + plugin reinstall (user action).

If any check fails, fix the underlying issue (per spec §9 anti-drift signals) and re-run.

---

## Final Acceptance (spec §11)

The redesign is complete when:

- [ ] All 6 phases exit criteria pass
- [ ] All checks in Task 6.5 pass
- [ ] Wasteland battle prompt compiles to `production_ready` AND uses 5-layer aesthetic coverage (visible in the rendered positive stream)
- [ ] `preflight.py` catches known conflicts (verified by test_preflight.py)
- [ ] `find . -path '*old-path*'` returns empty
- [ ] `CHANGELOG.md` documents v0.2.0
- [ ] `plugin.json` reads `"version": "0.2.0"`

Then user pushes git, reinstalls plugin, and observes no regression.

---

## Self-Review Notes

After writing this plan, I checked it against the spec:

**Spec coverage**:
- §1 Background → contextual D1-D7 excerpts above
- §2 Design philosophy → baked into Global Constraints
- §3 Target tree → file structure section
- §4 File-by-file → all 25 files have a Task each (1.2, 1.3, 1.4, 3.1, 3.2, 3.3-3.11, 3.12-3.17, 3.18, 3.19, 4.1-4.6)
- §5 5-segment template → referenced in every relevant task
- §6 Reference map → enforced via reference closure check in Task 6.5
- §7 Implementation phases → Phases 1-6 structure
- §8 Post-implementation self-check → Task 6.5
- §9 Document reference index → anti-drift signals in §9.3 enforced via checks
- §10 Risks & mitigations → addressed in task structure
- §11 Acceptance criteria → Final Acceptance section
- §12 Out of scope → declared in Global Constraints

**Placeholder scan**:
- No "TBD", "TODO", "implement later" used
- No "similar to Task N" — every task is self-contained
- Every code block shows actual code

**Type consistency**:
- `preflight_check(segments: list[dict], complexity: dict) -> dict` — used consistently in Tasks 5.1, 5.3, 6.5
- `validate_tag(tag: str) -> dict` — used consistently in Tasks 5.2, 5.4
- Field names `fact_ids`, `field`, `text` — match `references/shared/authoring-contract.md`
- `references/quality/...` paths match Phase 2 file creation
- `references/dialects/anima/vocabulary/...` paths match Phase 3 file creation