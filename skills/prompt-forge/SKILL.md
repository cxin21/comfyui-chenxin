---
name: prompt-forge
description: |
  LLM-first prompt authoring and quality-audit for image and video
  models. The LLM authors typed concept objects (Subject with
  identity / appearance / pose / gesture / expression / gaze /
  micro_action / costume / props; Costume with garment / material /
  color / condition / fit / details; Prop with item / material /
  condition / details; Environment with place / spatial / immediate
  surroundings / ambient / atmosphere; Atmosphere with haze /
  particles_foreground / particles_midground / particles_background /
  wind / sky; Lighting with key / fill / rim / practical / quality /
  shadow_density / contrast; Frame with shot / camera_height /
  camera_angle / lens / depth_of_field / composition / foreground /
  midground / background / aspect_ratio / quality) into a
  Specification. Each dialect projector composes those concepts into
  dialect-appropriate prose at the renderer's natural detail density:
  Flux / Krea-2 / Qwen-Image get 200+ word rich paragraphs; Anima /
  SDXL / SD-1.5 get richer tag forms; video dialects (Wan / Kling /
  Sora / Seedance / Veo / LTX) get explicit motion beats. Five
  validation propositions (P1 visibility, P2 causality, P3 continuity
  with role-anchored tokens, P4 completeness, P5 density) gate the
  output. Use this skill when the goal is a renderable prompt for an
  image or video model, including photography-rich briefs, literal-text
  rendering (ideogram / qwen_image / krea_2), multi-frame video with
  persistence locks, and 31 canonical dialects spanning flux / anima /
  qwen_image / sdxl / wan / sora / veo / seedance / kling / minimax_h3
  / runway / luma / vidu / pika / svd / pixverse / gemini_omni_flash.
---

# Prompt Forge

## When to use

Use this skill to:

- Draft an image or video prompt against a named model dialect.
- Adapt an existing prompt between dialects (e.g. Wan -> H3 Chinese).
- Audit a prompt for renderability before submission.
- Generate a MiniMax H3 Chinese production brief.
- Enforce persistence / continuity requirements across multi-frame video,
  with role-anchored tokens that cannot drift to the wrong subject.

Do NOT use this skill for:

- ComfyUI installation, node errors, model downloads (use comfyui-chenxin-mcp).
- Sampling parameter tuning (cfg, steps, scheduler).
- Memory management, workflow JSON repair, or hardware diagnostics.

## What this skill does

The LLM authors a Specification (typed concept objects). The skill:

1. Resolves the target model dialect.
2. Composes the concept objects into model-input text via the
   dialect's own projector (each dialect owns its composition).
3. Runs five deterministic validation gates (P1-P5).
4. Returns a PromptPackage envelope ready for downstream submission.

The skill is offline, side-effect free, and never touches execution
state. Downstream tools (comfyui-chenxin-mcp, camera skills) consume
the package.

## Three invariants

- **Visibility** (P1): every Subject has an identity; every concept
  field is drawable.
- **Causality** (P2): every change has trigger + action + result.
- **Continuity** (P3): every declared constraint holds in every state.
  Tokens can be anchored to a specific concept role (subject, costume,
  prop, lighting, environment, atmosphere) so a constraint cannot
  drift to the wrong element.

These three properties are derived from first principles, not from a
word list. See docs/theory.md for the rationale.

## Process

1. Read docs/theory.md to understand the three invariants.
2. Read docs/specification.md for the concept-object shapes.
3. Choose a dialect from docs/dialects.md.
4. Author the spec; the LLM is the author.
5. Run `compile(spec, dialect_id)`; the validator runs inside.
6. Inspect `package.violations`; each carries a stable code (P1-1, P2-3, ...).
7. Iterate.

