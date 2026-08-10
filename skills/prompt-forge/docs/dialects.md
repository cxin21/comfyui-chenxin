# Dialect selector

Each model is a projection from Specification to model-input text.
The projection chooses ordering, form, and what to drop.

Lookup is by exact id or alias (case-insensitive).
Aliases are listed in `registry/dialects.json`.

## Consolidation policy

We do **not** expose every version variant as a separate canonical entry.
Version variants of the same model family are aliases of a single
canonical entry because their prompt form is identical.

Aliases that resolve to a different projection (because the model is
genuinely different in prompt language, e.g. flux_1_kontext is an
edit-only model while flux is a generation model) get their own
canonical entry.

Currently: **31 canonical dialects, 44 aliases.**

## Image dialects (15 canonical)

| Canonical | Form | Render strategy | Aliases |
|---|---|---|---|
| flux | natural prose | rich 200-450 word paragraph from concept renderers | flux_kontext (gen only) |
| flux_1_kontext | edit instruction | edit task with preservation list | — |
| anima | Danbooru tags | every concept field rendered as underscore-joined tag | miaomiao_harem, nano_banana_2/2_lite/pro |
| qwen_image | structured NL | task-framed "Generate an image of ..." + concept blocks | qwen |
| qwen_image_edit | structured edit | edit task + change + preserve | — |
| sdxl | hybrid prose | rich prose composition, supports negative | stable_diffusion_xl |
| sd_1_5 | weighted tags | tag form with concept-per-field rendering | sd15, stable_diffusion_1_5 |
| gpt_image | rich prose | prose composition with concept renderers | gpt_image_1, gpt_image_2 |
| krea_2 | ultra-detailed NL | one sentence per concept field | krea_1 |
| hidream_i1 | subject-first NL | reuses flux composition | — |
| nano_banana | rich prose | reuses gpt_image composition | (see anima row) |
| ideogram | typography-aware | leads with literal text framing | ideogram_2, ideogram_3 |
| recraft | design brief | reuses gpt_image composition | — |
| grok_image | 5-part visual brief | reuses gpt_image composition | — |
| ernie_image | instruction + spec | reuses gpt_image composition | — |

## Video dialects (16 canonical)

| Canonical | Form | Render strategy | Aliases |
|---|---|---|---|
| wan | cinematic shot | shot header + per-transition motion beats + environment + lighting + style | wan, wan_2/5/6, wan_2_1_2_2, wan_2_2 |
| ltx | shot sequence | opening frame + transitions + camera + lighting | ltx, ltx_2, ltx_2_pro |
| kling | subject + motion | subjects + action beats + environment + lighting + frame + ending | kling, kling_ai |
| sora | storyboard | subjects + environment + shot + per-transition beats | sora, sora_2, sora_2_pro |
| veo | cinematic sequence | shot header + subjects + environment + lighting + per-transition beats | veo_2, veo_3, veo_3_3_1 |
| seedance | directed beats | shot header + subjects + environment + action beats + lens + lighting + style | seedance_1, seedance_2, seedance_1_0_and_2_0 |
| hunyuan | detailed motion | subjects + environment + per-transition actions + shot + style | hunyuan, hunyuan_video_1_5 |
| minimax_h3 | Chinese brief | seven-section Chinese production brief | — |
| hailuo | subject + action + place + camera | subjects + per-transition actions + environment + camera + style | hailuo, minimax |
| runway | content + motion | subjects + per-transition actions + environment + style | gen_3, gen_4, runway_gen_4_gen_4_5 |
| luma | subject + action + place | subjects + per-transition actions + environment + style | luma, ray_2, luma_ray_2_ray_3 |
| vidu | subject + camera + ending | subjects + shot + per-transition beats + style | — |
| pika | subject + motion + effect | subjects + per-transition actions + shot + style | — |
| svd | image-conditioned | subjects + per-transition actions + style | — |
| pixverse | structured motion | subjects + per-transition actions + shot + environment + style | — |
| gemini_omni_flash | structured brief | goal + environment + per-transition beats + continuity + style | — |

## Choosing a dialect

1. Decide modality (image vs video).
2. Decide form (natural prose vs tag form vs Chinese brief vs edit instruction).
3. Pick the dialect from the matching column.
4. If unsure, start with flux (image) or wan (video).

## Known traps

- flux does not read negative prompts; express exclusions positively.
- anima tags are validated against a curated lexicon in the
  consuming skill (legacy constraint); novel tags may be rejected.
- minimax_h3 must declare flow (drama/action/storyboard) explicitly.
  No native negative; express exclusions via constraints.
- kling ignores negative prompts in some variants.
- sora performs best with explicit shot beats, not just one paragraph.
- svd is image-conditioned: spec.references must include the source
  frame.
- flux_1_kontext and qwen_image_edit are edit-only models; supply
  source via spec.references and describe what to change, not the
  full scene.