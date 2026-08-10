# Example: MiniMax H3 (Chinese production brief, v3 schema)

The MiniMax H3 brief format is unchanged in v3; the format itself is
the value. The v3 schema populates the brief sections through the
concept-object projectors.

## Spec

```python
from internals.spec import (
    Specification, State, Style, Constraint, Transition,
    Subject, Costume, Environment, Lighting, Frame,
)
from internals.compile import compile

spec = Specification(
    modality="video",
    initial_state=State(
        subjects=(
            Subject(
                identity="\u4e00\u4f4d\u7a7f\u7ea2\u8863\u7684\u5251\u5ba2",
                costume=(Costume(garment="\u8863\u88c5", color="\u7ea2"),),
                props=("\u7389\u5251",),
            ),
        ),
        environment=Environment(place="\u6708\u5149\u4e0b\u7684\u7af9\u6797\u8fb9\u7f18"),
        lighting=Lighting(key="\u51b7\u8272\u8f6e\u5ed3\u5149"),
        frame=Frame(shot="\u4e2d\u666f", aspect_ratio="16:9"),
    ),
    transitions=(
        Transition(
            start=0.0, end=5.0,
            trigger="\u98ce\u8d77",
            action="\u5251\u5ba2\u8f6c\u8eab\u9762\u5411\u7af9\u6797",
            result=State(
                subjects=(
                    Subject(
                        identity="\u4e00\u4f4d\u7a7f\u7ea2\u8863\u7684\u5251\u5ba2",
                        costume=(Costume(garment="\u8863\u88c5", color="\u7ea2"),),
                    ),
                ),
            ),
        ),
    ),
    duration=5.0,
    h3_flow="drama",
)

package = compile(spec, "minimax_h3")
```

## Output

The H3 projector emits a seven-section Chinese production brief:

1. Header (\u751f\u6210\u4e00\u6bb55\u79d2...)
2. \u6838\u5fc3\u6982\u5ff5 (core concept)
3. \u4eba\u7269\u4e0e\u573a\u666f\u9501\u5b9a (locks, if any)
4. \u65f6\u95f4\u7ebf (timeline)
5. \u6444\u5f71\u4e0e\u526a\u8f91 (camera / editing)
6. \u89c6\u89c9\u98ce\u683c (visual style)
7. \u58f0\u97f3\u8bbe\u8ba1 (sound design)
8. \u7ed3\u5c3e\u7ed3\u679c (ending result)

## v3 schema in action

- **Subject** with `costume=tuple[Costume, ...]` is rendered by the
  H3 projector as the subject summary in the brief header.
- **Environment** supplies `place` for the header and the camera
  block.
- **Lighting** supplies `key` for the lighting block (if present).
- **Frame** supplies `shot` and `aspect_ratio` for the camera block.

## Notes

- Anima camera workflow asset is fixed (see project AGENTS.md);
  prompt-forge only owns the prompt text.
- H3 has no native negative prompt; express exclusions via
  `Constraint(kind="exclusion", anchor_role=...)`.
- h3_flow must be "drama", "action", or "storyboard".

## Variations

- Set `h3_flow="action"` for martial arts scenes (15+ transitions).
- Set `h3_flow="storyboard"` with a nine-grid reference (9 fixed
  transitions mapping to the grid).