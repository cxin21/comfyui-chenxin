# Style signatures

> A "style signature" is a **named cluster of Anima tags** that, when grouped
> together, reliably invoke a recognizable visual family. Two flavors live
> here: artist tags (prefixed `@`) that Anima has learned as visual
> fingerprints, and genre/medium tags invoking named aesthetic movements
> without an artist name (cyberpunk noir, pastel Ghibli, monochrome
> ukiyo-e). Artist tags are the highest-leverage aesthetic lever Anima
> exposes — pull `@<name>` from the bundled dictionary; never invent.

## 核心公式

> Signature = `kind:name` bound to a tag cluster + visual fingerprint. Cite
> as `style-signatures.md#<kind>:<name>`. Verify each tag against the
> bundled Anima dictionary before shipping.

## 变体维度表

| 维度 | 可选签名 |
|---|---|
| artist | `@ciloranko`, `@shal.e`, `@fuzichoco`, `@kawacy`, `@necömi`, `@photonondragon`, `@mifuji`, `@ask_zak`, `@frfr`, `@tiv`, `@bittersweet` |
| medium | `noir` |
| genre | `cinematic_blockbuster`, `cyberpunk`, `pastel_ghibli`, `wes_anderson_pastel`, `helmut_newton_bw`, `wuxia_ink`, `ukiyo_e`, `risograph` |

### Artist signatures (verify `@<name>` in bundled dictionary first)

#### `@ciloranko`

- **signature_tags**: `cinematic lighting, dramatic lighting, bokeh, depth of field, beautiful detailed eyes, light particles`
- **visual**: painterly-romantic, dreamy close-ups, water/glass highlights, hair blowing in wind
- **invoke_when**: portrait, romantic, fantasy character, soft magical mood
- **avoid_when**: hard sci-fi, brutalist, comic/cartoon, mechanical
- **cite**: `style-signatures.md#artist:ciloranko`

#### `@shal.e`

- **signature_tags**: `cinematic lighting, dramatic lighting, from side, depth of field, lens flare, hair flowing`
- **visual**: cinematic color grading, side-lit drama, strong rim light, often motorcycle/outdoor girl themes
- **invoke_when**: cinematic character beat, wind/motion in hair, urban dusk
- **avoid_when**: pure slice-of-life interior, chibi
- **cite**: `style-signatures.md#artist:shal.e`

#### `@fuzichoco`

- **signature_tags**: `cinematic lighting, depth of field, bokeh, beautiful detailed eyes, light particles, ethereal`
- **visual**: dreamy, romantic, candy-soft palette, flower/petal motifs, fantasy costume
- **invoke_when**: romantic, fantasy girl, costume, magical
- **avoid_when**: horror, grunge, realism
- **cite**: `style-signatures.md#artist:fuzichoco`

#### `@kawacy`

- **signature_tags**: `cinematic lighting, dramatic lighting, atmospheric, depth of field, beautiful detailed eyes`
- **visual**: classical-romantic, painterly faces, often nostalgic or wistful scenes
- **invoke_when**: nostalgic, classical, romantic portrait
- **avoid_when**: modern tech, neon, action
- **cite**: `style-signatures.md#artist:kawacy`

#### `@necömi`

- **signature_tags**: `cinematic lighting, beautiful detailed eyes, depth of field, atmospheric, fantasy`
- **visual**: anime-fantasy, big expressive eyes, ethereal backgrounds, often white/pastel palette
- **invoke_when**: fantasy girl, dream sequence, lighthearted magical
- **avoid_when**: realistic, gritty, mechanical
- **cite**: `style-signatures.md#artist:necömi`

#### `@photonondragon`

- **signature_tags**: `dramatic lighting, cinematic lighting, depth of field, atmospheric, detailed background, fantasy`
- **visual**: high-detail fantasy illustration, dragon/mythological creature themes
- **invoke_when**: fantasy creatures, mythological, epic
- **avoid_when**: mundane slice-of-life, photographic realism
- **cite**: `style-signatures.md#artist:photonondragon`

#### `@mifuji`

