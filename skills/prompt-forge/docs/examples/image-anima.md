# Example: Anima (Danbooru tag form, v3 schema)

Demonstrates the v3 concept-object schema rendered as Danbooru
underscore-joined tags. Every concept field is walked and tagged.

## Spec

```python
from internals.spec import (
    Specification, State, Style,
    Subject, Costume, Prop, Environment, Atmosphere, Lighting, Frame,
)
from internals.compile import compile

spec = Specification(
    modality="image",
    initial_state=State(
        subjects=(
            Subject(
                identity="1girl",
                appearance="long_hair, blue_eyes",
                pose="standing, weight on back foot",
                gesture="hand on sword hilt",
                expression="weary",
                costume=(
                    Costume(garment="dress", material="silk",
                            color="vermilion", condition="worn"),
                ),
                props=(
                    Prop(item="sword", material="jade-hilted steel",
                         condition="weathered"),
                ),
            ),
        ),
        environment=Environment(
            place="moonlit_bamboo_grove",
            atmosphere=Atmosphere(
                haze="thin_ground_fog",
                particles_foreground=("drifting_fireflies",),
                sky="waning_crescent_moon",
            ),
        ),
        lighting=Lighting(
            key="moonlight_from_upper_right",
            rim="cold_rim_from_behind-left",
            shadow_density="deep_shadows_crushe_dblacks",
        ),
        frame=Frame(
            shot="medium_shot",
            lens="85mm_portrait",
            depth_of_field="shallow",
            composition="rule_of_thirds",
            aspect_ratio="3:2",
            quality=("masterpiece", "sharp_focus"),
        ),
    ),
    negative=("lowres", "bad_anatomy", "blurry"),
    style=Style(medium="cinematic_photography", art_movement="wuxia_xianxia"),
)

package = compile(spec, "anima")
```

## Output

```
score_9, 1girl, long_hair, blue_eyes, standing_weight_on_back_foot,
hand_on_sword_hilt, weary_expression, vermilion, silk, dress, worn,
jade-hilted_steel, sword, weathered, moonlit_bamboo_grove,
thin_ground_fog, drifting_fireflies, waning_crescent_moon,
moonlight_from_upper_right, cold_rim_from_behind-left,
deep_shadows_crushe_dblacks, medium_shot, 85mm_portrait, shallow,
rule_of_thirds, 3:2, masterpiece, sharp_focus, cinematic_photography,
wuxia_xianxia
```

```
package.negative = "lowres, bad_anatomy, blurry"
```

## What the v3 schema enables here

- Every concept field becomes its own tag. v2 emitted 7 tags; v3
  emits ~30 for the same spec.
- Style fields (medium, art_movement, palette, ...) tag-emit too.
- `negative` field (v3 fix) is now emitted as a comma-joined tag
  string. v2 referenced `spec.negative` in package but did not
  define it; that bug is fixed.

## Notes

- Anima is the only dialect that emits a `score_9` prefix.
- v3 tags are deterministic; the same spec always produces the same
  output.
- Composing habits: subjects before environment before lighting
  before frame before style is the canonical ordering for tag-form
  dialects.