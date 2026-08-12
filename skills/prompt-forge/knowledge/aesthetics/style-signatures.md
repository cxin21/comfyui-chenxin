# Style signatures — Anima tag vocabulary

> A "style signature" is a **named cluster of tags** that, when grouped together,
> reliably invoke a recognizable visual family. Two flavors live here:
>
> 1. **Artist tags** (prefixed `@`) — names that the Anima tag dictionary has
>    already learned as visual fingerprints.
> 2. **Genre / medium tags** — named aesthetic movements you can invoke without
>    an artist name (cyberpunk noir, pastel Ghibli, monochrome ukiyo-e).
>
> Artist tags are the highest-leverage aesthetic lever Anima exposes. Pull them
> from the bundled dictionary; never invent `@<name>` without verification.

## Using this file

- For each signature, read the `signature_tags` column — those are the **exact
  Anima tags** that compose the look. Pick 3–6 of them; the rest follows.
- `invoke_when` and `avoid_when` tell you which subjects or contexts the
  signature was trained for. A silhouette portrait in `@shal.e` makes sense; a
  pixel-art mascot in `@shal.e` does not.
- `cite` is what you put in the fact's `source_ref` to prove you used this file,
  not arbitrary prose.

---

## Artist signatures (verify `@<name>` in the bundled dictionary first)

### `@ciloranko`
- **signature_tags**: `cinematic lighting, dramatic lighting, bokeh, depth of field, beautiful detailed eyes, light particles`
- **visual**: painterly-romantic, dreamy close-ups, water/glass highlights, hair blowing in wind
- **invoke_when**: portrait, romantic, fantasy character, soft magical mood
- **avoid_when**: hard sci-fi, brutalist, comic/cartoon, mechanical
- **cite**: `style-signatures.md#artist:ciloranko`

### `@shal.e`
- **signature_tags**: `cinematic lighting, dramatic lighting, from side, depth of field, lens flare, hair flowing`
- **visual**: cinematic color grading, side-lit drama, strong rim light, often motorcycle/outdoor girl themes
- **invoke_when**: cinematic character beat, wind/motion in hair, urban dusk
- **avoid_when**: pure slice-of-life interior, chibi
- **cite**: `style-signatures.md#artist:shal.e`

### `@fuzichoco`
- **signature_tags**: `cinematic lighting, depth of field, bokeh, beautiful detailed eyes, light particles, ethereal`
- **visual**: dreamy, romantic, candy-soft palette, flower/petal motifs, fantasy costume
- **invoke_when**: romantic, fantasy girl, costume, magical
- **avoid_when**: horror, grunge, realism
- **cite**: `style-signatures.md#artist:fuzichoco`

### `@kawacy`
- **signature_tags**: `cinematic lighting, dramatic lighting, atmospheric, depth of field, beautiful detailed eyes`
- **visual**: classical-romantic, painterly faces, often nostalgic or wistful scenes
- **invoke_when**: nostalgic, classical, romantic portrait
- **avoid_when**: modern tech, neon, action
- **cite**: `style-signatures.md#artist:kawacy`

### `@necömi`
- **signature_tags**: `cinematic lighting, beautiful detailed eyes, depth of field, atmospheric, fantasy`
- **visual**: anime-fantasy, big expressive eyes, ethereal backgrounds, often white/pastel palette
- **invoke_when**: fantasy girl, dream sequence, lighthearted magical
- **avoid_when**: realistic, gritty, mechanical
- **cite**: `style-signatures.md#artist:necömi`

### `@photonondragon`
- **signature_tags**: `dramatic lighting, cinematic lighting, depth of field, atmospheric, detailed background, fantasy`
- **visual**: high-detail fantasy illustration, dragon/mythological creature themes
- **invoke_when**: fantasy creatures, mythological, epic
- **avoid_when**: mundane slice-of-life, photographic realism
- **cite**: `style-signatures.md#artist:photonondragon`

### `@mifuji`
- **signature_tags**: `cinematic lighting, beautiful detailed eyes, depth of field, soft lighting, romantic`
- **visual**: soft, romantic, gentle, warm palette, often flowers or nature
- **invoke_when**: soft romance, gentle moment, nature backdrop
- **avoid_when**: violent, dark, mechanical
- **cite**: `style-signatures.md#artist:mifuji`

### `@ask (ask_zak)` / `@ask_zak`
- **signature_tags**: `cinematic lighting, dramatic lighting, depth of field, beautiful detailed eyes`
- **visual**: clean cinematic anime faces, modern fashion, contemporary city life
- **invoke_when**: modern urban, fashion, contemporary slice-of-life
- **avoid_when**: fantasy creatures, period, horror
- **cite**: `style-signatures.md#artist:ask`

### `@frfr`
- **signature_tags**: `cinematic lighting, depth of field, beautiful detailed eyes, soft lighting, atmospheric`
- **visual**: emotional, character-focused, often gentle expressions, indie mood
- **invoke_when**: emotional portrait, character focus, indie story
- **avoid_when**: epic battle, action, comedy
- **cite**: `style-signatures.md#artist:frfr`

