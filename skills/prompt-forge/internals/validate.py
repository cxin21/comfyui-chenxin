"""Validation: enforce the three invariants on a Specification.

Design (v3 redesign, virgin-principle rewrite):

v2 validated flat string fields on State (place, light, camera, etc.).
v3 validates concept objects (Subject, Costume, Prop, Environment,
Atmosphere, Lighting, Frame). Each rule is a proposition: every X
must Y. Rules are layered from coarse to fine:

  P1 - Visibility (invariant A): every Subject has an identity; every
       concept field is drawable.
  P2 - Causality  (invariant B): every Transition has trigger + action + result.
  P3 - Continuity (invariant C): every Constraint holds in every result State.
       v3 adds `anchor_role`: a constraint anchored to a specific concept
       only validates tokens against that concept's rendered text, not
       anywhere in the spec. This stops drift ("red envelope" accidentally
       satisfying a "red robe" constraint).
  P4 - Completeness: the spec satisfies the dialect required dimensions.
  P5 - Density: each field carries enough information to be actionable.

A failure is a Violation(code, location, message). Codes are stable so
docs and tests can reference them (P1-1, P2-3, ...).

v2's free-form `description` substring matching is gone. The validator
reads `must_contain` tokens directly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .dialect import Dialect
from .spec import (
    Specification, State, Transition, Subject,
    Costume, Prop, Environment, Atmosphere, Lighting, Frame,
)


# ===========================================================================
# Lexicons
# ===========================================================================

_PRONOUNS = frozenset({
    "he", "she", "it", "they", "him", "her", "them", "his", "hers", "its",
    "their", "theirs",
    "\u4ed6", "\u5979", "\u5b83", "\u4ed6\u4eec", "\u5979\u4eec",
})

_ABSTRACT_MARKERS = frozenset({
    "feel", "felt", "feeling", "emotion", "mood", "atmosphere",
    "\u611f\u89c9", "\u611f\u53d7", "\u5fc3\u60c5", "\u5fc3\u5883", "\u60c5\u7eea", "\u6c1b\u56f4",
    "want", "wants", "wanted", "believe", "believed", "think", "thinks",
    "\u60f3\u8981", "\u4ee5\u4e3a", "\u76f8\u4fe1", "\u8ba4\u4e3a",
    "seems", "appears", "as if", "like a", "resembles",
    "\u4f3c\u4e4e", "\u4eff\u4f5b", "\u72b9\u5982", "\u7c7b\u4f3c",
    "epic", "awesome", "magical", "mystical",
    "\u58ee\u4e3d", "\u795e\u5947", "\u5947\u8ff9", "\u5e7d\u7075",
})

_PHYSICAL_VERBS = frozenset({
    "stand", "stands", "stood", "walk", "walks", "walked", "step", "steps",
    "run", "runs", "ran", "sit", "sits", "sat", "kneel", "kneels", "knelt",
    "turn", "turns", "turned", "look", "looks", "looked", "gaze", "gazes",
    "hold", "holds", "held", "draw", "draws", "drew", "lift", "lifts",
    "reach", "reaches", "push", "pushes", "pull", "pulls", "throw", "throws",
    "jump", "jumps", "leap", "leaps", "fall", "falls", "fell", "land", "lands",
    "swing", "swings", "block", "blocks", "parry", "dodge", "strike",
    "lean", "leans", "crouch", "crouches", "rise", "rises", "exhale", "inhale",
    "open", "opens", "close", "closes", "place", "places", "pick", "picks",
    "\u7ad9", "\u8d70", "\u8dd1", "\u5750", "\u8df3", "\u8e72", "\u8eba", "\u8f6c",
    "\u62ac", "\u4f4e", "\u4f38", "\u6536", "\u63a8", "\u62c9", "\u6478", "\u62ff",
    "\u62d4", "\u63d2", "\u62a4", "\u62a5", "\u6253",
    "\u8e0f", "\u8df9", "\u8de8", "\u542c", "\u770b", "\u7ffb", "\u6253\u5f00",
    "\u5173\u95ed", "\u653e\u4e0b", "\u63d0\u8d77", "\u62ac\u8d77", "\u4f4e\u5934",
    "\u62ac\u5934", "\u4f4e\u578b", "\u62ac\u773c", "\u4f4e\u773c",
})


@dataclass(frozen=True)
class Violation:
    code: str
    location: str
    message: str


def validate(spec: Specification, dialect: Dialect) -> tuple:
    """Run all five propositions. Returns a tuple (possibly empty)."""
    out = []
    out.extend(_P1_visibility(spec))
    out.extend(_P2_causality(spec))
    out.extend(_P3_continuity(spec))
    out.extend(_P4_completeness(spec, dialect))
    out.extend(_P5_density(spec))
    return tuple(out)


# ===========================================================================
# P1 - Visibility (invariant A)
# ===========================================================================

def _P1_visibility(spec: Specification) -> list:
    out = []
    # Initial state must have at least one subject with identity.
    if not spec.initial_state.subjects:
        out.append(Violation(
            "P1-1", "initial_state.subjects",
            "Initial state must declare at least one Subject.",
        ))
    else:
        for i, subj in enumerate(spec.initial_state.subjects):
            if not subj.identity.strip():
                out.append(Violation(
                    "P1-2", f"initial_state.subjects[{i}].identity",
                    f"Subject {i} must have a non-empty identity.",
                ))
    for i, t in enumerate(spec.transitions):
        if t.trigger and _is_abstract_only(t.trigger):
            out.append(Violation(
                "P1-3", f"transitions[{i}].trigger",
                f"Transition {i} trigger has only abstract markers; needs a physical cause.",
            ))
        if t.action and _is_abstract_only(t.action):
            out.append(Violation(
                "P1-4", f"transitions[{i}].action",
                f"Transition {i} action has only abstract markers; needs a physical action.",
            ))
        if not t.result.subjects:
            out.append(Violation(
                "P1-5", f"transitions[{i}].result.subjects",
                f"Transition {i} result must declare at least one Subject.",
            ))
    return out


# ===========================================================================
# P2 - Causality (invariant B)
# ===========================================================================

def _P2_causality(spec: Specification) -> list:
    out = []
    if spec.modality == "video" and not spec.transitions:
        out.append(Violation(
            "P2-0", "transitions",
            "Video specifications must declare at least one transition.",
        ))
        return out
    for i, t in enumerate(spec.transitions):
        if not t.trigger.strip():
            out.append(Violation(
                "P2-1", f"transitions[{i}].trigger",
                f"Transition {i} trigger must be non-empty (the cause of the change).",
            ))
        if not t.action.strip():
            out.append(Violation(
                "P2-2", f"transitions[{i}].action",
                f"Transition {i} action must be non-empty (what the subject did).",
            ))
        if not t.result.subjects:
            out.append(Violation(
                "P2-3", f"transitions[{i}].result",
                f"Transition {i} result must declare the visible state after the change.",
            ))
    return out


# ===========================================================================
# P3 - Continuity (invariant C)
# ===========================================================================

def _P3_continuity(spec: Specification) -> list:
    out = []
    # Timeline must be contiguous from 0 to duration.
    if spec.modality == "video" and spec.transitions:
        if spec.transitions[0].start != 0:
            out.append(Violation(
                "P3-1", "transitions[0].start",
                f"First transition must start at 0, got {spec.transitions[0].start}.",
            ))
        for i in range(len(spec.transitions) - 1):
            prev_end = spec.transitions[i].end
            next_start = spec.transitions[i + 1].start
            if next_start != prev_end:  # gap or overlap
                out.append(Violation(
                    "P3-2", f"transitions[{i + 1}].start",
                    f"Gap or overlap in timeline: transition {i} ends at {prev_end}, "
                    f"transition {i + 1} starts at {next_start}.",
                ))
        last_end = spec.transitions[-1].end
        if spec.duration is not None and last_end > spec.duration + 1e-6:
            out.append(Violation(
                "P3-3", "transitions[-1].end",
                f"Last transition ends at {last_end} but duration is {spec.duration}.",
            ))
    # Constraint tokens must appear in result states.
    for ci, c in enumerate(spec.constraints):
        if not c.must_contain:
            continue
        states_to_check = [spec.initial_state] + [t.result for t in spec.transitions]
        for si, state in enumerate(states_to_check):
            text = _render_state_for_constraint(state)
            for tok in c.must_contain:
                if c.anchor_role:
                    # Anchor: only check this concept role.
                    concept_text = _render_concept_for_role(state, c.anchor_role)
                    if not _token_present(concept_text, tok):
                        out.append(Violation(
                            "P3-4",
                            f"constraints[{ci}].must_contain[{tok!r}] -> {c.anchor_role}",
                            f"Constraint token {tok!r} anchored to {c.anchor_role!r} "
                            f"not present in state {si}.",
                        ))
                else:
                    if not _token_present(text, tok):
                        out.append(Violation(
                            "P3-5",
                            f"constraints[{ci}].must_contain[{tok!r}]",
                            f"Constraint token {tok!r} not present in state {si}.",
                        ))
    return out


def _render_state_for_constraint(state: State) -> str:
    """Render the State to text for constraint matching."""
    bits = []
    for subj in state.subjects:
        bits.append(subj.identity)
        if subj.appearance:
            bits.append(subj.appearance)
        for c in subj.costume:
            for f in (c.color, c.material, c.garment, c.condition, c.fit, c.details):
                if f:
                    bits.append(f)
        for p in subj.props:
            for f in (p.material, p.item, p.condition, p.details):
                if f:
                    bits.append(f)
    e = state.environment
    if e.place:
        bits.append(e.place)
    if e.spatial:
        bits.append(e.spatial)
    for s in e.immediate_surroundings:
        bits.append(s)
    if e.ambient:
        bits.append(e.ambient)
    a = e.atmosphere
    if a.haze:
        bits.append(a.haze)
    for layer in (a.particles_foreground, a.particles_midground, a.particles_background):
        for p in layer:
            bits.append(p)
    if a.wind:
        bits.append(a.wind)
    if a.sky:
        bits.append(a.sky)
    l = state.lighting
    for f in (l.key, l.fill, l.rim, l.quality, l.shadow_density, l.contrast):
        if f:
            bits.append(f)
    for p in l.practical:
        bits.append(p)
    f = state.frame
    for field in (f.shot, f.camera_height, f.camera_angle, f.lens, f.depth_of_field, f.composition):
        if field:
            bits.append(field)
    for layer in (f.foreground, f.midground, f.background):
        for x in layer:
            bits.append(x)
    return " ".join(bits)


def _render_concept_for_role(state: State, role: str) -> str:
    """Render only the named concept role for anchored constraints."""
    if role == "subject":
        bits = []
        for subj in state.subjects:
            bits.append(subj.identity)
            if subj.appearance:
                bits.append(subj.appearance)
            if subj.pose:
                bits.append(subj.pose)
            if subj.gesture:
                bits.append(subj.gesture)
            if subj.expression:
                bits.append(subj.expression)
            if subj.gaze:
                bits.append(subj.gaze)
        return " ".join(bits)
    if role == "costume":
        bits = []
        for subj in state.subjects:
            for c in subj.costume:
                for f in (c.color, c.material, c.garment, c.condition, c.fit, c.details):
                    if f:
                        bits.append(f)
        return " ".join(bits)
    if role == "prop":
        bits = []
        for subj in state.subjects:
            for p in subj.props:
                for f in (p.material, p.item, p.condition, p.details):
                    if f:
                        bits.append(f)
        return " ".join(bits)
    if role == "place" or role == "environment":
        e = state.environment
        bits = []
        if e.place:
            bits.append(e.place)
        if e.spatial:
            bits.append(e.spatial)
        for s in e.immediate_surroundings:
            bits.append(s)
        return " ".join(bits)
    if role == "lighting":
        l = state.lighting
        bits = []
        for f in (l.key, l.fill, l.rim, l.quality, l.shadow_density, l.contrast):
            if f:
                bits.append(f)
        for p in l.practical:
            bits.append(p)
        return " ".join(bits)
    if role == "atmosphere":
        a = state.environment.atmosphere
        bits = []
        if a.haze:
            bits.append(a.haze)
        for layer in (a.particles_foreground, a.particles_midground, a.particles_background):
            for p in layer:
                bits.append(p)
        if a.wind:
            bits.append(a.wind)
        if a.sky:
            bits.append(a.sky)
        return " ".join(bits)
    # Unknown role: fall back to whole-state render.
    return _render_state_for_constraint(state)


def _token_present(text: str, token: str) -> bool:
    """Whole-word match for ASCII; substring for CJK."""
    if not text or not token:
        return True
    tok = token.casefold().strip()
    if not tok:
        return True
    if re.match(r"^[a-z0-9][a-z0-9'\-]*$", tok):
        return bool(re.search(r"\b" + re.escape(tok) + r"\b", text))
    return tok in text


# ===========================================================================
# P4 - Completeness (dialect-aware)
# ===========================================================================

def _P4_completeness(spec: Specification, dialect: Dialect) -> list:
    out = []
    s = spec.initial_state
    for req in dialect.required:
        req_l = req.lower()
        if req_l in ("subjects", "subject", "identity"):
            if not s.subjects:
                out.append(Violation(
                    "P4-1", "initial_state.subjects",
                    f"Dialect {dialect.id!r} requires subjects; initial state has none.",
                ))
        elif req_l in ("scene", "place", "environment", "place_motion"):
            if not s.environment.place:
                out.append(Violation(
                    "P4-2", "initial_state.environment.place",
                    f"Dialect {dialect.id!r} requires a place; initial state has none.",
                ))
        elif req_l in ("light", "lighting"):
            if not s.lighting.key and not s.lighting.fill and not s.lighting.rim:
                out.append(Violation(
                    "P4-3", "initial_state.lighting",
                    f"Dialect {dialect.id!r} requires lighting; initial state has none.",
                ))
        elif req_l in ("camera", "shot"):
            if not s.frame.shot:
                out.append(Violation(
                    "P4-4", "initial_state.frame.shot",
                    f"Dialect {dialect.id!r} requires a shot; initial state has none.",
                ))
    if spec.modality == "video":
        if not spec.transitions:
            out.append(Violation(
                "P4-5", "transitions",
                "Video specifications must declare at least one transition.",
            ))
        if spec.duration is None or spec.duration <= 0:
            out.append(Violation(
                "P4-6", "duration",
                "Video specifications must declare a positive duration in seconds.",
            ))
    return out


# ===========================================================================
# P5 - Density
# ===========================================================================

def _P5_density(spec: Specification) -> list:
    out = []
    for i, t in enumerate(spec.transitions):
        if len(_tokenize(t.trigger)) < 2:
            out.append(Violation(
                "P5-1", f"transitions[{i}].trigger",
                f"Transition {i} trigger needs at least 2 word-tokens to be actionable.",
            ))
        if len(_tokenize(t.action)) < 2:
            out.append(Violation(
                "P5-2", f"transitions[{i}].action",
                f"Transition {i} action needs at least 2 word-tokens to be actionable.",
            ))
        if spec.modality == "video" and t.duration() < 0.5:
            out.append(Violation(
                "P5-3", f"transitions[{i}]",
                f"Transition {i} duration {t.duration()}s is too short to be actionable (<0.5s).",
            ))
    return out


# ===========================================================================
# Helpers (shared)
# ===========================================================================

def _is_abstract_only(text: str) -> bool:
    """Heuristic: a sentence is abstract-only if it has many abstract
    markers and no physical verb."""
    lower = text.casefold()
    abstract_hits = sum(1 for m in _ABSTRACT_MARKERS if m in lower)
    physical_hits = sum(1 for v in _PHYSICAL_VERBS if v in lower)
    return abstract_hits >= 1 and physical_hits == 0


def _tokenize(text: str) -> list:
    if not isinstance(text, str):
        return []
    s = re.sub(r"([\u4e00-\u9fff])", r" \1 ", text)
    return [t for t in re.split(r"\s+", s) if t and (len(t) >= 2 or re.match(r"^[\u4e00-\u9fff]$", t))]