"""Projection: Specification -> model-input text.

v4 redesign (virgin-principle rewrite): the narrative weaver.

v3 made each dialect own its composition order, but kept shared
_render_* helpers that emitted field-label debug prose ("Place: ...",
"Key light: ...", "Fill: ..."). Three consequences followed: every
prose dialect read like a labeled data dump; prose dialects were
near-identical (flux ~= krea_2 ~= gpt_image ~= nano_banana); tag
dialects left whole descriptive sentences glued into single tags; and
most video dialects dropped trigger/camera_motion/sound entirely,
emitting only the bare action.

v4 inverts the renderer's job. It WEAVES concepts into dialect-native
narrative:

  - Never emits field labels in natural-prose dialects. "Place:" /
    "Key light:" are debug aids belonging to render.py, not model
    input. Labels survive only where a dialect's native form IS a
    structured brief (recraft design brief, gpt_image creative brief,
    h3 seven-section Chinese brief).
  - Subjects get subordinate structure (identity - state clause), not
    an 8-element comma waterfall.
  - Lighting is one cohesive lighting sentence, not seven labeled
    fragments.
  - Frame is a coherent camera sentence (the v3 frame block was
    grammatically broken: missing periods, phrases glued together).
  - Every video transition is a full causal beat:
        When [trigger], [action] (camera ...; sound ...; now [delta]).
    No video dialect drops trigger/camera/sound anymore.
  - Video result states render only the changed attributes (delta),
    not a full re-dump of environment + lighting per beat.
  - Tag dialects atomize descriptive phrases (split on commas) and
    derive structural tags (1girl/solo/outdoors/night/holding/weapon)
    plus the Pony quality stack.

Three first-principle propositions:
  1. Projection != concatenation. Concepts are rewritten, not listed.
  2. Concepts are not islands. The subject sits in the environment;
     light falls on materials; the camera frames the subject.
  3. Dialect != field set. Each model has its own idiom; aliases that
     share a projector (nano_banana == gpt_image in v3) are a bug.

Conventions:
  - Pure functions: same spec -> same text, no I/O.
  - Never invent facts: empty field -> nothing emitted.
  - Video transitions always carry the full causal beat.
"""
from __future__ import annotations

import re
from typing import Optional

from .spec import (
    Specification, State, Style, Transition, Subject, Costume, Prop,
    Environment, Atmosphere, Lighting, Frame,
)


# ===========================================================================
# Shared string plumbing
# ===========================================================================

def _jn(parts, sep=", "):
    """Join non-empty stripped string parts."""
    return sep.join(
        p for p in (str(x).strip() for x in parts if x and str(x).strip())
        if p
    )


