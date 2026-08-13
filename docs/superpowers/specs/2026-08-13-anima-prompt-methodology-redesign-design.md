---
title: Anima prompt methodology redesign — virgin rewrite of the authoring method
date: 2026-08-13
status: draft
author: claude
related:
  - docs/superpowers/specs/2026-08-13-prompt-forge-redesign-design.md (v2.0 structure refactor — INHERITED, not replaced)
  - skills/prompt-forge/references/dialects/anima/dialect.md (to be rewritten)
  - skills/prompt-forge/references/shared/authoring-contract.md (anima section to be rewritten)
  - skills/prompt-forge/prompt_forge/anima/author.py (field rank to be rewritten)
---

# Anima prompt methodology — virgin redesign

## 0. Relationship to prior work

The **v2.0 structure refactor** (`2026-08-13-prompt-forge-redesign-design.md`) is already implemented: the `references/{shared,quality,dialects}` tree, the 5-segment template, and the preflight scripts are in place. This spec **does not re-litigate structure**. It rewrites the **authoring methodology content** for the Anima still-image path, which the structure refactor left as legacy:

- v2.0's `output-protocol.md` hard rule **"No `(tag:1.2)` weight syntax"** contradicts Anima's official documented weighting support.
- v2.0's `authoring-contract.md` keeps a **14-field enum** with seven fields all at the same rank (`general` / `tag` / `attribute_binding` / `action_and_relation` / `composition_and_camera` / `environment_and_props` / `lighting_and_visual_style` = all rank 5) — no internal order.
- No positive quality-prefix baseline; negative baseline uses Pony's `score_4..6` instead of Anima's official `score_1..3`.
- No variant awareness (Base / Aesthetic / Turbo prompt differently).
- No artist-mixing methodology, no weight calibration, no sparse-input completion.

**Scope of this rewrite**: the Anima path only. H3 (`minimax-h3`) is untouched. The shared runtime (`facts.py`, `token_counting.py`, `artifacts.py`, `budgets.py` core, `compression.py` core) is touched only where the Anima path needs it — a single optional field on the shared segment model.

**Guiding principle (virgin)**: re-derive the Anima authoring method from the model's own facts — LLM text encoder, official tag dialect, documented weighting, dropout training, variant differences — not from Pony/NovelAI/SDXL habit. Drop anything that exists only for backward compatibility.

---

## 1. Evidence base

All methodology below is anchored to Anima's documented behavior (not inherited habit):

- **Official README** (CircleStone Labs × Comfy Org, 2B anime model): Qwen3-0.6B text encoder (not CLIP), lowercase + space-separated tags, `@artist` prefix required, Gelbooru-over-Danbooru canonical, weighting needs higher values than SDXL, random tag dropout, tag order `quality→count→character→series→artist→general`, positive prefix `masterpiece, best quality, score_7, safe`, negative `worst quality, low quality, score_1..3, blurry, jpeg artifacts, chromatic aberration`, Base/Aesthetic/Turbo variant differences.
- **AnimaLoraStudio tagging guide** (trainer view): 9-slot order `quality/safety→count→character→series→artist→appearance→tags→environment→nl`, natural-language description last after a period, character variants via space+parentheses.
- **Community practice** (Civitai / NGA / PTT): artist weights start at **2.0** and reach **3–4** without artifacts; score tags `score_8/9` stiffen composition — the sweet spot is `score_7`; to preserve artist style, minimize `masterpiece`/`score_*` and keep only `best quality`; the negative prompt is "temperamental" — keep it lean; `anime coloring` (strength <1) tames over-slick output; cold characters need natural-language attribution (`She is a character from the game "Azur Lane"...`); failed tags like `holding phone` must become `holding mobile phone`; more tags → raise Shift to 10–24.

---

## 2. Design axioms

1. **Anima is an LLM-encoder model, not CLIP.** Space-vs-underscore is real syntax; `(tag:weight)` is a first-class feature; tags and natural language mix freely; natural language closes the prompt after a period.
2. **The official tag order is authoritative.** We mirror it and extend it with the aesthetic layers in the correct natural position — never invent a divergent order.
3. **The official prefixes are a baseline the design enforces.** Positive and negative both get an explicit, variant-aware default. An author may override, but never silently omit.
4. **The model variant changes the prompt.** Base and Turbo use the full quality stack; Aesthetic drops `score_*` (they push into "slop"). This is an input knob, not prose advice.
5. **Dropout training ⇒ budget discipline.** Every tag must carry non-redundant information; the tag-count and token rulers remain, re-derived against the new slot structure.
6. **Sparse input is completed, not reflected back empty.** When the user gives little detail, the author fills the aesthetic layers and scene coherence by deliberate inference — always as removable embellishment, never overwriting a protected fact.

