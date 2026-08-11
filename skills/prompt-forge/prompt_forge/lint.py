"""Objective syntax lint; no creative rewriting."""
from __future__ import annotations

import re
from typing import Any

from .contracts import ForgeRequest
from .profiles import Profile


def lint_prompt(request: ForgeRequest, profile: Profile) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if profile.grammar == "anima-v1":
        _lint_anima(request, errors, warnings)
    elif profile.grammar == "h3-t2va-v1":
        _lint_h3_t2va(request, errors, warnings)
    elif profile.grammar == "h3-ref2va-v1":
        _lint_h3_ref2va(request, errors, warnings)
    else:
        errors.append({"code": "PROFILE_GRAMMAR_UNKNOWN", "message": profile.grammar})
    return {"passed": not errors, "errors": errors, "warnings": warnings}


def _lint_anima(request: ForgeRequest, errors: list, warnings: list) -> None:
    positive = request.positive
    for token in re.findall(r"(?<![A-Za-z0-9_])score_[A-Za-z0-9_]+", positive):
        if not re.fullmatch(r"score_[1-9](?:_up)?", token):
            errors.append({"code": "ANIMA_SCORE_TAG", "message": f"invalid score tag: {token}"})
    for token in re.findall(r"(?<![A-Za-z0-9])[_A-Za-z][-_A-Za-z0-9]+", positive):
        if "_" in token and not token.startswith("score_"):
            warnings.append({"code": "ANIMA_UNDERSCORE", "message": f"tag may need spaces: {token}"})
    for match in re.finditer(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9 ]*)", positive):
        value = match.group(1).strip()
        if value.startswith("artist ") and not value.startswith("@"):
            errors.append({"code": "ANIMA_ARTIST_PREFIX", "message": value})
    if request.negative and "artist name" not in request.negative and "artist_name" not in request.negative:
        warnings.append({"code": "ANIMA_NEGATIVE_BASELINE", "message": "profile baseline omits artist-name suppression"})
    if request.regional and any(not text.strip() for text in request.regional.values()):
        errors.append({"code": "ANIMA_EMPTY_REGION", "message": "regional prompts must be non-empty"})


def _lint_h3_t2va(request: ForgeRequest, errors: list, warnings: list) -> None:
    _require_exact_sections(request.positive, ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"), errors)
    if request.negative not in (None, ""):
        errors.append({"code": "H3_NEGATIVE_UNSUPPORTED", "message": "T2VA has no negative prompt slot"})
    _lint_h3_timeline(request.positive, request.duration, errors)
    _lint_h3_dialogue(request.positive, errors)
    if request.reference_count:
        errors.append({"code": "H3_T2VA_REFERENCES", "message": "T2VA cannot carry reference images"})


def _lint_h3_ref2va(request: ForgeRequest, errors: list, warnings: list) -> None:
    sections = ("subject_definitions", "summary", "retention_analysis", "detailed_description", "overall_soundscape", "non_diegetic_music")
    _require_exact_sections(request.positive, sections, errors)
    if request.negative not in (None, ""):
        errors.append({"code": "H3_NEGATIVE_UNSUPPORTED", "message": "Ref2VA has no negative prompt slot"})
    if request.reference_count < 1:
        errors.append({"code": "H3_REF2VA_REFERENCES", "message": "Ref2VA requires at least one reference image"})
    if request.reference_count > 3:
        errors.append({"code": "H3_REF2VA_REFERENCE_LIMIT", "message": "local Ref2VA supports at most three images"})
    _lint_h3_timeline(request.positive, request.duration, errors)
    _lint_h3_dialogue(request.positive, errors)
    labels = set(re.findall(r"<(?:Subject|Picture|Video|Audio) \d+>", request.positive))
    for label in labels:
        if request.positive.count(label) < 2:
            warnings.append({"code": "H3_REFERENCE_SINGLE_USE", "message": f"reference label appears once: {label}"})


def _require_exact_sections(text: str, sections: tuple[str, ...], errors: list) -> None:
    positions = []
    for section in sections:
        marker = f"{section}:"
        index = text.find(marker)
        if index < 0:
            errors.append({"code": "H3_SECTION_MISSING", "message": marker})
        else:
            positions.append((index, section))
    if [section for _, section in sorted(positions)] != list(sections):
        errors.append({"code": "H3_SECTION_ORDER", "message": "sections must follow the official order"})


def _lint_h3_timeline(text: str, duration: float | None, errors: list) -> None:
    cuts = [int(mm) * 60 + int(ss) + int(ms) / 1000 for mm, ss, ms in re.findall(r"\bAt (\d{2}):(\d{2})\.(\d{3})", text)]
    if cuts != sorted(cuts) or len(set(cuts)) != len(cuts):
        errors.append({"code": "H3_CUT_ORDER", "message": "shot cut timestamps must increase strictly"})
    if duration is not None and any(cut >= float(duration) for cut in cuts):
        errors.append({"code": "H3_CUT_RANGE", "message": "shot cut timestamp must be before duration"})


def _lint_h3_dialogue(text: str, errors: list) -> None:
    for block in re.findall(r"<d>(.*?)</d>", text, flags=re.DOTALL):
        if not re.match(r"^\[[^\]]+\] .+", block, flags=re.DOTALL):
            errors.append({"code": "H3_DIALOGUE_FORMAT", "message": "dialogue must be <d>[Language] original text</d>"})
    if text.count("<d>") != text.count("</d>"):
        errors.append({"code": "H3_DIALOGUE_UNCLOSED", "message": "dialogue tags are unbalanced"})
