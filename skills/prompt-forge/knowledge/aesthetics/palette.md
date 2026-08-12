# Palette — Anima tag vocabulary

> Palette means **one coherent color decision**, not scattered color words.
> Pick **one named palette or one named grade**, then optionally a modifier.
> Mixing two named palettes (e.g. `Wes Anderson` + `cyberpunk`) is a contradiction
> the model will resolve arbitrarily — don't.

## Named grades (single decisive tag)

| term | what it produces | use when | avoid when |
|---|---|---|---|
| `monochrome` | one color value, tonal | portrait, graphic, noir | colorful narrative |
| `black and white` | greyscale, photography | documentary, classic, dramatic | modern color scenes |
| `sepia` | warm brown tones, antique | vintage, memory, old photo | modern scenes |
| `grayscale` | pure neutral grey | illustration, line-art emphasis | color photography |
| `high contrast` | pushed blacks and whites, graphic | fashion, poster, comic | soft realism |
| `low contrast` | muted range, soft | slice-of-life, pastel, fog | dramatic scene |

## Named palettes (named after a cultural/textual source)

| term | what it produces | use when | avoid when |
|---|---|---|---|
| `teal and orange color grade` | complementary split, blockbuster cinema | Hollywood, blockbuster, action | historical, pastoral |
| `pastel color` | soft desaturated tones | Wes Anderson, Ghibli, kawaii | gritty realism |
| `vivid color` / `vibrant` | saturated, energetic | pop art, festival, energetic | noir, vintage |
| `muted color` | desaturated but not monochrome | contemporary realism, indie film | high-saturation posters |
| `dark` | heavy shadows, low-key | horror, noir, threat | bright scenes |
| `noir` | black/white + high contrast + shadows | crime, thriller, period | cheerful scenes |

## Color temperature (modifiers)

| term | what it produces | use when | avoid when |
|---|---|---|---|
| `warm color` | red/orange/yellow dominance | sunset, intimacy, fire | ice, night |
| `cool color` | blue/green/cyan dominance | night, melancholy, sci-fi | firelight, romance |

## Cultural / genre palettes

| term | what it produces | use when | avoid when |
|---|---|---|---|
| `cyberpunk` | magenta/teal neon on black | sci-fi, urban night, hacker | pastoral, daytime |
| `vintage` | faded, slightly desaturated, warm | 70s/80s memory, retro | modern, futuristic |
| `retro` | older artstyle or color treatment | period nostalgia | cutting-edge contemporary |
| `washed colors` | pulled toward grey, film-bleach | indie film, 90s music video | saturated pop |

## Co-use rules

- **One named palette + at most one temperature modifier**. Don't stack `warm color` + `cool color` + `noir` + `pastel`.
- `monochrome` is exclusive of all named palettes.
- Palette is independent of lighting. A scene with `cinematic lighting` and
  `monochrome` is valid and intentional.

## Citation format

`knowledge/aesthetics/palette.md#<cluster>:<term>`,
e.g. `palette.md#named_grades:monochrome` or
`palette.md#cultural:cyberpunk`.