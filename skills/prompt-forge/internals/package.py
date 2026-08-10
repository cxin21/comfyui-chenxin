"""PromptPackage envelope.

The contract:
  - Contains exactly: target, dialect, prompt, negative, spec, evidence,
    violations, quality flags. Nothing else.
  - Forbidden fields: workflow, node, hash, gpu, execution, mode, runtime,
    ready_to_execute, profile, slot, transport. These are runtime concerns
    that belong to downstream skills.
  - Forbidden fields may not appear at any depth, including camelCase.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

from .dialect import Dialect
from .evidence import CreativeEvidence
from .spec import (
    Specification, State, Style, Transition, Constraint, Reference,
    Subject, Costume, Prop, Environment, Atmosphere, Lighting, Frame,
)
from .validate import Violation


SCHEMA_VERSION = "3.0"
_FORBIDDEN_KEYS = frozenset({
    "workflow", "node", "hash", "gpu", "execution", "mode", "runtime",
    "ready_to_execute", "profile", "slot", "transport", "settings",
})
_FORBIDDEN_TOKENS = frozenset({
    "workflow", "node", "hash", "gpu", "execution", "mode", "runtime",
})


@dataclass(frozen=True)
class PromptPackage:
    """The output envelope.

    Attributes:
      prompt: model-input text produced by the projection.
      negative: negative prompt (tag-form dialects only).
      ready_for_review: True iff no violations and no missing facts.
    """
    schema_version: str
    target: str
    dialect: str
    prompt: str
    negative: str = ""
    spec: Specification = None  # type: ignore[assignment]
    evidence: CreativeEvidence = None  # type: ignore[assignment]
    violations: tuple = ()
    warnings: tuple = ()
    missing_facts: tuple = ()
    extras: tuple = ()

    @property
    def ready_for_review(self) -> bool:
        return not self.violations and not self.missing_facts

    def to_dict(self) -> dict:
        out: dict = {
            "schema_version": self.schema_version,
            "target": self.target,
            "dialect": self.dialect,
            "prompt": self.prompt,
            "negative": self.negative,
            "spec": _spec_to_dict(self.spec),
            "evidence": _evidence_to_dict(self.evidence),
            "violations": [{
                "code": v.code, "location": v.location, "message": v.message
            } for v in self.violations],
            "warnings": list(self.warnings),
            "missing_facts": list(self.missing_facts),
            "ready_for_review": self.ready_for_review,
        }
        if self.extras:
            out["extras"] = dict(self.extras)
        _strip_forbidden(out)
        return out


def _join_negative(dialect, spec) -> str:
    """Build the negative prompt for tag-form dialects."""
    if not getattr(dialect, "supports_negative", False):
        return ""
    neg = getattr(spec, "negative", ()) or ()
    if not neg:
        return ""
    return ", ".join(str(t).strip() for t in neg if str(t).strip())


def build_package(spec, dialect, prompt, evidence, violations, missing_facts=(), warnings=(), extras=()):
    """Build a PromptPackage from validated parts."""
    _reject_runtime_metadata(spec, "spec")
    _reject_runtime_metadata(evidence, "evidence")
    if extras:
        _reject_runtime_metadata(dict(extras), "extras")
    return PromptPackage(
        schema_version=SCHEMA_VERSION,
        target=spec.modality,
        dialect=dialect.id,
        prompt=prompt,
        spec=spec,
        evidence=evidence,
        violations=violations,
        missing_facts=missing_facts,
        warnings=warnings,
        negative=_join_negative(dialect, spec),
        extras=extras,
    )


def _reject_runtime_metadata(value, path="payload"):
    """Recursively raise on any forbidden key."""
    if isinstance(value, dict):
        for k, child in value.items():
            if _is_forbidden_key(str(k)):
                raise ValueError(f"runtime metadata field is not allowed: {path}.{k}")
            _reject_runtime_metadata(child, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, child in enumerate(value):
            _reject_runtime_metadata(child, f"{path}[{i}]")


def _is_forbidden_key(key):
    """Check raw key and camelCase variants."""
    if key.casefold() in _FORBIDDEN_KEYS:
        return True
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    parts = {p for p in re.split(r"[^a-zA-Z0-9]+", separated.casefold()) if p}
    return bool(parts & _FORBIDDEN_TOKENS)


def _strip_forbidden(value):
    """In-place strip forbidden keys at serialisation time."""
    if isinstance(value, dict):
        for k in list(value.keys()):
            if _is_forbidden_key(str(k)):
                value.pop(k)
        for child in value.values():
            _strip_forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _strip_forbidden(child)


# ===========================================================================
# Serialisers (v3 concept-aware)
# ===========================================================================

def _subject_to_dict(s):
    return {
        "identity": s.identity,
        "appearance": s.appearance,
        "age": s.age,
        "pose": s.pose,
        "gesture": s.gesture,
        "expression": s.expression,
        "gaze": s.gaze,
        "micro_action": s.micro_action,
        "costume": [_costume_to_dict(c) for c in s.costume],
        "props": [_prop_to_dict(p) for p in s.props],
    }


def _costume_to_dict(c):
    return {
        "garment": c.garment,
        "material": c.material,
        "color": c.color,
        "condition": c.condition,
        "fit": c.fit,
        "details": c.details,
    }


def _prop_to_dict(p):
    return {
        "item": p.item,
        "material": p.material,
        "condition": p.condition,
        "details": p.details,
    }


def _atmosphere_to_dict(a):
    return {
        "haze": a.haze,
        "particles_foreground": list(a.particles_foreground),
        "particles_midground": list(a.particles_midground),
        "particles_background": list(a.particles_background),
        "wind": a.wind,
        "sky": a.sky,
    }


def _environment_to_dict(e):
    return {
        "place": e.place,
        "spatial": e.spatial,
        "immediate_surroundings": list(e.immediate_surroundings),
        "ambient": e.ambient,
        "atmosphere": _atmosphere_to_dict(e.atmosphere),
    }


def _lighting_to_dict(l):
    return {
        "key": l.key,
        "fill": l.fill,
        "rim": l.rim,
        "practical": list(l.practical),
        "quality": l.quality,
        "shadow_density": l.shadow_density,
        "contrast": l.contrast,
    }


def _frame_to_dict(f):
    return {
        "shot": f.shot,
        "camera_height": f.camera_height,
        "camera_angle": f.camera_angle,
        "lens": f.lens,
        "depth_of_field": f.depth_of_field,
        "composition": f.composition,
        "foreground": list(f.foreground),
        "midground": list(f.midground),
        "background": list(f.background),
        "aspect_ratio": f.aspect_ratio,
        "quality": list(f.quality),
    }


def _state_to_dict(state):
    return {
        "subjects": [_subject_to_dict(s) for s in state.subjects],
        "environment": _environment_to_dict(state.environment),
        "lighting": _lighting_to_dict(state.lighting),
        "frame": _frame_to_dict(state.frame),
    }


def _style_to_dict(style):
    if style is None:
        return None
    return {
        "medium": style.medium,
        "rendering": style.rendering,
        "art_movement": style.art_movement,
        "texture": style.texture,
        "palette": style.palette,
        "mood": style.mood,
        "camera_feel": style.camera_feel,
        "motion_quality": style.motion_quality,
        "directives": list(style.directives),
    }


def _constraint_to_dict(c):
    return {
        "kind": c.kind,
        "must_contain": list(c.must_contain),
        "description": c.description,
        "anchor_role": c.anchor_role,
    }


def _transition_to_dict(t):
    return {
        "start": t.start,
        "end": t.end,
        "trigger": t.trigger,
        "action": t.action,
        "camera_motion": t.camera_motion,
        "sound": t.sound,
        "dialogue": [{"speaker": s, "line": l} for s, l in t.dialogue],
        "result": _state_to_dict(t.result),
    }


def _spec_to_dict(spec):
    return {
        "modality": spec.modality,
        "initial_state": _state_to_dict(spec.initial_state),
        "transitions": [_transition_to_dict(t) for t in spec.transitions],
        "constraints": [_constraint_to_dict(c) for c in spec.constraints],
        "style": _style_to_dict(spec.style),
        "duration": spec.duration,
        "references": [{"index": r.index, "role": r.role} for r in spec.references],
        "literal_text": list(spec.literal_text),
        "h3_flow": spec.h3_flow,
        "extras": dict(spec.extras) if spec.extras else {},
        "negative": list(spec.negative),
    }


def _evidence_to_dict(ev):
    return {
        "schema_version": ev.schema_version,
        "shared_known": [{"value": f.value, "origin": f.origin} for f in ev.shared_known],
        "user_known_agent_unknown": [{"value": f.value, "origin": f.origin} for f in ev.user_known_agent_unknown],
        "assistant_known_user_unknown": [{"value": f.value, "origin": f.origin} for f in ev.assistant_known_user_unknown],
        "joint_unknown": [{"hypothesis": j.hypothesis, "single_variable": j.single_variable, "success_signal": j.success_signal, "failure_signal": j.failure_signal, "next_data": j.next_data} for j in ev.joint_unknown],
        "locked_facts": list(ev.locked_facts),
        "continuity_locks": [{"kind": k, "description": d} for k, d in ev.continuity_locks],
        "style_evidence": [{"kind": k, "suggestion": s} for k, s in ev.style_evidence],
        "asset_refs": [{"asset_id": a, "role": r} for a, r in ev.asset_refs],
        "uncertainty": list(ev.uncertainty),
        "prohibited_expansion": list(ev.prohibited_expansion),
        "source_provenance": list(ev.source_provenance),
    }