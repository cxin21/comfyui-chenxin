# Example: Flux image (v3 schema)

Demonstrates the v3 concept-object schema with rich detail. The
projector walks every concept field and composes a ~200-450 word
paragraph for a fully-detailed spec.

## Spec

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
                identity="a weathered swordswoman",
                appearance="with a scar across her left eyebrow",
                age="in her late thirties",
                pose="weight on her back foot",
                gesture="right hand resting on sword hilt",
                expression="weary but resolute",
                gaze="fixed on the grove edge",
                micro_action="mid-breath, chest barely rising",
                costume=(
                    Costume(
                        garment="robe",
                        material="hand-spun silk",
                        color="iron-oxide vermilion",
                        condition="worn, frayed at the hem",
                        fit="loose, layered, ankle-length",
                        details="embroidered phoenix at the collar",
                    ),
                    Costume(
                        garment="wrist wraps",
                        material="leather",
                        condition="scuffed",
                        details="worn over both wrists",
                    ),
                ),
                props=(
                    Prop(
                        item="sword",
                        material="tarnished steel with jade-hilt pommel",
                        condition="weathered, edge dulled",
                        details="tassel of faded red silk at the guard",
                    ),
                ),
            ),
        ),
        environment=Environment(
            place="the edge of a moonlit bamboo grove",
            spatial="subject stands 6m from a stone lantern at frame right",
            immediate_surroundings=(
                "tall bamboo pressing close on her left",
                "moss-covered rocks at her feet",
            ),
            ambient="still air, slight chill, faint scent of moss",
            atmosphere=Atmosphere(
                haze="thin ground fog 0.3m tall, catching the rim light",
                particles_foreground=("drifting fireflies, four in frame",),
                particles_midground=("motes of pollen",),
                particles_background=("distant falling leaves",),
                wind="faint breeze from the north",
                sky="waning crescent moon, thin cloud cover",
            ),
        ),
        lighting=Lighting(
            key="moonlight from upper right, 4200K cool, soft directional",
            fill="ambient bamboo-filtered, dim teal, low intensity",
            rim="cold rim from behind-left, separates hair from background",
            practical=("single distant stone lantern, warm orange 2200K",),
            quality="soft directional, no harsh shadows",
            shadow_density="deep shadows, crushed blacks",
            contrast="high contrast, low-key",
        ),
        frame=Frame(
            shot="medium shot",
            camera_height="eye-level, slight low",
            camera_angle="three-quarter from the right",
            lens="85mm portrait, f/1.4",
            depth_of_field="shallow, focus locked on her eyes",
            composition="subject on left third, grove recedes right",
            foreground=("out-of-focus bamboo leaves, lower-left",),
            midground=("swordswoman, sword, ground fog",),
            background=("bamboo grove thinning to mist",),
            aspect_ratio="3:2",
            quality=("masterpiece", "8k uhd", "sharp focus"),
        ),
    ),
    constraints=(
        Constraint(must_contain=("vermilion", "silk"), kind="identity",
                   description="vermilion silk robe",
                   anchor_role="costume"),
        Constraint(must_contain=("jade", "steel"), kind="identity",
                   description="jade-hilted steel sword",
                   anchor_role="prop"),
    ),
    style=Style(
        medium="cinematic photography",
        rendering="photoreal",
        art_movement="wuxia xianxia",
        texture="fine film grain",
        palette="jade greens, charcoal blacks, single vermilion accent",
        mood="intimate, melancholic",
        camera_feel="anamorphic, slight halation",
        motion_quality="slow, weighty",
        directives=("matte stock", "low-key tungsten key", "shallow DOF"),
    ),
)

package = compile(spec, "flux")
```

## Output

The Flux projector walks every concept field in canonical order
(subjects -> environment -> lighting -> frame -> style). For the
above spec it produces a ~450 word paragraph covering identity,
appearance, age, expression, gaze, pose, gesture, micro-action,
costume details (color / material / garment / condition / fit /
details), props (material / item / condition / details), place,
spatial layout, immediate surroundings, ambient, atmosphere
(depth-layered haze / particles / wind / sky), key / fill / rim /
practical / quality / shadow_density / contrast lighting, shot /
camera_height / camera_angle / lens / depth_of_field / composition /
foreground / midground / background / aspect_ratio / quality frame,
and a style directive stack (medium / rendering / art_movement /
texture / palette / mood / camera_feel / motion_quality / directives).

## What the v3 schema enables here

- **Costume fields** carry color / material / condition / fit /
  details as named axes; the projector emits "vermilion hand-spun
  silk robe, loose, layered, ankle-length, worn, frayed at the
  hem, embroidered phoenix at the collar" — six renderable
  descriptors, not one flat string.
- **Lighting decomposition** surfaces key / fill / rim / practical
  / quality / shadow_density / contrast. v2 carried only `light=
  "cold rim light from the right"`.
- **Atmosphere** is depth-layered: haze volume, foreground particles,
  midground particles, background particles, wind, sky.
- **Frame** carries shot / camera_height / camera_angle / lens /
  depth_of_field / composition / foreground / midground / background
  / aspect_ratio / quality.
- **Style directives** is a free-form render cue stack
  ("matte stock; low-key tungsten key; shallow DOF") that lives
  alongside the conventional Style fields.
- **Constraint anchor_role** keeps the "vermilion / silk" continuity
  check inside the Costume concept only — preventing drift to
  unrelated text in the spec.

## Why it passes

- **P1 visibility**: every Subject has identity; every concept
  field is a concrete noun or visible descriptor.
- **P3 continuity**: `Constraint(must_contain=("vermilion", "silk"),
  anchor_role="costume")` is satisfied — both tokens appear in the
  Costume concept's rendered text.
- **P4 completeness**: flux requires subjects + action; the spec
  provides both (Subjects with full identity / pose / gesture, and
  action is implicit in pose + gesture + micro_action).
- **P5 density**: not applicable (no transitions for image specs).

## Why it would fail

- Removing all subjects: P1-1 fires.
- Setting `anchor_role="costume"` but the costume lacks both tokens:
  P3-4 fires.
- Setting `frame.shot=""` when the dialect requires a shot:
  P4-4 fires.