# Dictionary preflight

> **Python implementation:** `scripts/tag-validate.py` (Phase 5). This file documents the manual command.

---

(content from previous file below — unchanged)

The bundled Anima dictionary is an offline, read-only Gelbooru snapshot with Danbooru aliases.
It is the source of the audit's `canonical / known_alias / unverified` verdicts. **Check your
tags against it before compiling** so `unverified` is a decision you made, not a surprise you
read in the audit.

## The preflight command

Run from the skill root. It resolves each tag and prints `canonical`, match kind, category,
and source — `UNVERIFIED` means the dictionary does not know it.

```
python -c "
from prompt_forge.anima.dictionary import AnimaTagDictionary
d = AnimaTagDictionary()
for t in ['score_9', 'male', 'holding katana', 'melee combat']:
    c = d.resolve(t)
    print(repr(t), '->', None if c is None else (c.canonical, c.match_kind, c.category))
"
```

## Reading the verdicts

- **canonical** — the tag the model's vocabulary actually uses. Prefer these.
- **known_alias** — the dictionary maps your tag to a canonical form. The audit/verification
  resolves against that canonical, but the compiler renders your authored spelling **verbatim**
  — it does not rewrite `male` to `male_focus` or `low angle` to `from_below`. Prefer the
  canonical spelling yourself when authoring so the model sees the form its vocabulary knows.
- **unverified** — not in the dictionary. Advisory: the gate does not block it, but it is an
  honest signal that the model may not have learned that exact semantic.

Common canonicalizations you will hit:

| you write | canonical | kind |
|---|---|---|
| `male` | `male_focus` | alias |
| `holding katana` | `holding_sword` | alias |
| `god rays` | `sunbeam` | alias |
| `best quality` | `best_quality` | canonical (official) |
| `score_9` | `score_9` | canonical (official) |
| `melee combat`, `ruined city`, `mutant monster`, `teal and orange color grade` | — | unverified |

## Decision rules for unverified tags

1. **Semantically essential and no canonical near-synonym** (e.g. `mutant monster`,
   `teal and orange color grade`) → keep it. It is advisory; the CLIP text encoder still reads
   ordinary words. Write it in the model's order, link it to a fact, and accept the warning.
2. **A canonical form exists** → use the canonical form (`holding katana` → `holding_sword`
   if the sword fact matters more than the katana identity; keep `katana` as a separate tag if
   the blade type is load-bearing).
3. **The semantic is trivial flavor** → drop it rather than accumulate unverified noise.

## After compiling: verify the returned string

The `prompt` that `compile_prompt_artifact` returns is **exactly what the model sees** — your
authored spelling verbatim, in native field order, with any `render_weight` applied as
`(text:weight)`. It is **not** canonicalized: `low angle` stays `low angle` (dictionary
canonical `from_below`), `photo (medium)` stays as authored. The dictionary resolves only for
audit/verification. Diff the returned string against your segments before running
`camera-image`; if the native form surprises you (an unverified tag, a reordered segment), fix
your segments and recompile rather than shipping a prompt you have not read.
