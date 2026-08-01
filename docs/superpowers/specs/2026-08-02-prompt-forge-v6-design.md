# prompt-forge v6 — Semantic Enrichment + Translation Layer Design

**Date**: 2026-08-02
**Status**: approved (brainstorming Q1-Q5 + recommendation pass)
**Author**: brainstormed with user; design drafted by Claude

---

## Context

prompt-forge v5 (e7ce3f8 on main) inlined vault knowledge into the skill. End-to-end smoke test exposed three real gaps that prevent the skill from being usable for the user's stated goal — "tell me what to draw, the model fills in details and tags automatically":

1. **`tag_lookup.py` only handles English queries** — danbooru.csv is 140K English tags. User's natural Chinese query ("金发", "精灵", "樱花") returns `[]`.
2. **scene_keywords are Chinese-only** — INDEX.md is a 12-row CJK table. English queries fall through to `style-presets.md` headings ("风格预设", "选择逻辑") as fallback.
3. **frontmatter pollution** — vault-style `---` blocks at top of INDEX.md and other markdown files are parsed as table rows by `scene_match.py`, polluting token sets.

The user clarified the target behavior: when the user says "what to draw", the LLM should (a) enrich the input with details, (b) decompose into dimensions, (c) translate to English, (d) match tags, (e) assemble. v6 implements this with both an LLM-led phase (skill instructions) and a Python layer (translation CLI + translation table).

---

## §1 Scope

**In scope:**
- prompt-forge v5 → v6 upgrade (single skill, in-place)
- 1 new Python tool (`query_normalize.py`)
- 1 new data file (`dictionary/zh-en.json` — baseline 75+ entries in this spec; target 200 by v6 release)
- 3 Python tool upgrades (`tag_lookup.py`, `scene_match.py` — frontmatter skip; `recipe_lookup.py` — no change)
- SKILL.md v6 rewrite (new step 0.5 semantic enrichment)
- `aesthetics/INDEX.md` bilingual keywords
- `SPEC.md` updated to v6 sections
- ~20 new tests

**Out of scope:**
- Other 7 skills (manga-orchestrator, stage-1/2/3/4, ffmpeg-pipeline, lora-trainer) — no changes
- `recipes/MODELS.md` — no changes
- `hardware/8gb.json` — no changes (separate schema-drift issue)
- Cloud translation APIs — breaks "local-first" hard constraint
- Auto-rebuild of `zh-en.json` from any source — manual curation only

---

## §2 Architecture — Target Tree

```
skills/prompt-forge/
├── SKILL.md                       v6 (rewrite ~300 lines)
├── SPEC.md                        v6 spec (from spec-v3 + new sections)
├── recipes/MODELS.md              (unchanged)
├── dictionary/
│   ├── README.md
│   ├── danbooru.csv               (unchanged)
│   ├── wd14-tags.csv              (unchanged)
│   ├── tag-index.json             (unchanged)
│   ├── zh-en.json                 ★ NEW — 200-500 entries (curated)
│   └── README-zh-en.md            ★ NEW — usage notes
├── aesthetics/                    (mostly unchanged)
│   ├── INDEX.md                   ⚙️ bilingual keywords
│   └── ... (other unchanged)
├── negative/                      (unchanged)
├── models/                        (unchanged)
├── internals/
│   ├── query_normalize.py         ★ NEW — translation CLI
│   ├── query_normalize_test_data.json   ★ NEW — test fixtures
│   ├── tag_lookup.py              ⚙️ skip frontmatter
│   ├── scene_match.py             ⚙️ skip frontmatter + accept bilingual
│   ├── recipe_lookup.py           (unchanged from v5)
│   ├── recipe_yaml.py             (unchanged from v5)
│   ├── build_tag_index.py         (unchanged from v5)
│   ├── _aliases.py                (unchanged from v5)
│   └── tests/
│       ├── test_query_normalize.py   ★ NEW
│       ├── test_tag_lookup.py        ⚙️ +2 tests
│       ├── test_scene_match.py       ⚙️ +1 test
│       ├── test_recipe_lookup.py     (unchanged)
│       ├── test_recipe_yaml.py       (unchanged)
│       ├── test_aliases.py           (unchanged)
│       └── test_build_tag_index.py   (unchanged)
└── hardware/                      (unchanged)
```

