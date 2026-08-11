---
name: prompt-forge
description: |
  INVOKE THIS SKILL BEFORE hand-crafting any image or video prompt.
  Even a one-line user brief ("写个 Anima 的旗袍提示词") MUST go through
  compile(spec, dialect_id); you may summarize or trim the returned
  PromptPackage for the user, but the validator MUST run. Skip ONLY when
  the user explicitly says "no skill, raw text only" / "no validation" /
  "just write the prompt, don't run anything".

  LLM-first prompt authoring + renderability audit for image AND video
  models. The LLM authors typed concept objects (Subject with
  identity / appearance / pose / gesture / expression / gaze /
  micro_action / costume / props; Costume with garment / material /
  color / condition / fit / details; Prop with item / material /
  condition / details; Environment with place / spatial / immediate
  surroundings / ambient / atmosphere; Atmosphere with haze /
  particles_foreground / midground / background / wind / sky;
  Lighting with key / fill / rim / practical / quality /
  shadow_density / contrast; Frame with shot / camera_height /
  camera_angle / lens / depth_of_field / composition / foreground /
  midground / background / aspect_ratio / quality) into a
  Specification. Each dialect projector composes those concepts into
  dialect-appropriate prose at the renderer's natural detail density:
  Flux / Krea-2 / Qwen-Image get 200+ word rich paragraphs; Anima /
  SDXL / SD-1.5 / tag-trained models get richer Danbooru tag forms;
  video dialects (Wan / Kling / Sora / Seedance / Veo / LTX /
  MiniMax H3 / etc.) get explicit motion beats + temporal markers.

  Five validation propositions (P1 visibility, P2 causality, P3
  continuity with role-anchored tokens, P4 completeness, P5 density)
  gate the output. Use this skill when the goal is a renderable
  prompt for an image or video model, including photography-rich
  briefs, literal-text rendering (ideogram / qwen_image / krea_2),
  multi-frame video with persistence locks, multi-shot cinematic
  video (Seedance-style), and 31 canonical dialects spanning flux /
  anima / qwen_image / sdxl / wan / sora / veo / seedance / kling /
  minimax_h3 / runway / luma / vidu / pika / svd / pixverse /
  gemini_omni_flash.

  Methodology baked in (do not bypass): tiered anchor system,
  prompt-structure ordering, CLIP weight syntax `(word:1.3)` and
  BREAK tokens, model-specific negative selection, per-dialect
  CFG/sampling, Higgsfield shot-structure opener for video dialects,
  temporal markers `0-3s: ... 3-6s: ...`, VFX brackets `[VFX: ...]`,
  slow-motion markers `RAMPS TO SLOW MOTION`, lip-sync
  `Character says: \"...\"`, reference-image bracket
  `[reference_image: ...]` with `[identity_lock]`, camera motion
  vocabulary (zoom / pan / Ken Burns / dolly / tilt / arc / crane),
  negation patterns ("no cuts", "no zoom"), realism enforcement
  phrase ("no 3D, no cartoon, no VFX aesthetic"), and 5-point
  pre-submission heuristic.
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
- Author multi-shot cinematic video (Seedance-style) with temporal
  markers, VFX brackets, and lip-sync.

Do NOT use this skill for:

- ComfyUI installation, node errors, model downloads (use comfyui-chenxin-mcp).
- Sampling parameter tuning (cfg, steps, scheduler) — see the
  per-dialect CFG/sampling table below for guidance, but actual
  values are set in `RunConfig.sampling` at run-time.
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

## Scope

The skill is a structural renderability tool. It processes whatever
concept objects the caller supplies and produces a renderable prompt in
the target dialect's natural form. Content scope (subject matter,
maturity level) is the caller's decision; this skill does not restrict
it. The five validation gates (P1-P5) verify renderability, not
morality.

## Three invariants

- **Visibility** (P1): every Subject has an identity; every concept
  field is drawable.
- **Causality** (P2): every Transition has trigger + action + result.
- **Continuity** (P3): timeline is contiguous; every must_contain token of
  every constraint appears in every result state. When a constraint
  has `anchor_role`, tokens are checked only inside that concept's
  rendered text, not anywhere in the spec.

These three properties are derived from first principles, not from a
word list. See docs/theory.md for the rationale.

