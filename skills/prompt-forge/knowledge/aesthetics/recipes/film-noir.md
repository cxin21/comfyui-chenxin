# Recipe — film noir

> Pre-composed aesthetic profile for a noir detective / crime / urban-night
> request. Pull this when the user says "noir", "detective", "mystery",
> "rain-soaked street", "crime scene", "femme fatale".

## Recipe signature

**Cite**: `recipes/film-noir.md`

## Five-layer composition

### Composition (from `composition.md`)
- framing: `medium shot` *or* `long shot`
- angle: `from side` *or* `low angle`
- layout: `leading lines` (architecture, alleys)

### Lighting (from `lighting.md`)
- quality: `dramatic lighting` (NOT `soft lighting`)
- direction: `side lighting` *or* `partially shadowed`
- source: `neon lights` (urban) *or* `moonlight` (open)
- special: `chiaroscuro` (when portrait focus)

### Palette (from `palette.md`)
- named grade: `monochrome` (default for noir) *or* `noir`
- **never** stack `pastel color`, `vivid color`, or `vibrant` with noir

### Camera (from `camera.md`)
- render medium: `photo (medium)`
- optical: `depth of field`, `bokeh`
- film signature: `film grain` *or* `35mm`

### Mood / texture (from `mood-texture.md`)
- mood: `mysterious` *or* `dramatic`
- atmosphere: `rain` + `reflections` (urban) *or* `fog` (alley)
- particles: `smoke` (cigarette, alley vent)

## Genre signature (optional)

- From `style-signatures.md#medium:noir`:
  `monochrome, high contrast, dramatic lighting, side lighting, partially shadowed`

## Forbidden (from `anti-patterns.md`)

- `pastel color` — contradicts noir (section D)
- `warm color` + `cool color` together (section D)
- `soft lighting` — contradicts `dramatic lighting` (section D)
- `trending on artstation`, `masterpiece`, `8k` (sections A/C)

## Worked example

**User request**: "孤独的私家侦探在雨夜的巷子里，抽烟，霓虹灯反光，黑色电影风"

Authored fact ledger (excerpt):

```text
f_subject | subject_1 | appearance | man in trench coat and fedora, cigarette
f_action | subject_1 | action | leaning against wall, smoking
f_env | subject_1 | environment | wet alley, neon signs, puddles
f_comp | subject_1 | composition | medium shot, low angle, leading lines
f_light | subject_1 | lighting | dramatic lighting, side lighting, neon lights, partially shadowed
f_palette | subject_1 | palette | monochrome, high contrast
f_camera | subject_1 | camera | photo (medium), depth of field, film grain
f_mood | subject_1 | mood | mysterious
f_atmos | subject_1 | atmosphere | rain, reflections, smoke
```

Rendered (segment-form, Anima order):

```text
score_9, score_8, score_7, 1man, solo, trench coat, fedora, cigarette,
leaning, smoking, alley, neon lights, rain, puddles, wet,
low angle, medium shot, leading lines,
dramatic lighting, side lighting, partially shadowed,
monochrome, high contrast,
photo (medium), depth of field, film grain,
mysterious, rain, reflections, smoke
```