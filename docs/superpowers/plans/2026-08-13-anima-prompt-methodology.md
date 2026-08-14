# Anima Prompt Methodology Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the Anima still-image prompt authoring method from the model's own documented facts — 9-slot structure, enforced quality-prefix tiers, first-class prompt weighting, corrected negative baseline, variant awareness, and sparse-input completion — without touching the H3 path.

**Architecture:** The v2.0 directory structure stays. Code changes are minimal and weight-aware: one optional `render_weight` field on the shared segment model, a `deweight()` lexical helper in the Anima protocol layer, and a 14→9 positive / 5→4 negative field re-rank in the compiler. The methodology lives in the rewritten `references/` docs. TDD throughout: each code task writes its failing test first.

**Tech Stack:** Python 3 (`dataclasses`, `re`, `Literal`), `pytest`, the bundled `tokenizers` package, SQLite tag dictionary.

**Spec:** `docs/superpowers/specs/2026-08-13-anima-prompt-methodology-redesign-design.md`

## Global Constraints

- Virgin rewrite: **no** `legacy`/`deprecated`/`backward-compat` aliases anywhere; old field names are deleted, not mapped.
- Only the Anima path changes. H3 (`minimax-h3`) code and docs are untouched.
- The shared runtime is touched in exactly one place: `AuthoredSegment.render_weight: float | None = None`. No other shared signature changes.
- Negative baseline is `score_1, score_2, score_3` (never `4..6`).
- Weight validation window is `0.0–4.0`; the `1.0–2.0` band is the ordinary-tag norm, `2.0–4.0` the artist norm.
- Positive field names are exactly: `protocol_prefix, count, character, series, artist, appearance, general, environment, scene_description`.
- Negative field names are exactly: `quality_baseline, anatomy_and_structure, technical_defects, user_exclusions`.
- Prefix tiers: Standard `masterpiece, best quality, score_7, safe`; Artist-led `best quality, safe`; Aesthetic `best quality, safe`.
- Work in a git branch off `main` (see Task 0); commit each task.

---

## Task 0: Branch off main

**Files:**
- No file changes. Git only.

- [ ] **Step 1: Create the branch**

```bash
cd "D:/Projects/comfyui-chenxin" && git checkout -b feat/anima-prompt-methodology
```

Expected: `Switched to a new branch 'feat/anima-prompt-methodology'`.

---

## Task 1: Add `render_weight` and `variant` to the shared contracts

**Files:**
- Modify: `skills/prompt-forge/prompt_forge/contracts.py`
- Test: `skills/prompt-forge/tests/test_anima_author.py` (extend existing)

**Interfaces:**
- Produces: `AuthoredSegment.render_weight: float | None` (default `None`); `AnimaAuthoringRequest.variant: Literal["base","aesthetic","turbo"]` (default `"base"`). All later tasks read these.

- [ ] **Step 1: Write the failing test**

Append to `skills/prompt-forge/tests/test_anima_author.py`:

```python
def test_segment_render_weight_defaults_none():
    from prompt_forge.contracts import AuthoredSegment
    seg = AuthoredSegment(
        segment_id="s1", field="general", text="smile",
        fact_ids=("f1",), priority=1.0, adherence_risk=1.0, source_confidence=1.0,
    )
    assert seg.render_weight is None


def test_anima_request_variant_defaults_base():
    from prompt_forge.contracts import AnimaAuthoringRequest, Complexity
    req = AnimaAuthoringRequest(
        facts=(), positive_segments=(), complexity=Complexity(1, 0, 0, 0, 0),
    )
    assert req.variant == "base"
```

- [ ] **Step 2: Run the test, verify it fails**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_anima_author.py -k "render_weight or variant" -v
```

Expected: FAIL — `TypeError: unexpected keyword argument 'render_weight'` / `'variant'`.

- [ ] **Step 3: Add the fields**

In `contracts.py`, add `render_weight` to `AuthoredSegment` (after `source_confidence`):

```python
@dataclass(frozen=True)
class AuthoredSegment:
    segment_id: str
    field: str
    text: str
    fact_ids: tuple[str, ...]
    priority: float
    adherence_risk: float
    source_confidence: float
    render_weight: float | None = None