## Process

1. Read docs/theory.md to understand the three invariants.
2. Read docs/specification.md for the concept-object shapes.
3. Choose a dialect from docs/dialects.md (or the table below).
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

---

# Prompt authoring methodology

The methodology below is the engine's recommended authoring practice
distilled from FLUX / SDXL / Anima / Wan / Seedance / MiniMax H3
production data. The validation gates (P1-P5) below run on the
LLM-authored Specification, but the textual choices you make when
filling in Style.directives / Lighting.key / Frame.composition /
etc. directly determine render quality.

## Tiered anchor system

Three tiers of quality-critical tokens. Tier-1 is model-agnostic;
tier-2/3 are model-conditional.

### Tier-1 — confidence high, always include when relevant

**Lighting (most impactful single dimension):**

- `volumetric mist drifting through mountain peaks, ethereal cool
   light from above, warm rim light on the cultivator`
- `golden hour warm sidelight catching silk robes, deep shadows in
   pine forest`
- `cold blue moonlight cutting through bamboo grove, frost
   crystals in air`
- `chiaroscuro dramatic lighting, single key light from upper right,
   deep black background`
- `candlelight warm 2200K from screen-left, soft fill bouncing off
   skin, cool night ambient`
- `overcast diffuse softbox-style lighting, no harsh shadows, even
   skin tones`

**Composition:**

- `wide shot, three-quarter from below, low angle emphasizing the
   figure's power`
- `extreme long shot, tiny figure on cliff edge against vast
   landscape`
- `medium close-up, shallow depth of field, f/1.4 bokeh on
   background`
- `rule-of-thirds placement, character on left power point`

**Cultural / domain vocabulary** (swap per domain — keep ONE family):

- Chinese: `flowing silk hanfu, jade pendant, long sword with cyan
   glow, mountain immortal-cultivation hall, qi aura, thousand-year
   pine`
- Modern: `linen blazer, matte gold watch, glass-walled office, soft
   window light`
- Fantasy: `runic armor, glowing staff, ancient library, dust motes
   in light shafts`
- Cinematic noir: `trench coat, fedora, rain-slick cobblestone,
   venetian blind shadows`

**Medium anchor (commit to ONE):**

- `digital painting in the style of Chinese ink wash with rich color
   overlayer`
- `oil painting, classical fantasy realism, Caravaggio-influenced
   lighting`
- `cinematic film still, anamorphic lens, Arri Alexa LF`
- `photorealistic, RAW photo, Kodak Portra 400, natural skin`

### Tier-2 — model-conditional (only add what the dialect honors)

**FLUX / SDXL / Qwen-Image / Krea-2 / Midjourney v6+ (natural-prose):**

- Pick ONE: `physically-based atmospheric scattering` OR `volumetric
   god rays` (not both)
- `cinematic depth of field, shallow focus on eyes`
- `ARRI Signature Prime 75mm lens equivalent`
- Anchor with one: `photographed on Hasselblad medium format` OR
   `unreal engine 5 lighting` (not both)

**SD 1.5 / Pony / older tag-trained checkpoints:**

- Lead with: `masterpiece, best quality, absurdres, highres`
- Tag stacking still works, but use model-appropriate tags
- Specify: `1girl, long black hair, jade eyes, cold expression, dark
   black flowing robe, intricate embroidery, holding long sword`

**Anima (Qwen3 DiT) — Chinese-fantasy specialist:**

- Natural language prompts (like FLUX)
- Trigger words from LoRA training (e.g. `shenyuan`, `waner`); pair with
   style LoRA at node 26 for scene atmosphere
- Strong on cultural-specific vocabulary

### Tier-3 — DISCARD, these actively hurt

❌ `masterpiece, best quality, ultra-detailed, 8k, HDR, cinematic
lighting, sharp focus` (stacked)
❌ `trending on artstation` (outdated, weak on FLUX/SDXL)
❌ Mega-negative lists on FLUX/SDXL
❌ Tag soup on FLUX (model wants natural prose)
❌ `highly detailed, intricate, complex, stunning, beautiful,
masterpiece` without specific substance

## Prompt structure — recommended order

For natural-prose dialects (Flux / SDXL / Anima / Wan / MiniMax H3 /
Seedance), follow this order. Tag-form dialects (SD 1.5 / Pony) only
honor tags not order — skip this section.