---

## §3 Data Flow — 6.5 Step Pipeline

```
User: "用 Anima 出金发精灵女法师在樱花树下释放魔法的图"
   │
   ▼
① Model ID ──────── recipe_lookup.py --model anima
   │                 (unchanged from v5; 3-pass match, backwards compat)
   │
   ▼
② Semantic Enrichment ★ NEW ── LLM-led (SKILL.md §0.5)
   │                 Input: 5-word user query
   │                 Output: enriched JSON with 10 dims
   │                 {
   │                   "subject": "young elf mage",
   │                   "action": "casting fire magic",
   │                   "scene": "under cherry blossoms in forest",
   │                   "lighting": "soft window light from afternoon sun",
   │                   ...
   │                 }
   │
   ▼
③ Normalize + Translate ★ NEW ── query_normalize.py --enriched <JSON>
   │                 3-pass translation:
   │                   Pass 1: zh-en.json direct hit
   │                   Pass 2: substring (e.g. "女法师" → ["女","法师"] → ["female","mage"])
   │                   Pass 3: leave unmapped → SKILL.md §0.5 lets LLM handle in step ②
   │                 Output: {"english_query": "elf mage female casting fire magic ...",
   │                           "translations": [...], "unmapped": [...]}
   │
   ▼
④ Scene Recipes ─── scene_match.py --query <EN query>
   │                 (frontmatter skip + bilingual INDEX keywords)
   │                 → {lighting, composition, color}
   │
   ▼
⑤ Tag Validation ─── tag_lookup.py --query <EN tokens>
   │                  (frontmatter skip — moot for JSON, but applies if reading md)
   │                  → [{canonical, category, count, aliases, score}]
   │
   ▼
⑥ Assembly + 11-item self-check ── SKILL.md §4 + §5
   │
   ▼
                   mcp__comfyui-mcp__generate_image(prompt=..., negative_prompt=...)
```

**Key change from v5**: ② and ③ are LLM-led phases. LLM enriches input, then `query_normalize.py` translates CJK→EN. Python tools downstream always see English queries.

---

## §4 `dictionary/zh-en.json` Schema

```json
{
  "金发": "long_hair",
  "黑发": "black_hair",
  "银发": "silver_hair",
  "短发": "short_hair",
  "长发": "long_hair",
  "双马尾": "twintails",
  "精灵": "elf",
  "精灵耳": "pointy_ears",
  "猫耳": "cat_ears",
  "兽耳": "animal_ears",
  "魔法": "magic",
  "释放魔法": "casting_magic",
  "火球": "fireball",
  "冰冻": "freezing",
  "治愈": "healing",
  "樱花": "cherry_blossoms",
  "森林": "forest",
  "森林深处": "deep_in_forest",
  "夜景": "night",
  "雨": "rain",
  "雪": "snow",
  "海洋": "ocean",
  "山脉": "mountain",
  "废墟": "ruins",
  "城堡": "castle",
  "水彩": "watercolor",
  "油画": "oil_painting",
  "像素画": "pixel_art",
  "动漫": "anime",
  "写实": "realistic",
  "水墨": "ink_wash",
  "赛博朋克": "cyberpunk",
  "蒸汽朋克": "steampunk",
  "哥特": "gothic",
  "奇幻": "fantasy",
  "科幻": "sci-fi",
  "校园": "school",
  "战争": "war",
  "肖像": "portrait",
  "风景": "landscape",
  "室内": "indoor",
  "户外": "outdoor",
  "室内光线": "indoor_lighting",
  "窗光": "window_light",
  "自然光": "natural_light",
  "暖色调": "warm_tone",
  "冷色调": "cool_tone",
  "近景": "close_up",
  "中景": "medium_shot",
  "远景": "wide_shot",
  "全景": "panorama",
  "半身像": "bust",
  "全身像": "full_body",
  "侧脸": "side_face",
  "背影": "back_view",
  "微笑": "smile",
  "严肃": "serious",
  "悲伤": "sad",
  "愤怒": "angry",
  "平静": "calm",
  "战斗": "battle",
  "休息": "resting",
  "飞行": "flying",
  "奔跑": "running",
  "坐着": "sitting",
  "站立": "standing",
  "夜晚": "night",
  "白天": "daytime",
  "黎明": "dawn",
  "黄昏": "dusk",
  "正午": "noon",
  "凌晨": "early_morning",
  "金发精灵": "long_hair_elf",
  "森林精灵": "forest_elf",
  "红发": "red_hair",
  "粉发": "pink_hair",
  "蓝发": "blue_hair",
  "紫发": "purple_hair",
  "白毛": "white_hair"
}
```

