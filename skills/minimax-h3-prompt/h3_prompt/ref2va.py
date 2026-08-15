"""MiniMax-H3 reference-to-video-with-audio authoring."""
from __future__ import annotations
from .contracts import H3Ref2VAAuthoringRequest
from .audit import audit_ref2va, ref_fields
from .results import PromptResult

def author_h3_ref2va_prompt(request: H3Ref2VAAuthoringRequest) -> PromptResult:
    fields = ref_fields(request)
    findings = audit_ref2va(request)
    text = "\n\n".join(f"{key}: {value}" for key, value in fields.items())
    return PromptResult(text, findings)
