# prompt-forge v5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `comfyui-chenxin/skills/prompt-forge/` from v4 to v5 by inlining the obsidian vault's prompt-engineering knowledge (153K lines) into the skill itself, restoring v3's 10-dim extraction + scene-recipes matching + tag-dictionary validation.

**Architecture:** Vault content moves to `dictionary/`, `aesthetics/`, `negative/`, `models/` subdirectories inside the skill. Three new stdlib-only Python tools (`tag_lookup.py`, `scene_match.py`, `build_tag_index.py`) join the upgraded `recipe_lookup.py` and `recipe_yaml.py`. `tag-index.json` (built once from `danbooru.csv`) accelerates tag queries from ~3s to <100ms. SKILL.md is rewritten to ~250 lines, restoring the spec-v3 6-step pipeline.

**Tech Stack:** Python 3.11+ (stdlib only), YAML frontmatter (custom parser), JSON index, Markdown prose.

---

## Global Constraints

- **stdlib-only Python**: no `pip install`, no `PyYAML`, no `pandas`. Already enforced by v4 (`internals/recipe_yaml.py` is a custom YAML parser).
- **3-line Windows compat**: `_THIS.parent.parent` style path joins (existing pattern in `internals/recipe_yaml.py`).
- **exit code contract**: `0` success, `2` usage error, `3` missing dependency / schema invalid, `4` timeout (only for HTTP calls — none in v5).
- **JSON on stdout / status on stderr** (existing pattern).
- **No Cloud APIs**: skill stays local-only (matches project hard constraint).
- **Backwards compat**: v4's `recipe_lookup.py --model X` must keep working with same JSON shape + new `score` and `match_path` fields (additive).
- **No new MCP tool calls**: prompt-forge stays L4 router; MCP calls unchanged.

---

## File Structure (created / modified / deleted)

### Created (data — copied verbatim from vault)
- `skills/prompt-forge/dictionary/README.md` — sources, license, update flow
- `skills/prompt-forge/dictionary/danbooru.csv` — 140K rows (verbatim from vault)
- `skills/prompt-forge/dictionary/wd14-tags.csv` — 11K rows (verbatim from vault)
- `skills/prompt-forge/aesthetics/INDEX.md` — scene_match.py keyword index (NEW, derived from vault `scene-recipes.md`)
- `skills/prompt-forge/aesthetics/scene-recipes.md` — 31 rows (verbatim)
- `skills/prompt-forge/aesthetics/style-presets.md` — 39 rows (verbatim)
- `skills/prompt-forge/aesthetics/lighting/*.md` — 9 files (verbatim)
- `skills/prompt-forge/aesthetics/composition/*.md` — 7 files (verbatim)
- `skills/prompt-forge/aesthetics/color/*.md` — 9 files (verbatim)
- `skills/prompt-forge/aesthetics/medium-glossary.md` — 143 rows (verbatim)
- `skills/prompt-forge/aesthetics/motion-glossary.md` — 130 rows (verbatim)
- `skills/prompt-forge/aesthetics/concept-archetypes.md` — 227 rows (verbatim)
- `skills/prompt-forge/aesthetics/video-archetypes.md` — 149 rows (verbatim)
- `skills/prompt-forge/negative/negative-prompts.md` — 96 rows (verbatim)
- `skills/prompt-forge/models/INDEX.md` — (from vault `model-index.md`)
- `skills/prompt-forge/models/{anima,pony,illustrious,noobai,flux,sdxl,sd15,sd35,qwen-image,seedream,hunyuan-image,wan,ltx,kling,hailuo}.md` — 15 files (verbatim from vault `models/`)
- `skills/prompt-forge/SPEC.md` — curated subset of vault `spec-v3.md`

### Created (Python — new tools)
- `skills/prompt-forge/internals/_aliases.py` — shared alias table
- `skills/prompt-forge/internals/build_tag_index.py` — CSV → JSON
- `skills/prompt-forge/internals/tag_lookup.py` — tag dictionary query
- `skills/prompt-forge/internals/scene_match.py` — scene keyword → recipe paths

### Created (Python — tests, new file)
- `skills/prompt-forge/internals/tests/__init__.py`
- `skills/prompt-forge/internals/tests/test_recipe_lookup.py`
- `skills/prompt-forge/internals/tests/test_recipe_yaml.py`
- `skills/prompt-forge/internals/tests/test_tag_lookup.py`
- `skills/prompt-forge/internals/tests/test_scene_match.py`
- `skills/prompt-forge/internals/tests/test_build_tag_index.py`

### Created (data — generated)
- `skills/prompt-forge/dictionary/tag-index.json` — output of `build_tag_index.py`, git-trackable

### Modified
- `skills/prompt-forge/SKILL.md` — full rewrite (~230 → ~250 lines)
- `skills/prompt-forge/internals/recipe_lookup.py` — upgrade with `_ALIASES` + 3-pass matching
- `skills/prompt-forge/internals/recipe_yaml.py` — add `--validate-schema` + `--add-alias` + `--list-aliases`

### Untouched
- `skills/prompt-forge/recipes/MODELS.md` (81 recipes stay)
- `skills/prompt-forge/hardware/8gb.json`

---

## Task 1: Migrate vault data verbatim + create directory skeleton

**Files:**
- Create: 6 directories + ~50 vault-copied files + SPEC.md (curated)

