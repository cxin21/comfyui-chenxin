# Recipe — cyberpunk neon

> Pre-composed aesthetic profile for cyberpunk street / neon city / hacker /
> future dystopia. Pull this when the user says "cyberpunk", "neon city",
> "未来都市", "黑客", "赛博朋克", "rain-soaked neon street".

## Recipe signature

**Cite**: `recipes/cyberpunk-neon.md`

## Five-layer composition

### Composition (from `composition.md`)
- framing: `long shot` *or* `wide shot` (city scale)
- angle: `low angle` (skyscrapers looming) *or* `from below`
- layout: `leading lines` (street perspective, cables, signage)

### Lighting (from `lighting.md`)
- quality: `cinematic lighting` (default) *or* `dramatic lighting`
- direction: `rim light` *or* `backlighting`
- source: `neon lights` (mandatory)
- special: `lens flare`, `bloom`, `reflections` (wet surfaces)

### Palette (from `palette.md`)
- cultural palette: `cyberpunk` (mandatory as named anchor)
- grade: `dark` *or* `vibrant`
- temperature: `cool color` (dominant)
- **never** stack `pastel color` or `sepia` (contradicts cyberpunk)

### Camera (from `camera.md`)
- render medium: `photo (medium)` *or* `digital media`
- optical: `depth of field`, `bokeh` (city lights)
- film signature: `film grain` (slight)

### Mood / texture (from `mood-texture.md`)
- mood: `dramatic` *or* `mysterious`
- atmosphere: `rain` (mandatory for cyberpunk noir feel), `reflections`
- particles: `embers` *or* `light particles` (holograms, sparks)

## Genre signature (mandatory)

From `style-signatures.md#genre:cyberpunk`:

```text
cyberpunk, neon lights, rain, reflections, dark, dramatic lighting
```

## Forbidden (from `anti-patterns.md`)

- `pastel color`, `sepia`, `warm color` (section D)
- `low contrast` (section D — cyberpunk needs contrast)
- `masterpiece`, `trending on artstation`, `8k` (sections A/C)
- `painting` render medium when paired with `photo (medium)` (section D)

## Worked example

**User request**: "赛博朋克风格的女黑客在雨中霓虹街头，黑色皮夹克，远处广告牌"

Authored fact ledger (excerpt):

```text
f_subject | subject_1 | appearance | woman with short hair, black leather jacket, cybernetic visor
f_action | subject_1 | action | walking, looking over shoulder
f_env | subject_1 | environment | neon-lit street, holographic billboards, puddles
f_comp | subject_1 | composition | long shot, low angle, leading lines
f_light | subject_1 | lighting | cinematic lighting, neon lights, rim light, bloom
f_palette | subject_1 | palette | cyberpunk, dark, cool color
f_camera | subject_1 | camera | photo (medium), depth of field, bokeh, film grain
f_mood | subject_1 | mood | mysterious
f_atmos | subject_1 | atmosphere | rain, reflections, light particles
```

Rendered:

```text
score_9, score_8, 1girl, solo, short hair, black leather jacket, cybernetic visor,
walking, looking over shoulder, neon lights, billboard, puddles, wet, cyberpunk,
long shot, low angle, leading lines,
cinematic lighting, rim light, bloom, lens flare,
dark, cool color, cyberpunk,
photo (medium), depth of field, bokeh, film grain,
mysterious, rain, reflections, light particles
```