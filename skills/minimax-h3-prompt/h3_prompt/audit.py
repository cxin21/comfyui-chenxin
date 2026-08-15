"""Read-only MiniMax-H3 audit facade."""

from __future__ import annotations

from collections.abc import Callable

from .common import (
    H3AuditError,
    audit_dialogue_and_visible_text,
    audit_reference_labels,
    audit_shot_execution,
    audit_sound_music_separation,
    parse_shots,
)
from .contracts import H3Ref2VAAuthoringRequest, H3T2VAAuthoringRequest
from .facts import FactLedger


def audit_t2va(request: H3T2VAAuthoringRequest) -> tuple[str, ...]:
    ledger = FactLedger(request.facts)
    segments = (
        *request.integrated_multimodal_description,
        *request.overall_soundscape,
        *request.non_diegetic_music,
    )
    ledger.validate_segments(segments)
    description = " ".join(item.text for item in request.integrated_multimodal_description)
    soundscape = " ".join(item.text for item in request.overall_soundscape) or "N/A"
    music = " ".join(item.text for item in request.non_diegetic_music) or "N/A"
    findings: list[str] = []
    shots = _capture(
        findings,
        lambda: parse_shots(
            description,
            duration_seconds=request.duration_seconds,
            declared_shot_count=request.shot_count,
        ),
    )
    if shots is not None:
        _capture(findings, lambda: audit_shot_execution(shots, ledger))
    _capture(findings, lambda: audit_dialogue_and_visible_text(description, ledger))
    _capture(findings, lambda: audit_sound_music_separation(soundscape, music))
    return tuple(findings)


def audit_ref2va(request: H3Ref2VAAuthoringRequest) -> tuple[str, ...]:
    ledger = FactLedger(request.facts)
    segments = (
        *request.subject_definitions,
        *request.summary,
        *request.retention_analysis,
        *request.detailed_description,
        *request.overall_soundscape,
        *request.non_diegetic_music,
    )
    ledger.validate_segments(segments)
    fields = _ref_fields(request)
    findings: list[str] = []
    _capture(
        findings,
        lambda: audit_reference_labels(
            fields["subject_definitions"],
            fields["retention_analysis"] + "\n" + fields["detailed_description"],
            request.references,
        ),
    )
    shots = _capture(
        findings,
        lambda: parse_shots(
            fields["detailed_description"],
            duration_seconds=request.duration_seconds,
            declared_shot_count=request.shot_count,
        ),
    )
    if shots is not None:
        _capture(findings, lambda: audit_shot_execution(shots, ledger))
    _capture(
        findings,
        lambda: audit_dialogue_and_visible_text(fields["detailed_description"], ledger),
    )
    _capture(
        findings,
        lambda: audit_sound_music_separation(
            fields["overall_soundscape"], fields["non_diegetic_music"]
        ),
    )
    return tuple(findings)


def ref_fields(request: H3Ref2VAAuthoringRequest) -> dict[str, str]:
    return _ref_fields(request)


def _ref_fields(request: H3Ref2VAAuthoringRequest) -> dict[str, str]:
    return {
        "subject_definitions": "\n".join(item.text for item in request.subject_definitions),
        "summary": " ".join(item.text for item in request.summary),
        "retention_analysis": "\n".join(item.text for item in request.retention_analysis),
        "detailed_description": "\n".join(item.text for item in request.detailed_description),
        "overall_soundscape": " ".join(item.text for item in request.overall_soundscape) or "N/A",
        "non_diegetic_music": " ".join(item.text for item in request.non_diegetic_music) or "N/A",
    }


def _capture(findings: list[str], operation: Callable[[], object]):
    try:
        return operation()
    except H3AuditError as error:
        findings.append(str(error))
        return None
