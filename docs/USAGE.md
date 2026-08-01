# Usage Guide / 使用指南

> **EN**: Step-by-step concrete examples for the 3 most common workflows.
>
> **中文**:3 个最常用工作流的逐步具体示例。

---

## Workflow 1 — Generate a single image (EN: "prompt → PNG")

### Command sequence

```bash
# In a Claude Code session that has this plugin installed:

/chenxin-init                                       # one-time, per machine
"用 Anima 生成金发精灵女法师释放灭世级魔法, 832x1216"
```

### What happens (timeline)

```
t=0      Chenxin-core (L4) routes:
         - "Anima"   → recipe_lookup.py → anima dialect block
         - "魔法"    → aesthetic-match  (8-segment framework)
         - 832x1216  → hardware_decide.py (8GB profile)

t=200ms  vram_decide.py returns:
         {quant: fp8_e4m3fn, swap: 40, defaults: euler/4/1.0, blocked: false}

t=500ms  SKILL.md calls:
         mcp__comfyui-mcp__query_workflow(AnimaStandardV7.json, ids=[3,4])
         mcp__comfyui-mcp__modify_workflow(set node 3/4 to dialect+blend)

t=2s     mcp__comfyui-mcp__enqueue_workflow + get_job_status (poll)

t=15s    mcp__comfyui-mcp__get_image → PNG in <comfyui>/output/

t=16s    L5 gui_save.py writes <comfyui>/user/default/workflows/<ts>_anima-img.json
         (the graph for replay)

t=17s    aesthetic-judge algorithm (in stage-3-review module) scores 8.4/10

t=17.1s  Result returned to user with 6-dim breakdown table.
```

---

## Workflow 2 — Generate a 5-sec I2V with talking + post-audio

### Command sequence

```bash
"用 Wan 2.2 出 5 秒视频:金发精灵女法师释放灭世级魔法, 加台词 +
 后期, 8GB VRAM 友好"
```

### What happens

```
t=0      L4 routes to:
         - recipes/MODELS.md: wan (preferred on 8GB)
         - templates_index.json: img2vid matches → ltx23AllInOneWorkflowForRTX_v44
         - hardware_decide.py: 8GB profile → defaults

t=1s     Agent invokes mcp/extensions/vram_decide.py --vram 8 --model wan
         → may recommend lowering longer_edge to 1024 if LTX GGUF Q4

t=3s     L2 loads ltx23 workflow + 5-step backup-modify-execute-restore per workflow-config-guard.md

t=5s     mcp__comfyui-mcp__modify_workflow (5 white-listed nodes: 121/593/149/1792/1793)
         - set 121 = positive prompt
         - set 593 = negative
         - set 149 = first frame PNG
         - set 1792 = 1024 (resolution)
         - set 1793 = 5 (clip length)

t=10s    mcp__comfyui-mcp__enqueue_workflow
         → calls LTX Sampler (CFG distilled, 4-step lightx2v)

t=90s    Video + audio generated (LTX-2.3 GGUF on 8GB takes ~75s for 5s clip)

t=92s    ffmpeg-pipeline skill auto-invokes for optional SRT + concat

t=93s    Result returned with 4 products: mp4 / graph / manifest / SRT
```

---

## Workflow 3 — Full 6-stage manga pipeline

### Command sequence

```bash
"全自动生成漫剧 永劫无间宁红夜"
```

### What happens (simplified; real times scale with VRAM)

```
t=0min    L4 + L5 manga-orchestrator kick off
         SKILL.md enumerates 6 stages

Stage 0 (5min)
  scripts/bootstrap.sh --title-cn 永劫无间 --title-en yongjie_jianxin
  creates: 02_assets/, 03_storyboard/01_plan.md, pipeline_state.json
  writes vault: decision-{date}-manga-orchestrator.md

Stage 1 (60-120min per character)
  skills/lora-trainer/SKILL.md invoked, vit train_anima_standalone.sh
  produces: 02_assets/01_characters/<n>/<n>.safetensors
  verification: 5 test images + 6-dim ≥ 7.0 (in stages stage-3-review)
  writes vault: knowledge-{date}-{char}-lora-verified.md

Stage 2 (~30 min per 24 panels)
  Locked AnimaStandardV7.json (modify nodes 3/4 only)
  per-panel: backup → modify → enqueue → poll → image → restore
  scoring: 6-dim (absorbed aesthetic-judge)
  retry: 1× if < 7.0
  produces: 04_outputs/01_panels/scene_NN.png + manifest

Stage 3 (~10 min for 24 panels)
  Per-panel: view_image + 6-dim scoring
  redo: Stage 2 --panel N ×1 if <7.0
  produces: 04_review.md + redo_list.json

Stage 4 (~5min per 5-sec video × 24 scenes)
  Locked ltx23AllInOneWorkflowForRTX_v44.json
  per-scene: 5 white-listed nodes (121/593/149/1792/1793)
  audio: LTX auto VAE (no audio upload)
  produces: 02_micro_motion/scene_NN.mp4 per scene

Stage 5 (~5 min)
  ffmpeg-pipeline skill: concat + SRT auto-gen + optional burn-in
  produces: 05_final/final.mp4

Vault writes per stage (via on-write-sync-vault.sh hook).
```

**Total**: 3-8 hours depending on panel count + VRAM, all unattended after `init`.

---

## Obsidian Sync — how to read what got written

Every Stage completion + every `SPEC.md`/`plugin.json`/`marketplace.json` write pushes one file to:

```
$OBSIDIAN_VAULT_PATH/00-Inbox/processed/decision-<YYYY-MM-DD>-<event>.md
```

For example:

```
decision-2026-07-30-comfyui-chenxin-p0.1.md     # Phase 1 commit
decision-2026-07-30-comfyui-chenxin-p0.2.md     # Phase 2 commit
decision-2026-07-30-manga-stage-1-lora.md       # Each stage completion
knowledge-2026-07-30-ninghongye-lora-verified.md
stages-stage-2-panels-yongjie-2026-07-30.md
```

To grep them:

```bash
ls $OBSIDIAN_VAULT_PATH/00-Inbox/processed/ | tail -20     # recent
grep -l 'lora_verified: true' $OBSIDIAN_VAULT_PATH/00-Inbox/processed/*.md   # find lora approvals
```

To disable vault sync: `OBSIDIAN_VAULT_PATH=/dev/null`.

---

## Where to find help when stuck

| Symptom | Read first |
|---|---|
| "ComfyUI service unreachable" | [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) — section "Symptom: `bash scripts/obsidian-sync.sh` exits 0 but writes nothing" / "ComfyUI workflow fails with VRAM exceeded" |
| "Where do I get the recipes from?" | `skills/prompt-forge/recipes/MODELS.md` — 80 entries with YAML frontmatter |
| "How do the workflow stages hang together?" | `skills/manga-orchestrator/SKILL.md` — the 6-stage flowchart |
| "Why was the architecture decided that way?" | [`docs/vault-bridge/decision-v1-close.md`](vault-bridge/decision-v1-close.md) — full 8-phase close-out notes |
| "What changed in the latest release?" | `CHANGELOG.md` |
