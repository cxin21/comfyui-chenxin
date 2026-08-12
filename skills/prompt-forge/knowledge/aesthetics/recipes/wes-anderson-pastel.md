# Recipe — Wes Anderson pastel

> Pre-composed aesthetic profile for symmetrical / deadpan / pastel /
> quirky-cute. Pull this when the user says "Wes Anderson", "对称构图",
> "pastel color", "deadpan", "quirky", "deadpan hotel".

## Recipe signature

**Cite**: `recipes/wes-anderson-pastel.md`

## Five-layer composition

### Composition (from `composition.md`)
- framing: `medium shot` *or* `wide shot` (group scale)
- angle: `centered` (frontal deadpan) — **not** `low angle`/`high angle`
- layout: `symmetrical` (mandatory) *or* `centered` + `rule of thirds`

### Lighting (from `lighting.md`)
- quality: `soft lighting` (mandatory) *or* `ambient light`
- direction: `front lighting` (flat, even, no drama)
- source: `studio lighting` (controlled)
- **never** use `dramatic lighting`, `chiaroscuro`, `rim light` here

### Palette (from `palette.md`)
- named palette: `pastel color` (mandatory)
- grade: `low contrast` *or* `muted color`
- **never** stack `vivid color`, `high contrast`, `cyberpunk`, `monochrome`

### Camera (from `camera.md`)
- render medium: `illustration` (mandatory — Anderson is illustrated, not photographic)
- optical: `depth of field` *or* plain (no bokeh)
- film signature: none — clean digital

### Mood / texture (from `mood-texture.md`)
- mood: `serene` *or* `cheerful` (deadpan humor)
- atmosphere: clean (no fog, smoke, rain)
- surface: `matte` (not glossy / not wet)

## Genre signature (mandatory)

From `style-signatures.md#genre:wes_anderson_pastel`:

```text
pastel color, centered, symmetrical, soft lighting, illustration
```

## Forbidden (from `anti-patterns.md`)

- `dramatic lighting`, `rim light`, `chiaroscuro` (section D)
- `high contrast`, `vivid color`, `cyberpunk` (section D)
- `monochrome`, `black and white` (section D)
- `rain`, `fog`, `smoke`, `embers` (wrong mood — section D via mood cluster)
- `painting` *or* `photo (medium)` alongside `illustration` (section D)
- `masterpiece`, `8k`, `trending on artstation` (sections A/C)

## Worked example

**User request**: "Wes Anderson 风的酒店大堂，粉彩配色，对称构图，前台员工笔直站在中央"

Authored fact ledger (excerpt):

```text
f_subject | subject_1 | appearance | hotel concierge in pink uniform, deadpan expression
f_env | subject_1 | environment | symmetrical hotel lobby, pastel pink walls, mint-green accents
f_comp | subject_1 | composition | centered, symmetrical, medium shot
f_light | subject_1 | lighting | soft lighting, front lighting, studio lighting
f_palette | subject_1 | palette | pastel color, low contrast, muted color
f_camera | subject_1 | camera | illustration, depth of field
f_mood | subject_1 | mood | cheerful, serene
```

Rendered:

```text
score_9, score_8, 1girl, solo, hotel concierge, pink uniform, deadpan,
hotel lobby, pastel, symmetrical architecture,
centered, symmetrical, medium shot,
soft lighting, front lighting, studio lighting,
pastel color, low contrast, muted color,
illustration, depth of field,
cheerful, serene
```