- **signature_tags**: `cinematic lighting, beautiful detailed eyes, depth of field, soft lighting, romantic`
- **visual**: soft, romantic, gentle, warm palette, often flowers or nature
- **invoke_when**: soft romance, gentle moment, nature backdrop
- **avoid_when**: violent, dark, mechanical
- **cite**: `style-signatures.md#artist:mifuji`

#### `@ask_zak` (alias `@ask`)

- **signature_tags**: `cinematic lighting, dramatic lighting, depth of field, beautiful detailed eyes`
- **visual**: clean cinematic anime faces, modern fashion, contemporary city life
- **invoke_when**: modern urban, fashion, contemporary slice-of-life
- **avoid_when**: fantasy creatures, period, horror
- **cite**: `style-signatures.md#artist:ask`

#### `@frfr`

- **signature_tags**: `cinematic lighting, depth of field, beautiful detailed eyes, soft lighting, atmospheric`
- **visual**: emotional, character-focused, often gentle expressions, indie mood
- **invoke_when**: emotional portrait, character focus, indie story
- **avoid_when**: epic battle, action, comedy
- **cite**: `style-signatures.md#artist:frfr`

#### `@tiv`

- **signature_tags**: `cinematic lighting, dramatic lighting, depth of field, beautiful detailed eyes, atmospheric`
- **visual**: romantic-anime, dramatic facial lighting, often night scenes
- **invoke_when**: night scenes, romantic drama, close-up portraits
- **avoid_when**: bright day, comedy, chibi
- **cite**: `style-signatures.md#artist:tiv`

#### `@bittersweet`

- **signature_tags**: `cinematic lighting, depth of field, beautiful detailed eyes, atmospheric, soft lighting`
- **visual**: nostalgic, melancholic, soft grain, often school/classroom or street
- **invoke_when**: nostalgia, melancholy, sunset, school, casual
- **avoid_when**: sci-fi, combat, fantasy
- **cite**: `style-signatures.md#artist:bittersweet`

### Medium signatures (no `@` name — palette + lighting recipe)

#### `noir`

- **signature_tags**: `monochrome, high contrast, dramatic lighting, side lighting, partially shadowed`
- **visual**: black/white film noir, hard shadows, urban night, fedoras and trench coats
- **invoke_when**: crime, mystery, urban night, noir detective
- **avoid_when**: cheerful scenes, pastel, fantasy
- **cite**: `style-signatures.md#medium:noir`

### Genre signatures (no `@`-prefix required)

#### `cinematic_blockbuster`

- **signature_tags**: `teal and orange color grade, cinematic lighting, depth of field, dramatic lighting, rim light`
- **invoke_when**: action hero, blockbuster poster, urban night, dramatic tension
- **avoid_when**: period pastoral, monochrome, slice-of-life
- **cite**: `style-signatures.md#genre:cinematic_blockbuster`

#### `cyberpunk`

- **signature_tags**: `cyberpunk, neon lights, rain, reflections, dark, dramatic lighting`
- **invoke_when**: urban night, sci-fi street, hacker, future dystopia
- **avoid_when**: pastoral, bright day, fantasy castle
- **cite**: `style-signatures.md#genre:cyberpunk`

#### `pastel_ghibli`

- **signature_tags**: `pastel color, soft lighting, atmospheric, beautiful detailed eyes, light particles, sakura petals`
- **invoke_when**: nature, flight, gentle magic, child protagonist, kindness
- **avoid_when**: violence, urban noir, mechanical
- **cite**: `style-signatures.md#genre:pastel_ghibli`

#### `wes_anderson_pastel`

- **signature_tags**: `pastel color, centered, symmetrical, soft lighting, illustration`
- **invoke_when**: deadpan, symmetrical group, hotel-lobby humor, retro
- **avoid_when**: action, dark themes, gritty realism
- **cite**: `style-signatures.md#genre:wes_anderson_pastel`

#### `helmut_newton_bw`

- **signature_tags**: `monochrome, high contrast, dramatic lighting, side lighting, fashion, depth of field`
- **invoke_when**: fashion, noir portrait, provocative, sophisticated
- **avoid_when**: cute, kawaii, bright cartoon
- **cite**: `style-signatures.md#genre:helmut_newton_bw`

