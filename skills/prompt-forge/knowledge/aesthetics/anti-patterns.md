# Anti-patterns — what an aesthetic prompt must NOT contain

> This file is the **override** layer in `precedence`. If a prompt contains any
> of the patterns below, fix it before shipping, regardless of what the other
> five layers say. Aesthetic quality is determined as much by **exclusion** as
> by inclusion.

## A. Empty intensifiers (the model ignores them; they waste tokens)

| anti-pattern | why it's wrong | what to do instead |
|---|---|---|
| `beautiful`, `gorgeous`, `stunning`, `pretty`, `lovely` | zero semantic signal; the model already defaults toward pretty | drop; use specific aesthetic tags (`cinematic lighting`, `bokeh`) |
| `highly detailed`, `ultra detailed`, `extremely detailed` | vague; no subject, region, or texture specified | specify what detail (`intricate lace collar`, `filigree embroidery`) |
| `atmospheric`, `a lot of atmosphere` | un-nameable | name the atmosphere (`fog`, `volumetric lighting`, `dust`) |
| `masterpiece`, `masterful`, `amazing` | identical issue | drop |
| `intricate`, `ornate` (alone) | doesn't say what is intricate | `intricate lacework on collar`, `ornate brass filigree` |
| `professional`, `professional photography` (alone) | not a render cue | specify the render medium (`photo (medium)`, `35mm`) |
| `award-winning`, `prize-winning` | not a render cue | drop or replace with the actual aesthetic family |

## B. Empty scale / resolution tags (only meaningful with context)

| anti-pattern | why it's wrong | what to do instead |
|---|---|---|
| `8k`, `4k`, `2k`, `uhd` (alone) | the image is not 8k; this is gallery bait | drop or combine with intent (`highres` is in the official tag set and actually does something) |
| `high resolution`, `high quality` (alone) | vague | `highres` (official quality tag) |
| `photorealistic` (alone, without render-medium + lighting) | model averages to default render | pair with `photo (medium), cinematic lighting, depth of field` |

## C. Platform-name drop tags (gallery pandering)

| anti-pattern | why it's wrong |
|---|---|
| `trending on artstation`, `trending on pixiv`, `featured on pixiv`, `fanbox`, `patreon` | these were gallery-promotion tags in early SD communities; the model has learned them as **style fingerprints for low-effort art**, not as quality signals |

## D. Contradictions the model cannot reconcile

| anti-pattern | contradiction |
|---|---|
| `cinematic lighting` + `flat color` + `cel shading` (with no medium tag) | cinematic ≠ cel; drop one or pick `illustration` explicitly |
| `monochrome` + `pastel color` + `vivid color` | three palette grades, pick one |
| `low contrast` + `high contrast` | exclusive |
| `warm color` + `cool color` (alone, no context) | choose one temperature or move it to lighting (`golden hour` vs `moonlight`) |
| `soft lighting` + `hard lighting` | exclusive |
| `low angle` + `high angle` | exclusive (composition) |
| `centered` + `rule of thirds` (both as primary layout) | exclusive (composition) |
| `shallow depth of field` + `panoramic` | panoramic implies deep focus |
| `photo (medium)` + `painting` + `watercolor` + `sketch` | choose ONE render medium |
| `cyberpunk` + `pastel color` (with no mediating style) | genre-vs-palette mismatch |

## E. Tags the Anima model learned as low-effort

These tags **do** appear in training data, but they cluster with quick
sketches / lower-quality renders:

- `simple background`, `plain background` (with no compensating tags) — the
  prompt reads as "I didn't bother with environment". Use `detailed background`
  if you want effort.
- `bad anatomy`, `bad hands` in **positive** — they sometimes appear as tags
  in adversarial training. Drop.
- `watermark`, `signature` (in positive, unless the user wants a watermarked
  reference image) — drop.
- `lowres`, `worst quality`, `low quality`, `score_4`, `score_5`, `score_6`
  in **positive** — those belong in the negative stream only.

## F. Recipes that look clever but degrade quality

| anti-pattern | why |
|---|---|
| `(cinematic lighting:1.3)`-style emphasis weights | Anima does not use Danbooru `::` weights reliably in a clean way; emphasis tags add noise without consistent effect |
| repeating the same tag twice to "double it" | treated as duplicate semantics; audit flags |
| stacking 5+ lighting tags in one segment | layered excess; pick 2–3 complementary terms |
| trailing the prompt with `...` or `--` or any non-tag punctuation | the audit rejects or misreads them |

## G. Stacking the same layer with overlapping tags

- Two palette terms: drop one
- Two lighting qualities: drop one
- Two angles: drop one
- Two render mediums: drop one

## Override behavior

If your authored prompt contains any pattern in section A, B, or C, the
authoring method requires you to **remove it before compiling**, even if the
resulting prompt is shorter. Empty intensifiers are worse than absent content.

If your prompt contains any pattern in section D, **resolve the contradiction
first** — pick the term that fits the user's intent and discard the other.

If section E or F applies, drop the offending tag and keep everything else.

## Citation

When you explicitly remove an anti-pattern during authoring, log it as an
`agent_embellishment` fact whose `source_ref` is
`anti-patterns.md#<section>:<pattern>` (e.g.
`anti-patterns.md#A:empty_intensifiers`) — this makes the removal auditable.