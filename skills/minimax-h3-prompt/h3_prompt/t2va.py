"""MiniMax-H3 text-to-video-with-audio authoring."""
from __future__ import annotations
from .contracts import H3T2VAAuthoringRequest
from .audit import audit_t2va
from .results import PromptResult

def author_h3_t2va_prompt(request: H3T2VAAuthoringRequest) -> PromptResult:
    description = " ".join(segment.text for segment in request.integrated_multimodal_description)
    soundscape = " ".join(segment.text for segment in request.overall_soundscape) or "N/A"
    music = " ".join(segment.text for segment in request.non_diegetic_music) or "N/A"
    findings = audit_t2va(request)
    return PromptResult(f"integrated_multimodal_description: {description}\n\noverall_soundscape: {soundscape}\n\nnon_diegetic_music: {music}", findings)