#### `wuxia_ink`

- **signature_tags**: `traditional media, ink wash, watercolor, atmospheric, partially shadowed, dramatic lighting`
- **invoke_when**: martial arts, sword, mountain, crane, ancient China, mist
- **avoid_when**: neon, sci-fi, modern urban, anachronism
- **cite**: `style-signatures.md#genre:wuxia_ink`

#### `ukiyo_e`

- **signature_tags**: `traditional media, flat color, lineart, vintage, ukiyo-e`
- **invoke_when**: Edo period, waves, courtesan, kabuki, mountain
- **avoid_when**: photorealism, sci-fi, neon
- **cite**: `style-signatures.md#genre:ukiyo_e`

#### `risograph`

- **signature_tags**: `risograph, flat color, vintage, washed colors, illustration, film grain`
- **invoke_when**: indie poster, zine, music flyer, alt-art
- **avoid_when**: photographic realism, blockbuster
- **cite**: `style-signatures.md#genre:risograph`

## 氛围链

(omit — signatures are discrete; no chain applies)

## 使用提示

- Cite via `style-signatures.md#<kind>:<name>` — e.g.,
  `style-signatures.md#artist:ciloranko` or
  `style-signatures.md#genre:cyberpunk`. The `cite` field in each block is
  exactly the string to paste into a fact's `source_ref`.
- To add a new signature: append a new subsection under the matching kind
  (`Artist signatures`, `Medium signatures`, or `Genre signatures`) with
  `signature_tags` / `visual` / `invoke_when` / `avoid_when` / `cite`.
  Artist names must be verified against the bundled Anima dictionary
  before the new block is accepted.
- Pick 3–6 tags from `signature_tags` for the actual prompt; the rest
  follows from the cluster. `invoke_when` and `avoid_when` tell you which
  subjects the signature was trained for — respect them.
- When binding a signature to a prompt, use `kind:name` as a single tag
  fragment in `source_ref`. Two-artist stacks, opposing-genre stacks, or
  artist tags without the `@`-prefixed name itself all fail — see
  `anti-patterns.md` for the prohibited combinations.

### Authoring workflow

1. Decide the genre/aesthetic family from the user's request.
2. Pick one signature block above.
3. Copy its `signature_tags` into your fact ledger as `agent_embellishment`
   facts, each with `source_ref` set to the block's `cite` string.
4. Verify each tag against the bundled Anima dictionary via
   `python -c "from prompt_forge.anima.dictionary import AnimaTagDictionary; ..."`.
5. If a tag is `unverified`, drop it from the block rather than ship
   unverified noise (per `dictionary-preflight.md` decision rule 3).

### Anti-pattern: do not stack

- **Two artist signatures on the same subject** — model averages them and
  produces mush.
- **Genre signature + an opposing genre signature** — `cinematic_blockbuster`
  + `pastel_ghibli` = incoherent prompt.
- **Artist signature tags without the `@`-prefixed name itself** — the
  `signature_tags` alone do not invoke the artist's fingerprint reliably.

## 法典验证场景

### 场景 A — 浪漫肖像，cite `@ciloranko`

tags: signature binding via `source_ref`
备注: bind `style-signatures.md#artist:ciloranko` to an `agent_embellishment` fact when the user asks for a dreamy romantic portrait; the cite string is the only thing that proves the recipe came from this file.

### 场景 B — 赛博朋克街景，cite `cyberpunk`

tags: genre cite without artist
备注: cite `style-signatures.md#genre:cyberpunk` for an urban-night hacker scene; the genre signature supplies `neon lights, rain, reflections, dark` directly without needing an `@<name>`.

### 场景 C — 黑帮电影海报，cite `noir` medium

tags: medium cite when no artist fits
备注: cite `style-signatures.md#medium:noir` when the request is "1940s detective" with no artist angle; the medium signature covers `monochrome, high contrast, dramatic lighting, side lighting, partially shadowed` as a palette+lighting recipe.