1. **Quality anchor** (ONE only): `cinematic photography,
   photorealistic, 8k uhd` (commit to one and stop)
2. **Subject + identity**: `a young Chinese swordsman with long
   black hair`
3. **Subject details**: `cold piercing eyes, sharp eyebrows, dark
   black flowing robe`
4. **Cultural / domain anchors**: `holding ancient long sword with
   cyan glow, jade pendant`
5. **Action / pose**: `standing alone on snow cliff peak, wind
   blowing hair`
6. **Environment**: `eternal snowstorm, vast misty mountain range
   below`
7. **Lighting**: `dramatic cinematic lighting, volumetric mist,
   cool moonlight`
8. **Composition**: `wide shot, low angle, rule-of-thirds placement`
9. **Medium / style**: `cinematic film still, ARRI Alexa, Kodak
   Portra 400`
10. **Technical**: `sharp focus, depth of field, 8k uhd`

Each Specification field maps to one of these slots:
- `Subject.identity / appearance / age` -> 2, 3
- `Subject.costume[*].*` -> 4 (cultural anchor)
- `Subject.props[*].*` -> 4 (cultural anchor)
- `Subject.pose / gesture / expression / gaze / micro_action` -> 5
- `Environment.*` + `Atmosphere.*` -> 6
- `Lighting.*` -> 7
- `Frame.*` -> 8
- `Style.medium / rendering / art_movement / texture / palette /
   mood / directives` -> 9, 10

## CLIP weight syntax

For tag-form and many video dialects, the projector preserves CLIP
emphasis. Use sparingly — over-weighting degrades coherence.

| Syntax                | Effect              | Range   |
|-----------------------|---------------------|---------|
| `(word:1.3)`          | +30% emphasis       | 0.5–1.5 |
| `(word:0.7)`          | -30% de-emphasis    | 0.5–1.5 |
| `((word))`            | moderate (1.21x)     | —       |
| `(((word)))`          | strong (1.33x)      | —       |
| `[word]`              | slight (0.91x)      | —       |

Recommended emphasis for cinematic output:
- `(cinematic lighting:1.2)` — mood
- `(volumetric mist:1.3)` — atmosphere
- `(silk robe embroidery:1.2)` — detail
- `(sharp facial features:1.1)` — keep moderate

## BREAK tokens (CLIP 77-token chunking)

CLIP processes prompts in 77-token chunks. For long prompts, insert
`BREAK` to reset attention:

```
a young swordsman in flowing black silk robes standing on a snow
cliff peak
BREAK
cinematic composition, depth of field, f/1.4 bokeh, sharp focus on
character, masterpiece, best quality, photorealistic, 8k uhd
```

Place BREAK between logically distinct sections (subject / lighting /
composition), not inside a noun phrase.

## Negative prompt selection by dialect

The engine's `Specification.negative` field (tuple[str, ...]) is
emitted into the model's negative slot for tag-form dialects. For
natural-prose dialects, the engine emits empty negative by default —
**the model's native negative concept is usually weak or absent**, so
mega-negatives dilute the prompt. Match negatives to actual failure
modes you have observed.

| Dialect                    | Recommended negative                          |
|----------------------------|------------------------------------------------|
| Flux / Krea-2 / Qwen-Image | `blurry, low quality, distorted` (minimal)     |
| SDXL / Midjourney          | Same minimal — add `text, watermark, signature` |
| Anima                      | `blurry, distorted, low quality, deformed hands, extra fingers, mutated face, text, watermark, multiple people when only one, lowres, oversaturated` |
| SD 1.5 / Pony / Anima tag-form | Full: `(worst quality:1.4), (low quality:1.4), bad anatomy, bad hands, extra fingers, missing fingers, deformed, ugly, blurry, watermark, signature, text, jpeg artifacts, embedding:easynegative, embedding:badhandv4` |
| Wan / MiniMax H3 / Seedance / Kling / Sora / Veo / video dialects | Use the model's native language for motion artifacts: `static, motionless image, details are unclear, worst quality, low quality, ugly, extra fingers, deformed, distorted limbs, cluttered background` |
| MiniMax H3 (specifically) | No native negative input — express exclusions positively via `Constraint(kind="exclusion", anchor_role=...)`. |