```

Add `variant` to `AnimaAuthoringRequest` (after `exclusion_groups`):

```python
@dataclass(frozen=True)
class AnimaAuthoringRequest:
    facts: tuple[Fact, ...]
    positive_segments: tuple[AuthoredSegment, ...]
    complexity: Complexity
    negative_segments: tuple[AuthoredSegment, ...] = ()
    exclusion_groups: int = 0
    variant: Literal["base", "aesthetic", "turbo"] = "base"
```

- [ ] **Step 4: Run the test, verify it passes**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_anima_author.py -k "render_weight or variant" -v
```

Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
cd "D:/Projects/comfyui-chenxin" && git add skills/prompt-forge/prompt_forge/contracts.py skills/prompt-forge/tests/test_anima_author.py && git commit -m "feat(anima): add render_weight and variant to shared contracts"
```

---

## Task 2: Add a `deweight()` lexical helper to the Anima protocol layer

**Files:**
- Modify: `skills/prompt-forge/prompt_forge/anima/protocol.py`
- Test: `skills/prompt-forge/tests/test_anima_dictionary.py` (extend existing)

**Interfaces:**
- Produces: `prompt_forge.anima.protocol.deweight(text: str) -> str` — strips `(X:weight)` → `X`. Consumed by Task 3, 4, 5, 6.

- [ ] **Step 1: Write the failing test**

Append to `skills/prompt-forge/tests/test_anima_dictionary.py`:

```python
def test_deweight_strips_plain_weight():
    from prompt_forge.anima.protocol import deweight
    assert deweight("(chibi:2)") == "chibi"


def test_deweight_strips_artist_weight():
    from prompt_forge.anima.protocol import deweight
    assert deweight("(@wlop:1.2)") == "@wlop"


def test_deweight_leaves_bare_tag_unchanged():
    from prompt_forge.anima.protocol import deweight
    assert deweight("smile") == "smile"
```

- [ ] **Step 2: Run the test, verify it fails**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_anima_dictionary.py -k "deweight" -v
```

Expected: FAIL — `ImportError: cannot import name 'deweight'`.

- [ ] **Step 3: Implement `deweight`**

In `protocol.py`, add `import re` at the top and the helper after `semantic_form`:

```python
_WEIGHTED = re.compile(r"\(\s*([^:()]+?)\s*:\s*\d+(?:\.\d+)?\s*\)")


def deweight(text: str) -> str:
    """Strip a (tag:weight) wrapper down to the bare tag."""
    return _WEIGHTED.sub(r"\1", text).strip()
```

Update `canonical_form` and `semantic_form` to deweight first:

```python
def canonical_form(tag: str) -> str:
    value = " ".join(deweight(tag).lower().lstrip("@").split())
    return value if value.startswith("score_") else value.replace(" ", "_")


def semantic_form(value: str) -> str:
    return " ".join(deweight(value).lower().lstrip("@").replace("_", " ").split())
```

- [ ] **Step 4: Run the test, verify it passes**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_anima_dictionary.py -k "deweight" -v
```

Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd "D:/Projects/comfyui-chenxin" && git add skills/prompt-forge/prompt_forge/anima/protocol.py skills/prompt-forge/tests/test_anima_dictionary.py && git commit -m "feat(anima): add deweight helper to protocol layer"
```

---

## Task 3: Make the dictionary resolve weighted tags

**Files:**
- Modify: `skills/prompt-forge/prompt_forge/anima/dictionary.py`
- Test: `skills/prompt-forge/tests/test_anima_dictionary.py`

**Interfaces:**
- Consumes: `deweight` from Task 2.
- Produces: `AnimaTagDictionary.resolve("(chibi:2)")` returns the same candidate as `resolve("chibi")`.

- [ ] **Step 1: Write the failing test**

Append to `skills/prompt-forge/tests/test_anima_dictionary.py`:

```python
def test_resolve_weighted_tag_matches_bare_tag():
    from prompt_forge.anima.dictionary import AnimaTagDictionary
    d = AnimaTagDictionary()
    bare = d.resolve("score_9")
    weighted = d.resolve("(score_9:2)")
    assert bare is not None
    assert weighted is not None and weighted.canonical == bare.canonical
```

