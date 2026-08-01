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
