# Anima vocabulary

## Positioning

Anima's complete tag vocabulary knowledge — every tag the model has learned to render. **This is a dictionary, not a creation instruction.** The dictionary does not judge how its words are used.

## Files

| File | NSFW template § | Contents |
|---|---|---|
| [count-identity.md](count-identity.md) | §6 | count, IP, body type, age difference |
| [appearance.md](appearance.md) | §7 | hair, eyes, body, non-human, marks |
| [clothing.md](clothing.md) | §8 | garments + 7-dim modifications + contrast |
| [pose-action.md](pose-action.md) | §9 | single / dual / multi / storyboard |
| [expression.md](expression.md) | §10 | emotions + intensity Lv1-4 + reactions |
| [camera-shot.md](camera-shot.md) | §11 | framing, angle, POV, composition |
| [scene-environment.md](scene-environment.md) | §12 | locations + risk matrix + weather |
| [detail-mood.md](detail-mood.md) | §13 | texture + mood + tag blacklist |
| [special-themes.md](special-themes.md) | §14 | cross-slot theme recipes |

## Field mapping

Each vocabulary file maps to authoring-contract fields (the 9-slot structure — see `dialect.md`):

| Field | Vocabulary file(s) |
|---|---|
| `count` | count-identity.md |
| `character` | count-identity.md (IP) |
| `appearance` | appearance.md + clothing.md |
| `general` | expression.md + pose-action.md + camera-shot.md + detail-mood.md |
| `environment` | scene-environment.md |
| `scene_description` | special-themes.md |

`protocol_prefix`, `series`, and `artist` have no dedicated vocabulary file — `protocol_prefix` is the enforced quality baseline (see `dialect.md`), `series`/`artist` are authored from the request/facts.

## Usage constraints

1. Every tag must pass [shared/self-check.md](../../../shared/self-check.md) + [quality/style-consistency.md](../../../quality/style-consistency.md) + [quality/tag-count-ruler.md](../../../quality/tag-count-ruler.md).
2. Tag frequency warnings come from `scripts/tag-validate.py`.
3. No compatibility shim with the old NSFW template — content migrated, paths rewritten.

## Vocabulary file template (5-段式, 非 prompt 结构)

This is the **document** template each vocabulary file follows — distinct from the prompt's 9-slot structure (see `dialect.md`). The 5 segments organize the dictionary entry, not the generated prompt:

1. **核心公式** — one-sentence punch line
2. **变体维度表** — dimensions × tags
3. **氛围链** — light-to-heavy progression (omit if discrete)
4. **使用提示** — pitfalls
5. **法典验证场景** — 2-4 proven combinations

Tags in 法典验证场景 MUST be drawn from the same file's 变体维度表 (no cross-file borrowing).