### `@tiv`
- **signature_tags**: `cinematic lighting, dramatic lighting, depth of field, beautiful detailed eyes, atmospheric`
- **visual**: romantic-anime, dramatic facial lighting, often night scenes
- **invoke_when**: night scenes, romantic drama, close-up portraits
- **avoid_when**: bright day, comedy, chibi
- **cite**: `style-signatures.md#artist:tiv`

### `@bittersweet`
- **signature_tags**: `cinematic lighting, depth of field, beautiful detailed eyes, atmospheric, soft lighting`
- **visual**: nostalgic, melancholic, soft grain, often school/classroom or street
- **invoke_when**: nostalgia, melancholy, sunset, school, casual
- **avoid_when**: sci-fi, combat, fantasy
- **cite**: `style-signatures.md#artist:bittersweet`

### Noir-medium (no `@` name — it's a palette + lighting recipe)
- **signature_tags**: `monochrome, high contrast, dramatic lighting, side lighting, partially shadowed`
- **visual**: black/white film noir, hard shadows, urban night, fedoras and trench coats
- **invoke_when**: crime, mystery, urban night, noir detective
- **avoid_when**: cheerful scenes, pastel, fantasy
- **cite**: `style-signatures.md#medium:noir`

---

## Genre / medium signatures (no `@`-prefix required)

### Cinematic blockbuster
- **signature_tags**: `teal and orange color grade, cinematic lighting, depth of field, dramatic lighting, rim light`
- **invoke_when**: action hero, blockbuster poster, urban night, dramatic tension
- **avoid_when**: period pastoral, monochrome, slice-of-life
- **cite**: `style-signatures.md#genre:cinematic_blockbuster`

### Cyberpunk neon
- **signature_tags**: `cyberpunk, neon lights, rain, reflections, dark, dramatic lighting`
- **invoke_when**: urban night, sci-fi street, hacker, future dystopia
- **avoid_when**: pastoral, bright day, fantasy castle
- **cite**: `style-signatures.md#genre:cyberpunk`

### Pastel Ghibli
- **signature_tags**: `pastel color, soft lighting, atmospheric, beautiful detailed eyes, light particles, sakura petals`
- **invoke_when**: nature, flight, gentle magic, child protagonist, kindness
- **avoid_when**: violence, urban noir, mechanical
- **cite**: `style-signatures.md#genre:pastel_ghibli`

### Wes Anderson pastel
- **signature_tags**: `pastel color, centered, symmetrical, soft lighting, illustration`
- **invoke_when**: deadpan, symmetrical group, hotel-lobby humor, retro
- **avoid_when**: action, dark themes, gritty realism
- **cite**: `style-signatures.md#genre:wes_anderson_pastel`

### Helmut Newton black-and-white
- **signature_tags**: `monochrome, high contrast, dramatic lighting, side lighting, fashion, depth of field`
- **invoke_when**: fashion, noir portrait, provocative, sophisticated
- **avoid_when**: cute, kawaii, bright cartoon
- **cite**: `style-signatures.md#genre:helmut_newton_bw`

### Wuxia ink-wash
- **signature_tags**: `traditional media, ink wash, watercolor, atmospheric, partially shadowed, dramatic lighting`
- **invoke_when**: martial arts, sword, mountain, crane, ancient China, mist
- **avoid_when**: neon, sci-fi, modern urban, anachronism
- **cite**: `style-signatures.md#genre:wuxia_ink`

### Ukiyo-e woodblock
- **signature_tags**: `traditional media, flat color, lineart, vintage, ukiyo-e`
- **invoke_when**: Edo period, waves, courtesan, kabuki, mountain
- **avoid_when**: photorealism, sci-fi, neon
- **cite**: `style-signatures.md#genre:ukiyo_e`

### Risograph print
- **signature_tags**: `risograph, flat color, vintage, washed colors, illustration, film grain`
- **invoke_when**: indie poster, zine, music flyer, alt-art
- **avoid_when**: photographic realism, blockbuster
- **cite**: `style-signatures.md#genre:risograph`

---

## How to author with a signature

1. Decide the genre/aesthetic family from the user's request (or from
   `style-signatures.md` recipe by mood).
2. Pick one signature block above.
3. Copy its `signature_tags` into your fact ledger as `agent_embellishment`
   facts, each with `source_ref` set to the `cite` string of the block.
4. Verify each tag against the bundled Anima dictionary via
   `python -c "from prompt_forge.anima.dictionary import AnimaTagDictionary; ..."`.
5. If a tag is `unverified` in the dictionary, drop it from the block rather
   than ship unverified noise (per `dictionary-preflight.md` decision rule 3).

## Anti-pattern: do not stack

- **Two artist signatures on the same subject** (the model will average them
  and produce mush).
- **Genre signature + an opposing genre signature** (`cinematic blockbuster` +
  `pastel Ghibli` = incoherent prompt).
- **Artist signature tags without the `@`-prefixed name itself** (the
  signature_tags alone do not invoke the artist's fingerprint reliably).

## Citation

`knowledge/aesthetics/style-signatures.md#<kind>:<name>`,
e.g. `style-signatures.md#artist:ciloranko` or
`style-signatures.md#genre:cyberpunk`.