---

## 3. Slot structure (positive: 9 slots)

Replaces the legacy 14-field enum. Each slot is one unambiguous semantic; the seven rank-5 fields collapse into one ordered `general` slot plus a dedicated `environment` slot.

| # | Slot | Contents | Weight |
|---|---|---|---|
| 1 | `protocol_prefix` | quality + meta + year + safety tags | highest (enforced baseline) |
| 2 | `count` | subject count (`1girl`, `2boys`, `no humans`) | high |
| 3 | `character` | subject identity / IP character | high |
| 4 | `series` | source work / franchise | high |
| 5 | `artist` | `@artist`, weighted, mixable | medium-high |
| 6 | `appearance` | hair, eyes, body, clothing | medium |
| 7 | `general` | action/expression + five aesthetic layers, ordered (below) | medium |
| 8 | `environment` | location, props, weather | medium |
| 9 | `scene_description` | ≤1 natural-language bridge, after a period | lowest |

**`general` internal order** (the five aesthetic layers live here, in this order, after action/expression):

```
action / expression → composition → lighting → palette → camera → mood/texture
```

This gives the aesthetic layers a real ordering instead of a rank-5 tie, while keeping the slot count aligned to the model's training structure.

### 3.1 Negative slots (4 slots)

Replaces the legacy 5-field enum:

| Slot | Contents |
|---|---|
| `quality_baseline` | `worst quality, low quality, score_1, score_2, score_3` |
| `anatomy_and_structure` | `bad anatomy, bad hands, extra fingers, ...` (as needed) |
| `technical_defects` | `blurry, jpeg artifacts, chromatic aberration` |
| `user_exclusions` | user-specified exclusions only |

---

## 4. Quality prefix — enforced baseline, three tiers

The author **must** emit a `protocol_prefix`. The baseline is tiered by dominant intent:

| Tier | Trigger | Prefix |
|---|---|---|
| Standard | default (Base / Turbo) | `masterpiece, best quality, score_7, safe` |
| Artist-led | a `@artist` is present and the artist's style should dominate | `best quality, safe` |
| Aesthetic | model variant = Aesthetic | `best quality, safe` |

Rationale, all community-validated:
- `score_7` is the sweet spot; `score_8/9` stiffen composition (do not default to `score_9`).
- `masterpiece` and `score_*` dilute an artist's style — the artist-led tier drops them.
- Aesthetic was fine-tuned with quality tags stripped; `score_*` pushes toward slop.

The two quality systems (human `masterpiece..worst quality` and aesthetic `score_1..9`) may be used alone, together, or neither — this is documented, not forced.

> Note: Artist-led and Aesthetic tiers intentionally emit the same prefix (`best quality, safe`). The trigger differs (artist dominance vs. model variant); the outcome coinciding is a design fact, not an error.

---

## 5. Negative baseline — follow the official card

Enforced baseline: `worst quality, low quality, score_1, score_2, score_3` + `blurry, jpeg artifacts, chromatic aberration` + anatomy/count defects as needed + user exclusions.

**This replaces the legacy `score_4..6`** (a Pony habit — the direction is inverted for Anima). The negative prompt is kept **lean** per community warning that Anima's negative is temperamental; no padding.

---

## 6. Prompt weighting — first-class data

### 6.1 Segment model

`AuthoredSegment` gains an optional `render_weight: float | None = None`. When set, the segment renders as `(text:weight)`; when absent, as a bare tag. This is the **only** shared-layer change; H3 segments simply never set it.

### 6.2 Calibration (Anima-specific, documented as fact)

| Target | Range | Notes |
|---|---|---|
| ordinary tag | 1.0 – 2.0 | official example is `(chibi:2)` |
| artist tag | 2.0 – 4.0 | community: needs ≥2.0, 3–4 safe, whole block `(:2.0)` |
| validation window | 0.0 – 4.0 | outside ⇒ hard error; off the 1.0–2.0 band ⇒ warning |