Target: 200 entries by v6 release (this spec lists 76 as baseline seed); covers ~80% of common CJK tag vocabulary.

**Entry types:**
1. **Single token**: `"金发": "long_hair"`
2. **Compound phrase**: `"释放魔法": "casting_magic"` (longer phrases matched first)
3. **Compound canonical**: `"金发精灵": "long_hair_elf"` (already-canonicalized compound)

---

## §5 `query_normalize.py` API

### CLI

```bash
# Direct query
python query_normalize.py --query "金发精灵女法师"
# Output JSON to stdout

# Receive enriched JSON from step ② (LLM output)
python query_normalize.py --enriched <path-to-json-file>

# Read from stdin (for piping)
echo '{"query":"金发精灵"}' | python query_normalize.py --from-stdin

# Stats mode (verify zh-en.json loaded)
python query_normalize.py --stats
```

### Output JSON

```json
{
  "original": "金发精灵女法师",
  "tokens": ["金发", "精灵", "女法师"],
  "translations": [
    {"zh": "金发", "en": "long_hair", "source": "zh-en.json", "match_type": "exact"},
    {"zh": "精灵", "en": "elf", "source": "zh-en.json", "match_type": "exact"},
    {"zh": "女法师", "en": ["女", "法师"], "source": "substring-fallback",
     "match_type": "substring",
     "intermediate": "female mage"}
  ],
  "unmapped": [],
  "english_query": "long_hair elf female mage",
  "hit_rate": 1.0,
  "fallback_used": false
}
```

### Algorithm

```python
def normalize(text: str, zh_en: dict, ...) -> dict:
    # 1. Tokenize CJK + Latin (existing CJK-aware logic from scene_match.py)
    tokens = cjk_latin_tokenize(text)

    # 2. Pass 1: exact match in zh-en.json (longest n-gram first)
    for n in [4, 3, 2, 1]:  # n-gram length; try longest phrase first
        for span in extract_ngrams(tokens, n):
            if span in zh_en:
                translations.append(...)

    # 3. Pass 2: substring decomposition (e.g. "女法师" → ["女", "法师"])
    for unmapped_token in remaining:
        for char in unmapped_token:
            if char in zh_en:
                translations.append(...)

    # 4. Build english_query
    english_query = " ".join(t["en"] for t in translations)

    # 5. Compute hit_rate; flag fallback_used if any unmapped
```

---

## §6 `SKILL.md` v6 Outline (~300 lines)

| § | Content | Lines |
|---|---------|-------|
| §0 | First principles (unchanged from v5) | ~30 |
| §0.5 | **NEW — Semantic Enrichment Guidance** (LLM how-to): how to expand 5-word user query to 30-50 word enriched description with all 10 dims | ~30 |
| §1 | 6.5-step pipeline (updated diagram with step ② enrichment + step ③ normalize) | ~50 |
| §2 | Data sources (now includes `dictionary/zh-en.json` + `query_normalize.py`) | ~40 |
| §3 | 10-dimension framework (unchanged) | ~30 |
| §3.5 | **NEW — Normalization Call**: when to call `query_normalize.py` + how to interpret output | ~20 |
| §4 | Assembly principles (unchanged) | ~40 |
| §5 | 11-item self-check (unchanged) | ~30 |
| §6 | MCP + triggers (unchanged; still no `图生视频`) | ~30 |

**Total**: ~300 lines (vs. v5 ~250; +50 lines for §0.5 + §3.5 + flow updates)

