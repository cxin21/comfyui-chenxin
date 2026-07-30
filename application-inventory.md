# Application Inventory — P1.1 L5 Decoupling

> **Phase**: P1.1 — L5 application decoupling
> **Branch**: `phase/P1.1-l5-decoupling`
> **Date**: 2026-07-30
> **Reason**: chenxin-core (L4, P0.3) routes multi-stage pipelines to L5 application
> skills. Before P1.1, those 7 skills lived at `~/.claude/skills/<name>/` outside the
> plugin's discoverable surface — so `chenxin-core` step 7 silently fell through.
> P1.1 moves them into the plugin so the SKILL loader can find them.

## 1. Skills brought in

| # | Plugin slot | Source path (read-only) | Status | Bytes | Notes |
|---|---|---|---|---|---|
| 1 | `skills/manga-orchestrator/SKILL.md` | `~/.claude/skills/manga-bootstrap/SKILL.md` (closest equivalent — coordinator role) | **ported** | see git diff | frontmatter now declares `chenxin-core` upstream; bootstrap script logic inlined into skill body |
| 2 | `skills/manga-stage-1-lora/SKILL.md`  | `~/.claude/skills/manga-stage-1-lora/` (does not exist) | **skipped** | stub only | placeholder stub ships so inventory is symmetric; functional LoRA work covered by `lora-trainer` |
| 3 | `skills/manga-stage-2-panels/SKILL.md` | `~/.claude/skills/manga-stage-2-panels/SKILL.md` | **ported** | see git diff | v2.0 → v2.1; chenxin-core pointer added |
| 4 | `skills/manga-stage-3-review/SKILL.md` | `~/.claude/skills/manga-stage-3-review/SKILL.md` | **ported** | see git diff | v2.0 → v2.1; 6-dim scoring preserved |
| 5 | `skills/manga-stage-4-motion/SKILL.md` | `~/.claude/skills/manga-stage-4-motion/SKILL.md` | **ported** | see git diff | v3.0 → v3.1; lip-sync fallback documented |
| 6 | `skills/ffmpeg-pipeline/SKILL.md`     | `~/.claude/skills/ffmpeg-pipeline/SKILL.md`     | **ported** | see git diff | v1.0 → v1.1; codec note added |
| 7 | `skills/lora-trainer/SKILL.md`        | `~/.claude/skills/lora-trainer/SKILL.md`        | **ported** | see git diff | v2.2 → v2.3; Anima standalone path preserved |

**6 ported, 1 skipped (gap documented), 0 invented.**

## 2. Back-compat & old paths

### Old paths now redundant

After this merge, the canonical home for these skills is inside the plugin. The
following `~/.claude/skills/` paths are now redundant as primary entry points and
should be considered for soft-deprecation in a follow-up phase:

- `~/.claude/skills/manga-bootstrap/`        → superseded by `skills/manga-orchestrator/` in this plugin
- `~/.claude/skills/manga-orchestrator/`     → moved into `skills/manga-orchestrator/`
- `~/.claude/skills/manga-stage-2-panels/`   → moved into `skills/manga-stage-2-panels/`
- `~/.claude/skills/manga-stage-3-review/`   → moved into `skills/manga-stage-3-review/`
- `~/.claude/skills/manga-stage-4-motion/`   → moved into `skills/manga-stage-4-motion/`
- `~/.claude/skills/ffmpeg-pipeline/`        → moved into `skills/ffmpeg-pipeline/`
- `~/.claude/skills/lora-trainer/`           → moved into `skills/lora-trainer/`

### Files NOT touched (P1.1 contract)

- `~/.claude/skills/*` originals — **left in place** so any session that resolves
  skills by global `~/.claude/skills/` path still finds the content. The original
  files were NOT deleted or modified; only copied.
- `mcp/`, `agents/`, `commands/`, `hooks/`, `scripts/` in this repo — out of P1.1 scope.
- Any SKILL outside the listed 7 — untouched.

### When is a hard deprecation safe?

Not yet. Once a downstream user has installed this plugin AND chenxin-core's L4
route table points only at `skills/<name>/SKILL.md` paths, the global
`~/.claude/skills/<name>/` copies can be removed. Until then they are the
fallback. (See first-principles below.)

## 3. Application route map (L5 → L3 recipes)

This is the explicit mapping that `chenxin-core` (L4) needs in order to dispatch
multi-stage work. Each L5 skill is annotated with the L3 recipe it eventually
depends on (recipe IDs follow P0.1 `recipes_index.json`).

| L5 skill (plugin path) | L3 recipe it ultimately invokes | Primary use case |
|---|---|---|
| `skills/manga-orchestrator/SKILL.md`         | (orchestrates 0→5 below)       | 6-stage full pipeline coordinator |
| `skills/manga-stage-2-panels/SKILL.md`       | `recipe.anima.txt2img` (v1.0 AnimaStandardV7) | 24 panel PNGs at 832×1216 |
| `skills/manga-stage-3-review/SKILL.md`       | `recipe.aesthetic_judge.6d` (read-only) | 6-dim scoring, no generation |
| `skills/manga-stage-4-motion/SKILL.md`       | `recipe.ltx23.img2vid` (ltx23AllInOne) | 78-node LTX I2V; I2V_InfiniteTalk fallback for speaking |
| `skills/ffmpeg-pipeline/SKILL.md`            | (no L3 recipe — pure ffmpeg CLI) | concat + SRT + optional burn-in |
| `skills/lora-trainer/SKILL.md`               | `recipe.anima.lora_train` (standalone trainer) | Anima 1.0 LoRA, 8GB VRAM |
| `skills/manga-stage-1-lora/SKILL.md` (deferred) | — (gap; covered by `lora-trainer`) | tbd once source materializes |

### How routing works now

Before P1.1: a user said "全自动生成漫剧 ..." → chenxin-core L4 step 7 tried to
hand off to `manga-orchestrator` → no such SKILL existed in the plugin's loader
scope → silent fall-through.

After P1.1: chenxin-core L4 step 7 finds `skills/manga-orchestrator/SKILL.md`
inside the plugin → invokes it → it chains to `lora-trainer` → Stage 2 → Stage 3
→ Stage 4 → `ffmpeg-pipeline` → final mp4.

## 4. Smoke test contract

`tests/test_applications.sh` enforces, for each ported skill, that:

1. The file exists at `skills/<name>/SKILL.md`.
2. The file has YAML frontmatter delimited by `---`.
3. The frontmatter has both `name:` and `description:` keys.
4. The `description:` value contains the literal substring `chenxin-core` so L4
   routing metadata is present.

Run:

```bash
bash tests/test_applications.sh
```

Expected output: 6/6 PASS (manga-stage-1-lora is a stub — the test only runs
against ported skills).

## 5. Out of scope (deferred)

- P1.3 Obsidian sync for the new plugin-relative paths.
- P2.1 Marketplace publish — needs P1.1 merged first.
- Hard deprecation of `~/.claude/skills/<name>/` — needs adoption telemetry.

## 6. First-principles: why migration-by-copy, not deprecation

The old `~/.claude/skills/<name>/` paths still resolve to working skill content
on the operator's machine. If we hard-deprecated them in the same change that
moved them into the plugin, every session that was still resolving skills via
the global `~/.claude/skills/` discovery path would silently lose functionality
on the day the merge lands — there would be no way to roll back without
re-creating the global paths by hand. Migration-by-copy means the plugin owns the
canonical path **and** the global path keeps working as a fallback until the
plugin path is observed to win every time. This is the smallest change that
turns L4 routing on without turning anything off, and it leaves the deprecation
as a follow-up phase with its own evidence gate.