- [ ] **Step 2: Run the test, verify it fails**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_anima_dictionary.py -k "weighted_tag" -v
```

Expected: FAIL — `weighted` is `None` today.

- [ ] **Step 3: Deweight at resolve time**

In `dictionary.py`, import `deweight` and change the `display` line in `resolve` to:

```python
from .protocol import deweight
...
display = " ".join(deweight(tag).lower().lstrip("@").split())
```

`resolve_many` already delegates to `resolve`, so no further change is needed there.

- [ ] **Step 4: Run the test, verify it passes**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_anima_dictionary.py -k "weighted_tag" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/Projects/comfyui-chenxin" && git add skills/prompt-forge/prompt_forge/anima/dictionary.py skills/prompt-forge/tests/test_anima_dictionary.py && git commit -m "feat(anima): resolve weighted tags in dictionary"
```

---

## Task 4: Downgrade non-resolving `@` from error to warning

**Files:**
- Modify: `skills/prompt-forge/prompt_forge/anima/audit.py`
- Test: `skills/prompt-forge/tests/test_anima_author.py` (extend existing audit test)

**Interfaces:**
- Consumes: `deweight` from Task 2.
- Produces: an unresolvable `@`-prefixed tag yields `severity == "warning"` (code `unverified`), not `error` (`invalid_protocol_tag`).

- [ ] **Step 1: Write the failing test**

Append to `skills/prompt-forge/tests/test_anima_author.py`:

```python
def test_unresolvable_at_prefix_is_warning_not_error():
    from prompt_forge.anima.audit import audit_anima_prompt
    from prompt_forge.facts import FactLedger
    from prompt_forge.contracts import Fact
    ledger = FactLedger((
        Fact("f1", "@my style", "agent_embellishment", False, "s", "style"),
    ))
    report = audit_anima_prompt(("@my style",), "", ledger)
    assert all(f.severity != "error" for f in report.findings)
```

- [ ] **Step 2: Run the test, verify it fails**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_anima_author.py -k "at_prefix" -v
```

Expected: FAIL — the `@my style` finding has severity `error` today.

- [ ] **Step 3: Downgrade the finding**

In `audit.py`, import `deweight` and change the `@`-non-resolve branch to:

```python
elif exact is None and tag.startswith("@"):
    status = "unverified"
    findings.append(
        AnimaAuditFinding(
            "unverified",
            "warning",
            "reserved @ prefix does not resolve; treat as a style descriptor",
            index,
            raw_tag,
            fact_ids,
        )
    )
```

Also wrap the `raw_tag` passed to `resolve_many` with `deweight` so weighted `@` tags resolve: change `dictionary.resolve_many(tuple(raw_tag.strip() for raw_tag in tags))` to `dictionary.resolve_many(tuple(deweight(raw_tag.strip()) for raw_tag in tags))`.

- [ ] **Step 4: Run the test, verify it passes**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_anima_author.py -k "at_prefix" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/Projects/comfyui-chenxin" && git add skills/prompt-forge/prompt_forge/anima/audit.py skills/prompt-forge/tests/test_anima_author.py && git commit -m "feat(anima): downgrade unresolvable @ prefix to warning"
```

---

## Task 5: Re-rank fields to 9 positive / 4 negative slots and render weights

**Files:**
- Modify: `skills/prompt-forge/prompt_forge/anima/author.py`
- Test: `skills/prompt-forge/tests/test_anima_author.py`

**Interfaces:**
- Consumes: `render_weight` (Task 1), `deweight` (Task 2).
- Produces: a compiled prompt that (a) orders segments by the 9-slot rank, (b) renders `(text:weight)` when `render_weight` is set, (c) treats `scene_description` as the bridge field.

- [ ] **Step 1: Write the failing test**

Append to `skills/prompt-forge/tests/test_anima_author.py`:

```python
def test_author_renders_weighted_segment():
    from prompt_forge.anima.author import author_anima_prompt
    from prompt_forge.contracts import (
        AnimaAuthoringRequest, AuthoredSegment, Complexity, Fact,
    )
    facts = (Fact("f1", "smile", "agent_embellishment", False, "s", "expression"),)
    seg = AuthoredSegment(
        "s1", "general", "smile", ("f1",), 1.0, 1.0, 1.0, render_weight=1.3,
    )
    req = AnimaAuthoringRequest(
        facts=facts, positive_segments=(seg,),
        complexity=Complexity(1, 0, 0, 0, 0),
    )
    art = author_anima_prompt(req)
    assert "(smile:1.3)" in art.prompt["positive"]


def test_author_rejects_old_field_names():
    from prompt_forge.anima.author import author_anima_prompt
    from prompt_forge.contracts import (
        AnimaAuthoringRequest, AuthoredSegment, Complexity, Fact,
    )
    facts = (Fact("f1", "smile", "agent_embellishment", False, "s", "expression"),)
    seg = AuthoredSegment("s1", "composition_and_camera", "smile", ("f1",), 1.0, 1.0, 1.0)
    req = AnimaAuthoringRequest(
        facts=facts, positive_segments=(seg,),
        complexity=Complexity(1, 0, 0, 0, 0),
    )
    art = author_anima_prompt(req)
    assert art.status == "quality_rejected"
    assert "unsupported_positive_field" in art.audit["hard_gate_codes"]
```

