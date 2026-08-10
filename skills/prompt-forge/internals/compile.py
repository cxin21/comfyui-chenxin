"""Compile entry point: spec + dialect -> PromptPackage.

Design (v2 redesign, virgin-principle rewrite):

v1 had a separate projector path that injected evidence.locked_facts
as a trailing "Persistence locks:" sentence. v2 removes that special
path. Instead, compile() synthesises Constraint objects from each
locked_fact and appends them to spec.constraints before validation.
The locked facts then flow through the normal P3 enforcement: every
must_contain token must appear in every result state.

This is structurally cleaner:
  - The projector does not need to know about evidence.
  - locked_facts are validated like user-declared constraints.
  - P3 violations surface as errors, not as silently-ignored sentences.

If the locked_fact cannot be expressed as must-contain tokens (e.g.
"the lighting feels moody throughout"), the LLM should declare a
Constraint directly. The compile() synthesised constraints use the
description verbatim as the must_contain tokens; validators can do
their own parsing if they want richer semantics.
"""
from __future__ import annotations

import dataclasses
import re
from typing import Optional

from .dialect import lookup_dialect
from .evidence import CreativeEvidence
from .package import PromptPackage, build_package
from .project import project
from .spec import Constraint, Specification
from .validate import validate


def compile(
    spec: Specification,
    dialect_id: str,
    evidence: CreativeEvidence | None = None,
) -> PromptPackage:
    """Project spec to text, validate, and return a PromptPackage.

    If evidence is supplied and has locked_facts, those facts are
    promoted to Constraints and merged into spec.constraints before
    validation. This way the persistence requirements participate in
    the same P3 enforcement pipeline as user-declared constraints.
    """
    dialect = lookup_dialect(dialect_id)

    # Promote locked_facts to constraints.
    working_spec = _absorb_locked_facts(spec, evidence)

    prompt_text = project(working_spec, dialect.projection)
    violations = validate(working_spec, dialect)
    missing = _compute_missing_facts(working_spec, evidence)
    return build_package(
        spec=working_spec,
        dialect=dialect,
        prompt=prompt_text,
        evidence=evidence or _empty_evidence(),
        violations=violations,
        missing_facts=missing,
    )


def _absorb_locked_facts(
    spec: Specification,
    evidence: CreativeEvidence | None,
) -> Specification:
    """If evidence has locked_facts, synthesise Constraints and merge.

    Each locked fact becomes a Constraint whose must_contain tokens are
    the content words of the fact (filtered for stop words). The
    description is the verbatim fact text, for human-readable rendering.
    """
    if evidence is None:
        return spec
    facts = [f for f in (evidence.locked_facts or ()) if f and f.strip()]
    if not facts:
        return spec
    synth = tuple(
        Constraint(
            must_contain=_tokens_of(fact),
            kind="identity",
            description=fact,
        )
        for fact in facts
    )
    return dataclasses.replace(spec, constraints=spec.constraints + synth)


# Content words to drop when extracting must_contain tokens from a
# locked fact. Conservative; the validator does no further filtering.
_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for",
    "by", "with", "as", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its",
})


def _tokens_of(text: str) -> tuple:
    """Extract must_contain tokens from a free-form fact string.

    Splits on whitespace and punctuation, drops stop words, lower-cases,
    preserves CJK single-character tokens. Returns a tuple (preserves
    order, removes duplicates only if both appear in the same fact).
    """
    if not text:
        return ()
    parts = re.split(r"[\s,.;:!?()\[\]\"']+", text)
    tokens = []
    seen = set()
    for raw in parts:
        if not raw:
            continue
        # Preserve CJK single-character tokens as their own words.
        if re.match(r"^[一-鿿]$", raw):
            tok = raw
        else:
            # ASCII token: keep if length >= 2 and not a stop word.
            tok = raw.strip().lower()
            if len(tok) < 2 or tok in _STOP_WORDS:
                continue
        if tok in seen:
            continue
        seen.add(tok)
        tokens.append(tok)
    return tuple(tokens)


def _state_corpus(state) -> str:
    parts = []
    for subj in state.subjects:
        parts.append(subj.identity)
        if subj.appearance: parts.append(subj.appearance)
        if subj.age: parts.append(subj.age)
        if subj.pose: parts.append(subj.pose)
        if subj.gesture: parts.append(subj.gesture)
        if subj.expression: parts.append(subj.expression)
        if subj.gaze: parts.append(subj.gaze)
        if subj.micro_action: parts.append(subj.micro_action)
        for c in subj.costume:
            for f in (c.garment, c.material, c.color, c.condition, c.fit, c.details):
                if f: parts.append(f)
        for p in subj.props:
            for f in (p.item, p.material, p.condition, p.details):
                if f: parts.append(f)
    e = state.environment
    if e.place: parts.append(e.place)
    if e.spatial: parts.append(e.spatial)
    for s in e.immediate_surroundings: parts.append(s)
    if e.ambient: parts.append(e.ambient)
    a = e.atmosphere
    if a.haze: parts.append(a.haze)
    for layer in (a.particles_foreground, a.particles_midground, a.particles_background):
        for x in layer: parts.append(x)
    if a.wind: parts.append(a.wind)
    if a.sky: parts.append(a.sky)
    l = state.lighting
    for f in (l.key, l.fill, l.rim, l.quality, l.shadow_density, l.contrast):
        if f: parts.append(f)
    for p in l.practical: parts.append(p)
    f = state.frame
    for field in (f.shot, f.camera_height, f.camera_angle, f.lens, f.depth_of_field, f.composition):
        if field: parts.append(field)
    for layer in (f.foreground, f.midground, f.background):
        for x in layer: parts.append(x)
    if f.aspect_ratio: parts.append(f.aspect_ratio)
    for q in f.quality: parts.append(q)
    return " ".join(parts)


def _compute_missing_facts(spec, evidence):
    if evidence is None:
        return ()
    if not evidence.locked_facts:
        return ()
    corpus = _state_corpus(spec.initial_state)
    for t in spec.transitions:
        corpus += " " + _state_corpus(t.result)
        if t.trigger: corpus += " " + t.trigger
        if t.action: corpus += " " + t.action
        if t.camera_motion: corpus += " " + t.camera_motion
        if t.sound: corpus += " " + t.sound
    corpus = corpus.casefold()
    missing = []
    for fact in evidence.locked_facts:
        toks = [tok.casefold() for tok in _tokens_of(fact)]
        if not toks:
            continue
        word_pattern = re.compile(r"\b(?:" + "|".join(re.escape(t) for t in toks) + r")\b")
        if not word_pattern.search(corpus):
            missing.append(fact)
    return tuple(missing)


def _empty_evidence() -> CreativeEvidence:
    return CreativeEvidence(
        schema_version="2.0",
        shared_known=(),
        user_known_agent_unknown=(),
        assistant_known_user_unknown=(),
        joint_unknown=(),
        locked_facts=(),
        continuity_locks=(),
        style_evidence=(),
        asset_refs=(),
        uncertainty=(),
        prohibited_expansion=(),
        source_provenance=(),
    )