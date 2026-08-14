"""MiniMax-H3 reference-to-video-with-audio authoring."""
from __future__ import annotations
from .contracts import H3Ref2VAAuthoringRequest
from .common import parse_shots, audit_dialogue_and_visible_text, audit_shot_execution, audit_sound_music_separation, audit_reference_labels, H3AuditError
from .facts import FactLedger
from .results import PromptResult

def author_h3_ref2va_prompt(request: H3Ref2VAAuthoringRequest) -> PromptResult:
    ledger = FactLedger(request.facts)
    segments = (*request.subject_definitions, *request.summary, *request.retention_analysis, *request.detailed_description, *request.overall_soundscape, *request.non_diegetic_music)
    ledger.validate_segments(segments)
    fields = {
        "subject_definitions": "\n".join(x.text for x in request.subject_definitions),
        "summary": " ".join(x.text for x in request.summary),
        "retention_analysis": "\n".join(x.text for x in request.retention_analysis),
        "detailed_description": "\n".join(x.text for x in request.detailed_description),
        "overall_soundscape": " ".join(x.text for x in request.overall_soundscape) or "N/A",
        "non_diegetic_music": " ".join(x.text for x in request.non_diegetic_music) or "N/A",
    }
    findings: list[str] = []
    try:
        audit_reference_labels(fields["subject_definitions"], fields["retention_analysis"] + "\n" + fields["detailed_description"], request.references)
        shots = parse_shots(fields["detailed_description"], duration_seconds=request.duration_seconds, declared_shot_count=request.shot_count)
        audit_shot_execution(shots, ledger)
        audit_dialogue_and_visible_text(fields["detailed_description"], ledger)
        audit_sound_music_separation(fields["overall_soundscape"], fields["non_diegetic_music"])
    except H3AuditError as exc:
        findings.append(str(exc))
    text = "\n\n".join(f"{key}: {value}" for key, value in fields.items())
    return PromptResult(text, tuple(findings))