def _and(items):
    """Comma-join except last entry joined by ' and '."""
    items = [str(x).strip() for x in items if x and str(x).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _cap(s):
    """Capitalize first character."""
    s = (s or "").strip()
    return s[:1].upper() + s[1:] if s else s


def _lc(s):
    """Lowercase first character (for mid-sentence joining)."""
    s = (s or "").strip()
    return s[:1].lower() + s[1:] if s else s


def _ensure_period(text):
    """Ensure the prompt ends with a single period and a trailing space."""
    text = (text or "").rstrip()
    if not text:
        return text
    if text.endswith((".", "!", "?")):
        return text + " "
    return text + ". "


# Preposition-aware place phrasing (preserved from v3)
_PLACE_PREPOSITIONS = frozenset({
    "at", "in", "inside", "outside", "on", "under", "over", "above",
    "below", "near", "next", "beside", "beyond", "behind", "between",
    "through", "across", "along", "around", "against", "deeper",
    "within", "without", "upon", "into", "onto", "from", "toward",
    "towards", "off", "amid", "amongst", "past",
})
_ARTICLES = frozenset({"a", "an", "the", "this", "that", "these", "those"})


def _place_phrase(place):
    s = (place or "").strip()
    if not s:
        return ""
    head = s.split(maxsplit=1)[0].lower().rstrip(",.;:")
    if head in _PLACE_PREPOSITIONS:
        return s
    return "at " + s


def _camera_phrase(camera):
    s = (camera or "").strip()
    if not s:
        return ""
    head = s.split(maxsplit=1)[0].lower().rstrip(",.;:")
    if head in _ARTICLES:
        return "viewed from " + s
    if head == "extreme":
        return "viewed from an " + s
    return "viewed from a " + s


# ===========================================================================
# Concept weavers (v4: narrative, no field labels)
# ===========================================================================

def _weave_costume(c):
    """One costume as a renderable descriptor."""
    head = _jn([c.color, c.material, c.garment], " ")
    bits = [head] if head else []
    if c.fit:
        bits.append(c.fit)
    if c.condition:
        bits.append(c.condition)
    if c.details:
        bits.append(c.details)
    return _jn(bits, ", ")


def _weave_prop(p):
    """One prop as a renderable descriptor."""
    head = _jn([p.material, p.item], " ")
    if not head:
        return ""
    bits = [head]
    if p.condition:
        bits.append(p.condition)
    if p.details:
        bits.append(p.details)
    return _jn(bits, ", ")


def _weave_subjects(subjects):
    """One or more Subject objects as narrative prose with subordinate
    structure: identity - state clause, wearing ..., holding ...."""
    if not subjects:
        return ""
    out = []
    for subj in subjects:
        ident = _jn([subj.identity, subj.appearance, subj.age], ", ")
        state = []
        if subj.expression:
            state.append("expression " + subj.expression)
        if subj.gaze:
            state.append("gaze " + subj.gaze)
        if subj.pose:
            state.append(subj.pose)
        if subj.gesture:
            state.append(subj.gesture)
        if subj.micro_action:
            state.append(subj.micro_action)
        clause = ident
        if state:
            clause += " - " + _jn(state, ", ")
        if subj.costume:
            rendered = [r for r in (_weave_costume(c) for c in subj.costume) if r]
            if rendered:
                clause += ", wearing " + _jn(rendered, "; ")
        if subj.props:
            rendered = [r for r in (_weave_prop(p) for p in subj.props) if r]
            if rendered:
                clause += ", holding " + _jn(rendered, ", ")
        out.append(clause + ".")
    return " ".join(out)


def _weave_environment(env):
    """Environment as scene-setting prose. No 'Place:'/'Spatial:' labels."""
    bits = []
    if env.place:
        bits.append(_cap(env.place))
    if env.spatial:
        bits.append(env.spatial)
    if env.immediate_surroundings:
        bits.append(_jn(env.immediate_surroundings, ", "))
    if env.ambient:
        bits.append(env.ambient)
    atm = env.atmosphere
    ab = []
    if atm.haze:
        ab.append(atm.haze)
    if atm.particles_foreground:
        ab.append(_jn(atm.particles_foreground) + " in the foreground")
    if atm.particles_midground:
        ab.append(_jn(atm.particles_midground) + " in the midground")
    if atm.particles_background:
        ab.append(_jn(atm.particles_background) + " in the distance")
    if atm.wind:
        ab.append(atm.wind)
    if atm.sky:
        ab.append("the sky holds " + atm.sky)
    if ab:
        bits.append(_jn(ab, ", "))
    if not bits:
        return ""
    return _jn(bits, ", ") + "."


def _weave_lighting(lit):
    """Lighting as one cohesive lighting sentence. No Key:/Fill:/Rim: labels."""
    bits = []
    if lit.key:
        bits.append(lit.key)
    if lit.fill:
        bits.append(lit.fill + " fills the shadows")
    if lit.rim:
        bits.append(lit.rim)
    if lit.practical:
        bits.append(_jn(lit.practical) + " glows as a practical source")
    if not bits:
        return ""
    s = _cap(_jn(bits, ", ")) + "."
    tail = []
    if lit.quality:
        tail.append(lit.quality)
    if lit.shadow_density:
        tail.append(lit.shadow_density)
    if lit.contrast:
        tail.append(lit.contrast)
    if tail:
        s += " " + _cap(_jn(tail, ", ")) + "."
    return s


def _weave_frame(frame):
    """Frame as a coherent camera sentence. Fixes v3's broken concatenation."""
    bits = []
    if frame.shot:
        bits.append(_cap(frame.shot))
    if frame.camera_height:
        bits.append(frame.camera_height)
    if frame.camera_angle:
        bits.append("angled " + frame.camera_angle)
    if frame.lens:
        bits.append("on " + frame.lens)
    if frame.depth_of_field:
        bits.append("with " + frame.depth_of_field)
    if frame.composition:
        bits.append(frame.composition)
    s = _jn(bits, ", ") + "." if bits else ""
    depth = []
    if frame.foreground:
        depth.append("in the foreground, " + _jn(frame.foreground))
    if frame.midground:
        depth.append("in the midground, " + _jn(frame.midground))
    if frame.background:
        depth.append("in the background, " + _jn(frame.background))
    if depth:
        s += " " + _cap(_jn(depth, "; ")) + "."
    tail = []
    if frame.aspect_ratio:
        tail.append(frame.aspect_ratio + " aspect")
    if frame.quality:
        tail.append(_jn(frame.quality, ", "))
    if tail:
        s += " " + _jn(tail, ", ") + "."
    return s


def _weave_style(style):
    """Style as a directive-stack prose clause."""
    if style is None:
        return ""
    bits = []
    if style.medium:
        bits.append(style.medium)
    if style.rendering:
        bits.append(style.rendering + " rendering")
    if style.art_movement:
        bits.append(style.art_movement + " aesthetic")
    if style.texture:
        bits.append(style.texture)
    if style.palette:
        bits.append("a palette of " + style.palette)
    if style.mood:
        bits.append(style.mood + " mood")
    if style.camera_feel:
        bits.append(style.camera_feel)
    if style.motion_quality:
        bits.append(style.motion_quality + " motion")
    if style.directives:
        bits.append("; ".join(style.directives))
    return _cap(_jn(bits, ", ")) + "." if bits else ""


def _weave_state_full(state):
    """Full state render (subjects + environment + lighting + frame).

    Used for video opening frames and explicit ending states where the
    whole visible snapshot is wanted.
    """
    parts = []
    if state.subjects:
        parts.append(_weave_subjects(state.subjects))
    env = _weave_environment(state.environment)
    if env:
        parts.append(env)
    lit = _weave_lighting(state.lighting)
    if lit:
        parts.append(lit)
    fr = _weave_frame(state.frame)
    if fr:
        parts.append(fr)
    return " ".join(parts)


def _weave_state_delta(state):
    """Render only the changed/dynamic attributes of a result state.

    Video beats must not re-dump the full environment + lighting per
    transition (v3 did, producing 'Place: ...' three times). Only the
    subject's dynamic attributes and any new rim/lighting cue surface.
    """
    bits = []
    for subj in state.subjects:
        if subj.expression:
            bits.append("expression " + subj.expression)
        if subj.gaze:
            bits.append("gaze " + subj.gaze)
        if subj.pose:
            bits.append(subj.pose)
        if subj.gesture:
            bits.append(subj.gesture)
        if subj.micro_action:
            bits.append(subj.micro_action)
        for c in subj.costume:
            if c.details:
                bits.append(c.details)
        for p in subj.props:
            if p.details:
                bits.append(p.details)
    if state.lighting.rim:
        bits.append("rim " + state.lighting.rim)
    return _jn(bits, ", ")


def _weave_beat(t):
    """Project a Transition as a full causal beat.

    When [trigger], [action] (camera ...; sound ...; dialogue; now [delta]).
    Every video dialect uses this so trigger/camera/sound are never dropped.
    """
    parts = []
    if t.trigger:
        parts.append("When " + t.trigger.rstrip(".") + ",")
    if t.action:
        parts.append(t.action)
    beat = " ".join(parts)
    tail = []
    if t.camera_motion:
        tail.append("camera " + t.camera_motion)
    if t.sound and t.sound.strip():
        tail.append("sound: " + t.sound.strip())
    dialogue = list(t.dialogue or ())
    if dialogue:
        spoken = "; ".join(
            (sp or "voice") + ' says "' + line + '"'
            for sp, line in dialogue if sp or line
        )
        if spoken:
            tail.append(spoken)
    delta = _weave_state_delta(t.result)
    if delta:
        tail.append("now " + delta)
    if tail:
        beat += " (" + _jn(tail, "; ") + ")"
    return beat + "." if beat else ""


# ===========================================================================
# Tag atomization (anima / sd_1_5 / sdxl tail)
# ===========================================================================

def _atomize(s):
    """Split a descriptive phrase into atomic danbooru tags.

    Strips leading articles/prepositions, splits on commas/semicolons
    (so 'mid-breath, chest barely rising' -> ['mid-breath',
    'chest_barely_rising'], not one glued tag), underscore-joins.
    """
    s = (s or "").strip()
    if not s:
        return []
    s = re.sub(r"^(with|a|an|the|in|of|on)\s+", "", s, flags=re.IGNORECASE).strip()
    return [
        re.sub(r"\s+", "_", c.strip().lower())
        for c in re.split(r"[,;]", s)
        if c.strip()
    ]


_FEMALE_CUES = ("woman", "girl", "swordswoman", "lady", "witch", "queen",
                "princess", "maid", "she", "nun", "nurse")
_MALE_CUES = ("man", "boy", "swordsman", "warrior", "king", "knight", "soldier")


def _structural_subject_tags(subjects):
    out = []
    for subj in subjects:
        idl = subj.identity.lower()
        if any(c in idl for c in _FEMALE_CUES):
            out.extend(["1girl", "solo"])
        elif any(c in idl for c in _MALE_CUES):
            out.extend(["1boy", "solo"])
        else:
            out.append("character")
        for c in subj.costume:
            if c.garment:
                out.append("clothes")
        for p in subj.props:
            if p.item:
                it = p.item.lower()
                if any(w in it for w in ("sword", "blade", "saber", "katana")):
                    out.extend(["weapon", "holding", "sword"])
                elif any(w in it for w in ("bow", "staff", "spear", "lance", "axe")):
                    out.extend(["weapon", "holding"])
                elif any(w in it for w in ("shield", "armor", "helmet")):
                    out.append("equipment")
                else:
                    out.append("holding")
    return out


def _structural_env_tags(env):
    out = []
    pl = env.place.lower() if env.place else ""
    if any(w in pl for w in ("grove", "forest", "bamboo", "woods", "jungle", "field", "meadow")):
        out.extend(["outdoors", "scenery", "forest"])
    elif any(w in pl for w in ("room", "hall", "interior", "chamber", "studio", "tavern")):
        out.append("indoors")
    elif any(w in pl for w in ("street", "city", "town", "road", "alley")):
        out.extend(["outdoors", "scenery", "city"])
    elif pl:
        out.extend(["outdoors", "scenery"])
    if any(w in pl for w in ("night", "moonlit", "moon", "dark", "midnight", "dusk")):
        out.append("night")
    elif any(w in pl for w in ("dawn", "sun", "morning", "daylight", "noon", "sunlit")):
        out.append("day")
    return out


def _field_atoms(spec):
    """All concept fields atomized into tags, canonical order."""
    s = spec.initial_state
    tags = []
    for subj in s.subjects:
        for bit in (subj.identity, subj.appearance, subj.age, subj.pose,
                    subj.gesture, subj.expression, subj.gaze, subj.micro_action):
            tags.extend(_atomize(bit))
        for c in subj.costume:
            for f in (c.color, c.material, c.garment, c.fit, c.condition, c.details):
                tags.extend(_atomize(f))
        for p in subj.props:
            for f in (p.material, p.item, p.condition, p.details):
                tags.extend(_atomize(f))
    e = s.environment
    tags.extend(_atomize(e.place))
    tags.extend(_atomize(e.spatial))
    for x in e.immediate_surroundings:
        tags.extend(_atomize(x))
    tags.extend(_atomize(e.ambient))
    a = e.atmosphere
    for f in (a.haze, a.wind, a.sky):
        tags.extend(_atomize(f))
    for layer in (a.particles_foreground, a.particles_midground, a.particles_background):
        for x in layer:
            tags.extend(_atomize(x))
    l = s.lighting
    for f in (l.key, l.fill, l.rim, l.quality, l.shadow_density, l.contrast):
        tags.extend(_atomize(f))
    for x in l.practical:
        tags.extend(_atomize(x))
    f = s.frame
    for field in (f.shot, f.camera_height, f.camera_angle, f.lens,
                  f.depth_of_field, f.composition):
        tags.extend(_atomize(field))
    tags.extend(_atomize(f.aspect_ratio))
    for layer in (f.foreground, f.midground, f.background):
        for x in layer:
            tags.extend(_atomize(x))
    for q in f.quality:
        tags.extend(_atomize(q))
    if spec.style:
        st = spec.style
        for field in (st.medium, st.rendering, st.art_movement, st.texture,
                      st.palette, st.mood, st.camera_feel, st.motion_quality):
            tags.extend(_atomize(field))
        for d in st.directives:
            tags.extend(_atomize(d))
    return tags


def _dedupe(tags):
    seen = set()
    out = []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


# ===========================================================================
# Image dialects (15)
# ===========================================================================

def flux(spec):
    """Flux: single rich narrative paragraph; subject woven into environment."""
    s = spec.initial_state
    sentences = []
    subj = _weave_subjects(s.subjects)
    env = _weave_environment(s.environment)
    if env and subj:
        sentences.append(env.rstrip(".") + ", where " + _lc(subj))
    elif subj:
        sentences.append(subj)
    elif env:
        sentences.append(env)
    lit = _weave_lighting(s.lighting)
    if lit:
        sentences.append(lit)
    fr = _weave_frame(s.frame)
    if fr:
        sentences.append(fr)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            sentences.append(st)
    return _ensure_period(" ".join(sentences))


def krea_2(spec):
    """Krea-2: ultra-detailed narrative; each concept its own sentence; quoted text literal."""
    s = spec.initial_state
    sentences = []
    subj = _weave_subjects(s.subjects)
    if subj:
        sentences.append(subj)
    env = _weave_environment(s.environment)
    if env:
        sentences.append(env)
    lit = _weave_lighting(s.lighting)
    if lit:
        sentences.append(lit)
    fr = _weave_frame(s.frame)
    if fr:
        sentences.append(fr)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            sentences.append(st)
    lit_txt = list(spec.literal_text or ())
    if lit_txt:
        sentences.append('Render the text "' + ", ".join(lit_txt) + '" literally.')
    return _ensure_period(" ".join(sentences))


def qwen_image(spec):
    """Qwen Image: structured task framing with visible-text placeholders."""
    s = spec.initial_state
    blocks = ["Generate an image of"]
    subj = _weave_subjects(s.subjects)
    if subj:
        blocks.append(_lc(subj).rstrip("."))
    env = _weave_environment(s.environment)
    if env:
        blocks.append(_lc(env))
    lit = _weave_lighting(s.lighting)
    if lit:
        blocks.append(_lc(lit))
    fr = _weave_frame(s.frame)
    if fr:
        blocks.append(_lc(fr))
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            blocks.append(_lc(st))
    lit_txt = list(spec.literal_text or ())
    if lit_txt:
        blocks.append("with the visible text " + _and(lit_txt))
    return _ensure_period(" ".join(blocks))


def qwen_image_edit(spec):
    """Qwen Image Edit: structured edit instruction."""
    parts = ["Edit task:"]
    if spec.transitions:
        change = spec.transitions[0].action.strip()
        if change:
            parts.append("Change: " + change + ".")
    if spec.initial_state.subjects:
        parts.append("Target: " + _and([s.identity for s in spec.initial_state.subjects]) + ".")
    for c in spec.constraints:
        if c.description:
            parts.append("Preserve: " + c.description + ".")
    return " ".join(parts)


def anima(spec):
    """Anima: atomized Danbooru tags + structural tags + Pony quality stack."""
    s = spec.initial_state
    tags = ["score_9", "score_8_up", "score_7_up", "source_anime"]
    tags.extend(_structural_subject_tags(s.subjects))
    tags.extend(_structural_env_tags(s.environment))
    tags.extend(_field_atoms(spec))
    return ", ".join(_dedupe(tags))


def sdxl(spec):
    """SDXL: prose lead + tag tail (hybrid)."""
    s = spec.initial_state
    prose = []
    subj = _weave_subjects(s.subjects)
    if subj:
        prose.append(subj)
    env = _weave_environment(s.environment)
    if env:
        prose.append(env)
    lit = _weave_lighting(s.lighting)
    if lit:
        prose.append(lit)
    fr = _weave_frame(s.frame)
    if fr:
        prose.append(fr)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            prose.append(st)
    text = _ensure_period(" ".join(prose))
    tags = _structural_subject_tags(s.subjects) + _structural_env_tags(s.environment)
    tags.extend(["masterpiece", "best_quality", "highres"])
    if spec.style and spec.style.rendering:
        ra = _atomize(spec.style.rendering)
        if ra:
            tags.append(ra[0])
    tags = _dedupe(tags)
    if tags:
        text += " | " + ", ".join(tags)
    return text


def sd_1_5(spec):
    """SD 1.5: atomized weighted comma tags + structural tags."""
    s = spec.initial_state
    tags = _structural_subject_tags(s.subjects)
    tags.extend(_structural_env_tags(s.environment))
    tags.extend(_field_atoms(spec))
    tags.extend(["masterpiece", "best_quality", "highres"])
    return ", ".join(_dedupe(tags))


def gpt_image(spec):
    """GPT Image: goal-first structured creative brief."""
    s = spec.initial_state
    parts = []
    if spec.style and spec.style.medium:
        parts.append("Create a " + spec.style.medium + ".")
    else:
        parts.append("Create a detailed image.")
    if s.subjects:
        parts.append("Subject: " + _weave_subjects(s.subjects))
    env = _weave_environment(s.environment)
    if env:
        parts.append(_cap(env))
    lit = _weave_lighting(s.lighting)
    if lit:
        parts.append(lit)
    fr = _weave_frame(s.frame)
    if fr:
        parts.append(fr)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    for c in spec.constraints:
        if c.description:
            parts.append("Constraint: " + c.description + ".")
    return _ensure_period(" ".join(parts))


def hidream_i1(spec):
    """HiDream I1: subject-first natural language; style as final clause."""
    s = spec.initial_state
    sentences = []
    subj = _weave_subjects(s.subjects)
    if subj:
        sentences.append(subj)
    env = _weave_environment(s.environment)
    if env:
        sentences.append(env)
    lit = _weave_lighting(s.lighting)
    if lit:
        sentences.append(lit)
    fr = _weave_frame(s.frame)
    if fr:
        sentences.append(fr)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            sentences.append(st)
    return _ensure_period(" ".join(sentences))


def nano_banana(spec):
    """Nano Banana: rich descriptive prose, composition-forward."""
    s = spec.initial_state
    sentences = []
    subj = _weave_subjects(s.subjects)
    if subj:
        sentences.append(subj)
    fr = _weave_frame(s.frame)
    if fr:
        sentences.append(fr)
    env = _weave_environment(s.environment)
    if env:
        sentences.append(env)
    lit = _weave_lighting(s.lighting)
    if lit:
        sentences.append(lit)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            sentences.append(st)
    return _ensure_period(" ".join(sentences))


def ideogram(spec):
    """Ideogram: typography-aware brief; quoted text rendered literally."""
    s = spec.initial_state
    blocks = []
    lit_txt = list(spec.literal_text or ())
    if lit_txt:
        blocks.append("Image with the text " + _and(lit_txt) + ".")
    subj = _weave_subjects(s.subjects)
    if subj:
        blocks.append(subj)
    env = _weave_environment(s.environment)
    if env:
        blocks.append(env)
    lit = _weave_lighting(s.lighting)
    if lit:
        blocks.append(lit)
    fr = _weave_frame(s.frame)
    if fr:
        blocks.append(fr)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            blocks.append(st)
    return _ensure_period(" ".join(blocks))


def recraft(spec):
    """Recraft: design brief (asset_type, layout, style, palette)."""
    s = spec.initial_state
    parts = []
    asset = "illustration"
    if spec.style and spec.style.medium:
        asset = spec.style.medium
    parts.append(_cap(asset) + ".")
    layout = []
    if s.frame.composition:
        layout.append(s.frame.composition)
    elif s.frame.shot:
        layout.append(s.frame.shot)
    if layout:
        parts.append("Layout: " + _jn(layout) + ".")
    if s.subjects:
        parts.append("Subject: " + _weave_subjects(s.subjects))
    env = _weave_environment(s.environment)
    if env:
        parts.append(_cap(env))
    style_bits = []
    if spec.style:
        if spec.style.rendering:
            style_bits.append(spec.style.rendering)
        if spec.style.art_movement:
            style_bits.append(spec.style.art_movement)
        if spec.style.texture:
            style_bits.append(spec.style.texture)
    if style_bits:
        parts.append("Style: " + _jn(style_bits) + ".")
    if spec.style and spec.style.palette:
        parts.append("Palette: " + spec.style.palette + ".")
    return _ensure_period(" ".join(parts))


def grok_image(spec):
    """Grok Image: five-part visual brief (intent, subject, composition, look)."""
    s = spec.initial_state
    parts = []
    if spec.style and spec.style.mood:
        parts.append("A " + spec.style.mood + " visual brief.")
    else:
        parts.append("Visual brief.")
    if s.subjects:
        parts.append("Subject: " + _weave_subjects(s.subjects))
    env = _weave_environment(s.environment)
    if env:
        parts.append(_cap(env))
    fr = _weave_frame(s.frame)
    if fr:
        parts.append(fr)
    lit = _weave_lighting(s.lighting)
    if lit:
        parts.append(lit)
    look_bits = []
    if spec.style:
        if spec.style.rendering:
            look_bits.append(spec.style.rendering)
        if spec.style.art_movement:
            look_bits.append(spec.style.art_movement)
        if spec.style.palette:
            look_bits.append(spec.style.palette)
    if look_bits:
        parts.append("Look: " + _jn(look_bits) + ".")
    return _ensure_period(" ".join(parts))


def ernie_image(spec):
    """ERNIE Image: instruction + visual spec combined."""
    s = spec.initial_state
    parts = ["Render an image of the following scene."]
    if s.subjects:
        parts.append(_weave_subjects(s.subjects))
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    lit = _weave_lighting(s.lighting)
    if lit:
        parts.append(lit)
    fr = _weave_frame(s.frame)
    if fr:
        parts.append(fr)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def flux_1_kontext(spec):
    """Flux Kontext: edit instruction with preservation list."""
    parts = ["Edit task:"]
    if spec.transitions:
        change = spec.transitions[0].action.strip()
        if change:
            parts.append("Change: " + change + ".")
    if spec.initial_state.subjects:
        parts.append("Target: " + _and([s.identity for s in spec.initial_state.subjects]) + ".")
    for c in spec.constraints:
        if c.description:
            parts.append("Preserve: " + c.description + ".")
    return " ".join(parts)


# ===========================================================================
# Video dialects (16) - all use _weave_beat for full causal chains
# ===========================================================================

def wan(spec):
    """Wan 2.x: cinematic shot + causal motion beats, no state duplication."""
    s = spec.initial_state
    parts = []
    head = (_cap(s.frame.shot) if s.frame.shot else "Cinematic shot") + " of"
    subj = _weave_subjects(s.subjects)
    if subj:
        opening = head + " " + _lc(subj).rstrip(".")
    else:
        opening = head.rstrip(" of")
    env_o = []
    if s.environment.place:
        env_o.append(s.environment.place)
    atm = s.environment.atmosphere
    if atm.haze:
        env_o.append(atm.haze)
    if atm.wind:
        env_o.append(atm.wind)
    if env_o:
        opening += ", at " + _jn(env_o, ", ")
    parts.append(opening + ".")
    lb = []
    if s.lighting.key:
        lb.append(s.lighting.key)
    if s.lighting.rim:
        lb.append(s.lighting.rim)
    if lb:
        parts.append(_cap(_jn(lb, ", ")) + ".")
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def ltx(spec):
    """LTX 2.3: opening frame -> motion beats -> camera -> light."""
    s = spec.initial_state
    parts = []
    opening = _weave_state_full(s)
    if opening:
        parts.append("Opening frame: " + _lc(opening) + ".")
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if s.frame.shot:
        parts.append("Camera: " + s.frame.shot + ".")
    if s.frame.lens:
        parts.append("Lens: " + s.frame.lens + ".")
    lit = _weave_lighting(s.lighting)
    if lit:
        parts.append(lit)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def kling(spec):
    """Kling: subject + causal motion + place + camera + finish."""
    s = spec.initial_state
    parts = []
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj.rstrip("."))
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    lit = _weave_lighting(s.lighting)
    if lit:
        parts.append(lit)
    fr = _weave_frame(s.frame)
    if fr:
        parts.append(fr)
    if spec.transitions:
        ending = _weave_state_full(spec.transitions[-1].result)
        if ending:
            parts.append("ending with " + _lc(ending))
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(", ".join(parts))