- [ ] **Step 2: Run the tests, verify they fail**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_anima_author.py -k "weighted_segment or old_field_names" -v
```

Expected: FAIL — old `composition_and_camera` still passes; weighted segment renders bare `smile`.

- [ ] **Step 3: Replace the rank tables**

In `author.py`, replace `_FIELD_RANK` with:

```python
_FIELD_RANK = {
    "protocol_prefix": 0,
    "count": 1,
    "character": 2,
    "series": 3,
    "artist": 4,
    "appearance": 5,
    "general": 6,
    "environment": 7,
    "scene_description": 8,
}
```

Replace `_NEGATIVE_FIELDS` with:

```python
_NEGATIVE_FIELDS = {
    "quality_baseline",
    "anatomy_and_structure",
    "technical_defects",
    "user_exclusions",
}
```

Rename the bridge field: everywhere the code tests `segment.field == "natural_language_bridge"` (the `bridges` extraction and the compressed-tag/bridge split), change to `"scene_description"`.

- [ ] **Step 4: Render weights**

Add a helper near `_render_positive`:

```python
def _render_segment(segment: AuthoredSegment) -> str:
    if segment.render_weight is None:
        return segment.text
    return f"({segment.text}:{segment.render_weight:g})"
```

Use it in `_render_positive` (for both `tag_text` and `bridge_text`) and for `negative_text`:

```python
negative_text = ", ".join(_render_segment(segment) for segment in negative_result.segments)
```

- [ ] **Step 5: Run the tests, verify they pass**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_anima_author.py -v
```

Expected: PASS (new tests green; update any existing test that referenced old field names).

- [ ] **Step 6: Commit**

```bash
cd "D:/Projects/comfyui-chenxin" && git add skills/prompt-forge/prompt_forge/anima/author.py skills/prompt-forge/tests/test_anima_author.py && git commit -m "feat(anima): re-rank fields to 9/4 slots and render weights"
```

---

## Task 6: Make compression weight-aware

**Files:**
- Modify: `skills/prompt-forge/prompt_forge/compression.py`
- Test: `skills/prompt-forge/tests/test_compression.py`

**Interfaces:**
- Consumes: `deweight` (Task 2) — imported lazily inside the anima branch only, to avoid coupling H3 to Anima.
- Produces: for `structure == "anima"`, dedup compares de-weighted text; a weighted and un-weighted twin dedupe to one segment.

- [ ] **Step 1: Write the failing test**

Append to `skills/prompt-forge/tests/test_compression.py`:

```python
def test_anima_dedupes_weighted_and_bare_twin():
    from prompt_forge.compression import compress_to_budget
    from prompt_forge.facts import FactLedger
    from prompt_forge.contracts import AuthoredSegment, Fact
    from prompt_forge.token_counting import TokenCounter
    from pathlib import Path
    tokenizer_dir = Path(__file__).resolve().parents[1] / "knowledge" / "tokenizers" / "anima-qwen3-0.6b"
    ledger = FactLedger((
        Fact("f1", "smile", "agent_embellishment", False, "s", "expression"),
    ))
    a = AuthoredSegment("a", "general", "smile", ("f1",), 1.0, 1.0, 1.0)
    b = AuthoredSegment("b", "general", "(smile:1.3)", ("f1",), 1.0, 1.0, 1.0)
    counter = TokenCounter.load(tokenizer_dir, "anima-qwen3-0.6b")
    result = compress_to_budget(
        segments=(a, b), ledger=ledger, counter=counter,
        soft_limit=1000, quality_limit=2000, structure="anima",
    )
    assert len(result.segments) == 1
```

