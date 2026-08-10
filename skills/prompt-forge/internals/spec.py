"""Specification: the canonical, renderable description of a target world.

Design (v3 redesign, virgin-principle rewrite):

v2 stored every visual signal as a flat string on State. That forced
every concept (garment, material, color, condition, light direction,
camera angle, depth of field, atmosphere layering, foreground subject)
into the same flat string-typed slot. A spec author who knew "the robe
is hand-spun silk, dyed iron-oxide vermilion, frayed at the hem from
years of travel" had no way to express any of those five signals
structurally; the projector could only emit whatever the author had
crammed into one string.

v3 splits every visual concept into a typed dataclass:

  Subject     - who is rendered (identity, appearance, pose, gesture,
                expression, gaze, micro_action, costume, props)
  Costume     - one garment (garment, material, color, condition, fit,
                details)
  Prop        - one object (item, material, condition, details)
  Environment - where (place, spatial, immediate_surroundings, ambient,
                atmosphere)
  Atmosphere  - air (haze, particles_foreground/midground/background,
                wind, sky)
  Lighting    - light (key, fill, rim, practical, quality, shadow_density,
                contrast)
  Frame       - how we capture (shot, camera_height, camera_angle, lens,
                depth_of_field, composition, foreground/midground/
                background, aspect_ratio, quality)

Each concept is a frozen dataclass with empty defaults so a spec can
declare only the concepts it cares about. Concept objects are
independent of one another and unit-testable.

v2''s flat State is gone. v3 still has a State dataclass but it now
holds concept objects, not strings. State is a snapshot at one moment;
for video, every Transition.result is a State.

Style, Constraint, Transition, Reference, Specification stay in
spirit but tighten: Specification gains `negative` (v2 referenced it
but did not define it; bug fixed).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


# ===========================================================================
# Type aliases
# ===========================================================================

Modality = Literal["image", "video"]
H3Flow = Literal["drama", "action", "storyboard"]

ConstraintKind = Literal[
    "identity",     # who/what persists (e.g. "red robe", "jade-hilt sword")
    "direction",    # facing / movement direction (e.g. "facing north")
    "lighting",     # lighting continuity (e.g. "cold rim light")
    "exclusion",    # explicit absence (e.g. "no text on the robe")
    "other",        # catch-all
]


# ===========================================================================
# Subject: who is rendered.
#
# A spec that has multiple subjects (e.g. two swordswomen) carries two
# Subject objects; each has its own costume and props. The first subject
# is conventionally treated as the protagonist.
#
# `identity` is the only field P1 requires. The rest are render-directives
# the projector expands into prose when present.
# ===========================================================================

@dataclass(frozen=True)
class Subject:
    """Who is rendered.

    Invariant A (visibility): `identity` must name a drawable person,
    creature, or entity. Optional fields are render-directives: when
    present, the projector expands them into dialect-appropriate prose;
    when absent, the projector silently skips them.
    """

    identity: str                                       # "a weathered swordswoman"
    appearance: str = ""                                 # "with a scar across her left eyebrow"
    age: str = ""                                        # "in her late thirties"
    pose: str = ""                                       # "weight on back foot"
    gesture: str = ""                                    # "right hand resting on sword hilt"
    expression: str = ""                                 # "weary but resolute"
    gaze: str = ""                                       # "fixed on the grove's edge"
    micro_action: str = ""                               # "mid-breath, chest barely rising"
    costume: tuple = ()                                  # tuple of Costume
    props: tuple = ()                                    # tuple of Prop


@dataclass(frozen=True)
class Costume:
    """One garment.

    `garment` is the only field P1 requires for a non-empty Costume to
    be rendered. Optional fields project material/condition/color/fit
    vocabulary into dialect-appropriate prose.
    """

    garment: str                                         # "robe"
    material: str = ""                                   # "hand-spun silk"
    color: str = ""                                      # "iron-oxide vermilion"
    condition: str = ""                                  # "worn, frayed at the hem"
    fit: str = ""                                        # "loose, layered, ankle-length"
    details: str = ""                                    # "embroidered phoenix at the collar"


@dataclass(frozen=True)
class Prop:
    """One carried or staged object.

    `item` is the only field P1 requires. Optional fields project
    material / condition / detail vocabulary.
    """

    item: str                                            # "sword"
    material: str = ""                                   # "tarnished steel with jade-hilt pommel"
    condition: str = ""                                  # "weathered, edge dulled"
    details: str = ""                                    # "tassel of faded red silk at the guard"


# ===========================================================================
# Environment + Atmosphere: where and what the air is doing.
#
# Atmosphere is split out because haze/particles/wind/sky are layered
# in renderable space (foreground particles, midground mist, background
# sky). Cramming them into one `atmosphere` string makes layered
# rendering impossible.
# ===========================================================================

@dataclass(frozen=True)
class Atmosphere:
    """What the air is doing.

    Fields are layered in render-space: haze (volume), particles
    (foreground/midground/background), wind (motion), sky (background).
    The projector expands each layer into dialect-appropriate prose
    and orders them by depth.
    """

    haze: str = ""                                       # "thin ground fog 0.3m tall, catching rim light"
    particles_foreground: tuple = ()                     # "drifting fireflies, 4 in frame"
    particles_midground: tuple = ()                      # "motes of pollen"
    particles_background: tuple = ()                     # "distant falling leaves"
    wind: str = ""                                       # "faint breeze from the north"
    sky: str = ""                                        # "waning crescent moon, thin cloud cover"


@dataclass(frozen=True)
class Environment:
    """Where the scene takes place.

    `place` is the only field P1 requires. Optional fields add spatial
    specificity that the projector expands into prose.
    """

    place: str = ""                                      # "the edge of a moonlit bamboo grove"
    spatial: str = ""                                    # "subject stands 6m from a stone lantern"
    immediate_surroundings: tuple = ()                   # "tall bamboo pressing close on her left"
    ambient: str = ""                                    # "still air, slight chill, faint scent of moss"
    atmosphere: Atmosphere = Atmosphere()                # depth-layered air


# ===========================================================================
# Lighting: how the scene is lit.
# ===========================================================================

@dataclass(frozen=True)
class Lighting:
    """How the scene is lit.

    All fields are optional. The projector composes them into a
    lighting paragraph; missing fields are silently skipped.
    """

    key: str = ""                # "moonlight from upper right, 4200K cool, soft directional"
    fill: str = ""               # "ambient bamboo-filtered, dim teal, low intensity"
    rim: str = ""                # "cold rim from behind-left, separates hair from background"
    practical: tuple = ()        # "single distant stone lantern, warm orange 2200K"
    quality: str = ""            # "soft directional, no harsh shadows"
    shadow_density: str = ""     # "deep shadows, crushed blacks"
    contrast: str = ""           # "high contrast, low-key"


# ===========================================================================
# Frame: how we capture the scene.
# ===========================================================================

@dataclass(frozen=True)
class Frame:
    """How we capture the scene.

    `shot` is the only field most dialects require (P4). Optional fields
    add depth stratification, focal length, and composition cues.
    """

    shot: str = ""                                       # "medium shot"
    camera_height: str = ""                              # "eye-level, slight low"
    camera_angle: str = ""                               # "three-quarter from the right"
    lens: str = ""                                       # "85mm portrait, f/1.4"
    depth_of_field: str = ""                             # "shallow, focus locked on eyes"
    composition: str = ""                                # "subject on left third, grove recedes right"
    foreground: tuple = ()                               # "out-of-focus bamboo leaves, lower-left"
    midground: tuple = ()                                # "swordswoman, sword, ground fog"
    background: tuple = ()                               # "bamboo grove thinning to mist"
    aspect_ratio: str = ""                               # "3:2"
    quality: tuple = ()                                  # "masterpiece", "8k uhd", "sharp focus"


# ===========================================================================
# State: a snapshot of what's visible at one moment.
# ===========================================================================

@dataclass(frozen=True)
class State:
    """A snapshot of what is visible at one moment.

    Invariant A (visibility): every non-empty concept names something
    a storyboard artist can draw. Empty concepts are allowed and mean
    "not declared" — the projector decides whether to skip them or
    ask the user.
    """

    subjects: tuple = ()                    # tuple of Subject
    environment: Environment = Environment()
    lighting: Lighting = Lighting()
    frame: Frame = Frame()


# ===========================================================================
# Transition: a directed change from one State to another.
# ===========================================================================

@dataclass(frozen=True)
class Transition:
    """A directed change from one State to another over a time range.

    Invariant B (causality): every change has a trigger, an action, and
    a result. Empty values fail at validate-time (P2), not at struct-time.
    """

    start: float
    end: float
    trigger: str
    action: str
    result: State
    camera_motion: str = ""
    sound: str = ""
    dialogue: tuple = ()

    def duration(self) -> float:
        return self.end - self.start


# ===========================================================================
# Constraint: an invariant that must hold across every Transition result.
# ===========================================================================

@dataclass(frozen=True)
class Constraint:
    """An invariant that must hold across every Transition result State.

    `must_contain` is the set of tokens (case-insensitive) that must
    each appear in the result state for the constraint to hold.

    `anchor_role` (v3 addition) names which concept the constraint
    belongs to: `subject`, `costume`, `prop`, `lighting`, `place`.
    When set, the validator only checks tokens appear inside the
    matching concept's rendered text, not just anywhere.
    """

    must_contain: tuple
    kind: ConstraintKind = "other"
    description: str = ""
    anchor_role: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.description and self.must_contain:
            object.__setattr__(
                self, "description", ", ".join(self.must_contain)
            )


# ===========================================================================
# Reference: a reference image attached to the prompt.
# ===========================================================================

@dataclass(frozen=True)
class Reference:
    """A reference image attached to the prompt."""

    index: int
    role: str


# ===========================================================================
# Style: visual-language envelope.
# ===========================================================================

@dataclass(frozen=True)
class Style:
    """Visual-language envelope. Advisory, not load-bearing.

    A Style may change aesthetic vocabulary but cannot change identity,
    plot facts, props, dialogue, or continuity constraints.

    `directives` (v3 addition) is a free-form render directive stack.
    When non-empty, the projector expands each item as its own render
    cue rather than treating the style as four labels.
    """

    medium: str = ""
    rendering: str = ""
    art_movement: str = ""
    texture: str = ""
    palette: str = ""
    mood: str = ""
    camera_feel: str = ""
    motion_quality: str = ""
    directives: tuple = ()


# ===========================================================================
# Specification: the root object.
# ===========================================================================

@dataclass(frozen=True)
class Specification:
    """The complete specification of a target world (image) or world-
    sequence (video).

    v3 fix: `negative` is now a first-class field. v2 referenced it in
    package._join_negative but did not define it on Specification; that
    was a latent bug.
    """

    modality: Modality
    initial_state: State

    transitions: tuple = ()
    constraints: tuple = ()
    style: Optional[Style] = None

    duration: Optional[float] = None
    references: tuple = ()
    literal_text: tuple = ()
    h3_flow: Optional[H3Flow] = None
    extras: tuple = ()
    negative: tuple = ()


def is_video(spec: Specification) -> bool:
    return spec.modality == "video"


def is_image(spec: Specification) -> bool:
    return spec.modality == "image"