# Recipe — Helmut Newton black-and-white

> Pre-composed aesthetic profile for sophisticated / provocative / high-fashion /
> monochrome noir-portrait. Pull this when the user says "Helmut Newton",
> "fashion noir", "high fashion portrait", "provocative fashion",
> "黑白时尚".

## Recipe signature

**Cite**: `recipes/helmut-newton-bw.md`

## Five-layer composition

### Composition (from `composition.md`)
- framing: `full body` *or* `medium shot`
- angle: `low angle` (empowering subject) *or* `from side` (architectural)
- layout: `rule of thirds` *or* `negative space`

### Lighting (from `lighting.md`)
- quality: `hard lighting` (Newton's signature) *or* `dramatic lighting`
- direction: `side lighting` *or* `rim light`
- source: `studio lighting`
- special: `chiaroscuro`, `partially shadowed`

### Palette (from `palette.md`)
- named grade: `monochrome` (mandatory) *or* `black and white`
- grade modifier: `high contrast` (Newton uses pushed blacks)
- **never** stack `pastel color`, `vivid color`, `sepia`

### Camera (from `camera.md`)
- render medium: `photo (medium)` (mandatory)
- optical: `shallow depth of field`, `bokeh`
- film signature: `35mm` (Newton's signature film look)

### Mood / texture (from `mood-texture.md`)
- mood: `dramatic` (fashion intensity)
- atmosphere: clean studio, no weather
- surface: `polished` (skin, fabric)

## Genre signature (mandatory)

From `style-signatures.md#genre:helmut_newton_bw`:

```text
monochrome, high contrast, dramatic lighting, side lighting, fashion, depth of field
```

## Forbidden (from `anti-patterns.md`)

- `pastel color`, `vivid color`, `sepia`, `warm color` (section D)
- `soft lighting` (section D — Newton is hard-light)
- `cute`, `kawaii`, `chibi` — Newton is not cute
- `painting`, `illustration`, `watercolor` (Newton is photographic — section D)
- `masterpiece`, `trending on artstation` (sections A/C)

## Worked example

**User request**: "Helmut Newton 风格的黑白时尚人像，模特穿着晚礼服，城市夜景背景"

Authored fact ledger (excerpt):

```text
f_subject | subject_1 | appearance | tall female model in backless evening gown
f_env | subject_1 | environment | city skyline at night, hotel terrace
f_comp | subject_1 | composition | full body, low angle, rule of thirds
f_light | subject_1 | lighting | hard lighting, side lighting, chiaroscuro, studio lighting
f_palette | subject_1 | palette | monochrome, high contrast, black and white
f_camera | subject_1 | camera | photo (medium), shallow depth of field, bokeh, 35mm
f_mood | subject_1 | mood | dramatic
```

Rendered:

```text
score_9, score_8, 1girl, solo, tall, evening gown, backless, model,
city skyline, night, hotel terrace,
full body, low angle, rule of thirds,
hard lighting, side lighting, chiaroscuro,
monochrome, high contrast, black and white,
photo (medium), shallow depth of field, bokeh, 35mm,
dramatic
```