def sora(spec):
    """Sora 2: shotlist form with explicit beats."""
    s = spec.initial_state
    parts = []
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj.rstrip("."))
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    if s.frame.shot:
        parts.append(_cap(s.frame.shot) + ".")
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(". ".join(parts))


def veo(spec):
    """Veo: cinematic sequence with temporal change cues."""
    s = spec.initial_state
    parts = []
    if s.frame.shot:
        parts.append(_cap(_camera_phrase(s.frame.shot)))
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(_lc(subj).rstrip("."))
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    lit = _weave_lighting(s.lighting)
    if lit:
        parts.append(lit)
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(". ".join(parts))


def seedance(spec):
    """Seedance: opening -> action beats -> camera -> ending."""
    s = spec.initial_state
    parts = []
    if s.frame.shot:
        parts.append(_cap(s.frame.shot) + " of")
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(_lc(subj).rstrip("."))
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if s.frame.lens:
        parts.append("Lens: " + s.frame.lens + ".")
    lit = _weave_lighting(s.lighting)
    if lit:
        parts.append(lit)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def hunyuan(spec):
    """Hunyuan Video: detailed natural language motion description."""
    s = spec.initial_state
    parts = []
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj.rstrip("."))
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if s.frame.shot:
        parts.append(s.frame.shot + ".")
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def hailuo(spec):
    """Hailuo: subject + causal action + place + camera."""
    s = spec.initial_state
    parts = []
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj.rstrip("."))
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    if s.frame.shot:
        parts.append("Camera: " + s.frame.shot + ".")
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(". ".join(parts))