**Source-of-truth vault path:** `D:\ObsidianWorkSpace\workspace\10-Projects\prompt-forge\`

**Maps (vault → skill):**

| Vault path | Skill destination |
|---|---|
| `tags/danbooru.csv` | `dictionary/danbooru.csv` |
| `tags/wd14-tags.csv` | `dictionary/wd14-tags.csv` |
| `aesthetics/scene-recipes.md` | `aesthetics/scene-recipes.md` |
| `aesthetics/style-presets.md` | `aesthetics/style-presets.md` |
| `aesthetics/lighting/*.md` | `aesthetics/lighting/*.md` |
| `aesthetics/composition/*.md` | `aesthetics/composition/*.md` |
| `aesthetics/color/*.md` | `aesthetics/color/*.md` |
| `aesthetics/medium-glossary.md` | `aesthetics/medium-glossary.md` |
| `aesthetics/motion-glossary.md` | `aesthetics/motion-glossary.md` |
| `aesthetics/concept-archetypes.md` | `aesthetics/concept-archetypes.md` |
| `aesthetics/video-archetypes.md` | `aesthetics/video-archetypes.md` |
| `negative/negative-prompts.md` | `negative/negative-prompts.md` |
| `model-index.md` | `models/INDEX.md` |
| `models/{name}.md` | `models/{name}.md` |
| `spec-v3.md` | `SPEC.md` (curated — see Step 5) |

- [ ] **Step 1: Create directory skeleton**

```bash
mkdir -p D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary
mkdir -p D:/Projects/comfyui-chenxin/skills/prompt-forge/aesthetics/lighting
mkdir -p D:/Projects/comfyui-chenxin/skills/prompt-forge/aesthetics/composition
mkdir -p D:/Projects/comfyui-chenxin/skills/prompt-forge/aesthetics/color
mkdir -p D:/Projects/comfyui-chenxin/skills/prompt-forge/negative
mkdir -p D:/Projects/comfyui-chenxin/skills/prompt-forge/models
mkdir -p D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/tests
```

Expected: all 7 dirs created.

- [ ] **Step 2: Copy CSV data verbatim**

```bash
cp D:/ObsidianWorkSpace/workspace/10-Projects/prompt-forge/tags/danbooru.csv D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary/danbooru.csv
cp D:/ObsidianWorkSpace/workspace/10-Projects/prompt-forge/tags/wd14-tags.csv D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary/wd14-tags.csv
wc -l D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary/*.csv
```

Expected: `danbooru.csv 140782`, `wd14-tags.csv 10862`.

- [ ] **Step 3: Copy aesthetics/ verbatim**

```bash
VAULT=D:/ObsidianWorkSpace/workspace/10-Projects/prompt-forge
SKILL=D:/Projects/comfyui-chenxin/skills/prompt-forge
cp "$VAULT/aesthetics/scene-recipes.md" "$SKILL/aesthetics/scene-recipes.md"
cp "$VAULT/aesthetics/style-presets.md" "$SKILL/aesthetics/style-presets.md"
cp "$VAULT/aesthetics/medium-glossary.md" "$SKILL/aesthetics/medium-glossary.md"
cp "$VAULT/aesthetics/motion-glossary.md" "$SKILL/aesthetics/motion-glossary.md"
cp "$VAULT/aesthetics/concept-archetypes.md" "$SKILL/aesthetics/concept-archetypes.md"
cp "$VAULT/aesthetics/video-archetypes.md" "$SKILL/aesthetics/video-archetypes.md"
cp "$VAULT/aesthetics/lighting/"*.md "$SKILL/aesthetics/lighting/"
cp "$VAULT/aesthetics/composition/"*.md "$SKILL/aesthetics/composition/"
cp "$VAULT/aesthetics/color/"*.md "$SKILL/aesthetics/color/"
ls -la "$SKILL/aesthetics/lighting/" | wc -l
```

Expected: 11 (header + 9 files + summary) for `lighting/`; 8 for composition; 10 for color.

- [ ] **Step 4: Copy negative/ + models/ verbatim**

```bash
VAULT=D:/ObsidianWorkSpace/workspace/10-Projects/prompt-forge
SKILL=D:/Projects/comfyui-chenxin/skills/prompt-forge
cp "$VAULT/negative/negative-prompts.md" "$SKILL/negative/negative-prompts.md"
cp "$VAULT/model-index.md" "$SKILL/models/INDEX.md"
cp "$VAULT/models/"*.md "$SKILL/models/"
ls "$SKILL/models/" | wc -l
```

Expected: 16 files (15 models + INDEX.md).

- [ ] **Step 5: Create SPEC.md (curated subset of vault spec-v3.md)**

Write `skills/prompt-forge/SPEC.md`:

```markdown
# Prompt-Forge v5 Design Spec (Curated)

## 1. Why a v5

v4 (current) removed the obsidian-vault read dependency but never re-implemented
v3's capabilities: 10-dimension extraction, scene-recipes matching, tag-dictionary
validation. v5 inlines the vault into the skill itself so it works with `git clone`
alone.

## 2. 10-Dimension Framework

Subject / Action / Scene / Lighting / Composition / Color / Style / Mood /
Medium / Quality. Missing dims are marked `[unset]` and filled by scene-recipes
or style-presets.

## 3. First-10-Token Rule

| Encoder | Strategy |
|---|---|
| LLM (Anima / Flux / Qwen / SD 3.5) | Subject + Action first; quality anchors at tail |
| CLIP (Pony / Illustrious / SDXL / SD 1.5) | Per-model `tag_order_strategy` (see `models/*.md`) |

CLIP uses single-direction attention; position equals weight. Pony's `score_*`
chain MUST lead.

## 4. Three Dialects

- **tag-style** (Danbooru comma-separated): Anima / Pony / SDXL / SD 1.5
- **natural-language** (sentence, order-sensitive): Flux / Qwen
- **video** (shot + camera + temporal): Wan / LTX

## 5. 11-Item Self-Check

1. 10-dim complete  2. tags validated  3. first-10 = SUBJECT+ACTION
4. STYLE in first 25%  5. lighting/composition/color each present
6. token range  7. no abstract stacking  8. STYLE names medium
9. LoRA compatible  10. model-specific constraints  11. concept density > 0.6

## 6. P0 Errors Corrected from v2

1. Anima safety: `questionable` → `nsfw`
2. Pony rating_*: official recommendations
3. Illustrious: no `score_*`, masterpiece stack
4. Illustrious year: no `year_*`, use newest/recent/oldest
5. Seedream: 5.0 doesn't exist → fall back to 4.5
6. Kolors: DEPRECATED
7. HunyuanDiT → HunyuanImage 2.1/3.0
8. SD 3.5: 2B → 8B / 2.5B
9. Flux.2: no negative prompts
10. Flux.2: JSON / hex / multi-language / multi-reference supported
```

- [ ] **Step 6: Create test package init + dictionary README**

```bash
touch D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/tests/__init__.py
```

Write `skills/prompt-forge/dictionary/README.md`:

```markdown
# dictionary/ — in-skill tag dictionary

Sources:

- `danbooru.csv` — 140,782 rows from [Danbooru](https://danbooru.donmai.us/wiki_pages/help:tags) (jsDelivr CDN mirror).
- `wd14-tags.csv` — 10,862 rows from [SmilingWolf/wd-v1-4-tags](https://huggingface.co/SmilingWolf/wd-v1-4-tags) (hf-mirror).
- `tag-index.json` — precomputed index (built by `python internals/build_tag_index.py`).

## Update flow

```bash
python internals/build_tag_index.py        # rebuild index from CSV
python internals/build_tag_index.py --check   # CI: exit 1 if CSV newer
```

## License

Danbooru tags are released under the [Danbooru Terms of Service](https://danbooru.donmai.us/wiki_pages/help:tags) for non-commercial use with attribution. WD14 tags are released by SmilingWolf under the [CreativeML Open RAIL-M license](https://huggingface.co/SmilingWolf/wd-v1-4-tags). See `../LICENSE` for this skill's MIT terms.
```

- [ ] **Step 7: Verify all 153K+ lines migrated**

```bash
find D:/Projects/comfyui-chenxin/skills/prompt-forge -type f \( -name '*.md' -o -name '*.csv' \) | xargs wc -l | tail -1
find D:/ObsidianWorkSpace/workspace/10-Projects/prompt-forge -type f \( -name '*.md' -o -name '*.csv' \) | xargs wc -l | tail -1
```

Expected: skill total ≥ vault total (skill has +1 SPEC.md, +1 INDEX.md, +1 README.md).

- [ ] **Step 8: Ready to commit**

Tell user: data migration done; ready to commit when they say so.

---

## Task 2: Create `internals/_aliases.py` (shared alias table)

**Files:**
- Create: `skills/prompt-forge/internals/_aliases.py`
- Create: `skills/prompt-forge/internals/tests/test_aliases.py`

**Interfaces:**
- Consumes: nothing
- Produces: `ALIASES: dict[str, list[str]]` — alias → [canonical_id] reverse mapping

- [ ] **Step 1: Write the failing test**

```python
# skills/prompt-forge/internals/tests/test_aliases.py
from internals._aliases import ALIASES, resolve_alias, all_aliases


def test_resolve_alias_known():
    assert resolve_alias("anima_baseV10") == "anima"
    assert resolve_alias("AnimaStandardV7") == "anima"


def test_resolve_alias_unknown():
    assert resolve_alias("nonexistent_xyz") is None


def test_resolve_alias_case_insensitive():
    assert resolve_alias("ANIMASTANDARDV7") == "anima"


def test_all_aliases_count():
    assert len(all_aliases()) >= 50


def test_aliases_format():
    for alias, canonicals in ALIASES.items():
        assert isinstance(canonicals, list)
        assert len(canonicals) >= 1


def test_resolve_sdxl_aliases():
    assert resolve_alias("sdxl_base") == "sdxl"
    assert resolve_alias("stable_diffusion_xl") == "sdxl"


def test_resolve_flux_aliases():
    assert resolve_alias("flux_1_dev") == "flux_1"
    assert resolve_alias("flux_1_schnell") == "flux_1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_aliases.py -v
```

Expected: ImportError on `from internals._aliases import ALIASES, ...`.

- [ ] **Step 3: Write the alias table**

```python
# skills/prompt-forge/internals/_aliases.py
"""Shared model alias table for recipe_lookup.py and recipe_yaml.py.

Maps common variant names to canonical recipe ids in recipes/MODELS.md.
Maintained via `python recipe_yaml.py --add-alias <alias>=<canonical>`.
"""

ALIASES: dict[str, list[str]] = {
    # Anima
    "anima_basev10": ["anima"],
    "animastandardv7": ["anima"],
    "anima_standardv7": ["anima"],
    "anima_base_v10": ["anima"],
    "anima-basev10": ["anima"],

    # SDXL
    "sdxl_base": ["sdxl"],
    "sdxl_base_1.0": ["sdxl"],
    "stable_diffusion_xl": ["sdxl"],
    "stable-diffusion-xl": ["sdxl"],

    # Pony
    "pony_diffusion_v6_xl": ["pony"],
    "pony_diffusion_v6": ["pony"],
    "pony_v6": ["pony"],

    # Illustrious
    "illustrious_xl": ["illustrious"],
    "illustriousxl": ["illustrious"],

    # NoobAI
    "noobai_xl": ["noobai"],
    "noobai-xl": ["noobai"],

    # Flux.1
    "flux_1_dev": ["flux_1"],
    "flux_1_schnell": ["flux_1"],
    "flux1_dev": ["flux_1"],
    "flux1_schnell": ["flux_1"],
    "flux_dev": ["flux_1"],
    "flux_schnell": ["flux_1"],

    # Flux.2
    "flux_2_klein": ["flux_2"],
    "flux_2_pro": ["flux_2"],
    "flux2_klein": ["flux_2"],
    "flux2_pro": ["flux_2"],

    # SD 1.5
    "sd_1.5": ["sd15"],
    "sd15": ["sd15"],
    "stable_diffusion_1.5": ["sd15"],
    "stable-diffusion-1.5": ["sd15"],

    # SD 3.5
    "sd_3.5": ["sd35"],
    "sd35_large": ["sd35"],
    "sd35_medium": ["sd35"],

    # Qwen-Image
    "qwen_image": ["qwen-image"],
    "qwen-image-edit": ["qwen-image"],

    # Seedream
    "seedream_4.5": ["seedream"],
    "seedream-4.5": ["seedream"],

    # HunyuanImage
    "hunyuan_image_3.0": ["hunyuan-image"],
    "hunyuan_image_2.1": ["hunyuan-image"],

    # Wan
    "wan_2.1": ["wan"],
    "wan_2.2": ["wan"],
    "wan_2.5": ["wan"],
    "wan_2.6": ["wan"],
    "wan2.1": ["wan"],
    "wan2.2": ["wan"],
    "wan2.5": ["wan"],

    # LTX
    "ltx_2.3": ["ltx"],
    "ltx_2_pro": ["ltx"],
    "ltx_video": ["ltx"],
    "ltx-video": ["ltx"],
    "ltx23": ["ltx"],

    # Kling
    "kling_1.6": ["kling"],
    "kling_2.0": ["kling"],

    # Hailuo
    "hailuo_video": ["hailuo"],
    "hailuo-02": ["hailuo"],
}


def resolve_alias(alias: str) -> str | None:
    """Return canonical id for a known alias (case-insensitive), or None."""
    key = alias.lower().strip()
    canonicals = ALIASES.get(key)
    return canonicals[0] if canonicals else None


def all_aliases() -> list[str]:
    """Return all alias keys."""
    return list(ALIASES.keys())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_aliases.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Ready to commit**

Tell user: ready to commit when they say so.

---

## Task 3: `build_tag_index.py` (TDD)

**Files:**
- Create: `skills/prompt-forge/internals/build_tag_index.py`
- Create: `skills/prompt-forge/internals/tests/test_build_tag_index.py`

**Interfaces:**
- Consumes: `dictionary/danbooru.csv`, `dictionary/wd14-tags.csv`
- Produces: `dictionary/tag-index.json` with shape `{"_meta": {...}, "by_canonical": {...}, "by_alias": {...}}`

- [ ] **Step 1: Write the failing test**

```python
# skills/prompt-forge/internals/tests/test_build_tag_index.py
import json
from pathlib import Path
import tempfile
from internals.build_tag_index import parse_danbooru_csv, build_index, write_index


def test_parse_danbooru_csv_first_row():
    rows = parse_danbooru_csv(Path("D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary/danbooru.csv"))
    assert len(rows) > 100000
    first = rows[0]
    assert "name" in first and "category" in first and "count" in first and "aliases" in first


def test_parse_danbooru_csv_long_hair_row():
    rows = parse_danbooru_csv(Path("D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary/danbooru.csv"))
    long_hair = next((r for r in rows if r["name"] == "long_hair"), None)
    assert long_hair is not None
    assert long_hair["count"] > 1000000
    assert "/lh" in long_hair["aliases"]


def test_build_index_has_by_canonical_and_by_alias():
    rows = parse_danbooru_csv(Path("D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary/danbooru.csv"))
    idx = build_index(rows, version="test")
    assert "by_canonical" in idx
    assert "by_alias" in idx
    assert "long_hair" in idx["by_canonical"]
    assert idx["by_canonical"]["long_hair"]["count"] > 1000000


def test_build_index_meta():
    rows = parse_danbooru_csv(Path("D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary/danbooru.csv"))
    idx = build_index(rows, version="test-version")
    assert idx["_meta"]["version"] == "test-version"
    assert idx["_meta"]["row_count"] == len(rows)


def test_write_index_atomic():
    rows = parse_danbooru_csv(Path("D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary/danbooru.csv"))
    idx = build_index(rows, version="test")
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "tag-index.json"
        write_index(idx, out)
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["_meta"]["version"] == "test"


def test_cli_build_runs():
    import subprocess
    r = subprocess.run(
        ["python", "D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/build_tag_index.py"],
        capture_output=True, text=True,
        cwd="D:/Projects/comfyui-chenxin",
    )
    assert r.returncode == 0
    out = Path("D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary/tag-index.json")
    assert out.exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_build_tag_index.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write the implementation**

```python
# skills/prompt-forge/internals/build_tag_index.py
#!/usr/bin/env python3
"""build_tag_index — build tag-index.json from danbooru.csv + wd14-tags.csv.

One-shot script (CI-style). Produces a deterministic JSON index that
tag_lookup.py loads at runtime for fast (≤100ms) tag queries.

Usage:
    python build_tag_index.py                # build (overwrites tag-index.json)
    python build_tag_index.py --check        # exit 1 if CSV newer than index
    python build_tag_index.py --stats        # print row counts, alias ratios

Output: dictionary/tag-index.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
DICT_DIR = SKILL_DIR / "dictionary"
DANBOORU_CSV = DICT_DIR / "danbooru.csv"
WD14_CSV = DICT_DIR / "wd14-tags.csv"
INDEX_JSON = DICT_DIR / "tag-index.json"

INDEX_VERSION = "2026-08-01"


def parse_danbooru_csv(path: Path) -> list[dict]:
    """Parse danbooru.csv: name,category,count,aliases.

    aliases is a CSV-escaped quoted list like '"/lh,longhair"'.
    """
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                count = int(r.get("count", "0"))
            except (ValueError, TypeError):
                count = 0
            aliases_field = r.get("aliases", "") or ""
            aliases: list[str] = []
            if aliases_field.startswith('"') and aliases_field.endswith('"'):
                inner = aliases_field[1:-1]
                aliases = [a.strip() for a in inner.split(",") if a.strip()]
            rows.append({
                "name": (r.get("name") or "").strip(),
                "category": int(r.get("category", "0") or "0"),
                "count": count,
                "aliases": aliases,
            })
    return rows


def build_index(rows: list[dict], version: str) -> dict:
    """Build the index dict from parsed danbooru rows."""
    by_canonical: dict[str, dict] = {}
    by_alias: dict[str, list[str]] = {}
    for r in rows:
        name = r["name"]
        if not name:
            continue
        by_canonical[name] = {
            "cat": r["category"],
            "count": r["count"],
            "aliases": r["aliases"],
        }
        for a in r["aliases"]:
            by_alias.setdefault(a, []).append(name)
    return {
        "_meta": {
            "source": "danbooru.csv",
            "version": version,
            "row_count": len(rows),
            "built_at_epoch": int(time.time()),
        },
        "by_canonical": by_canonical,
        "by_alias": by_alias,
    }


def write_index(idx: dict, path: Path) -> None:
    """Atomically write index to path."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _is_csv_newer_than_index() -> bool:
    if not INDEX_JSON.exists():
        return True
    idx_mtime = INDEX_JSON.stat().st_mtime
    for csv in (DANBOORU_CSV, WD14_CSV):
        if csv.exists() and csv.stat().st_mtime > idx_mtime:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_tag_index")
    parser.add_argument("--check", action="store_true", help="Exit 1 if CSV is newer than index")
    parser.add_argument("--stats", action="store_true", help="Print row/alias counts and exit")
    args = parser.parse_args(argv)

    if not DANBOORU_CSV.exists():
        print(f"[build_tag_index] missing {DANBOORU_CSV}", file=sys.stderr)
        return 3

    if args.stats:
        rows = parse_danbooru_csv(DANBOORU_CSV)
        idx = build_index(rows, INDEX_VERSION)
        total = sum(len(v) for v in idx["by_alias"].values())
        print(f"rows={idx['_meta']['row_count']} aliases={total} categories={len(set(r['category'] for r in rows))}")
        return 0

    if args.check:
        if _is_csv_newer_than_index():
            print("[build_tag_index] CSV newer than index — rebuild needed", file=sys.stderr)
            return 1
        print("[build_tag_index] index is fresh")
        return 0

    rows = parse_danbooru_csv(DANBOORU_CSV)
    idx = build_index(rows, INDEX_VERSION)
    write_index(idx, INDEX_JSON)
    total = sum(len(v) for v in idx["by_alias"].values())
    print(f"[build_tag_index] wrote {INDEX_JSON} rows={idx['_meta']['row_count']} aliases={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_build_tag_index.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Build the index**

```bash
python D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/build_tag_index.py
python D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/build_tag_index.py --stats
```

Expected: `[build_tag_index] wrote .../tag-index.json rows=140782 aliases=...` and stats line.

- [ ] **Step 6: Verify index is loadable**

```bash
cd D:/Projects/comfyui-chenxin
python -c "import json; d=json.load(open('skills/prompt-forge/dictionary/tag-index.json',encoding='utf-8')); assert d['by_canonical']['long_hair']['count']>1000000; print('ok')"
```

Expected: `ok`.

- [ ] **Step 7: Ready to commit**

Tell user: ready to commit when they say so.

---

## Task 4: `tag_lookup.py` (TDD)

**Files:**
- Create: `skills/prompt-forge/internals/tag_lookup.py`
- Create: `skills/prompt-forge/internals/tests/test_tag_lookup.py`

**Interfaces:**
- Consumes: `dictionary/tag-index.json` (built by Task 3)
- Produces: CLI `--query <token>` → JSON array of tag hits
- Used by: SKILL.md §1 step 4

- [ ] **Step 1: Write the failing test**

```python
# skills/prompt-forge/internals/tests/test_tag_lookup.py
import json
from pathlib import Path
from internals.tag_lookup import load_index, lookup


INDEX = Path("D:/Projects/comfyui-chenxin/skills/prompt-forge/dictionary/tag-index.json")


def test_load_index():
    idx = load_index(INDEX)
    assert "by_canonical" in idx
    assert "by_alias" in idx
    assert "long_hair" in idx["by_canonical"]


def test_lookup_exact_canonical():
    idx = load_index(INDEX)
    results = lookup(idx, "long_hair")
    assert len(results) >= 1
    assert results[0]["canonical"] == "long_hair"
    assert results[0]["count"] > 1000000


def test_lookup_via_alias():
    idx = load_index(INDEX)
    results = lookup(idx, "/lh")
    assert len(results) >= 1
    assert any(r["canonical"] == "long_hair" for r in results)


def test_lookup_substring_match():
    idx = load_index(INDEX)
    results = lookup(idx, "hair", limit=10)
    assert len(results) >= 1
    assert all("hair" in r["canonical"].lower() for r in results)


def test_lookup_cjk_substring():
    idx = load_index(INDEX)
    results = lookup(idx, "金发")
    assert isinstance(results, list)


def test_lookup_no_match():
    idx = load_index(INDEX)
    results = lookup(idx, "definitely_nonexistent_xyz_12345")
    assert results == []


def test_lookup_category_filter():
    idx = load_index(INDEX)
    results = lookup(idx, "1girl", category=0)
    assert all(r.get("category") == 0 for r in results)


def test_lookup_respects_limit():
    idx = load_index(INDEX)
    results = lookup(idx, "hair", limit=3)
    assert len(results) <= 3


def test_cli_query_long_hair():
    import subprocess
    r = subprocess.run(
        ["python", "D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/tag_lookup.py",
         "--query", "long_hair"],
        capture_output=True, text=True,
        cwd="D:/Projects/comfyui-chenxin",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert any(t["canonical"] == "long_hair" for t in data)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_tag_lookup.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write the implementation**

```python
# skills/prompt-forge/internals/tag_lookup.py
#!/usr/bin/env python3
"""tag_lookup — query danbooru tag dictionary via precomputed index.

Loads dictionary/tag-index.json (built by build_tag_index.py) and exposes
a 3-pass lookup: exact canonical → alias → substring.

Usage:
    python tag_lookup.py --query "long_hair"
    python tag_lookup.py --query "elf" --limit 5
    python tag_lookup.py --query "1girl" --category 0
    python tag_lookup.py --exact "long_hair"

Stdlib only. Output: JSON array on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
INDEX_JSON = SKILL_DIR / "dictionary" / "tag-index.json"


def load_index(path: Path = INDEX_JSON) -> dict:
    if not path.exists():
        print(f"[tag_lookup] missing {path} — run build_tag_index.py first", file=sys.stderr)
        sys.exit(3)
    return json.loads(path.read_text(encoding="utf-8"))


def lookup(idx: dict, query: str, limit: int | None = None,
           category: int | None = None, exact: bool = False) -> list[dict]:
    """3-pass lookup. Returns list of {canonical, category, count, aliases, score}."""
    q = query.lower().strip()
    if not q:
        return []

    by_canonical = idx.get("by_canonical", {})
    by_alias = idx.get("by_alias", {})
    results: list[dict] = []
    seen: set[str] = set()

    def add(name: str, score: float) -> None:
        if name in seen:
            return
        entry = by_canonical.get(name)
        if entry is None:
            return
        cat = entry["cat"]
        if category is not None and cat != category:
            return
        seen.add(name)
        results.append({
            "canonical": name,
            "category": cat,
            "count": entry["count"],
            "aliases": entry["aliases"],
            "score": score,
        })

    # Pass 1: exact canonical name
    if q in by_canonical:
        add(q, 1.0)

    # Pass 2: exact alias match
    if q in by_alias:
        for c in by_alias[q]:
            add(c, 0.95)

    if exact:
        return results[:limit] if limit else results

    # Pass 3: substring match on canonical names, scored by count desc
    matches: list[tuple[float, str]] = []
    for name in by_canonical:
        if name in seen:
            continue
        if q in name:
            count = by_canonical[name]["count"]
            score = 0.6 + min(0.3, count / 10_000_000)
            matches.append((score, name))
    matches.sort(reverse=True)
    for score, name in matches:
        add(name, score)

    return results[:limit] if limit else results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tag_lookup")
    parser.add_argument("--query", required=True, help="Token to search (substring or exact)")
    parser.add_argument("--limit", type=int, default=None, help="Max results")
    parser.add_argument("--category", type=int, default=None, help="Filter by category")
    parser.add_argument("--exact", action="store_true", help="Strict canonical match only")
    parser.add_argument("--index", type=Path, default=INDEX_JSON)
    args = parser.parse_args(argv)

    idx = load_index(args.index)
    results = lookup(idx, args.query, limit=args.limit, category=args.category, exact=args.exact)
    json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_tag_lookup.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Smoke test**

```bash
python D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/tag_lookup.py --query "long_hair"
python D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/tag_lookup.py --query "/lh" --limit 2
```

Expected: JSON with `long_hair` first result.

- [ ] **Step 6: Ready to commit**

---

## Task 5: `scene_match.py` (TDD)

**Files:**
- Create: `skills/prompt-forge/aesthetics/INDEX.md` (1-row-per-scene table)
- Create: `skills/prompt-forge/internals/scene_match.py`
- Create: `skills/prompt-forge/internals/tests/test_scene_match.py`

**Interfaces:**
- Consumes: `aesthetics/INDEX.md`, `aesthetics/style-presets.md` (fallback)
- Produces: CLI `--query "..."` → JSON array of `{scene, keywords_matched, recipes, score}`
- Used by: SKILL.md §1 step 3

- [ ] **Step 1: Write `aesthetics/INDEX.md`**

```markdown
| scene | keywords | lighting | composition | color |
|-------|----------|----------|-------------|-------|
| night_street | 夜景,霓虹,街景,都市夜 | lighting/lighting-neon-noir | composition/composition-low-angle | color/color-teal-orange |
| golden_hour | 黄昏,日落,金色时刻,夕阳 | lighting/lighting-golden-hour | composition/composition-eye-level | color/color-warm-palette |
| soft_window | 室内,窗光,柔光,自然光 | lighting/lighting-window-soft | composition/composition-medium-shot | color/color-neutral-warm |
| dramatic_rim | 戏剧,逆光,边缘光,剪影 | lighting/lighting-rim-dramatic | composition/composition-cowboy-shot | color/color-warm-cool-contrast |
| rembrandt | 伦勃朗,古典肖像,三角光 | lighting/lighting-rembrandt | composition/composition-cowboy-shot | color/color-warm-palette |
| harsh_top | 顶光,正午阳光,烈日 | lighting/lighting-harsh-top | composition/composition-eye-level | color/color-desaturated |
| overcast | 阴天,柔光,均匀光 | lighting/lighting-overcast | composition/composition-wide-shot | color/color-desaturated |
| diffused_mist | 雾,柔焦,朦胧,仙境 | lighting/lighting-diffused-mist | composition/composition-wide-shot | color/color-cool-blue |
| natural_soft | 自然柔光,日出,清晨 | lighting/lighting-natural-soft | composition/composition-medium-shot | color/color-skin-natural |
| low_angle | 仰拍,英雄,权力 | lighting/lighting-rim-dramatic | composition/composition-low-angle | color/color-warm-cool-contrast |
| dutch_angle | 倾斜,不安,心理 | lighting/lighting-harsh-top | composition/composition-dutch-angle | color/color-warm-cool-contrast |
| wide_landscape | 风景,远景,开阔 | lighting/lighting-natural-soft | composition/composition-landscape | color/color-earth-green |
```

- [ ] **Step 2: Write the failing test**

```python
# skills/prompt-forge/internals/tests/test_scene_match.py
import json
from pathlib import Path
from internals.scene_match import load_index, match


INDEX = Path("D:/Projects/comfyui-chenxin/skills/prompt-forge/aesthetics/INDEX.md")
PRESETS = Path("D:/Projects/comfyui-chenxin/skills/prompt-forge/aesthetics/style-presets.md")


def test_load_index():
    idx = load_index(INDEX)
    assert len(idx) >= 10
    assert all("scene" in e and "keywords" in e and "lighting" in e for e in idx)


def test_match_clear_hit():
    idx = load_index(INDEX)
    results = match(idx, "夜景 霓虹", top=3)
    assert len(results) >= 1
    assert results[0]["scene"] == "night_street"
    assert "夜景" in results[0]["keywords_matched"]


def test_match_no_keywords_miss_returns_presets():
    idx = load_index(INDEX)
    results = match(idx, "完全无关的查询 xyz123", top=3, presets_path=PRESETS)
    assert len(results) >= 1


def test_match_top_n():
    idx = load_index(INDEX)
    results = match(idx, "光 摄影", top=2)
    assert len(results) <= 2


def test_match_score_threshold():
    idx = load_index(INDEX)
    results = match(idx, "夜景", top=10)
    for r in results:
        if r.get("keywords_matched"):
            assert r["score"] >= 0.2


def test_cli_query_night():
    import subprocess
    r = subprocess.run(
        ["python", "D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/scene_match.py",
         "--query", "夜景", "--top", "1"],
        capture_output=True, text=True,
        cwd="D:/Projects/comfyui-chenxin",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data[0]["scene"] == "night_street"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_scene_match.py -v
```

Expected: ImportError.

- [ ] **Step 4: Write the implementation**

```python
# skills/prompt-forge/internals/scene_match.py
#!/usr/bin/env python3
"""scene_match — match scene keywords to aesthetic recipes.

Reads aesthetics/INDEX.md (markdown table: scene | keywords | lighting | composition | color)
and returns top-N scene matches for a user query. Falls back to style-presets.md
when no scene scores above threshold.

Usage:
    python scene_match.py --query "夜景 霓虹"
    python scene_match.py --query "樱花树下" --top 1

Stdlib only. Output: JSON array on stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
INDEX_MD = SKILL_DIR / "aesthetics" / "INDEX.md"
PRESETS_MD = SKILL_DIR / "aesthetics" / "style-presets.md"

THRESHOLD = 0.2


def _tokenize(text: str) -> set[str]:
    """CJK char + word tokenization. CJK each char, Latin words."""
    text = text.lower().strip()
    cjk_chars = set(c for c in text if "\u4e00" <= c <= "\u9fff")
    latin_words = set(re.findall(r"[a-z0-9_]+", text))
    return cjk_chars | latin_words


def load_index(path: Path = INDEX_MD) -> list[dict]:
    """Parse INDEX.md markdown table into list of scene dicts."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = [l.strip() for l in text.splitlines() if l.strip().startswith("|") and not l.startswith("|---")]
    if len(lines) < 2:
        return []
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    entries: list[dict] = []
    for line in lines[1:]:
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < len(header):
            continue
        row = dict(zip(header, cols))
        keywords = _tokenize(row.get("keywords", ""))
        entries.append({
            "scene": row.get("scene", ""),
            "keywords": keywords,
            "lighting": row.get("lighting", ""),
            "composition": row.get("composition", ""),
            "color": row.get("color", ""),
        })
    return entries


def match(scenes: list[dict], query: str, top: int = 3,
         presets_path: Path | None = PRESETS_MD) -> list[dict]:
    """Match query tokens against scene keyword sets. Returns top-N, or presets fallback."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return _presets_fallback(presets_path, top)

    scored: list[dict] = []
    for s in scenes:
        scene_tokens: set[str] = s["keywords"]
        if not scene_tokens:
            continue
        overlap = q_tokens & scene_tokens
        if not overlap:
            continue
        score = len(overlap) / len(q_tokens)
        if score < THRESHOLD:
            continue
        scored.append({
            "scene": s["scene"],
            "keywords_matched": sorted(overlap),
            "recipes": {
                "lighting": s["lighting"],
                "composition": s["composition"],
                "color": s["color"],
            },
            "score": round(score, 2),
        })

    scored.sort(key=lambda x: (-x["score"], x["scene"]))

    if not scored:
        return _presets_fallback(presets_path, top)
    return scored[:top]


def _presets_fallback(path: Path | None, top: int) -> list[dict]:
    """Read style-presets.md and return top-N preset names as fallback."""
    if path is None or not path.exists():
        return [{"scene": "_no_fallback", "score": 0}]
    text = path.read_text(encoding="utf-8")
    headings = [l.strip().lstrip("#").strip() for l in text.splitlines() if l.strip().startswith("#")]
    return [{"scene": h, "score": 0, "fallback": True} for h in headings[:top]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scene_match")
    parser.add_argument("--query", required=True, help="Scene keyword query")
    parser.add_argument("--top", type=int, default=3, help="Max scenes to return")
    parser.add_argument("--index", type=Path, default=INDEX_MD)
    args = parser.parse_args(argv)

    scenes = load_index(args.index)
    results = match(scenes, args.query, top=args.top)
    json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_scene_match.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Smoke test**

```bash
python D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/scene_match.py --query "夜景 霓虹"
python D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/scene_match.py --query "完全无关的查询" --top 2
```

Expected: 夜景 → `night_street`; 无关 → preset fallback names.

- [ ] **Step 7: Ready to commit**

---

## Task 6: Upgrade `recipe_lookup.py` (TDD — must remain backwards compatible)

**Files:**
- Modify: `skills/prompt-forge/internals/recipe_lookup.py`
- Create: `skills/prompt-forge/internals/tests/test_recipe_lookup.py`

**Interfaces (after upgrade):**
- `--model X` → 3-pass matching (exact → alias → weighted fuzzy), adds `score` + `match_path` fields to JSON output
- `--check-alias <alias>` → resolve to canonical
- `--list-aliases` → dump alias table
- Consumes: `_aliases.py` (Task 2)

- [ ] **Step 1: Write the failing test**

```python
# skills/prompt-forge/internals/tests/test_recipe_lookup.py
import json
import subprocess
from pathlib import Path
from internals.recipe_lookup import _match_recipe, _parse_recipes, RECIPES_PATH


def test_exact_match_returns_score_one():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "anima")
    assert result is not None
    assert score == 1.0
    assert path == "exact"


def test_alias_match_resolves_to_canonical():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "anima_baseV10")
    assert result is not None
    assert score == 0.95
    assert path == "alias"
    assert result["frontmatter"]["id"] == "anima"


def test_weighted_fuzzy_match():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "stable_diffusion_xl")
    assert result is not None
    assert path in ("alias", "weighted_fuzzy")
    assert result["frontmatter"]["id"] == "sdxl"


def test_no_match_returns_none():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "totally_made_up_xyz")
    assert result is None


def test_backwards_compat_v4_signature():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "anima")
    assert "matched" in result
    assert "matched_id" in result
    assert "heading" in result
    assert "frontmatter" in result
    assert "dialect_block" in result
    assert "score" in result
    assert "match_path" in result


def test_cli_alias_resolution():
    r = subprocess.run(
        ["python", "D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_lookup.py",
         "--check-alias", "anima_baseV10"],
        capture_output=True, text=True,
        cwd="D:/Projects/comfyui-chenxin",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["canonical"] == "anima"


def test_cli_anima_backwards_compat():
    r = subprocess.run(
        ["python", "D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_lookup.py",
         "--model", "anima"],
        capture_output=True, text=True,
        cwd="D:/Projects/comfyui-chenxin",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["matched"] is True
    assert data["matched_id"] == "anima"
    assert "frontmatter" in data
    assert "dialect_block" in data
    assert data["score"] == 1.0
    assert data["match_path"] == "exact"


def test_cli_list_aliases():
    r = subprocess.run(
        ["python", "D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_lookup.py",
         "--list-aliases"],
        capture_output=True, text=True,
        cwd="D:/Projects/comfyui-chenxin",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "anima_basev10" in data
    assert "stable_diffusion_xl" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_recipe_lookup.py -v
```

Expected: ImportError on `_match_recipe`.

- [ ] **Step 3: Replace recipe_lookup.py with upgraded version**

Overwrite `skills/prompt-forge/internals/recipe_lookup.py` with:

```python
#!/usr/bin/env python3
"""recipe_lookup — query recipes/MODELS.md by model id (with weighted fuzzy + alias).

Stdlib only. Returns JSON on stdout.

Usage:
    python recipe_lookup.py --model <id>
    python recipe_lookup.py --model <substring> --n 50
    python recipe_lookup.py --check-alias <alias>
    python recipe_lookup.py --list-aliases
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _aliases import ALIASES, resolve_alias, all_aliases

_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
RECIPES_PATH = SKILL_DIR / "recipes" / "MODELS.md"

_RECIPE_BLOCK_RE = re.compile(
    r"^---\n(?P<yaml>.*?)\n---\n+(?P<body>.*?)(?=\n---\n|\Z)",
    re.M | re.S,
)

_FIELD_WEIGHTS = {
    "id": 1.0,
    "family": 0.7,
    "modality": 0.4,
    "heading": 0.3,
    "dialect": 0.5,
}


def _require_python_311() -> None:
    if sys.version_info < (3, 11):
        print("[recipe_lookup] Python 3.11+ required", file=sys.stderr)
        sys.exit(3)


def _parse_yaml_block(yaml_text: str) -> dict:
    """Minimal YAML parser for the subset used in MODELS.md."""
    out: dict = {}
    current_key: str | None = None
    for raw in yaml_text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("  -") or line.startswith("    -"):
            value = line.lstrip().lstrip("-").strip()
            value = value.strip('"').strip("'")
            if current_key and current_key in out:
                if isinstance(out[current_key], list):
                    out[current_key].append(value)
                else:
                    out[current_key] = [value]
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if m:
            key = m.group(1)
            value = m.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1]
                out[key] = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
            elif value:
                out[key] = value.strip('"').strip("'")
            else:
                out[key] = []
            current_key = key
    return out


def _split_heading_body(heading_line: str) -> tuple[str, str]:
    if "- **" in heading_line:
        i = heading_line.index("- **")
        return heading_line[:i].rstrip(), heading_line[i:]
    return heading_line, ""


def _parse_recipes(text: str) -> list[dict]:
    recipes: list[dict] = []
    for m in _RECIPE_BLOCK_RE.finditer(text):
        yaml_text = m.group("yaml")
        body = m.group("body")
        try:
            frontmatter = _parse_yaml_block(yaml_text)
        except Exception as e:
            print(f"[recipe_lookup] skip block (yaml parse failed): {e}", file=sys.stderr)
            continue
        heading = ""
        body_lines: list[str] = []
        for line in body.splitlines():
            if line.startswith("### ") and not heading:
                heading, glued = _split_heading_body(line)
                if glued:
                    body_lines.append(glued)
                continue
            if heading:
                body_lines.append(line)
        recipes.append({
            "frontmatter": frontmatter,
            "heading": heading,
            "body_lines": body_lines,
        })
    return recipes


def _format_dialect(heading: str, body_lines: list[str], n: int) -> str:
    out = [heading] + body_lines[:n]
    return "\n".join(out)


def _score(text: str, query: str, weight: float) -> float:
    """exact=weight, substring=weight*0.6, char-overlap=weight*0.3."""
    t = text.lower()
    q = query.lower()
    if t == q:
        return weight
    if q in t or t in q:
        return weight * 0.6
    common = sum(1 for c in set(q) if c in set(t))
    return weight * (common / max(len(set(q)), 1)) * 0.3


def _match_recipe(recipes: list[dict], query: str) -> tuple[dict | None, float, str]:
    """3-pass match. Returns (recipe_dict, score, match_path)."""
    q = query.lower().strip()
    if not q:
        return None, 0.0, "none"

    # Pass 1: exact id match
    for r in recipes:
        rid = (r["frontmatter"].get("id") or "").lower()
        if rid == q:
            return r, 1.0, "exact"

    # Pass 2: alias match
    canonical = resolve_alias(query)
    if canonical:
        for r in recipes:
            rid = (r["frontmatter"].get("id") or "").lower()
            if rid == canonical.lower():
                return r, 0.95, "alias"

    # Pass 3: weighted fuzzy across 5 fields
    scored: list[tuple[float, dict]] = []
    for r in recipes:
        fm = r["frontmatter"]
        score = (
            _score(fm.get("id", ""), q, _FIELD_WEIGHTS["id"]) +
            _score(fm.get("family", ""), q, _FIELD_WEIGHTS["family"]) +
            _score(fm.get("modality", ""), q, _FIELD_WEIGHTS["modality"]) +
            _score(r["heading"], q, _FIELD_WEIGHTS["heading"]) +
            _score(fm.get("dialect", ""), q, _FIELD_WEIGHTS["dialect"])
        )
        if score >= 0.5:
            scored.append((score, r))
    if scored:
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored[0][1], scored[0][0], "weighted_fuzzy"

    return None, 0.0, "none"


def main(argv: list[str] | None = None) -> int:
    _require_python_311()
    parser = argparse.ArgumentParser(prog="recipe_lookup")
    parser.add_argument("--model", help="Recipe id (exact), alias, or substring")
    parser.add_argument("--n", type=int, default=30, help="Max body lines in dialect block")
    parser.add_argument("--path", type=Path, default=RECIPES_PATH)
    parser.add_argument("--check-alias", help="Resolve alias to canonical id")
    parser.add_argument("--list-aliases", action="store_true", help="Dump full alias table")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"[recipe_lookup] missing {args.path}", file=sys.stderr)
        return 3

    if args.list_aliases:
        json.dump(ALIASES, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 0

    if args.check_alias is not None:
        canonical = resolve_alias(args.check_alias)
        json.dump({"alias": args.check_alias, "canonical": canonical}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 0 if canonical else 2

    if not args.model:
        parser.error("--model is required (or use --check-alias / --list-aliases)")

    text = args.path.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    matched, score, path = _match_recipe(recipes, args.model)

    if matched is None:
        json.dump({"matched": False, "query": args.model, "score": 0.0, "match_path": path}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 0

    fm = matched["frontmatter"]
    out = {
        "matched": True,
        "matched_id": fm.get("id", ""),
        "heading": matched["heading"],
        "frontmatter": fm,
        "dialect_block": _format_dialect(matched["heading"], matched["body_lines"], args.n),
        "score": score,
        "match_path": path,
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_recipe_lookup.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Smoke test backwards compat**

```bash
python D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_lookup.py --model anima
python D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_lookup.py --model __nonexistent
python D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_lookup.py --check-alias AnimaStandardV7
python D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_lookup.py --list-aliases
```

Expected: anima → matched=true, score=1.0; __nonexistent → matched=false; AnimaStandardV7 → canonical=anima; --list-aliases → JSON of alias table.

- [ ] **Step 6: Ready to commit**

---

## Task 7: Upgrade `recipe_yaml.py` (add `--validate-schema` + `--add-alias` + `--list-aliases`)

**Files:**
- Modify: `skills/prompt-forge/internals/recipe_yaml.py`
- Create: `skills/prompt-forge/internals/tests/test_recipe_yaml.py`

**Interfaces (after upgrade):**
- All v4 modes preserved (default, `--check`, `--path`)
- NEW `--validate-schema` → exit 1 if any recipe missing `id` or schema violated
- NEW `--add-alias <alias>=<canonical>` → append to `_aliases.ALIASES` and persist
- NEW `--list-aliases` → dump alias table

- [ ] **Step 1: Write the failing test**

```python
# skills/prompt-forge/internals/tests/test_recipe_yaml.py
import subprocess


def test_validate_schema_clean():
    r = subprocess.run(
        ["python", "D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_yaml.py",
         "--validate-schema"],
        capture_output=True, text=True,
        cwd="D:/Projects/comfyui-chenxin",
    )
    assert r.returncode == 0, f"validate-schema failed: {r.stderr}"


def test_check_idempotent():
    r = subprocess.run(
        ["python", "D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_yaml.py",
         "--check"],
        capture_output=True, text=True,
        cwd="D:/Projects/comfyui-chenxin",
    )
    assert r.returncode == 0


def test_list_aliases():
    r = subprocess.run(
        ["python", "D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_yaml.py",
         "--list-aliases"],
        capture_output=True, text=True,
        cwd="D:/Projects/comfyui-chenxin",
    )
    assert r.returncode == 0
    assert "anima_basev10" in r.stdout
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_recipe_yaml.py -v
```

Expected: `validate-schema` mode not implemented → exit non-zero.

- [ ] **Step 3: Patch recipe_yaml.py**

Read the current file first:

```bash
cat D:/Projects/comfyui-chenxin/skills/prompt-forge/internals/recipe_yaml.py
```

Apply targeted edits (do NOT rewrite the whole file — preserve v4 normalization logic):

1. In the existing argparse parser, after `add_argument("--path", ...)`, add:
```python
parser.add_argument("--validate-schema", action="store_true",
    help="Check that every recipe has required fields (id, dialect). Exits 1 on failure.")
parser.add_argument("--add-alias", metavar="ALIAS=CANONICAL",
    help="Append an alias to internals/_aliases.ALIASES.")
parser.add_argument("--list-aliases", action="store_true",
    help="Dump alias table as JSON.")
```

2. In `main()`, after existing arg handling, insert (before existing `normalize()` call):
```python
if args.list_aliases:
    from _aliases import ALIASES
    json.dump(ALIASES, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0

if args.add_alias:
    from _aliases import ALIASES
    if "=" not in args.add_alias:
        print("[recipe_yaml] --add-alias requires ALIAS=CANONICAL", file=sys.stderr)
        return 2
    alias_key, _, canonicals = args.add_alias.partition("=")
    alias_norm = alias_key.lower().strip()
    canonicals_list = [c.strip() for c in canonicals.split(",") if c.strip()]
    if not canonicals_list:
        print("[recipe_yaml] --add-alias requires at least one canonical id", file=sys.stderr)
        return 2
    ALIASES[alias_norm] = canonicals_list
    aliases_path = Path(__file__).resolve().parent / "_aliases.py"
    text = aliases_path.read_text(encoding="utf-8")
    new_line = f'    "{alias_norm}": {json.dumps(canonicals_list)},'
    pattern = re.compile(rf'    "{re.escape(alias_norm)}":\s*\[[^\]]*\],?\n')
    if pattern.search(text):
        text = pattern.sub(new_line + "\n", text)
    else:
        text = text.rstrip()
        if text.endswith("}"):
            text = text[:-1].rstrip() + new_line + "\n}\n"
    aliases_path.write_text(text, encoding="utf-8")
    print(f"[recipe_yaml] added alias '{alias_norm}' → {canonicals_list}")
    return 0

if args.validate_schema:
    text = args.path.read_text(encoding="utf-8") if args.path.exists() else ""
    errors = []
    seen_ids: set[str] = set()
    block_re = re.compile(r"^---\n(.*?)\n---\n", re.M | re.S)
    for i, m in enumerate(block_re.finditer(text)):
        yaml_text = m.group(1)
        if "id:" not in yaml_text:
            errors.append(f"block #{i}: missing 'id' field")
            continue
        m_id = re.search(r"^id:\s*(\S+)", yaml_text, re.M)
        if m_id:
            id_val = m_id.group(1)
            if not re.match(r"^[a-z0-9_-]+$", id_val):
                errors.append(f"block #{i}: id '{id_val}' contains invalid chars")
            if id_val in seen_ids:
                errors.append(f"block #{i}: duplicate id '{id_val}'")
            seen_ids.add(id_val)
    if errors:
        for e in errors:
            print(f"[recipe_yaml] {e}", file=sys.stderr)
        print(f"[recipe_yaml] {len(errors)} schema error(s)", file=sys.stderr)
        return 1
    print(f"[recipe_yaml] schema OK ({len(seen_ids)} recipes)")
    return 0
```

Also ensure the imports at the top of `recipe_yaml.py` include `json` and `re` (if not already present).

- [ ] **Step 4: Run test to verify it passes**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/test_recipe_yaml.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Ready to commit**

---

## Task 8: Rewrite `SKILL.md` to v5 (~250 lines, restore spec-v3 6-step pipeline + 10-dim framework)

**Files:**
- Modify: `skills/prompt-forge/SKILL.md` (full rewrite)

- [ ] **Step 1: Overwrite SKILL.md with v5 content**

Overwrite `skills/prompt-forge/SKILL.md` with the content below (full body; YAML frontmatter first).

```markdown
---
name: prompt-forge
description: |
  文生图/视频提示词生成 — L4 路由器。触发词: prompt, negative prompt,
  提示词, 反向提示词, 分镜头, 运镜, 写分镜, anima, flux, sdxl, wan, ltx,
  hunyuan, comfyui, 文生视频.
  流程: ① 识别模型 → ② 10 维要素提取 → ③ scene-recipes 匹配 → ④ tag 字典验证
  → ⑤ 组装 prompt → ⑥ 11 项自检 → 调 mcp__comfyui-mcp__generate_image / video.
  本 skill 拥有 prompt 质量；MCP 拥有调用引擎。
version: 5.0.0
triggers:
  - prompt
  - negative prompt
  - 提示词
  - 反向提示词
  - 分镜头
  - 运镜
  - 写分镜
  - anima
  - flux
  - sdxl
  - wan
  - ltx
  - hunyuan
  - comfyui
  - 文生视频
---

# prompt-forge v5 — L4 路由器

## §0 第一性原理

> **ComfyUI 只画 prompt，没有 taste**。
> 决策表全在数据里：recipes/MODELS.md (81 个模型配方) + dictionary/ (140K tag 字典) + aesthetics/ (24 个场景配方)。
> Python 只做查询和规范化；LLM (Claude) 做组装和判断。
> prompt-forge 拥有 prompt **质量**；mcp__comfyui-mcp__* 拥有调用 **引擎**。

## §1 6 步流水线

```
用户: "用 Anima 出金发精灵女法师在樱花树下释放魔法的图"
   │
   ▼
① 模型识别 ──────── recipe_lookup.py --model anima
   │                  3-pass: exact(1.0) > alias(0.95) > weighted_fuzzy(≥0.5)
   │                  → {matched, matched_id, heading, frontmatter, dialect_block, score, match_path}
   │
   ▼
② 10 维要素提取 ── SKILL.md §3 框架
   │                  subject / action / scene / lighting / composition / color / style / mood / medium / quality
   │                  缺失维度标记 [unset]
   │
   ▼
③ scene-recipes ─── scene_match.py --query "樱花树下 释放魔法"
   │                  INDEX.md 关键词扫描 → top-3 scenes
   │                  → lighting/rembrandt.md + composition/cowboy-shot.md + color/warm-cool-contrast.md
   │                  miss → style-presets.md 兜底（3 个 preset）
   │
   ▼
④ tag 字典验证 ──── tag_lookup.py --query "金发" "精灵" "樱花"
   │                  3-pass: exact(1.0) > alias(0.95) > substring(≥0.6)
   │                  → [{canonical, category, count, aliases, score}, ...]
   │
   ▼
⑤ 组装 prompt ──── §4 编排原则
   │                  tag 系 (Anima): score_9, score_8_up, [subject], [action], [lighting], ...
   │                  + aesthetic 覆盖 (lighting + composition + color)
   │                  + dialect block (from step 1)
   │                  前 10 token 策略（按 encoder 类型）
   │
   ▼
⑥ 11 项自检 ──────── §5
                      ↓
                   mcp__comfyui-mcp__generate_image(prompt=..., negative_prompt=...)
```

## §2 数据源

```
skills/prompt-forge/
├── recipes/MODELS.md          81 模型 recipes（YAML frontmatter）
├── dictionary/                tag 字典（danbooru.csv 140K + wd14-tags.csv 11K + tag-index.json）
├── aesthetics/                24 个场景配方 + scene-recipes + style-presets + 4 个 glossary
├── negative/negative-prompts.md  负向模板
├── models/                    15 个模型元数据（encoder / tag_style / negative）
├── internals/                 5 个 stdlib Python 工具
└── hardware/8gb.json          8GB 显存决策矩阵（13-key schema v1）
```

## §3 10 维度框架

| 维度 | 描述 | 来源 |
|------|------|------|
| subject | 谁/什么 | 用户输入 |
| action | 在做什么 | 用户输入 |
| scene | 在哪里/什么场景 | scene_match.py / user |
| lighting | 光照类型 | aesthetics/lighting/ |
| composition | 构图 | aesthetics/composition/ |
| color | 色彩/色调 | aesthetics/color/ |
| style | 风格（动漫/写实/油画...） | 用户输入 + recipe |
| mood | 氛围（孤独/温馨...） | 用户输入 |
| medium | 媒介（水彩/胶片/...） | aesthetics/medium-glossary.md |
| quality | 质量锚点（masterpiece 链） | recipe frontmatter |

**缺失维度**：标记 `[unset]`，由 scene_match 或 style-presets 兜底。

## §4 组装原则

### 前 10 token 策略

| 编码器 | 策略 | 原因 |
|--------|------|------|
| **LLM** (Anima / Flux / Qwen / SD 3.5) | 主体+动作在前，质量锚点在尾 | LLM 全局注意力，第一句定骨架 |
| **CLIP** (Pony / Illustrious / SDXL / SD 1.5) | 按模型 `tag_order_strategy`（见 models/*.md） | CLIP 单向注意力，位置即权重 |

### 3 种 dialect

| dialect | 适用 | 例子 |
|---------|------|------|
| **tag 系** (Danbooru comma-separated) | Anima / Pony / SDXL / SD 1.5 | `score_9, score_8_up, pointy_ears, long_hair, ...` |
| **自然语言** (句子, 顺序敏感) | Flux / Qwen | `A young elf mage with long golden hair casts fire magic under cherry blossoms.` |
| **视频** (shot + camera + temporal) | Wan / LTX | `Wide shot → close-up → pan left → slow motion → dusk lighting` |

## §5 11 项自检

1. 10 维度齐全（缺则填 `[unset]`）
2. 所有 tag 经 tag_lookup.py 验证
3. 前 10 token = SUBJECT + ACTION
4. STYLE 在前 25% token 位置
5. lighting / composition / color 各为独立段
6. token 总数在模型限制内
7. 无抽象赞美词堆叠（"beautiful amazing stunning"）
8. STYLE 段显式命名媒介
9. LoRA 兼容性（trigger token 完整）
10. 模型专属约束（见 models/{name}.md）
11. 概念密度 > 0.6（具体词 ≥ 60%）

## §6 与 MCP / 触发词

```
prompt-forge (本 skill) → mcp__comfyui-mcp__* (108 工具) → ComfyUI
        ↑ 先出 prompt                                    ↑ 后出图
```

**触发词列表**（已从 v4 移除 `图生视频` 以避免与 stage-4-motion 路由歧义——视频 prompt 写作由 scene_match.py 走 video-archetypes.md 流程处理）：

`prompt` `negative prompt` `提示词` `反向提示词` `分镜头` `运镜` `写分镜`
`anima` `flux` `sdxl` `wan` `ltx` `hunyuan` `comfyui` `文生视频`
```

- [ ] **Step 2: Smoke-test all 5 Python tools in sequence (mimicking §1 6-step flow)**

```bash
cd D:/Projects/comfyui-chenxin
echo "=== Step 1: model ==="
PYTHONPATH=skills/prompt-forge python skills/prompt-forge/internals/recipe_lookup.py --model anima | head -5
echo "=== Step 3: scene ==="
PYTHONPATH=skills/prompt-forge python skills/prompt-forge/internals/scene_match.py --query "夜景 释放魔法" --top 1
echo "=== Step 4: tag ==="
PYTHONPATH=skills/prompt-forge python skills/prompt-forge/internals/tag_lookup.py --query "long_hair" | head -5
echo "=== Build check ==="
PYTHONPATH=skills/prompt-forge python skills/prompt-forge/internals/build_tag_index.py --check
echo "=== Schema check ==="
PYTHONPATH=skills/prompt-forge python skills/prompt-forge/internals/recipe_yaml.py --validate-schema
```

Expected: all exit 0, sensible output.

- [ ] **Step 3: Run full test suite**

```bash
cd D:/Projects/comfyui-chenxin
PYTHONPATH=skills/prompt-forge python -m pytest skills/prompt-forge/internals/tests/ -v
```

Expected: 7 + 3 + 6 + 9 + 7 + 3 = 35 tests pass.

- [ ] **Step 4: Ready to commit**

---

## Self-Review

1. **Spec coverage** — all 10 spec sections traced to tasks (see Self-Review at end of plan).
2. **Placeholder scan** — no TBD/TODO/"implement later".
3. **Type consistency** — `match_path` values (`exact`/`alias`/`weighted_fuzzy`/`none`) consistent across Tasks 3, 6, 7. `ALIASES` shape consistent across Tasks 2, 6, 7. `tag-index.json` `_meta` shape consistent between Task 3 build and Task 4 read.
4. **Gap noted in plan** — spec §3.2 uniqueness check was added to Task 7 Step 3 inline.