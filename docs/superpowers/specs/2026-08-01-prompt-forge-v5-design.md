# prompt-forge v5 — In-Skill Optimization Design Spec

**Date**: 2026-08-01
**Status**: approved (brainstorming Q1–Q4 + recommendation pass)
**Author**: brainstormed with user; design drafted by Claude

---

## Context

The current `comfyui-chenxin/skills/prompt-forge/` (v4.0.0) is a **slimmed-down** version of an earlier v3 design that depended on an external Obsidian vault (`D:\ObsidianWorkSpace\workspace\10-Projects\prompt-forge\`, ~153K lines of curated prompt-engineering knowledge). v4 removed the obsidian read dependency (commit `a1e64d7`: "merge chenxin-core into prompt-forge") but **never re-implemented v3's capabilities**: 10-dimension extraction, scene-recipes matching, tag-dictionary validation, style-preset fallback. SKILL.md v4 §5 still references "tag dictionary check" and "前 10 token 决定画面基调" but no tool exists to actually do these.

**Goal**: bring v4 up to parity with v3 — and better — by **inlining the vault into the skill itself** so the skill becomes fully self-contained, version-controlled, and importable. No external Obsidian dependency.

**Success criteria**:
- skill works with `git clone` alone — no `~/.claude/...` or vault setup
- tag-dictionary lookups ≤ 100 ms (vs. grep on 140K lines: ~3 s)
- scene-recipes matching surfaces ≤ 3 recipes per query
- 6-step pipeline (model → 10-dim → scene → tag → assemble → self-check) all implemented
- no regression: v4 81-recipe lookup still works (recipe_lookup.py upgrade is backwards compatible)

---

## §1 Architecture — Target Tree

```
skills/prompt-forge/
├── SKILL.md                       v5 router (~250 lines)
├── SPEC.md                        design rationale (from vault spec-v3.md)
├── recipes/
│   └── MODELS.md                  81 recipes (unchanged)
├── dictionary/                    ★ NEW: in-skill tag dictionary
│   ├── README.md                  sources, license, update flow
│   ├── danbooru.csv               140K rows, original file verbatim
│   ├── wd14-tags.csv              11K rows, original file verbatim
│   └── tag-index.json             build_tag_index.py output (git-track)
├── aesthetics/                    ★ NEW: from vault
│   ├── INDEX.md                   scene_match.py keyword index
│   ├── scene-recipes.md           31 rows (scene → recipe mapping)
│   ├── style-presets.md           39 rows (fallback 3-of-N)
│   ├── lighting/*.md              9 recipes
│   ├── composition/*.md           7 recipes
│   ├── color/*.md                 9 recipes
│   ├── medium-glossary.md         143 rows
│   ├── motion-glossary.md         130 rows
│   ├── concept-archetypes.md      227 rows
│   └── video-archetypes.md        149 rows
├── negative/
│   └── negative-prompts.md        96 rows (from vault)
├── models/                        ★ NEW: 15 model metadata
│   ├── INDEX.md                   (from vault model-index.md)
│   └── {anima,pony,illustrious,noobai,flux,sdxl,sd15,sd35,qwen-image,seedream,hunyuan-image,wan,ltx,kling,hailuo}.md
├── internals/                     5 stdlib-only Python tools
│   ├── recipe_lookup.py           ★ upgraded: weighted + alias table
│   ├── recipe_yaml.py             ★ upgraded: schema validation + alias maintenance
│   ├── tag_lookup.py              ★ NEW
│   ├── scene_match.py             ★ NEW
│   └── build_tag_index.py         ★ NEW (one-shot CSV → JSON)
└── hardware/
    └── 8gb.json                   unchanged (13-key schema v1)
```

**Net change**: +4 directories (dictionary, aesthetics, negative, models), +3 new Python tools, ~160K lines inlined from vault.

---

## §2 Data Flow — 6-Step Pipeline

```
User: "用 Anima 出金发精灵女法师在樱花树下释放魔法的图"
   │
   ▼
① Model ID ────────── recipe_lookup.py --model anima
   │                   weighted match: id(1.0) > family(0.7) > dialect(0.5) > heading(0.3)
   │                   alias table: anima_baseV10, AnimaStandardV7 → anima
   │                   → {matched, matched_id, heading, frontmatter, dialect_block, score}
   │
   ▼
② 10-Dim extraction ── SKILL.md §3 (v3 framework restored)
   │                   subject / action / scene / lighting / composition / color / style / mood / medium / quality
   │                   missing dims marked [unset]
   │
   ▼
③ Scene match ──────── scene_match.py --query "樱花树下 释放魔法"
   │                   INDEX.md keyword scan → matched scene(s)
   │                   → lighting/rembrandt.md + composition/cowboy-shot.md + color/warm-cool-contrast.md
   │                   miss → style-presets.md fallback (3 presets)
   │
   ▼
④ Tag validation ───── tag_lookup.py --query "金发" "精灵" "樱花"
   │                   tag-index.json lookup
   │                   → [{canonical: long_hair, category: 0, count: 4350743, aliases: ["/lh","longhair"]}, ...]
   │
   ▼
⑤ Prompt assembly ──── SKILL.md §4
   │                   tag dialect (Anima): score_9, score_8_up, [subject], [action], [lighting], ...
   │                   + aesthetic overlay (lighting + composition + color)
   │                   + dialect block (from step 1)
   │                   first-10-token rule per encoder type (LLM vs CLIP)
   │
   ▼
⑥ 11-item self-check ─ SKILL.md §5
                       1) 10-dim complete  2) tags validated  3) first-10 = SUBJECT+ACTION
                       4) STYLE in first 25%  5) lighting/composition/color each present
                       6) token range  7) no abstract stacking  8) STYLE names medium
                       9) LoRA compatible  10) model-specific constraints  11) concept density > 0.6
                       ↓
                     mcp__comfyui-mcp__generate_image(prompt=..., negative_prompt=...)
```

---

## §3 Python Tools — 5 stdlib-only

### 3.1 `recipe_lookup.py` (upgraded)

**Purpose**: model ID → recipe + dialect block.

**API**:
```bash
python recipe_lookup.py --model anima             # exact + weighted fuzzy match
python recipe_lookup.py --model "stable_diff"      # substring fallback
python recipe_lookup.py --check-alias anima_baseV10   # alias → canonical
python recipe_lookup.py --list-aliases             # dump full alias table
```

**Output**:
```json
{
  "matched": true,
  "matched_id": "anima",
  "heading": "### Anima (Black Forest Labs)",
  "frontmatter": {"id": "anima", "family": "...", "dialect": "...", ...},
  "dialect_block": "### Anima ...\n- **Prompt style:** ...\n...",
  "score": 0.95,
  "match_path": "exact"  # or "alias" or "weighted_fuzzy"
}
```

**Algorithm (3-pass)**:
1. **Pass 1 — exact id match** (case-insensitive). Score 1.0.
2. **Pass 2 — alias match** via internal `_ALIASES` dict. Score 0.95.
3. **Pass 3 — weighted fuzzy** across 5 fields (`id`, `family`, `modality`, `heading`, `dialect`). Threshold 0.5.

**Internal table `_ALIASES`** (hardcoded in module, also maintainable via `recipe_yaml.py --add-alias`):
```python
_ALIASES = {
    "anima_baseV10": ["anima"],
    "AnimaStandardV7": ["anima"],
    "sdxl_base": ["sdxl"],
    "stable_diffusion_xl": ["sdxl"],
    "pony_diffusion_v6_xl": ["pony"],
    "flux_1_dev": ["flux_1"],
    "flux_1_schnell": ["flux_1"],
    "ltx_2_3": ["ltx_2_pro"],
    # ... 50 entries target
}
```

**Stdlib-only score function**:
```python
def _score(text: str, query: str, weight: float) -> float:
    """exact=1.0, substring=0.6, char-overlap=0.3."""
    t = text.lower()
    if t == query: return weight
    if query in t or t in query: return weight * 0.6
    common = sum(1 for c in set(query) if c in set(t))
    return weight * (common / max(len(set(query)), 1)) * 0.3
```

### 3.2 `recipe_yaml.py` (upgraded)

**Purpose**: idempotent normalization + schema validation + alias maintenance.

**API**:
```bash
python recipe_yaml.py                          # normalize in place (default)
python recipe_yaml.py --check                  # exit 1 if drift, 0 if up-to-date
python recipe_yaml.py --validate-schema        # exit 1 if 9-field missing or schema_version absent
python recipe_yaml.py --add-alias anima=anima_baseV10,AnimaStandardV7  # append to _ALIASES
python recipe_yaml.py --list-aliases           # print full table
python recipe_yaml.py --path <file>            # override default MODELS.md path
```

**Schema rules enforced** (`--validate-schema`):
- `id` field required (every recipe)
- `family`, `modality`, `dialect`, `negative_policy`, `triggers`, `license`, `source`, `sample_prompts` required if present in upstream
- unknown fields preserved (not rejected) but warned
- `modality` ∈ {`image`, `video`, `audio`, `utility`, `conditioning`, `3d`}
- `id` snake_case, unique

### 3.3 `tag_lookup.py` (NEW)

**Purpose**: danbooru/wd14 tag dictionary query.

**API**:
```bash
python tag_lookup.py --query "金发"               # substring + alias match
python tag_lookup.py --query "pointy_ears"        # exact
python tag_lookup.py --query "elf" --limit 5      # top-N substring
python tag_lookup.py --category 0                 # filter by category
python tag_lookup.py --exact "long_hair"          # strict match only
```

**Output**:
```json
[
  {
    "canonical": "long_hair",
    "category": 0,
    "count": 4350743,
    "aliases": ["/lh", "longhair"],
    "source": "danbooru"
  },
  ...
]
```

**Algorithm**:
1. Load `dictionary/tag-index.json` once at startup (cached).
2. Pass 1 — exact canonical name match.
3. Pass 2 — alias match (reverse-lookup alias → canonical).
4. Pass 3 — substring match on canonical names, scored by `count` desc.

**Index schema** (built by `build_tag_index.py`):
```json
{
  "_meta": {"source": "danbooru.csv", "version": "2026-08-01", "row_count": 140782},
  "by_canonical": {"long_hair": {"cat": 0, "count": 4350743, "aliases": ["/lh", "longhair"]}, ...},
  "by_alias": {"/lh": ["long_hair"], "longhair": ["long_hair"], ...}
}
```

### 3.4 `scene_match.py` (NEW)

**Purpose**: scene keyword → recipe file paths (lighting + composition + color).

**API**:
```bash
python scene_match.py --query "樱花树下 释放魔法"
python scene_match.py --query "夜景" --top 1
python scene_match.py --query "" --list            # dump all scenes in INDEX.md
```

**Output**:
```json
[
  {
    "scene": "night_street",
    "keywords_matched": ["夜景", "霓虹"],
    "recipes": {
      "lighting": "aesthetics/lighting/lighting-neon-noir.md",
      "composition": "aesthetics/composition/composition-low-angle.md",
      "color": "aesthetics/color/color-teal-orange.md"
    },
    "score": 0.85
  },
  ...
]
```

**Algorithm**:
1. Read `aesthetics/INDEX.md` (1-line per scene: `keywords: ..., lighting: ..., composition: ..., color: ...`).
2. Tokenize user query (CJK char + space + punctuation aware).
3. For each scene line, count keyword overlap.
4. Return top-3 (or `--top N`) scenes with score ≥ 0.2.

**Fallback**: if no scene has score ≥ 0.2, return `style-presets.md` top 3 entries.

### 3.5 `build_tag_index.py` (NEW, one-shot)

**Purpose**: build `dictionary/tag-index.json` from `danbooru.csv` + `wd14-tags.csv`.

**API**:
```bash
python build_tag_index.py                # build (overwrites tag-index.json)
python build_tag_index.py --check        # exit 1 if CSV newer than index
python build_tag_index.py --stats        # print row counts, alias ratios
```

**Algorithm**:
1. Parse `danbooru.csv` row-by-row. Schema: `name,category,count,aliases`.
2. Parse aliases column (CSV-escaped quoted list).
3. Build `by_canonical` (name → {cat, count, aliases}) and `by_alias` (alias → [canonical]).
4. Merge with `wd14-tags.csv` (tag_id → name, category, count).
5. Write atomically to `dictionary/tag-index.json` with `_meta` header.

**Idempotent**: re-running produces byte-stable output. CI-style usage: `python build_tag_index.py && git diff --exit-code dictionary/tag-index.json` to detect drift.

---

## §4 SKILL.md v5 Outline (~250 lines)

| § | Content | Lines |
|---|---------|-------|
| §0 First principles | "ComfyUI only paints to the prompt; it has no taste" + decisions live in data | ~30 |
| §1 6-step pipeline | (see §2 above) | ~50 |
| §2 Data sources | directory + aesthetics + negative + models + recipes + hardware | ~40 |
| §3 10-dimension framework | subject/action/scene/lighting/composition/color/style/mood/medium/quality | ~30 |
| §4 Assembly principles | first-10-token rule per encoder (LLM vs CLIP); 3 dialects; weighting | ~40 |
| §5 11-item self-check | (existing 10+1) | ~30 |
| §6 MCP relationship + triggers | (existing; drop `图生视频` overlap with stage-4-motion — see §6) | ~30 |

**Total**: ~250 lines (vs. current v4 ~230 lines; +20 lines for 10-dim + scene-recipes flow).

---

## §5 Cross-Tool Compatibility

- **Backwards compat**: `recipe_lookup.py --model X` continues to work. v4 callers see no signature change.
- **v5-only tools**: `tag_lookup.py`, `scene_match.py`, `build_tag_index.py` are net-new. No v4 callers depend on them.
- **Alias table**: shared between `recipe_lookup.py` (read) and `recipe_yaml.py` (write). To avoid duplication, store in `internals/_aliases.py` as a single module imported by both.

---

## §6 Trigger Word Cleanup

The current `prompt-forge/SKILL.md` frontmatter triggers list `图生视频`. This collides with `manga-stage-4-motion`'s `图生视频` trigger, creating ambiguous routing. In v5:

- **prompt-forge** drops `图生视频` from its triggers. The skill's role is prompt engineering; video prompt writing is handled by step 5 (`scene_match.py` → `video-archetypes.md` → assembly).
- **Rationale to add to SKILL.md §0**: "prompt-forge owns prompt quality; image-vs-video routing is the LLM's job after assembly (via tool choice `mcp__comfyui-mcp__generate_image` vs `__generate_video`)."

---

## §7 Verification Plan

### Unit (each Python tool):
```bash
python recipe_lookup.py --model anima        # exit 0, JSON, matched=true
python recipe_lookup.py --model __nonexistent  # exit 0, JSON, matched=false
python recipe_yaml.py --check               # exit 0 if no drift
python recipe_yaml.py --validate-schema     # exit 0
python tag_lookup.py --query "金发"          # exit 0, JSON array
python scene_match.py --query "夜景"          # exit 0, JSON array
python build_tag_index.py --stats           # prints counts
python build_tag_index.py --check           # exit 0 (index fresh)
```

### Integration:
- Run `SKILL.md §1` 6-step flow end-to-end with user query. Confirm each tool call succeeds.
- Verify recipe_lookup still finds all 81 existing recipes (no regression).
- Verify tag_lookup returns canonical names that match what the user actually typed.
- Verify scene_match returns recipes whose content is genuinely relevant to the query.

### Performance:
- `recipe_lookup.py --model X`: < 50 ms (81 recipes in memory)
- `tag_lookup.py --query X`: < 100 ms (140K tags in preloaded index)
- `scene_match.py --query X`: < 30 ms (≤ 100 INDEX.md lines)
- `build_tag_index.py`: < 10 s (one-shot; not on critical path)

---

## §8 Out of Scope (explicit non-goals)

- ❌ **Adding new recipes** to MODELS.md (out of scope; v5 only restructures existing data)
- ❌ **Replacing the SKILL.md frontmatter `description` field** with English (out of scope)
- ❌ **Building a separate `aesthetics_index.py`** (YAGNI — INDEX.md 1-pass grep is sufficient)
- ❌ **Building `prompt_builder.py`** (LLM-as-assembly is smarter than Python-as-assembly; SKILL.md §4 covers this)
- ❌ **Migrating spec-v3.md full text** to SPEC.md verbatim (only the parts that inform v5 design)
- ❌ **Updating `manga-orchestrator` or other skills** (out of scope; their references to prompt-forge remain valid)

---

## §9 Migration Order

1. **Create directories**: `dictionary/`, `aesthetics/`, `negative/`, `models/`, `docs/superpowers/specs/`
2. **Copy data verbatim** from vault into skill dirs (no transformation yet).
3. **Add `build_tag_index.py`** + first-time `tag-index.json` build.
4. **Add `tag_lookup.py`** with index loading + 3-pass matching.
5. **Add `scene_match.py`** with INDEX.md parser + keyword scoring.
6. **Upgrade `recipe_lookup.py`**: add `_ALIASES` + 3-pass matching + score output.
7. **Upgrade `recipe_yaml.py`**: add `--validate-schema` + `--add-alias`.
8. **Rewrite `SKILL.md` v5** (250 lines, drop `图生视频` trigger, restore 6-step + 10-dim).
9. **Migrate `spec-v3.md`** → `SPEC.md` (curated subset).
10. **Run all verification**; commit.

---

## §10 Open Questions (deferred to implementation)

- Alias table size target: 50 hardcoded entries, expandable via `--add-alias`?
- INDEX.md format: `csv` vs `markdown table` vs `json`? (Default: markdown table, 1 row per scene.)
- `tag-index.json` compression: gzip or plain? (Plain — git-trackable diffs matter.)
- `--exact` flag on tag_lookup: when does it differ from no flag? (No `--exact` = substring; `--exact` = strict canonical only.)

These are implementation-time decisions; spec leaves them open for the plan.