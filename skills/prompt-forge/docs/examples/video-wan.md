# Example: Wan video (v3 schema)

Demonstrates multi-frame video with v3 concept objects, transition
beats, and role-anchored continuity constraints.

## Spec

```python
from internals.spec import (
    Specification, State, Style, Constraint, Transition,
    Subject, Costume, Prop, Environment, Atmosphere, Lighting, Frame,
)
from internals.compile import compile

spec = Specification(
    modality="video",
    initial_state=State(
        subjects=(
            Subject(
                identity="a swordswoman",
                costume=(Costume(garment="robe", material="silk", color="vermilion"),),
                props=(Prop(item="sword", material="jade-hilted steel"),),
            ),
        ),
        environment=Environment(
            place="the edge of a moonlit bamboo grove",
            atmosphere=Atmosphere(haze="thin ground fog"),
        ),
        lighting=Lighting(
            key="moonlight from upper right, 4200K cool",
            rim="cold rim from behind-left",
        ),
        frame=Frame(shot="medium shot", lens="35mm wide"),
    ),
    transitions=(
        Transition(
            start=0.0, end=3.0,
            trigger="wind picks up",
            action="her hair sways and her shoulders turn toward the grove",
            camera_motion="static",
            sound="rustling bamboo leaves",
            result=State(
                subjects=(Subject(
                    identity="a swordswoman",
                    costume=(Costume(garment="robe", material="silk", color="vermilion"),),
                    props=(Prop(item="sword", material="jade-hilted steel"),),
                ),),
                environment=Environment(
                    place="deeper in the bamboo grove",
                    atmosphere=Atmosphere(haze="thin ground fog"),
                ),
            ),
        ),
        Transition(
            start=3.0, end=6.0,
            trigger="she steps forward",
            action="she walks three paces into the grove, hand on her sword",
            camera_motion="slow dolly forward",
            sound="footsteps on moss",
            result=State(
                subjects=(Subject(
                    identity="a swordswoman",
                    costume=(Costume(garment="robe", material="silk", color="vermilion"),),
                    props=(Prop(item="sword", material="jade-hilted steel"),),
                ),),
                environment=Environment(
                    place="inside the bamboo grove",
                    atmosphere=Atmosphere(haze="thin ground fog"),
                ),
            ),
        ),
    ),
    constraints=(
        Constraint(must_contain=("vermilion", "silk"), kind="identity",
                   description="vermilion silk robe",
                   anchor_role="costume"),
    ),
    duration=6.0,
)

package = compile(spec, "wan")
```

## Output

Wan projector emits:

1. A shot header: "Medium shot of a swordswoman, wearing vermilion
   silk robe, holding jade-hilted steel sword."
2. Per-transition motion beats: "wind picks up, her hair sways and
   her shoulders turn toward the grove, camera static, audio:
   rustling bamboo leaves, resulting in a swordswoman, wearing
   vermilion silk robe, holding jade-hilted steel sword. Place:
   deeper in the bamboo grove. Haze: thin ground fog."
3. Each subsequent transition as its own beat with the same shape.
4. Closing environment + lighting blocks.
5. Style block (if set).

## Why it passes

- **P1 visibility**: every Subject has identity; every transition
  has physical verbs ("sways", "turn", "walks").
- **P2 causality**: every transition has trigger + action + result.
- **P3 continuity**: timeline is contiguous (0->3->6);
  `must_contain=("vermilion", "silk")` anchored to `costume` is
  satisfied because both tokens appear in every transition's
  Costume concept.
- **P4 completeness**: wan requires subjects + action; all present.
- **P5 density**: triggers and actions have >= 2 word-tokens;
  each transition is 3s (> 0.5s).

## v3 schema in action

- **Camera motion** is its own Transition field, distinct from
  `action` (body motion). v3 emits both: "camera static" vs
  "camera slow dolly forward".
- **Sound** is surfaced per transition.
- **Atmosphere** is per-result-state, so the haze carries across
  frames.
- **Constraint.anchor_role="costume"** keeps the vermilion / silk
  check inside Costume only.

## Persistence locks via evidence (optional)

```python
from internals.evidence import normalize_evidence

evidence = normalize_evidence({
    "schema_version": "3.0",
    "locked_facts": [
        "the swordswoman wears the same red robe throughout",
        "the jade-hilt sword stays at her hip",
    ],
})

pkg = compile(spec, "wan", evidence)
```

The locked facts are promoted to `Constraint(must_contain=...)`
without anchor_role (since the source fact doesn't carry one).
To make them role-anchored, extend the synthesis in
`compile._absorb_locked_facts` to map fact text to anchor_role
heuristically, or declare Constraints directly.