"""Render a Specification as a human-readable description.

A debug aid - does not affect validation or projection. Lets a developer
or LLM see what a spec looks like without reading dataclass fields.
"""
from __future__ import annotations

from .spec import (
    Specification, State, Style, Transition,
    Subject, Costume, Prop, Environment, Atmosphere, Lighting, Frame,
)


def render_spec(spec: Specification, *, indent: int = 0) -> str:
    pad = "  " * indent
    lines: list[str] = []
    lines.append(f"{pad}Modality: {spec.modality}")
    if spec.duration is not None:
        lines.append(f"{pad}Duration: {spec.duration}s")
    if spec.h3_flow is not None:
        lines.append(f"{pad}H3 flow: {spec.h3_flow}")
    if spec.references:
        refs = ", ".join(f"#{r.index} {r.role}" for r in spec.references)
        lines.append(f"{pad}References: {refs}")
    if spec.literal_text:
        literals = ", ".join(spec.literal_text)
        lines.append(f"{pad}Literal text: {literals}")
    lines.append(f"{pad}Initial state:")
    lines.append(_render_state(spec.initial_state, indent + 1))
    if spec.style is not None:
        lines.append(f"{pad}Style:")
        lines.append(_render_style(spec.style, indent + 1))
    if spec.constraints:
        lines.append(f"{pad}Constraints:")
        for c in spec.constraints:
            lines.append(f"{pad}  [{c.kind}] must_contain={c.must_contain} ('{c.description}')")
    if spec.transitions:
        lines.append(f"{pad}Transitions ({len(spec.transitions)}):")
        for i, t in enumerate(spec.transitions):
            lines.append(_render_transition(i, t, indent + 1))
    return "\n".join(lines)


def _render_state(s: State, indent: int) -> str:
    pad = "  " * indent
    rows = []
    if s.subjects:
        rows.append(f"{pad}# WHO")
        for i, subj in enumerate(s.subjects):
            rows.append(_render_subject(subj, indent))
    if s.environment.place or s.environment.atmosphere.haze or s.environment.immediate_surroundings:
        rows.append(f"{pad}# WHERE")
        if s.environment.place:
            rows.append(f"{pad}  place: {s.environment.place}")
        if s.environment.spatial:
            rows.append(f"{pad}  spatial: {s.environment.spatial}")
        for surr in s.environment.immediate_surroundings:
            rows.append(f"{pad}  surrounding: {surr}")
        if s.environment.ambient:
            rows.append(f"{pad}  ambient: {s.environment.ambient}")
        atm = s.environment.atmosphere
        if atm.haze or atm.particles_foreground or atm.wind or atm.sky:
            rows.append(f"{pad}  atmosphere:")
            if atm.haze:
                rows.append(f"{pad}    haze: {atm.haze}")
            for layer_name, layer in (
                ("particles_foreground", atm.particles_foreground),
                ("particles_midground", atm.particles_midground),
                ("particles_background", atm.particles_background),
            ):
                for p in layer:
                    rows.append(f"{pad}    {layer_name}: {p}")
            if atm.wind:
                rows.append(f"{pad}    wind: {atm.wind}")
            if atm.sky:
                rows.append(f"{pad}    sky: {atm.sky}")
    if s.lighting.key or s.lighting.fill or s.lighting.rim:
        rows.append(f"{pad}# LIGHT")
        if s.lighting.key:
            rows.append(f"{pad}  key: {s.lighting.key}")
        if s.lighting.fill:
            rows.append(f"{pad}  fill: {s.lighting.fill}")
        if s.lighting.rim:
            rows.append(f"{pad}  rim: {s.lighting.rim}")
        for p in s.lighting.practical:
            rows.append(f"{pad}  practical: {p}")
        if s.lighting.quality:
            rows.append(f"{pad}  quality: {s.lighting.quality}")
        if s.lighting.shadow_density:
            rows.append(f"{pad}  shadow_density: {s.lighting.shadow_density}")
        if s.lighting.contrast:
            rows.append(f"{pad}  contrast: {s.lighting.contrast}")
    if s.frame.shot or s.frame.lens or s.frame.composition:
        rows.append(f"{pad}# FRAME")
        if s.frame.shot:
            rows.append(f"{pad}  shot: {s.frame.shot}")
        if s.frame.camera_height:
            rows.append(f"{pad}  camera_height: {s.frame.camera_height}")
        if s.frame.camera_angle:
            rows.append(f"{pad}  camera_angle: {s.frame.camera_angle}")
        if s.frame.lens:
            rows.append(f"{pad}  lens: {s.frame.lens}")
        if s.frame.depth_of_field:
            rows.append(f"{pad}  depth_of_field: {s.frame.depth_of_field}")
        if s.frame.composition:
            rows.append(f"{pad}  composition: {s.frame.composition}")
        for layer_name, layer in (
            ("foreground", s.frame.foreground),
            ("midground", s.frame.midground),
            ("background", s.frame.background),
        ):
            for x in layer:
                rows.append(f"{pad}  {layer_name}: {x}")
        if s.frame.aspect_ratio:
            rows.append(f"{pad}  aspect_ratio: {s.frame.aspect_ratio}")
        for q in s.frame.quality:
            rows.append(f"{pad}  quality: {q}")
    return "\n".join(rows) if rows else f"{pad}(empty)"