- [ ] **Step 2: Run the test, verify it fails**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_compression.py -k "weighted_and_bare" -v
```

Expected: FAIL — the twins are not deduped today (different text).

- [ ] **Step 3: De-weight in dedup keys**

In `compression.py`, add a helper and thread `structure` into the two dedup passes:

```python
def _dedupe_text(text: str, structure: Structure) -> str:
    if structure != "anima":
        return text
    from .anima.protocol import deweight
    return deweight(text)
```

Change `_exact_dedupe(current, counter)` → `_exact_dedupe(current, counter, structure)` and `_semantic_dedupe(current, counter)` → `_semantic_dedupe(current, counter, structure)`, and inside them replace `_exact_text(segment.text)` / `_semantic_text(segment.text)` with `_dedupe_text(_exact_text(segment.text), structure)` / `_dedupe_text(_semantic_text(segment.text), structure)`.

- [ ] **Step 4: Run the test, verify it passes**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/test_compression.py -v
```

Expected: PASS (new test green; existing H3 compression tests unchanged).

- [ ] **Step 5: Commit**

```bash
cd "D:/Projects/comfyui-chenxin" && git add skills/prompt-forge/prompt_forge/compression.py skills/prompt-forge/tests/test_compression.py && git commit -m "feat(anima): weight-aware compression dedup"
```

---

## Task 7: Rewrite the Anima dialect (core methodology doc)

**Files:**
- Modify: `skills/prompt-forge/references/dialects/anima/dialect.md`

**Interfaces:**
- Produces: the authoritative 9-slot order, three prefix tiers, weight calibration table, artist-mixing forms, variant notes, and sparse-input completion pointers. No code consumes it; the LLM author reads it.

- [ ] **Step 1: Rewrite `dialect.md`** — replace the "Native form" section and add the sections below:

```markdown
# Anima authoring dialect

## Native form

Positive prompt, in this exact order (front-weighted):

1. `protocol_prefix` — quality/meta/year/safety baseline
2. `count` — subject count
3. `character` — subject identity
4. `series` — source work
5. `artist` — `@artist`, weighted, mixable
6. `appearance` — hair/eyes/body/clothing
7. `general` — action/expression, then composition → lighting → palette → camera → mood/texture
8. `environment` — location/props/weather
9. `scene_description` — ≤1 natural-language bridge, after a period

Separate tags with `, ` (comma-space). Lowercase + spaces for ordinary tags; underscores only in `score_N`. Artist tags require `@`. A weighted tag renders `(text:weight)`.

## Quality prefix (enforced baseline)

| Tier | Trigger | Prefix |
|---|---|---|
| Standard | default (Base / Turbo) | `masterpiece, best quality, score_7, safe` |
| Artist-led | `@artist` present, style should dominate | `best quality, safe` |
| Aesthetic | variant = Aesthetic | `best quality, safe` |

Use `score_7`, not `score_8/9` (they stiffen composition). The two quality systems (human + score) may be used alone, together, or neither.

## Negative baseline

`worst quality, low quality, score_1, score_2, score_3` + `blurry, jpeg artifacts, chromatic aberration` + anatomy/count defects as needed + user exclusions. Keep it lean — Anima's negative is temperamental.

## Weight calibration

| Target | Range |
|---|---|
| ordinary tag | 1.0 – 2.0 |
| artist tag | 2.0 – 4.0 (whole block `(:2.0)` allowed) |
| window | 0.0 – 4.0 |

## Artist mixing

1. comma list: `@a, @b`
2. natural language: `using artist @A and @B to draw a picture`
3. weighted block: `Mixed style of following artists: (@artist1, @artist2:2.0)`
4. inline weights: `(@a:2.0), (@b:0.8)`

Warning: anime character names carry style bias — raise artist weight or bind to distinguishing features.

## Variants

- `base` (default, what camera-image pins): full quality stack.
- `aesthetic`: drop `score_*`; keep `best quality, safe`.
- `turbo`: full quality stack; CFG 1, 8–12 steps.

## Sparse input

When the user gives little detail, complete it by coherent inference (see `references/shared/aesthetic-coverage.md`) — five coherence layers, all as removable `agent_embellishment`.

## Token limit

32,768 physical; use the calibrated quality limits, not the physical ceiling.
```

- [ ] **Step 2: Verify no old field names remain**

