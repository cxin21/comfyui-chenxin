# Camera / lens / film — Anima tag vocabulary

> The Anima tag vocabulary is rooted in image-board culture, so "lens language"
> means **render-medium** + **optical-style**, not Hasselblad model numbers.
> Use these to give the prompt a physical render signature instead of leaving
> it medium-agnostic.

## Render medium (what the picture looks like it was made with)

| term | visual effect | use when | avoid when |
|---|---|---|---|
| `photo (medium)` | photographic render | default realism | illustration, lineart |
| `photorealistic` | strong photo-render emphasis | cinematic realism, portrait | anime/chibi illustration |
| `illustration` | clearly drawn, painted | book, magazine | photorealistic |
| `painting` | painterly texture | traditional, gallery | photo |
| `watercolor` / `watercolour` | soft translucent washes | tender, soft scenes | hard surfaces |
| `sketch` | visible line work | planning, rough, indie comic | finished realism |
| `lineart` | dominant outlines, flat color | manga, anime, comic | photorealistic |
| `comic` | sequential art look | graphic novel, manga | cinematic realism |
| `traditional media` | pencil, ink, watercolor cue | vintage, handcrafted | digital slick |
| `digital media` | clean digital render | modern illustration | vintage handcraft |

## Optical style (how the camera "sees")

| term | visual effect | use when | avoid when |
|---|---|---|---|
| `depth of field` | layered focus, bokeh background | cinematic, environmental | flat illustration |
| `shallow depth of field` | strong background blur | portrait, isolation | landscape, ensemble |
| `bokeh` | out-of-focus light circles | night lights, city, romance | bright daylight |
| `motion blur` | smeared movement | action, speed | static portrait |
| `fisheye` | ultra-wide distortion | sports, music video, edge | classical portrait |
| `macro` | extreme close-up detail | small subject, texture | wide scene |
| `panoramic` | wide horizontal frame | landscape, vista | portrait |
| `wide angle` | exaggerates foreground distance | architecture, interior | portrait |

## Film / texture signature

| term | visual effect | use when | avoid when |
|---|---|---|---|
| `film grain` | visible grain, analog feel | vintage, photography, mood | clean digital illustration |
| `35mm` | 35mm film stock look | photography, retro | digital |
| `polaroid` | square frame, soft color, white border | instant photo, nostalgic | cinematic widescreen |
| `instagram` | filtered, square, soft | modern social, casual | formal, cinematic |

## Co-use rules

- Pair **one render medium** with **one optical style** for clarity:
  `photo (medium), shallow depth of field` reads as portrait photography;
  `illustration, lineart` reads as anime.
- Don't pair two mediums: `photo (medium)` + `painting` is contradictory.
- Don't pair `shallow depth of field` + `panoramic` (panoramic implies deep focus).
- `film grain` + `polaroid` is intentionally cumulative (both film texture signatures); allowed.

## Citation format

`knowledge/aesthetics/camera.md#<cluster>:<term>`,
e.g. `camera.md#render_medium:photorealistic` or
`camera.md#optical:shallow_depth_of_field`.