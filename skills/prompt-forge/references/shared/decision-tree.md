# Decision tree

Route scene type first; then fill slots. Use generic scene names — never NSFW-specific naming.

## Routes

### single_subject
- brief: portrait, character sheet, single-figure focus
- slots: count(1) + appearance(high) + camera(close/cowboy/full body)
- skipped: relation, multi-attribute bridge
- camera rec: `close-up` / `cowboy shot` / `full body`

### two_subject_soft_interaction
- brief: daily interaction, collaboration, conversation, low-intensity conflict
- slots: count(2) + appearance×2 + action + scene
- skipped: heavy-intensity mood, extreme body details
- camera rec: `medium shot` / `from side`

### two_subject_full_interaction
- brief: battle, fight, confrontation, high-intensity interaction
- slots: count(2) + action(high) + camera(wide/low) + scene
- skipped: expression-only focus
- camera rec: `wide shot` + `low angle` + `leading lines`

### two_subject_special_position
- brief: unconventional framing, POV ambush, asymmetric angles
- slots: camera(unusual) + action + bridge
- skipped: standard camera rules
- camera rec: `pov` / `dutch angle` / `from above` + `from below` combo (only if compatible)

### multi_subject
- brief: group shot, ensemble, crowd
- slots: count(N) + scene + camera(wide) + bridge(character attribution)
- skipped: per-character expression detail
- camera rec: `wide shot` / `from above` / `panoramic`

### two_subject_same_type
- brief: same-type pair deep interaction (双女, 双男, 同种族)
- slots: count + appearance×2 + action
- skipped: hetero-specific relational tags
- camera rec: `from side` / `from above` for symmetric action

### cross_slot_theme
- brief: themes spanning multiple slots (围困, 战后, 仪式, 群像主题)
- slots: cross-multiple — see [dialects/anima/vocabulary/special-themes.md](../dialects/anima/vocabulary/special-themes.md)
- skipped: standard slot order
- camera rec: depends on theme

## How to use

1. Match brief to one of 7 routes.
2. Skip slots marked "skipped" — do not add their tags.
3. Apply slot emphasis as starting point; refine with [aesthetic-coverage.md](aesthetic-coverage.md).