Add to negative ONLY when failure is observed, not preemptively:
- Text/garbled characters -> `text, watermark, signature`
- Extra fingers -> `extra fingers, malformed hands`
- Bad faces -> `deformed, ugly, asymmetric face`

## Per-dialect CFG / sampling guidance

These values are RECOMMENDED; actual values are set in
`RunConfig.sampling` at run-time. Prompt-forge does not own the
sampler — it only owns the prompt text.

| Dialect                          | CFG   | Notes                                            |
|----------------------------------|-------|--------------------------------------------------|
| SD 1.5 / Pony                    | 7–9   | Detail-heavy negative matters                     |
| SDXL                             | 5–8   | Moderate sensitivity                            |
| Flux / Krea-2 / Qwen-Image       | **1.0 only** | NEVER higher                              |
| Anima (Qwen3)                    | 5–7   | Natural language works best                     |
| Wan 2.2 (lightning)              | 1.0   | Plus lightning LoRA                              |
| Wan 2.2 (standard)               | 3.5   | Plus ModelSamplingSD3 shift=8                    |
| MiniMax H3 (t2v / i2v-video)     | follow dialect preset | Hard-coded by camera-video skill            |
| Seedance 2.0 / Kling / Sora / Veo | follow provider default | Provider-dependent                    |

---

# Video prompt methodology

For video dialects (Wan / Kling / Sora / Veo / Seedance / MiniMax H3
/ LTX / Runway / Luma / Vidu / Pika / SVD / Pixverse /
gemini_omni_flash), the prompt must additionally describe **motion,
choreography, and audio**. The image-only methodology above is a
necessary but insufficient subset.

## Shot-structure declaration (Higgsfield canonical — applies to all
multi-shot video dialects)

**CRITICAL: open every video prompt with a shot-structure declaration
before any creative description.** This is the single biggest quality
lever for video. Pick one opener, then extend.

**Action / combat / multi-shot (highest-performing):**
```
Montage, multi-shot Hollywood action, don't use one camera angle or
single cut, cinematic lighting, photorealistic, 35mm film quality,
ARRI ALEXA aesthetic, heavy film grain, sharp but imperfect focus,
motion blur on fast actions, halation on highlights, soft highlight
rolloff, wide-angle lens with strong distortion, subtle chromatic
aberration near frame edges, no 3D, no cartoon, no VFX aesthetic.
```

**Single continuous POV:**
```
Single continuous shot, first-person POV perspective, the camera IS
[his/her] eyes, hyper-chaotic handheld motion, completely unstabilized,
violent raw human movement, constant micro-jitters, aggressive head
swings, abrupt jerks, frequent over-rotation, no smoothness at all,
no cuts, no zoom, 35mm film, photorealistic.
```

**Locked POV reaction:**
```
One continuous shot, POV [setting] perspective, no cuts, no zoom,
natural head movement, photorealistic, 35mm film grain.
```

## Video body structure (after the opener)

1. **Environment / location** — sensory detail (wet asphalt, sodium
   lamps, neon bleed, rain particulates, volumetric haze)
2. **Character block** — with reference tags and identity-lock
   language (see Reference-to-video below)
3. **Enemy / secondary character block** — same detail level
4. **Beat-by-beat choreography** with **TEMPORAL MARKERS**:
   `0-3s: ...  3-6s: ...  6-10s: ...` (one beat per 2-3 seconds)
5. **VFX inline in brackets:** `[VFX: branching white-blue electric
   arcs pulsing along forearms, sparks jumping between fingers]`
6. **Slow-motion markers:** write `RAMPS TO SLOW MOTION` before the
   impact beat, `SNAPS BACK TO REAL TIME` on resume
7. **Sound design block:** either `no music, only raw SFX` or
   explicit SFX sequence. Music language stays textural.

## Combat vocabulary (proven to hit for action dialects)

- `snaps forward`, `lunges`, `sprints`, `weaves`, `chambers`, `drives`,
   `pivots`, `redirects`, `ducks`, `slips`
- `explodes outward`, `devastating`, `raw force`, `kinetic`, `overload`,
   `compresses`, `erupts`, `fractures`, `ripples`
- **Avoid soft verbs**: `attacks`, `hits`, `fights` — these read
   generic and Seedance/Wan/Sora underdeliver