```bash
cd "D:/Projects/comfyui-chenxin" && grep -n "natural_language_bridge\|copyright\|composition_and_camera\|environment_and_props\|lighting_and_visual_style" skills/prompt-forge/references/dialects/anima/dialect.md
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
cd "D:/Projects/comfyui-chenxin" && git add skills/prompt-forge/references/dialects/anima/dialect.md && git commit -m "docs(anima): rewrite dialect with 9-slot order, prefix tiers, weight calibration"
```

---

## Task 8: Update shared authoring docs (contract, output protocol, natural language, aesthetic coverage)

**Files:**
- Modify: `skills/prompt-forge/references/shared/authoring-contract.md`
- Modify: `skills/prompt-forge/references/shared/output-protocol.md`
- Modify: `skills/prompt-forge/references/shared/natural-language.md`
- Modify: `skills/prompt-forge/references/shared/aesthetic-coverage.md`

- [ ] **Step 1: Rewrite the anima field enums in `authoring-contract.md`**

Replace the "Positive field enums" list with:

```markdown
## Positive slots (anima)

`protocol_prefix`, `count`, `character`, `series`, `artist`, `appearance`, `general`, `environment`, `scene_description`

Ordered front-weighted; `general` internally orders action/expression → composition → lighting → palette → camera → mood.

## Negative slots (anima)

`quality_baseline`, `anatomy_and_structure`, `technical_defects`, `user_exclusions`

## Weighted segment

A segment may set `render_weight: float | None`. When set, it renders `(text:weight)`. Dedup/audit/compression operate on the de-weighted text.
```

- [ ] **Step 2: Remove the weight prohibition in `output-protocol.md`**

Delete the rule "No `(tag:1.2)` weight syntax" and replace with:

```markdown
4. Weighted tags render `(tag:weight)`; bare tags render as-is.
```

- [ ] **Step 3: Extend `natural-language.md`**

Append:

```markdown
## Sparse and multi-character guidance

- Multiple characters: name the character first, then describe appearance — listing names alone confuses the model.
- A pure natural-language author path needs ≥2 sentences; very short NL is unstable.
- Long NL drifts toward realism/over-detail — keep the bridge short.
- Cold characters: `She is a character from the game "Azur Lane", and her name is Anchorage`.
```

- [ ] **Step 4: Add sparse-input completion to `aesthetic-coverage.md`**

Append:

```markdown
## Sparse-input completion

When the user's request is thin, complete it by coherent inference — never reflect it back empty. All completion is `agent_embellishment` (removable). Five coherence layers, in order:

| Layer | Fill example |
|---|---|
| appearance coherence | `brown hair` + `amber eyes` + `leather jacket` |
| environment coherence | `abandoned city` + `crumbling overpass` + `ashfall` |
| action↔environment | `running` under `blizzard` ⇒ `struggling through deep snow` |
| lighting coherence | `golden hour` + `backlighting` + long shadows |
| mood coherence | wasteland ⇒ `somber`, `desaturated`, `overcast` |

Every filled tag passes aesthetic retrieval + dictionary verification.
```

- [ ] **Step 5: Verify no old field names remain**

```bash
cd "D:/Projects/comfyui-chenxin" && grep -rn "natural_language_bridge\|composition_and_camera\|environment_and_props\|lighting_and_visual_style\|copyright" skills/prompt-forge/references/shared/
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
cd "D:/Projects/comfyui-chenxin" && git add skills/prompt-forge/references/shared/ && git commit -m "docs(anima): update shared authoring docs for 9 slots, weights, sparse completion"
```

---

## Task 9: Update budget policy, quality docs, vocabulary map, and recipes

**Files:**
- Modify: `skills/prompt-forge/knowledge/anima/budget-policy.json`
- Modify: `skills/prompt-forge/references/quality/budget-ruler.md`
- Modify: `skills/prompt-forge/references/quality/tag-count-ruler.md`
- Modify: `skills/prompt-forge/references/dialects/anima/vocabulary/README.md`
- Modify: `skills/prompt-forge/references/dialects/anima/recipes/*.md` (6 files)

- [ ] **Step 1: Fix the negative baseline in `budget-ruler.md`**

Replace `score_4..6` with `score_1, score_2, score_3` in the "Three standard baselines" bullet:

```markdown
1. **Standard baselines** (mandatory floor): `score_1, score_2, score_3`, `worst quality`, `low quality`, `blurry`, `jpeg artifacts`, `chromatic aberration`, anatomy/structure defects.
```