The author sees these numbers as the model's real behavior — not SDXL's 0.8–1.4 habit.

### 6.3 Rendering

- `render_weight` set ⇒ `(text:weight)`; artist inside the parens: `(@artist:1.2)`.
- Weight is **rendered**, but **dedup / audit / compression operate on the de-weighted text** (strip `(...:w)` before comparing or looking up). Weight never changes a tag's semantic identity.

---

## 7. Artist mixing — four documented forms

Anima's LLM encoder merges artist semantics contextually, so SDXL-style chaining breaks. The dialect documents four working forms, from simplest to most controlled:

1. Comma list — `@artist_a, @artist_b` (community: often best).
2. Natural language — `using artist @A and @B to draw a picture`.
3. Weighted block — `Mixed style of following artists: (@artist1, @artist2:2.0)`.
4. Inline weights — `(@artist_a:2.0), (@artist_b:0.8)`.

Plus one mandatory warning: **anime character names carry style bias** — a famous character can pollute the intended artist style, so raise artist weight or bind to distinguishing features (expression, nose, eye shape). `@` also works on style descriptors such as `@anime coloring`.

---

## 8. Natural-language scene description

Rules (kept from the prior design, now with the missing guidance):

- **Count ≤ 1**, position **last**, after a period.
- **Dimensions**: `ownership | spatial_relation | causal_action | action_result | relation`.
- **No overlap** with tag segments (bind a fact once).
- **New guidance**: for multiple characters, name the character first then describe appearance — listing names alone confuses the model. A pure-NL author path needs ≥2 sentences (short NL gives unstable output). Long NL drifts toward realism/over-detail — keep it a *bridge*, not an essay.

---

## 9. Sparse-input completion (the "imagine and fill" principle)

This is the core authoring obligation when the user's request is thin. It is **deliberate inference**, not reflection.

**Rules:**
1. User facts (`user_locked` / `user_explicit` / `necessary_inference`) are protected — never altered, never dropped.
2. All completion is authored as `agent_embellishment` — removable, and the first thing compression deletes under budget pressure.
3. Completion follows five coherence layers, applied in order:

   | Layer | Question the author answers | Example fill |
   |---|---|---|
   | appearance coherence | do hair/eyes/body/clothing agree? | `brown hair` + `amber eyes` + `leather jacket` |
   | environment coherence | do location/props/weather agree? | `abandoned city` + `crumbling overpass` + `ashfall` |
   | action↔environment coherence | is the action physically possible here? | `running` under `blizzard` ⇒ `struggling through deep snow` |
   | lighting coherence | does light source match time/weather? | `golden hour` + `backlighting` + long shadows |
   | mood coherence | does atmosphere match genre? | wasteland ⇒ `somber`, `desaturated`, `overcast` |

4. Every filled tag passes the five-layer aesthetic retrieval + dictionary verification. No tag is invented from memory; an unverified tag is dropped or replaced with a verified canonical.
5. Completion is **coherent imagination**, not tag stacking — the five layers must tell one consistent story.

This is how "稀疏输入 → 优秀提示词" is achieved without violating the deterministic, fact-protecting contract.

---

## 10. Cold characters and failed tags

- **Cold character** (model may not know it): render via natural language — `She is a character from the game "Azur Lane", and her name is Anchorage`. Bind name → appearance explicitly.
- **Failed tags** (`holding phone` vs `holding mobile phone`): the dictionary verification in the audit is the guard. When a tag resolves to no dictionary entry, the author replaces it with the verified canonical before compile — not after a rejection.

---

## 11. Variant awareness

An **input knob**, not prose: the authoring request carries the target variant (`base` | `aesthetic` | `turbo`), defaulting to `base` (what `camera-image` pins). It only changes the quality-prefix tier (§4) and documents the `turbo` sampler reality (CFG 1, 8–12 steps) in the dialect. No other authoring behavior branches on it.

---

## 12. Dictionary / audit / compression — weight-aware

- `resolve` / `canonical_form` / `semantic_form` strip an optional trailing `:weight` before lookup or comparison, so `(chibi:2)` verifies as `chibi`.
- `@` handling: a non-resolving `@` is **downgraded from hard error to warning** to permit `@style` descriptors; a `@` that resolves to an artist still requires the `@` prefix.
- Compression dedup compares de-weighted text; lexical compression never strips the weight marker; agent-embellishment deletion counts the weighted token cost.
- Budget counts the **rendered** (weighted) form.