## Camera behavior — state what it IS and ISN'T doing

Video models misfire when camera intent is ambiguous. Always explicitly
**negate** what you don't want:

- `no cuts` (for continuous POV)
- `no zoom` (prevents unnatural perspective punch-ins)
- `no stabilization` (when you want chaotic handheld)
- `no smoothness at all`
- `no 3D, no cartoon, no VFX aesthetic` — counter-intuitive but
   forces photoreal skin/texture/lighting even when the scene has
   heavy VFX elements

## Realism enforcement phrase

When the brief has VFX but you want photoreal skin / textures (not
plastic Marvel-cartoon look), include:
```
no 3D, no cartoon, no VFX aesthetic — photorealistic textures, real
skin pores, authentic fabric detail, grounded in reality
```

## Reference-to-video (character identity)

When you have character / product / wardrobe references, use the
reference-to-video endpoint with bracket tagging:

```
[reference_image: hero_portrait.png]
[identity_lock]
The same character — bald, blue arrow tattoo, orange robes —
consistent across all shots, no drift or deformation. Do not alter
clothing category or primary color.

Shot 1 (wide, slow push-in): hero walks across the snowy Air Temple
courtyard, wind lifting robes.
Shot 2 (medium close-up): hero turns toward camera, staff in hand.
Shot 3 (extreme close-up, rack focus): hero's eyes open, wind
whipping.
```

**Identity-anchor phrases that measurably reduce face drift** (stack
them — redundancy helps):
- `the same character`
- `consistent across all shots`
- `no drift or deformation`
- `do not alter clothing category or primary color`

## Lip-sync from quoted dialogue

```
Character A stands on the cliff edge, staff raised, wind in cloak.
Character A says: "I won't run anymore."
Character B, half a step behind, replies: "Then we fight."
```

Use `Character says: "..."` / `Character replies: "..."` exactly —
mouth shapes key off quoted strings. Keep each line under ~6 words;
longer lines risk drift on fast clips.

## Audio cues that work

- **Ambient**: `distant thunder rolling over mountains`, `wind
   through reeds`, `crackling campfire`
- **Diegetic**: `boots crunching snow`, `staff planting on stone`,
   `wingbeats overhead`
- **Music direction** (light touch only): `low orchestral swell
   building`, `taiko drums entering on Shot 3`
- **Do not** request complex multi-instrument scores — keep music
   language textural.

## Multi-shot inside one generation

Seedance / Wan / MiniMax H3 honor explicit shot lists inside one
prompt. Format each shot:

```
Shot 1 (wide establishing, slow aerial push-in): ...
Shot 2 (medium close-up, handheld): ...
Shot 3 (extreme close-up, rack focus): ...
```

Keep subject description consistent across shots for identity
stability. The **2.5-second-per-shot rhythm** is empirically optimal
for multi-shot generations; a 15-second clip = 6 shots × 2.5s.

## Camera motion vocabulary

For all video dialects, name the camera motion explicitly:

- `dolly` (push toward or pull away from subject)
- `tilt` (camera rotates up/down on fixed axis)
- `pan` (camera rotates left/right on fixed axis)
- `arc` (camera moves in a curve around subject)
- `crane` (camera moves vertically through space)
- `Ken Burns` (zoom + pan on still image — only for image-animation
   pipelines, NOT for true video generation)
- `handheld` (deliberate micro-jitter for realism)
- `steadicam` (smooth tracking shot)

Combine freely but cap at 2-3 motions per shot — too many produces
incoherent motion.

---

# 5-point pre-submission heuristic

Before submitting any prompt, run this check. If any answer is "no",
revise before generation.

1. **Does the prompt commit to ONE medium anchor?** (digital painting /
   photo / oil / cinematic — not multiple)
2. **Does it specify lighting with direction + color temperature?**
   (not just "dramatic lighting")
3. **For natural-prose dialects: does the order follow the 10-step
   structure?** (subject -> action -> environment -> lighting ->
   composition -> medium)
4. **For video: does it include a shot-structure opener AND
   temporal markers?**
5. **For negative: does it only address observed failure modes?**
   (no mega-list on FLUX / SDXL)

---

# Templates

