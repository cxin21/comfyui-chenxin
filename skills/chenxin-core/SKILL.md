---
name: chenxin-core
description: |
  Use this skill whenever a ComfyUI / generative-model request comes in for
  Claude Code. Trigger on ANY of: "comfyui", "comfy ui", "workflow", "出图",
  "跑工作流", "生成图片", "生成视频", "出视频", "manga", "漫画", "anime",
  "anima", "wan", "ltx", "ltx-2.3", "hunyuan", "flux", "sdxl", "sd 1.5",
  "sd1.5", "stable diffusion", "krea", "seedream", "nano banana",
  "Qwen-Image", "ideogram", "Recraft", "Kling", "Seedance", "Veo", "Sora",
  "Runway", "Luma", "Stable Audio", "ACE-Step", "video", "talking head",
  "inpaint", "upscale", "controlnet", "IP-Adapter", "refiner", "LoRA",
  "8 GB VRAM", "8GB", "small VRAM", "low VRAM", "vae", "unload model".
  This is the L4 mega-skill — it owns the dispatch table from a single Claude
  Code entry point to L1 (ComfyUI runtime), L2 (MCP driver), L3 (knowledge
  substrate: 80 recipes + 662 templates + 8 GB hardware matrix), and L5
  (application skills, future P1.1). For ANY generative-model prompt, read
  this skill first to find the right tool, recipe, and VRAM-safe defaults
  before writing the prompt or invoking a workflow.
---

# chenxin-core — L4 mega-skill

This skill is the **single entry point** for any ComfyUI / generative-model
work in Claude Code. It owns the routing from a user request to the right
combination of L1 / L2 / L3 / L5 tool, recipe, and hardware defaults.

It exists because P0.1 + P0.2 gave us the pieces (recipes, templates,
hardware matrix, MCP tools) but no single place to dispatch from. Without L4
the rest is dormant content.

## What L4 does

1. **Routes keywords → tools.** "出动漫角色" is NOT a single command —
   it's a recipe lookup + a VRAM decision + a workflow selection + a
   generation call. L4 owns this composition.
2. **Enforces the auto-pull rule.** When a specific model is named in the
   request, L4 reads its recipe dialect (via `internals/recipe_lookup.py`)
   BEFORE the prompt is written — never after.
3. **Overlays recipe overrides on hardware defaults.** `internals/hardware_decide.py`
   layers recipe-level `quant` / `steps` / `cfg` / `scheduler` on top of the
   P0.2 hardware matrix.
4. **Prefer Chinese-first naming, English-fallback search.** When the user
   writes "动漫" or "漫画", prefer Chinese-canon model families first
   (Anima, Wan, LTX-2.3, Hunyuan); fall back to Western canon (FLUX, SDXL)
   only if the user signals it explicitly.

## When to invoke this skill

Invoke chenxin-core **before** doing ANY of the following:

- Calling `mcp__comfyui-mcp__*` tools (L2)
- Writing a generation prompt for a specific named model
- Selecting a workflow template (L3 templates_index.json)
- Choosing sampler / quant / steps / cfg for a model on given VRAM
- Wiring a multi-stage pipeline (L5 / manga-orchestrator style work)

Skip chenxin-core ONLY when the user explicitly asks for "raw ComfyUI" with
no model recommendations (rare, mostly debugging sessions).

## Routing recipe

When invoked, follow this decision tree:

