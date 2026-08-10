"""CLI: compile a v3 compile-envelope into a PromptPackage dict.

Design (v3 redesign, virgin-principle rewrite):

v2 had `prompt_compile.py` as a CLI entry that took a v2-style draft
(`positive` / `negative` / `positive_zh` / `positive_en` /
`global_prompt` / `timeline_segments` / `dialogue_attribution` /
`continuity_locks`) and only validated it. v3 takes a different
envelope (`spec` + `evidence` + `dialect_id`) and synthesizes prose
via the concept-object projector. The CLI surface is intentionally
similar (`python -m internals.prompt_compile --stdin`) so the MCP
bridge (`comfyui_chenxin_mcp.engine.prompt_forge`) keeps working with a JSON
payload on stdin and a JSON PromptPackage on stdout.

v2 prompt_compile called `validate_draft` (no projection). v3 calls
`compile(spec, dialect_id, evidence)` (project + validate). The two
philosophies are mutually exclusive; we keep v3's.

v3 prompt_compile also accepts an optional `--envelope` flag that
enables a more verbose output (full spec dump, all concept fields).

Conventions:
  - All input validation happens in this module (not the bridge).
  - Forbidden metadata is rejected before reaching spec / evidence.
  - Returns a PromptPackage dict (schema_version 3.0) on stdout.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Optional

from .compile import compile as compile_spec
from .dialect import lookup_dialect
from .evidence import normalize_evidence
from .package import PromptPackage, build_package
from .spec import (
    Atmosphere, Constraint, Costume, Environment, Frame, Lighting,
    Prop, Reference, State, Style, Subject, Specification, Transition,
)


def _parse_subject(payload: dict) -> Subject:
    return Subject(
        identity=str(payload.get("identity", "")).strip(),
        appearance=str(payload.get("appearance", "")).strip(),
        age=str(payload.get("age", "")).strip(),
        pose=str(payload.get("pose", "")).strip(),
        gesture=str(payload.get("gesture", "")).strip(),
        expression=str(payload.get("expression", "")).strip(),
        gaze=str(payload.get("gaze", "")).strip(),
        micro_action=str(payload.get("micro_action", "")).strip(),
        costume=tuple(_parse_costume(c) for c in payload.get("costume", []) or ()),
        props=tuple(_parse_prop(p) for p in payload.get("props", []) or ()),
    )


def _parse_costume(payload: dict) -> Costume:
    return Costume(
        garment=str(payload.get("garment", "")).strip(),
        material=str(payload.get("material", "")).strip(),
        color=str(payload.get("color", "")).strip(),
        condition=str(payload.get("condition", "")).strip(),
        fit=str(payload.get("fit", "")).strip(),
        details=str(payload.get("details", "")).strip(),
    )


def _parse_prop(payload: dict) -> Prop:
    return Prop(
        item=str(payload.get("item", "")).strip(),
        material=str(payload.get("material", "")).strip(),
        condition=str(payload.get("condition", "")).strip(),
        details=str(payload.get("details", "")).strip(),
    )


def _parse_atmosphere(payload: dict) -> Atmosphere:
    return Atmosphere(
        haze=str(payload.get("haze", "")).strip(),
        particles_foreground=tuple(str(x).strip() for x in payload.get("particles_foreground", []) or () if str(x).strip()),
        particles_midground=tuple(str(x).strip() for x in payload.get("particles_midground", []) or () if str(x).strip()),
        particles_background=tuple(str(x).strip() for x in payload.get("particles_background", []) or () if str(x).strip()),
        wind=str(payload.get("wind", "")).strip(),
        sky=str(payload.get("sky", "")).strip(),
    )


def _parse_environment(payload: dict) -> Environment:
    atmosphere_payload = payload.get("atmosphere", {}) or {}
    return Environment(
        place=str(payload.get("place", "")).strip(),
        spatial=str(payload.get("spatial", "")).strip(),
        immediate_surroundings=tuple(str(x).strip() for x in payload.get("immediate_surroundings", []) or () if str(x).strip()),
        ambient=str(payload.get("ambient", "")).strip(),
        atmosphere=_parse_atmosphere(atmosphere_payload) if isinstance(atmosphere_payload, dict) else Atmosphere(),
    )


def _parse_lighting(payload: dict) -> Lighting:
    return Lighting(
        key=str(payload.get("key", "")).strip(),
        fill=str(payload.get("fill", "")).strip(),
        rim=str(payload.get("rim", "")).strip(),
        practical=tuple(str(x).strip() for x in payload.get("practical", []) or () if str(x).strip()),
        quality=str(payload.get("quality", "")).strip(),
        shadow_density=str(payload.get("shadow_density", "")).strip(),
        contrast=str(payload.get("contrast", "")).strip(),
    )


def _parse_frame(payload: dict) -> Frame:
    return Frame(
        shot=str(payload.get("shot", "")).strip(),
        camera_height=str(payload.get("camera_height", "")).strip(),
        camera_angle=str(payload.get("camera_angle", "")).strip(),
        lens=str(payload.get("lens", "")).strip(),
        depth_of_field=str(payload.get("depth_of_field", "")).strip(),
        composition=str(payload.get("composition", "")).strip(),
        foreground=tuple(str(x).strip() for x in payload.get("foreground", []) or () if str(x).strip()),
        midground=tuple(str(x).strip() for x in payload.get("midground", []) or () if str(x).strip()),
        background=tuple(str(x).strip() for x in payload.get("background", []) or () if str(x).strip()),
        aspect_ratio=str(payload.get("aspect_ratio", "")).strip(),
        quality=tuple(str(x).strip() for x in payload.get("quality", []) or () if str(x).strip()),
    )


def _parse_state(payload: dict) -> State:
    return State(
        subjects=tuple(_parse_subject(s) for s in payload.get("subjects", []) or ()),
        environment=_parse_environment(payload.get("environment", {}) or {}),
        lighting=_parse_lighting(payload.get("lighting", {}) or {}),
        frame=_parse_frame(payload.get("frame", {}) or {}),
    )


def _parse_constraint(payload: dict) -> Constraint:
    must_contain = payload.get("must_contain", []) or ()
    if not isinstance(must_contain, (list, tuple)):
        raise ValueError("constraint.must_contain must be a list of strings")
    must_contain = tuple(str(x).strip() for x in must_contain if str(x).strip())
    kind = str(payload.get("kind", "other")).strip() or "other"
    description = str(payload.get("description", "")).strip()
    anchor_role = payload.get("anchor_role")
    if anchor_role is not None:
        anchor_role = str(anchor_role).strip() or None
    return Constraint(
        must_contain=must_contain,
        kind=kind,  # type: ignore[arg-type]
        description=description,
        anchor_role=anchor_role,
    )


def _parse_transition(payload: dict) -> Transition:
    start = payload.get("start")
    end = payload.get("end")
    if not isinstance(start, (int, float)):
        raise ValueError("transition.start must be a number")
    if not isinstance(end, (int, float)):
        raise ValueError("transition.end must be a number")
    if end <= start:
        raise ValueError(f"transition.end ({end}) must be > start ({start})")
    trigger = str(payload.get("trigger", "")).strip()
    action = str(payload.get("action", "")).strip()
    if not trigger:
        raise ValueError("transition.trigger must be non-empty")
    if not action:
        raise ValueError("transition.action must be non-empty")
    result_payload = payload.get("result", {}) or {}
    if not isinstance(result_payload, dict):
        raise ValueError("transition.result must be an object")
    return Transition(
        start=float(start),
        end=float(end),
        trigger=trigger,
        action=action,
        result=_parse_state(result_payload),
        camera_motion=str(payload.get("camera_motion", "")).strip(),
        sound=str(payload.get("sound", "")).strip(),
        dialogue=tuple((d.get("speaker", ""), d.get("line", "")) for d in payload.get("dialogue", []) or () if isinstance(d, dict)),
    )


def _parse_style(payload: dict) -> Style:
    if not payload:
        return None
    return Style(
        medium=str(payload.get("medium", "")).strip(),
        rendering=str(payload.get("rendering", "")).strip(),
        art_movement=str(payload.get("art_movement", "")).strip(),
        texture=str(payload.get("texture", "")).strip(),
        palette=str(payload.get("palette", "")).strip(),
        mood=str(payload.get("mood", "")).strip(),
        camera_feel=str(payload.get("camera_feel", "")).strip(),
        motion_quality=str(payload.get("motion_quality", "")).strip(),
        directives=tuple(str(x).strip() for x in payload.get("directives", []) or () if str(x).strip()),
    )


def _parse_reference(payload: dict) -> Reference:
    index = payload.get("index")
    role = str(payload.get("role", "")).strip()
    if not isinstance(index, int):
        raise ValueError("reference.index must be an integer")
    if not role:
        raise ValueError("reference.role must be non-empty")
    return Reference(index=index, role=role)


def _parse_spec(payload: dict) -> Specification:
    modality = str(payload.get("modality", "")).strip()
    if modality not in ("image", "video"):
        raise ValueError(f"spec.modality must be 'image' or 'video', got {modality!r}")
    initial_state_payload = payload.get("initial_state", {}) or {}
    if not isinstance(initial_state_payload, dict):
        raise ValueError("spec.initial_state must be an object")
    spec = Specification(
        modality=modality,  # type: ignore[arg-type]
        initial_state=_parse_state(initial_state_payload),
        transitions=tuple(_parse_transition(t) for t in payload.get("transitions", []) or ()),
        constraints=tuple(_parse_constraint(c) for c in payload.get("constraints", []) or ()),
        style=_parse_style(payload.get("style", {}) or {}),
        duration=payload.get("duration"),
        references=tuple(_parse_reference(r) for r in payload.get("references", []) or ()),
        literal_text=tuple(str(x).strip() for x in payload.get("literal_text", []) or () if str(x).strip()),
        h3_flow=payload.get("h3_flow"),
        extras=tuple((str(k), v) for k, v in (payload.get("extras", {}) or {}).items()),
        negative=tuple(str(x).strip() for x in payload.get("negative", []) or () if str(x).strip()),
    )
    return spec


# ===========================================================================
# Forbidden metadata guard
# ===========================================================================

_FORBIDDEN_KEYS = frozenset({
    "workflow", "node", "hash", "gpu", "execution", "mode", "runtime",
    "ready_to_execute", "profile", "slot", "transport", "settings",
})


import re as _re
_SPLIT_KEY_RE = _re.compile(r"[^a-zA-Z0-9]+")


def _is_runtime_metadata_key(key) -> bool:
    """True if a key is forbidden runtime metadata, in any case/separator form.

    Catches: workflow, workflowHash, workflow_hash, nodeId, node_id,
    executionState, gpuMemory, runtimeOptions, etc.
    """
    if not isinstance(key, str):
        return False
    if key.casefold() in _FORBIDDEN_KEYS:
        return True
    separated = _re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    parts = {p for p in _SPLIT_KEY_RE.split(separated.casefold()) if p}
    return bool(parts & _FORBIDDEN_KEYS)


def _check_envelope(envelope: dict) -> None:
    """Reject envelopes that carry runtime metadata at any depth."""
    def walk(value, path: str):
        if isinstance(value, dict):
            for k, child in value.items():
                if _is_runtime_metadata_key(k):
                    raise ValueError(
                        f"runtime metadata field is not allowed: {path}.{k}"
                    )
                walk(child, f"{path}.{k}")
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}[{i}]")
        elif isinstance(value, tuple):
            for i, child in enumerate(value):
                walk(child, f"{path}[{i}]")
    walk(envelope, "envelope")


def _is_forbidden_top_key(key) -> bool:
    return _is_runtime_metadata_key(key)


# ===========================================================================
# Entry
# ===========================================================================

def compile_envelope(envelope: dict) -> dict:
    """Compile a v3 envelope into a PromptPackage dict.

    Envelope shape:
      {
        "evidence":   <CreativeEvidence payload dict>,
        "spec":       <Specification payload dict>,
        "dialect_id": <string>,
      }
    """
    if not isinstance(envelope, dict):
        raise ValueError("envelope must be an object")
    # Forbidden metadata is a hard error: must be reported before any other
    # field-shape check so callers see the actual problem.
    _check_envelope(envelope)
    allowed = {"evidence", "spec", "dialect_id"}
    unknown = sorted(set(envelope) - allowed)
    if unknown:
        # Distinguish runtime-metadata leakage from arbitrary unknown fields.
        for k in unknown:
            if _is_forbidden_top_key(k):
                raise ValueError(
                    f"runtime metadata field is not allowed: envelope.{k}"
                )
        raise ValueError(f"envelope has unexpected fields: {', '.join(unknown)}")
    for key in ("evidence", "spec", "dialect_id"):
        if key not in envelope:
            raise ValueError(f"envelope missing required field: {key}")
    if not isinstance(envelope["dialect_id"], str) or not envelope["dialect_id"].strip():
        raise ValueError("envelope.dialect_id must be a non-empty string")

    evidence = normalize_evidence(envelope["evidence"])
    spec = _parse_spec(envelope["spec"])

    # Modality check on the dialect.
    dialect = lookup_dialect(envelope["dialect_id"], modality=spec.modality)
    pkg = compile_spec(spec, dialect.id, evidence)
    return pkg.to_dict()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="JSON envelope path")
    source.add_argument("--stdin", action="store_true",
                        help="read JSON envelope from stdin")
    parser.add_argument("--pretty", action="store_true",
                        help="pretty-print the output JSON")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
        envelope = json.loads(raw)
        package = compile_envelope(envelope)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    indent = 2 if args.pretty else None
    print(json.dumps(package, ensure_ascii=False, indent=indent))
    return 0 if package["ready_for_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())