Six examples spanning the major dialect families. These are reference
output — your job is to author the Specification and let compile()
produce the prompt text.

### Template 1 — Cinematic portrait (FLUX / SDXL / Anima)

A cinematic portrait of a young Chinese swordsman with long black hair
and cold piercing eyes, wearing dark black flowing silk hanfu with
intricate gold embroidery, holding an ancient long sword glowing with
cyan qi energy, jade pendant around neck, soft cinematic lighting from
upper left, volumetric mist background, ethereal cool tones with warm
rim light, shallow depth of field, rule-of-thirds placement,
photorealistic, 8k uhd, ARRI Alexa LF, Kodak Portra 400.

### Template 2 — Wide landscape (FLUX / Anima)

An epic wide shot of an immortal cultivation palace floating among
mountain peaks shrouded in volumetric mist, jade architecture with
golden rooftops, ancient pine trees clinging to cliffs, immortal crane
silhouettes in the distance, dramatic golden hour lighting piercing
through cloud breaks, ethereal atmosphere, deep foreground and
background depth, Chinese ink wash overlayer with cinematic color
grading, photorealistic, 8k uhd.

### Template 3 — SD 1.5 anime (tag-trained)

masterpiece, best quality, absurdres, 1girl, long black hair, jade
eyes, sharp features, dark black flowing robe, intricate embroidery,
holding long sword, jade pendant, standing on snow cliff, snowstorm,
dramatic lighting, ethereal atmosphere, cinematic composition, depth
of field, sharp focus

Negative: `(worst quality:1.4), (low quality:1.4), bad anatomy, bad
hands, extra fingers, deformed, watermark, embedding:easynegative,
embedding:badhandv4`

### Template 4 — MiniMax H3 Chinese production brief

Generate a 12-second, 16:9, native stereo cinematic short film of a
weathered swordswoman in a moonlit bamboo grove. She kneels slowly on
a moss-covered stone, jade pendant catching the moonlight, ancient
sword laid across her knees. Camera dollies from wide to close-up
while wind stirs the bamboo leaves around her. Sound: bamboo
rustling, distant temple bell, gentle wind ambience.

### Template 5 — Seedance multi-shot action

Montage, multi-shot Hollywood action, don't use one camera angle or
single cut, cinematic lighting, photorealistic, 35mm film quality,
ARRI ALEXA aesthetic, heavy film grain, no 3D, no cartoon, no VFX
aesthetic.

0-3s: hero in dark alley, neon reflections on wet asphalt, two
enemies flanking.
3-6s: hero lunges forward, snaps forward through the gap, RAMPS TO
SLOW MOTION on the impact beat.
6-9s: SNAPS BACK TO REAL TIME, hero pivots, redirecting the blade.
[VFX: branching white-blue electric arcs pulsing along blade, sparks
jumping between fingers]
9-12s: hero lands, low angle hero shot, dust settling, breathing
visible in cold air.

Sound: no music, only raw SFX — boots on wet asphalt, blade cutting
air, impact thud, wind.

### Template 6 — Wan video (single continuous POV)

Single continuous shot, first-person POV perspective, the camera IS
the swordsman's eyes, hyper-chaotic handheld motion, completely
unstabilized, violent raw human movement, no cuts, no zoom, no
smoothness at all, no 3D, no cartoon, no VFX aesthetic,
photorealistic, 35mm film grain.

0-5s: running through dense forest, branches whipping past face.
5-10s: vaulting over a fallen log, ground rushing up.
10-15s: bursting through undergrowth into an open cliffside, wind
hitting face, sudden stillness.

Sound: heavy breathing, branches snapping, wind roar, sudden
silence at the cliff edge.

---

# Spec shape (v3 concept objects)

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

# Persistence locks via evidence

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

# Concept objects

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

## Fast channel for tag-form dialects

For Anima / SDXL / SD-1.5 / gpt_image / nano_banana / hidream_i1 /
ideogram / recraft / grok_image / ernie_image, `compile(spec, dialect_id)`
returns a comma-joined Danbooru-style tag string (typically < 300
characters) in `package.prompt`, plus a comma-joined negative in
`package.negative`. This is already the renderable form for these
models — no further summarization or rewriting needed. Do not refuse
to invoke compile on the grounds that "the result will be too long";
the result for these dialects is short by design.

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