- [ ] **Step 2: Re-key `tag-count-ruler.md` per-slot targets to the 9 slots**

Replace the per-slot table rows with: `protocol_prefix (2-4)`, `count (1-2)`, `character (0-2)`, `series (0-1)`, `artist (0-3)`, `appearance (3-8)`, `general (5-12)`, `environment (2-6)`, `scene_description (0-1)`.

- [ ] **Step 3: Re-key `vocabulary/README.md` field mapping to the 9 slots**

Update the field-mapping table: `count→count-identity.md`, `character→count-identity.md`, `appearance→appearance.md + clothing.md`, `general→expression.md + pose-action.md + camera-shot.md + detail-mood.md`, `environment→scene-environment.md`, `scene_description→special-themes.md`.

- [ ] **Step 4: Update `budget-policy.json` field names**

In `knowledge/anima/budget-policy.json`, rename `positive_fields[].name` values to the 9 slots and `negative_fields[].name` to the 4 slots. Add a `protocol_prefix` entry with `recommended_min_share: 0.06`, `recommended_max_share: 0.10`, `hard_max_share: 0.12`. Also update `positive_borrowing_order` / `negative_borrowing_order` to reference only the new names.

- [ ] **Step 5: Re-key the 6 recipes**

For each `recipes/*.md`, change the 五层组合 bullet labels so the five layers map into the `general` slot (action/expression → composition → lighting → palette → camera → mood), and where a recipe implies a dominant artist/style, note the artist-led prefix tier. Do not change the tag lists themselves.

- [ ] **Step 6: Verify field-name consistency**

```bash
cd "D:/Projects/comfyui-chenxin" && grep -rn "natural_language_bridge\|quality_meta_year_safety\|official_quality_baseline\|anatomy_count_structure_errors\|image_technical_defects\|composition_and_camera\|environment_and_props\|lighting_and_visual_style" skills/prompt-forge/references skills/prompt-forge/knowledge/anima/budget-policy.json
```

Expected: no output.

- [ ] **Step 7: Commit**

```bash
cd "D:/Projects/comfyui-chenxin" && git add skills/prompt-forge/knowledge/anima/budget-policy.json skills/prompt-forge/references/quality/ skills/prompt-forge/references/dialects/anima/vocabulary/README.md skills/prompt-forge/references/dialects/anima/recipes/ && git commit -m "docs(anima): update budget policy, quality docs, vocabulary map, recipes"
```

---

## Task 10: Full verification and merge

**Files:**
- No new files. Full-suite run and acceptance check.

- [ ] **Step 1: Run the full test suite**

```bash
cd "D:/Projects/comfyui-chenxin/skills/prompt-forge" && python -m pytest tests/ -v
```

Expected: all pass (new weight/slot tests green; H3 tests unchanged and green).

- [ ] **Step 2: Run the acceptance greps from spec §15**

```bash
cd "D:/Projects/comfyui-chenxin" && grep -rn "score_4\|score_5\|score_6\|no weight syntax" skills/prompt-forge/references skills/prompt-forge/knowledge/anima/budget-policy.json
```

Expected: no output.

- [ ] **Step 3: Merge to main**

```bash
cd "D:/Projects/comfyui-chenxin" && git checkout main && git merge --no-ff feat/anima-prompt-methodology -m "feat(anima): rewrite prompt methodology (9 slots, weights, prefix tiers, sparse completion)"
```

---

## Self-Review Notes (already applied)

- **Spec coverage:** §3 (slots) → Task 5/7; §4 (prefix tiers) → Task 7/8; §5 (negative) → Task 9; §6 (weighting) → Tasks 1/2/3/5/6; §7 (artist mixing) → Task 7; §8 (NL) → Task 8; §9 (sparse completion) → Task 8; §10 (cold/failed tags) → Task 8 + Task 4; §11 (variant) → Task 1/7; §12 (weight-aware) → Tasks 2/3/4/6.
- **Type consistency:** `deweight(text: str) -> str` (Task 2) is imported by Tasks 3, 4, 6 with the same signature. `render_weight` (Task 1) read by Task 5. `variant` (Task 1) read by Task 7 documentation; no runtime branch consumes it (the prefix tier is authored, not computed — a runtime tier switch would be a separate task).
- **Placeholder scan:** no TBD/TODO; every code step carries actual code.