## File layout

    prompt-forge/
    +-- SKILL.md                # this file
    +-- README.md               # overview
    +-- CHANGELOG.md            # version history
    +-- internals/              # core modules (single responsibility)
    |   +-- spec.py              # concept objects: Subject, Costume, Prop,
    |   |                        # Environment, Atmosphere, Lighting, Frame,
    |   |                        # State, Style, Constraint, Transition
    |   +-- evidence.py          # four-quadrant evidence normalization
    |   +-- dialect.py           # dialect registry + lookup
    |   +-- project.py           # spec -> model text projection (31 dialects)
    |   +-- validate.py          # P1-P5 propositions
    |   +-- package.py           # PromptPackage envelope + forbidden-field guard
    |   +-- render.py            # debug renderer (concept-aware)
    |   +-- compile.py           # user-facing entry point
    +-- registry/
    |   +-- dialects.json        # 31 dialect definitions
    +-- docs/                   # theory, contracts, dialect guide, examples
    +-- .gitignore

## Quick start

```python
from internals.spec import (
    Specification, State, Style, Constraint,
    Subject, Costume, Prop, Environment, Atmosphere, Lighting, Frame,
)
from internals.compile import compile

spec = Specification(
    modality="image",
    initial_state=State(
        subjects=(
            Subject(
                identity="a weathered swordswoman",
                appearance="with a scar across her left eyebrow",
                pose="weight on her back foot",
                gesture="right hand resting on sword hilt",
                expression="weary but resolute",
                gaze="fixed on the grove edge",
                costume=(
                    Costume(
                        garment="robe",
                        material="hand-spun silk",
                        color="iron-oxide vermilion",
                        condition="worn, frayed at the hem",
                        details="embroidered phoenix at the collar",
                    ),
                ),
                props=(
                    Prop(
                        item="sword",
                        material="tarnished steel with jade-hilt pommel",
                        details="tassel of faded red silk at the guard",
                    ),
                ),
            ),
        ),
        environment=Environment(
            place="the edge of a moonlit bamboo grove",
            spatial="subject stands 6m from a stone lantern at frame right",
            immediate_surroundings=("tall bamboo pressing close on her left",),
            atmosphere=Atmosphere(
                haze="thin ground fog 0.3m tall, catching the rim light",
                particles_foreground=("drifting fireflies, four in frame",),
                wind="faint breeze from the north",
                sky="waning crescent moon",
            ),
        ),
        lighting=Lighting(
            key="moonlight from upper right, 4200K cool",
            fill="ambient bamboo-filtered, dim teal",
            rim="cold rim from behind-left, separates hair from background",
            practical=("single distant stone lantern, warm orange 2200K",),
            shadow_density="deep shadows, crushed blacks",
        ),
        frame=Frame(
            shot="medium shot",
            camera_height="eye-level, slight low",
            lens="85mm portrait, f/1.4",
            depth_of_field="shallow, focus locked on eyes",
            composition="subject on left third",
            foreground=("out-of-focus bamboo leaves, lower-left",),
            background=("bamboo grove thinning to mist",),
            aspect_ratio="3:2",
            quality=("masterpiece", "8k uhd", "sharp focus"),
        ),
    ),
    constraints=(
        Constraint(must_contain=("vermilion", "silk"), kind="identity",
                   anchor_role="costume"),
    ),
    style=Style(
        medium="cinematic photography",
        rendering="photoreal",
        art_movement="wuxia xianxia",
        palette="jade greens, charcoal blacks, single vermilion accent",
        mood="intimate, melancholic",
        directives=("matte stock", "low-key tungsten key", "shallow DOF"),
    ),
)

package = compile(spec, "flux")
print(package.prompt)
print(package.ready_for_review)  # True if no violations
```

## Negative prompts

Image specs support a `negative` field (a tuple of tags to avoid).
PromptPackage carries both `prompt` (positive) and `negative`.

- Tag-form dialects (anima, sd_1_5, sdxl, etc.) emit negative as
  comma-joined tags.
- Natural-prose dialects (flux, qwen_image, etc.) leave negative empty;
  they do not consume negative prompts.
- Video dialects (wan, kling, sora, etc.) leave negative empty when
  the model has no native negative input.
