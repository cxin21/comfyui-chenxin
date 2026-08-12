# Recipe — wuxia ink-wash

> Pre-composed aesthetic profile for martial arts / ancient China / swordplay /
> mountain-and-mist. Pull this when the user says "wuxia", "武侠", "江湖",
> "古风", "swordplay", "水墨", "ink wash", "sword saint", "swordsman on mountain".

## Recipe signature

**Cite**: `recipes/wuxia-ink.md`

## Five-layer composition

### Composition (from `composition.md`)
- framing: `long shot` *or* `wide shot` (mountain scale)
- angle: `from below` (looking up at hero on cliff) *or* `low angle`
- layout: `negative space` (mountains, mist) *or* `leading lines` (river)

### Lighting (from `lighting.md`)
- quality: `cinematic lighting` *or* `volumetric lighting` (mist backlit)
- direction: `backlighting` (mountain silhouette) *or* `side lighting`
- source: `moonlight` (night swordplay) *or* `dappled sunlight` (forest)
- special: `partially shadowed` (hero half-lit), `chiaroscuro`

### Palette (from `palette.md`)
- named palette: `muted color` (ink-wash default)
- grade: `low contrast` (soft ink)
- temperature: cool-leaning (ink is grey-blue by default)
- **never** stack `vivid color`, `cyberpunk`, `pastel color`

### Camera (from `camera.md`)
- render medium: `traditional media` (mandatory — ink wash look)
- optical: plain (no depth-of-field tricks — flat illustration)
- film signature: none

### Mood / texture (from `mood-texture.md`)
- mood: `epic` *or* `melancholic` *or* `mysterious`
- atmosphere: `fog` / `misty` (mandatory — wuxia reads as misty mountain)
- particles: `sakura petals` (when cherry season) *or* `leaves` (autumn)
- surface: `matte` (no glossy, no wet)

## Genre signature (mandatory)

From `style-signatures.md#genre:wuxia_ink`:

```text
traditional media, ink wash, watercolor, atmospheric, partially shadowed, dramatic lighting
```

## Forbidden (from `anti-patterns.md`)

- `cyberpunk`, `vivid color`, `pastel color`, `high contrast` (section D)
- `neon lights`, `lens flare`, `bloom` (section D — modern lighting cues)
- `rain`, `wet` surface (contradicts ink wash — section D)
- `photo (medium)`, `digital media`, `35mm` (section D)
- `bokeh`, `depth of field` (contradicts flat ink look — section D)
- `masterpiece`, `8k`, `trending on artstation` (sections A/C)

## Worked example

**User request**: "武侠风的剑客站在山顶，雾气弥漫，月光从云层后透出，水墨画风格"

Authored fact ledger (excerpt):

```text
f_subject | subject_1 | appearance | swordsman in flowing robe, long hair, sword on back
f_env | subject_1 | environment | mountain peak, swirling mist, moon in clouds
f_comp | subject_1 | composition | long shot, from below, negative space
f_light | subject_1 | lighting | cinematic lighting, volumetric lighting, backlighting, moonlight
f_palette | subject_1 | palette | muted color, low contrast
f_camera | subject_1 | camera | traditional media, ink wash, watercolor
f_mood | subject_1 | mood | epic, mysterious
f_atmos | subject_1 | atmosphere | fog, misty, partially shadowed
```

Rendered:

```text
score_9, score_8, 1man, solo, swordsman, flowing robe, long hair, sword,
mountain peak, mist, moon,
long shot, from below, negative space,
cinematic lighting, volumetric lighting, backlighting, moonlight,
muted color, low contrast,
traditional media, ink wash, watercolor,
epic, mysterious, fog, misty, partially shadowed
```