def runway(spec):
    """Runway Gen-3/4: content + motion + finish."""
    s = spec.initial_state
    parts = []
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj.rstrip("."))
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def luma(spec):
    """Luma: subject + action + place + temporal finish."""
    s = spec.initial_state
    parts = []
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj.rstrip("."))
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    if spec.transitions:
        ending = _weave_state_delta(spec.transitions[-1].result)
        if ending:
            parts.append("finishing with " + ending + ".")
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def vidu(spec):
    """Vidu: subject + camera + causal sequence."""
    s = spec.initial_state
    parts = []
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj.rstrip("."))
    if s.frame.shot:
        parts.append(s.frame.shot + ".")
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def pika(spec):
    """Pika: subject + motion + effect + camera + finish."""
    s = spec.initial_state
    parts = []
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj.rstrip("."))
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if s.frame.shot:
        parts.append(s.frame.shot + ".")
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def svd(spec):
    """SVD: image-conditioned; subject motion + ending state."""
    s = spec.initial_state
    parts = []
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj.rstrip("."))
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def pixverse(spec):
    """PixVerse: structured motion + camera + place."""
    s = spec.initial_state
    parts = []
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj.rstrip("."))
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if s.frame.shot:
        parts.append(s.frame.shot + ".")
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


def gemini_omni_flash(spec):
    """Gemini Omni Flash: goal + scene + action + continuity."""
    s = spec.initial_state
    parts = ["Goal: render a coherent motion sequence."]
    env = _weave_environment(s.environment)
    if env:
        parts.append(env)
    subj = _weave_subjects(s.subjects)
    if subj:
        parts.append(subj)
    for t in spec.transitions:
        b = _weave_beat(t)
        if b:
            parts.append(b)
    if spec.constraints:
        ct = _and([c.description for c in spec.constraints if c.description])
        if ct:
            parts.append("Continuity: " + ct + ".")
    if spec.style:
        st = _weave_style(spec.style)
        if st:
            parts.append(st)
    return _ensure_period(" ".join(parts))


