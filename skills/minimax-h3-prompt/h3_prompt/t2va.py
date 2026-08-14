"""MiniMax-H3 text-to-video-with-audio authoring."""
from __future__ import annotations
from .contracts import H3T2VAAuthoringRequest
from .common import parse_shots, audit_dialogue_and_visible_text, audit_shot_execution, audit_sound_music_separation, H3AuditError
from .facts import FactLedger
from .results import PromptResult

def author_h3_t2va_prompt(request: H3T2VAAuthoringRequest) -> PromptResult:
    ledger = FactLedger(request.facts)
    segments = (*request.integrated_multimodal_description, *request.overall_soundscape, *request.non_diegetic_music)
    ledger.validate_segments(segments)
    description = " ".join(segment.text for segment in request.integrated_multimodal_description)
    soundscape = " ".join(segment.text for segment in request.overall_soundscape) or "N/A"
    music = " ".join(segment.text for segment in request.non_diegetic_music) or "N/A"
    findings: list[str] = []
    try:
        shots = parse_shots(description, duration_seconds=request.duration_seconds, declared_shot_count=request.shot_count)
        audit_shot_execution(shots, ledger)
        audit_dialogue_and_visible_text(description, ledger)
        audit_sound_music_separation(soundscape, music)
    except H3AuditError as exc:
        findings.append(str(exc))
    return PromptResult(f"integrated_multimodal_description: {description}\n\noverall_soundscape: {soundscape}\n\nnon_diegetic_music: {music}", tuple(findings))