def _render_subject(s: Subject, indent: int) -> str:
    pad = "  " * indent
    rows = [f"{pad}subject: {s.identity}"]
    if s.appearance:
        rows.append(f"{pad}  appearance: {s.appearance}")
    if s.age:
        rows.append(f"{pad}  age: {s.age}")
    if s.pose:
        rows.append(f"{pad}  pose: {s.pose}")
    if s.gesture:
        rows.append(f"{pad}  gesture: {s.gesture}")
    if s.expression:
        rows.append(f"{pad}  expression: {s.expression}")
    if s.gaze:
        rows.append(f"{pad}  gaze: {s.gaze}")
    if s.micro_action:
        rows.append(f"{pad}  micro_action: {s.micro_action}")
    for c in s.costume:
        rows.append(_render_costume(c, indent + 1))
    for p in s.props:
        rows.append(_render_prop(p, indent + 1))
    return "\n".join(rows)


def _render_costume(c: Costume, indent: int) -> str:
    pad = "  " * indent
    rows = [f"{pad}costume: {c.garment}"]
    if c.material:
        rows.append(f"{pad}  material: {c.material}")
    if c.color:
        rows.append(f"{pad}  color: {c.color}")
    if c.condition:
        rows.append(f"{pad}  condition: {c.condition}")
    if c.fit:
        rows.append(f"{pad}  fit: {c.fit}")
    if c.details:
        rows.append(f"{pad}  details: {c.details}")
    return "\n".join(rows)


def _render_prop(p: Prop, indent: int) -> str:
    pad = "  " * indent
    rows = [f"{pad}prop: {p.item}"]
    if p.material:
        rows.append(f"{pad}  material: {p.material}")
    if p.condition:
        rows.append(f"{pad}  condition: {p.condition}")
    if p.details:
        rows.append(f"{pad}  details: {p.details}")
    return "\n".join(rows)


def _render_style(s: Style, indent: int) -> str:
    pad = "  " * indent
    rows = []
    for fname in ("medium", "rendering", "art_movement", "texture",
                  "palette", "mood", "camera_feel", "motion_quality"):
        val = getattr(s, fname)
        if val:
            rows.append(f"{pad}{fname}: {val}")
    for d in s.directives:
        rows.append(f"{pad}directive: {d}")
    return "\n".join(rows) if rows else f"{pad}(empty)"


def _render_transition(i: int, t: Transition, indent: int) -> str:
    pad = "  " * indent
    inner_pad = "  " * (indent + 1)
    lines = [f"{pad}{i}: {t.start}--{t.end}s"]
    if t.trigger:
        lines.append(f"{inner_pad}trigger: {t.trigger}")
    if t.action:
        lines.append(f"{inner_pad}action: {t.action}")
    if t.camera_motion:
        lines.append(f"{inner_pad}camera_motion: {t.camera_motion}")
    if t.sound:
        lines.append(f"{inner_pad}sound: {t.sound}")
    if t.dialogue:
        for speaker, line in t.dialogue:
            lines.append(f"{inner_pad}dialogue: {speaker}: \"{line}\"")
    lines.append(f"{inner_pad}result:")
    lines.append(_render_state(t.result, indent + 2))
    return "\n".join(lines)