- minimax_h3 has no negative concept by design; express exclusions
  positively via Constraint(kind="exclusion", anchor_role=...).

## Supported dialects

31 dialects are registered in registry/dialects.json:

Image (15): flux, flux_1_kontext, anima, qwen_image, qwen_image_edit,
  sdxl, sd_1_5, gpt_image, krea_2, hidream_i1, nano_banana, ideogram,
  recraft, grok_image, ernie_image

Video (16): wan, ltx, kling, sora, veo, seedance, hunyuan, minimax_h3,
  minimax_hailuo, runway, luma_dream_machine, vidu, pika_2_2_2_5, svd,
  pixverse, gemini_omni_flash

Lookup is by exact id or alias (case-insensitive). Aliases are listed
in registry/dialects.json.

## Validations (P1-P5)

Five propositions gate every prompt. Codes are stable (P1-1, P2-3, ...)
and documented in docs/validation.md.

- P1 Visibility: every Subject has an identity; every concept field
  is drawable.
- P2 Causality: every Transition has trigger + action + result.
- P3 Continuity: timeline is contiguous; every must_contain token of
  every constraint appears in every result state. When a constraint
  has `anchor_role`, tokens are checked only inside that concept's
  rendered text, not anywhere in the spec.
- P4 Completeness: required dimensions are non-empty.
- P5 Density: trigger and action carry at least 2 word-tokens each.

## Spec shape (v3 concept objects)

```python
Specification(
    modality='image',                          # or 'video'
    initial_state=State(
        subjects=tuple[Subject, ...],          # who
        environment=Environment,                # where
        lighting=Lighting,                      # light
        frame=Frame,                            # how we capture
    ),
    transitions=tuple[Transition, ...],         # optional for image; required for video
    constraints=tuple[Constraint, ...],         # continuity locks (role-anchored)
    style=Style(
        medium, rendering, art_movement, texture,        # FORM
        palette, mood, camera_feel, motion_quality,       # PALETTE
        directives=tuple[str, ...],                      # v3 free-form render cues
    ),
    negative=tuple[str, ...],                            # tag-form image dialects only
    references=tuple[Reference, ...],                    # for image-to-X workflows
    h3_flow='drama',                                      # minimax_h3 only
    literal_text=tuple[str, ...],                         # ideogram / qwen_image / krea_2
    duration=15.0,                                        # video only
)
```

## Concept objects

- **Subject**: identity, appearance, age, pose, gesture, expression,
  gaze, micro_action, costume (tuple[Costume]), props (tuple[Prop])
- **Costume**: garment, material, color, condition, fit, details
- **Prop**: item, material, condition, details
- **Environment**: place, spatial, immediate_surroundings, ambient,
  atmosphere
- **Atmosphere**: haze, particles_foreground / midground / background,
  wind, sky
- **Lighting**: key, fill, rim, practical (tuple), quality,
  shadow_density, contrast
- **Frame**: shot, camera_height, camera_angle, lens, depth_of_field,
  composition, foreground / midground / background, aspect_ratio,
  quality

## Persistence locks via evidence

When the caller supplies a `CreativeEvidence` whose `locked_facts`
list is non-empty, `compile()` synthesises a `Constraint` for each
locked fact and merges them into `spec.constraints`. The locked facts
then flow through the normal P3 enforcement pipeline.

`Constraint.anchor_role` is the v3 way to make a continuity lock
stick to a specific concept. Use:
- `anchor_role="costume"` for wardrobe continuity ("red robe throughout")
- `anchor_role="prop"` for carried objects ("sword stays at her hip")
- `anchor_role="lighting"` for lighting continuity ("cold rim light")
- `anchor_role="subject"` for identity ("the same swordswoman")
- `anchor_role="environment"` for place continuity
- `anchor_role="atmosphere"` for atmospheric continuity

Without `anchor_role`, the validator checks tokens appear anywhere in
the spec (the v2 behaviour). With `anchor_role`, tokens must appear
inside that specific concept's rendered text only.