---

## §7 `aesthetics/INDEX.md` Bilingual Update

| scene | keywords (bilingual) | lighting | composition | color |
|-------|----------------------|----------|-------------|-------|
| night_street | 夜景,霓虹,街景,都市夜,neon,night,urban | lighting/lighting-neon-noir | composition/composition-low-angle | color/color-teal-orange |
| golden_hour | 黄昏,日落,金色时刻,夕阳,sunset,dusk,golden hour | ... |
| ... | ... | ... | ... | ... |

**Constraint**: 12 rows unchanged. Each row's `keywords` cell grows to ~10 tokens (5 CJK + 5 EN). Backwards compatible: `scene_match.py` tokenization handles both.

---

## §8 Compatibility & Migration

| Aspect | v5 behavior | v6 behavior | Risk |
|--------|-------------|-------------|------|
| v5 recipe_lookup API | unchanged | unchanged | 0 |
| v5 tag_lookup API | unchanged | unchanged (frontmatter skip is internal) | 0 |
| v5 scene_match API | unchanged | unchanged | 0 |
| zh-en.json | NEW | 200-500 entries loaded by query_normalize.py | low — only affects new tool |
| SKILL.md triggers | 15 keywords | 15 keywords (no change to v5 list) | 0 |
| Tests | 40 pass | 40 + ~20 new pass | 0 |

**Backwards compat**: every v5 caller of recipe_lookup.py / tag_lookup.py / scene_match.py sees no behavior change (new files/tools are additive).

---

## §9 Verification Plan

### Unit (after each component):

```bash
# After dictionary/zh-en.json created
PYTHONPATH=skills/prompt-forge python -c "
import json
d = json.load(open('skills/prompt-forge/dictionary/zh-en.json'))
assert len(d) >= 100, 'too few entries'
assert d['金发'] == 'long_hair'
assert d['释放魔法'] == 'casting_magic'
print('OK', len(d), 'entries')
"

# After query_normalize.py created
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_query_normalize.py -v

# After tag_lookup / scene_match upgrades
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/ -v
# Expect: 40 (v5) + ~20 (new) = ~60 passing
```

### End-to-end smoke (LLM-driven, manual):

```bash
# ① recipe_lookup.py --model anima
# ② LLM enriches "用 Anima 出金发精灵女法师" (manual)
# ③ query_normalize.py --enriched /tmp/enriched.json
# ④ scene_match.py --query <EN normalized>
# ⑤ tag_lookup.py --query <EN tokens>
# ⑥ LLM assembles + 11-check + mcp__comfyui-mcp__generate_image(...)
```

### Compatibility:

```bash
# Existing v5 callers still work
PYTHONPATH=skills/prompt-forge python skills/prompt-forge/internals/recipe_lookup.py --model anima
PYTHONPATH=skills/prompt-forge python skills/prompt-forge/internals/tag_lookup.py --query "elf"
```

---

## §10 Risks & YAGNI

| Risk | Mitigation |
|------|-----------|
| zh-en.json 200-500 entries may miss edge cases | 80% common cases covered; SKILL.md §0.5 lets LLM handle unmapped (LLM rewrites to English in step ②) |
| LLM translation non-deterministic | Step ② has fixed prompt template; cache common rewrites |
| Bilingual INDEX.md inflates rows | Cap at 10 tokens per cell; 12 rows × 10 tokens = small |
| query_normalize.py grows unwieldy | Cap at 200 lines; use stdlib only |
| v6 scope creep into other skills | No changes to other 7 skills |
| v6 zh-en.json becomes stale | Manual curation; documented in `dictionary/README-zh-en.md` |

---

## §11 Out of Scope (explicit non-goals)

- ❌ External translation APIs (breaks local-first)
- ❌ Auto-extend zh-en.json from existing sources (manual curation only)
- ❌ Changes to other 7 skills
- ❌ Changes to `recipes/MODELS.md` or `hardware/8gb.json`
- ❌ Cloud LLM for translation (breaks local-first)
- ❌ Frontend UI / dashboard for zh-en editing
- ❌ Bidirectional EN→zh translation
- ❌ v7 design (deferred)