# ===========================================================================
# MiniMax H3: seven-section Chinese production brief
# ===========================================================================

def minimax_h3(spec):
    """MiniMax H3: seven-section Chinese production brief."""
    _QH = "："
    _JH = "。"
    _DH = "，"
    _FH = "；"

    sections = []
    duration = int(spec.duration) if spec.duration else 15
    aspect = spec.initial_state.frame.aspect_ratio or "16:9"
    sections.append(
        f"生成一段{duration}秒、{aspect}、原生立体声的MiniMax H3电影级文戏短片。"
    )
    s = spec.initial_state
    subject_summary = _and([subj.identity for subj in s.subjects]) if s.subjects else "角色"
    if spec.transitions:
        first_trigger = spec.transitions[0].trigger.strip() if spec.transitions[0].trigger else ""
        last_subject = _and([subj.identity for subj in spec.transitions[-1].result.subjects]) if spec.transitions[-1].result.subjects else subject_summary
        core = f"一次由{first_trigger}触发、最终导致{last_subject}的因果链。"
        sections.append("核心概念" + _QH + core)
    if spec.constraints:
        constraint_text = _FH.join(c.description for c in spec.constraints if c.description) + _JH
        sections.append("人物与场景锁定" + _QH + constraint_text)

    timeline_lines = ["时间线" + _QH]
    for t in spec.transitions:
        start_str = "{:g}".format(t.start) if t.start != int(t.start) else str(int(t.start))
        end_str = "{:g}".format(t.end) if t.end != int(t.end) else str(int(t.end))
        line = start_str + "-" + end_str + "秒" + _QH + t.action.strip()
        if t.trigger:
            line = t.trigger.strip() + _DH + line
        if t.camera_motion:
            line += "（镜头" + t.camera_motion + "）"
        if t.sound and t.sound.strip():
            line += "（声音" + t.sound.strip() + "）"
        timeline_lines.append(line)
    if len(timeline_lines) > 1:
        sections.append("\n".join(timeline_lines))

    camera_bits = []
    if s.frame.shot:
        camera_bits.append(s.frame.shot)
    if s.frame.lens:
        camera_bits.append(s.frame.lens)
    if s.frame.composition:
        camera_bits.append(s.frame.composition)
    if camera_bits:
        camera_text = _DH.join(camera_bits) + _JH
    else:
        camera_text = "按新信息与动作因果切长镜，保持人物站位、视线与运动方向连续。"
    sections.append("摄影与剪辑" + _QH + camera_text)

    if spec.style:
        style_bits = []
        if spec.style.medium:
            style_bits.append(spec.style.medium)
        if spec.style.palette:
            style_bits.append(spec.style.palette + "调")
        if spec.style.texture:
            style_bits.append(spec.style.texture)
        if spec.style.motion_quality:
            style_bits.append("运动观感" + spec.style.motion_quality)
        style_text = _DH.join(style_bits) + _JH if style_bits else "电影级写实质感。"
    else:
        style_text = "电影级写实质感。"
    sections.append("视觉风格" + _QH + style_text)

    sounds = [t.sound for t in spec.transitions if t.sound.strip()]
    if sounds:
        sound_text = _FH.join(sounds) + _JH
    else:
        sound_text = "原生立体声呈现环境声与克制音乐。"
    sections.append("声音设计" + _QH + sound_text)

    if spec.transitions:
        ending = _weave_state_full(spec.transitions[-1].result)
        ending_text = (ending + _JH) if ending else "完成动作。"
    else:
        ending_text = "完成画面。"
    sections.append("结尾结果" + _QH + ending_text)
    return "\n".join(sections)