```
1. Identify the model family (or surface it to the user).
   - If named  →  recipe_lookup.py --model <id>  →  dialect block.
   - If ambiguous  →  prompt the user with 2-3 candidates from the
     recipe index (image / video / audio / utility buckets).

2. Identify the VRAM budget.
   - hardware/8gb.json (the only profile shipped today)
   - OR ask the user if they know their VRAM.

3. Call hardware_decide.py --vram <N> --model <id>.
   - It returns: quant, swap_blocks, sampler_defaults, blocked?,
     and any recipe overrides applied.

4. Choose a workflow template (L3 templates_index.json).
   - Filter by --use-case (txt2img, img2img, upscale, etc.) +
     --modality (image, video, audio).

5. Compose the prompt:
   - dialect block from step 1
   - VRAM-safe settings from step 3
   - any user-supplied content (subject, style, mood)

6. Invoke the right L2 tool:
   - mcp__comfyui-mcp__generate_image            (text-to-image)
   - mcp__comfyui-mcp__generate_video            (text-to-video)
   - mcp__comfyui-mcp__generate_audio            (text-to-audio)
   - mcp__comfyui-mcp__generate_with_controlnet  (controlnet-conditioned)
   - mcp__comfyui-mcp__generate_with_ip_adapter  (IP-Adapter)
   - mcp__comfyui-mcp__remove_background         (BiRefNet)
   - mcp__comfyui-mcp__upscale_image             (ESRGAN upscale)

7. For multi-stage pipelines, hand off to the L5 skill:
   - skills/manga-orchestrator/SKILL.md     (Stage 0–6 coordinator — ported in P1.1)
   - skills/manga-stage-{1..4}-*/SKILL.md   (ported in P1.1)
   - skills/ffmpeg-pipeline/SKILL.md        (Stage 5)
   - skills/lora-trainer/SKILL.md           (Stage 1 standalone)
```

## What L4 explicitly does NOT do

- **Does not invent recipes.** L4 reads from `skills/chenxin-core/recipes/MODELS.md`
  only. If a model is missing, L4 surfaces that to the user — it never
  hallucinates dialect rules.
- **Does not bypass the recipe_expert adversarial check.** When the L4
  reviewer agent runs (`agents/chenxin-reviewer.md`), it MUST consult
  recipe-expert for any new recipe addition. L4 itself never adds recipes.
- **Does not edit `recipes/MODELS.md` directly.** The chef who edits that
  file is `internals/recipe_yaml.py` (idempotent re-format only). All other
  edits happen via the recipe author workflow (P0.1 owner).

## Self-update cadence

L4 reads from L3 (`recipes/`, `templates_index.json`, `hardware/`). When the
L7 self-update script (`scripts/self-update.sh`) pulls upstream deltas from
SlavaSexton + Comfy-Org, L3 files change on disk and L4 picks them up on
the next invocation — no re-install required. The hardware matrix is the
only file that may need a manual update (no upstream).

## Adversarial review (P0.3 / future)

Every PR to L4 must pass the 5-dim review defined in `ROADMAP.md`:

1. code-reviewer           — quality, naming, < 800 lines/file
2. security-reviewer       — secrets, MCP injection, auth scope
3. aesthetic-judge         — if workflow JSON changed
4. comfyui-doctor          — if VRAM decision logic changed
5. recipe-expert           — if recipe content changed

## File map

- `SKILL.md`             — this file (entry point)
- `internals/recipe_yaml.py`      — re-format MODELS.md (idempotent)
- `internals/recipe_lookup.py`    — read recipe by id/substring → JSON
- `internals/hardware_decide.py`  — recipe-overridden VRAM recommendation
- `internals/context_graph.md`    — L1→L8 data flow map
- `recipes/MODELS.md`            — 80 recipe bodies (P0.1, edited via recipe_yaml)
- `templates_index.json`         — 662 workflow templates (P0.1)
- `hardware/8gb.json`            — 8 GB VRAM decision matrix (P0.1)

## One-paragraph first-principles answer

> Why is L4 (this mega-skill) better than letting L5 (the application) own
> the dispatch logic? Because L5 is per-app and only sees its own prompt
> context; L4 sees every ComfyUI call across every app and so is the only
> layer that can enforce the cross-cutting rules (recipe auto-pull, VRAM
> safety, model-name → dialect binding) consistently. If manga-orchestrator
> owned dispatch, an openmontage user would silently get raw prompts with
> no recipe lookup; if openmontage owned it, the manga pipeline would skip
> the recipe-expert review gate. One dispatch table, owned by L4, is
> the only way to keep the cross-cutting rules alive as the plugin grows.