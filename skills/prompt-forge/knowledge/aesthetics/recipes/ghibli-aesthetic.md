# Recipe — Ghibli aesthetic

> Pre-composed aesthetic profile for gentle / nature / flying / magical-childhood.
> Pull this when the user says "Ghibli", "Studio Ghibli", "宫崎骏",
> "吉卜力", "totoro aesthetic", "spiral", "flying girl", "gentle magic",
> "child protagonist".

## Recipe signature

**Cite**: `recipes/ghibli-aesthetic.md`

## Five-layer composition

### Composition (from `composition.md`)
- framing: `long shot` *or* `wide shot` (nature scale)
- angle: `from side` (profile flight, walking) *or* `low angle` (looking up at sky)
- layout: `depth of field` *or* `leading lines` (clouds, river)

### Lighting (from `lighting.md`)
- quality: `soft lighting` *or* `cinematic lighting`
- direction: `backlighting` (sun behind character, halo)
- source: `dappled sunlight` (forest) *or* `golden hour` (summer evening)
- special: `volumetric lighting` (clouds, mist)

### Palette (from `palette.md`)
- named palette: `pastel color` (mandatory)
- grade: `vivid color` *or* `muted color`
- temperature: `warm color` (sunny) *or* mix with `cool color` (sky)
- **never** stack `monochrome`, `cyberpunk`, `noir`, `high contrast`

### Camera (from `camera.md`)
- render medium: `traditional media` *or* `watercolor` (watercolor edges)
- optical: `depth of field` *or* plain
- film signature: none — clean illustration look

### Mood / texture (from `mood-texture.md`)
- mood: `serene` *or* `nostalgic` *or* `ethereal`
- atmosphere: `light particles` (mandatory — magic dust, fireflies, spirit)
- particles: `sakura petals` (spring) *or* `leaves` (autumn)

## Genre signature (mandatory)

From `style-signatures.md#genre:pastel_ghibli`:

```text
pastel color, soft lighting, atmospheric, beautiful detailed eyes, light particles, sakura petals
```

## Forbidden (from `anti-patterns.md`)

- `monochrome`, `cyberpunk`, `noir`, `high contrast` (section D)
- `dramatic lighting`, `hard lighting`, `chiaroscuro` (section D)
- `rain`, `smoke`, `embers`, `dust` (wrong atmosphere — section D)
- `painting` alongside `watercolor` *or* `traditional media` (section D)
- `masterpiece`, `8k`, `trending on artstation` (sections A/C)
- any `award-winning`, `professional photography` (sections A/C)

## Worked example

**User request**: "宫崎骏风格的少女站在草坡上，看着远方的天空，云层里有光斑，花瓣飘落"

Authored fact ledger (excerpt):

```text
f_subject | subject_1 | appearance | young girl in simple summer dress
f_env | subject_1 | environment | grassy hilltop, sky with clouds, sakura petals
f_comp | subject_1 | composition | long shot, from side, depth of field
f_light | subject_1 | lighting | soft lighting, backlighting, dappled sunlight
f_palette | subject_1 | palette | pastel color, vivid color, warm color
f_camera | subject_1 | camera | traditional media, watercolor, depth of field
f_mood | subject_1 | mood | serene, nostalgic
f_atmos | subject_1 | atmosphere | light particles, sakura petals
```

Rendered:

```text
score_9, score_8, 1girl, solo, summer dress, young,
grassy hilltop, sky, clouds,
long shot, from side, depth of field,
soft lighting, backlighting, dappled sunlight,
pastel color, vivid color, warm color,
traditional media, watercolor,
serene, nostalgic, light particles, sakura petals
```