# ===========================================================================
# Dispatch
# ===========================================================================

_PROJECTIONS = {
    # Image (15)
    "flux": flux,
    "flux_1_kontext": flux_1_kontext,
    "anima": anima,
    "qwen_image": qwen_image,
    "qwen_image_edit": qwen_image_edit,
    "sdxl": sdxl,
    "sd_1_5": sd_1_5,
    "gpt_image": gpt_image,
    "krea_2": krea_2,
    "hidream_i1": hidream_i1,
    "nano_banana": nano_banana,
    "ideogram": ideogram,
    "recraft": recraft,
    "grok_image": grok_image,
    "ernie_image": ernie_image,
    # Video (16)
    "wan": wan,
    "ltx": ltx,
    "kling": kling,
    "sora": sora,
    "veo": veo,
    "seedance": seedance,
    "hunyuan": hunyuan,
    "minimax_h3": minimax_h3,
    "hailuo": hailuo,
    "runway": runway,
    "luma": luma,
    "vidu": vidu,
    "pika": pika,
    "svd": svd,
    "pixverse": pixverse,
    "gemini_omni_flash": gemini_omni_flash,
}


def project(spec, projection_id):
    """Resolve projection short name, dispatch to the function."""
    fn = _PROJECTIONS.get(projection_id)
    if fn is None:
        from .dialect import lookup_dialect
        try:
            dialect = lookup_dialect(projection_id)
        except ValueError:
            raise ValueError("unknown projection: " + repr(projection_id))
        fn = _PROJECTIONS.get(dialect.projection)
        if fn is None:
            raise ValueError("unknown projection: " + repr(projection_id))
    return fn(spec)


def available_projections():
    return tuple(_PROJECTIONS.keys())