---

## 13. Files affected

### Rewritten (methodology content)

| File | Change |
|---|---|
| `references/dialects/anima/dialect.md` | 9-slot order, quality-prefix tiers, weight calibration, artist mixing, variant notes |
| `references/shared/authoring-contract.md` | replace the 14-field anima enum with the 9-slot + 4-slot structure; add `render_weight` |
| `references/shared/output-protocol.md` | **remove** the "no weight syntax" rule; document `(tag:weight)` rendering |
| `references/shared/natural-language.md` | add multi-character naming, ≥2-sentence pure-NL floor, long-NL realism warning |
| `references/quality/budget-ruler.md` | negative baseline `score_4..6` → `score_1..3`; prefix share reservation |
| `references/quality/tag-count-ruler.md` | per-slot targets re-keyed to the 9 slots |
| `references/dialects/anima/vocabulary/README.md` | field mapping re-keyed to 9 slots |
| `references/shared/aesthetic-coverage.md` | add the sparse-input five-coherence layers (§9) |
| `references/dialects/anima/recipes/*.md` (6) | re-key to 9 slots; artist-led tier where a recipe implies a style |

### Code (minimal, methodology-serving)

| File | Change |
|---|---|
| `prompt_forge/contracts.py` | `AuthoredSegment.render_weight: float \| None = None` (shared, H3 unaffected); `AnimaAuthoringRequest.variant: Literal["base","aesthetic","turbo"] = "base"` |
| `prompt_forge/anima/author.py` | `_FIELD_RANK` → 9-slot rank; `_NEGATIVE_FIELDS` → 4-slot; render weights; emit prefix baseline |
| `prompt_forge/anima/protocol.py` | de-weight in `canonical_form` / `semantic_form` |
| `prompt_forge/anima/dictionary.py` | de-weight before resolve |
| `prompt_forge/anima/audit.py` | de-weight lookup; `@` non-resolve → warning |
| `prompt_forge/compression.py` | de-weight dedup; weighted token cost (anima structure only) |
| `knowledge/anima/budget-policy.json` | `protocol_prefix` share + negative baseline keys |

### Tests

| File | Change |
|---|---|
| `tests/test_anima_author.py` | 9-slot ordering, prefix baseline per tier, negative `score_1..3`, weight rendering |
| `tests/test_anima_dictionary.py` | weighted-tag resolution |
| new `tests/test_anima_weight.py` | weight render / de-weight dedup / calibration window |

---

## 14. Non-backward-compatible deltas (explicit)

- 14 positive fields → **9 slots**; 5 negative fields → **4 slots**. Old field names are gone; no alias mapping.
- `score_4..6` negative baseline → `score_1..3`. Old compiled negatives change.
- Weight syntax is now **legal and first-class**; the "no weight syntax" rule is deleted.
- `@` non-resolve changes from hard error to warning.
- `render_weight` appears in the segment model; old artifacts without it still parse (the field is optional), but new authoring emits it where weighted.

---

## 15. Acceptance criteria

1. A thin request ("wasteland battle, two fighters") compiles to `production_ready` **and** the produced positive prompt demonstrates all five aesthetic layers filled by coherent inference (§9), each tag dictionary-verified.
2. The positive prompt opens with the correct tier prefix (`masterpiece, best quality, score_7, safe` for Base standard) and orders slots per §3.
3. The negative prompt contains `score_1, score_2, score_3` (not `4..6`).
4. A weighted segment renders as `(text:weight)`; the same tag un-weighted dedupes against its weighted twin.
5. `@` on an unresolvable style descriptor yields a warning, not a hard error.
6. `pytest tests/` passes; the 9-slot and weight tests are green.
7. `grep -rn 'score_4\|score_5\|score_6\|no weight syntax\|(tag:1.2)'` returns no methodology hits outside history.

---

## 16. Out of scope

- H3 (`minimax-h3`) methodology.
- The v2.0 directory structure (already done).
- Dictionary acquisition, benchmark methodology, `mcp_server/` code, camera-skill runtime.
- Adding new model dialects.
