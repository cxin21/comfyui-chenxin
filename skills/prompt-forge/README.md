# Prompt Forge

LLM-first prompt authoring and quality-audit for image and video
models. v3 redesign.

## Layout

```
prompt-forge/
├── SKILL.md             # Skill entry point
├── internals/
│   ├── spec.py          # Concept objects + dataclasses
│   ├── evidence.py      # Evidence normalization
│   ├── dialect.py       # Dialect registry
│   ├── project.py       # Per-dialect projectors
│   ├── validate.py      # Validation propositions (P1-P5)
│   ├── package.py       # PromptPackage envelope
│   ├── render.py        # Debug renderer (concept-aware)
│   ├── compile.py       # User entry point
│   ├── registry/
│   │   └── dialects.json  # 31 dialect definitions
│   ├── docs/            # Theory, contracts, examples
│   └── legacy-archive/  # v2 backup (not imported)
└── .gitignore
```

## Architecture

```
                    ┌────────────────────┐
                    │     LLM (caller)   │
                    │   authors concept  │
                    │     objects        │
                    └──────────┬─────────┘
                               │
                               ▼
   ┌─────────────────────────────────────────────────────────┐
   │                  compile(spec, dialect)                 │
   │                                                         │
   │   evidence.py    dialect.py    project.py    validate  │
   │        │            │             │              │      │
   │        ▼            ▼             ▼              ▼      │
   │   normalize    lookup       spec->text    P1..P5       │
   └────────────────────────┬────────────────────────────────┘
                            │
                            ▼
                  ┌──────────────────────┐
                  │   PromptPackage      │
                  │   (envelope)         │
                  └──────────────────────┘
```

## Quick start

```python
from internals.spec import (
    Specification, State, Style, Constraint,
    Subject, Costume, Prop, Environment, Atmosphere, Lighting, Frame,
)
from internals.compile import compile

spec = Specification(
    modality="image",
    initial_state=State(
        subjects=(
            Subject(
                identity="a mage in a red robe",
                costume=(Costume(garment="robe", material="silk", color="vermilion"),),
                props=(Prop(item="jade staff"),),
            ),
        ),
        environment=Environment(place="a tower"),
        lighting=Lighting(key="candlelight"),
        frame=Frame(shot="medium shot"),
    ),
    style=Style(medium="ink wash", palette="charcoal and vermilion"),
)

package = compile(spec, "flux")
assert package.ready_for_review
print(package.prompt)
```

## Design principles

1. **First principles, not enumeration**: validation uses structural
   propositions (P1-P5), not growing word lists.
2. **Concepts, not flat strings**: every visual signal is a typed
   field on a concept object. The projector expands each concept
   into dialect-appropriate prose.
3. **Per-dialect composition**: each dialect owns its render
   strategy. No shared clause skeleton.
4. **Single responsibility**: each `internals/*.py` does one thing.
5. **Frozen dataclasses**: types are the documentation; mutations
   are forbidden.
6. **Forbidden fields**: `workflow`, `node`, `hash`, `gpu`,
   `execution`, `mode`, `runtime` cannot enter the envelope at any
   depth.
7. **No backward compatibility**: v2 lives in `internals/_v2_*_backup.py`
   files (not imported, kept for diff review).

## Adding a dialect

1. Append to `registry/dialects.json` (canonical id, projection
   short name, modality, form, ordering, required, supports flags,
   notes).
2. Add a function in `internals/project.py` named by the
   `projection` field. Compose the concept renderers in your
   preferred order; do not share clause structure with other dialects.
3. Register the function in `_PROJECTIONS`.
4. Call `compile(spec, dialect_id)` and inspect `ready_for_review`.