"""MCP adapter for the canonical MiniMax-H3 authoring functions."""
from __future__ import annotations

from typing import Any

from .contracts import (
    AuthoredSegment,
    Fact,
    H3ReferenceImage,
    H3Ref2VAAuthoringRequest,
    H3T2VAAuthoringRequest,
)
from .ref2va import author_h3_ref2va_prompt
from .t2va import author_h3_t2va_prompt


def get_prompt_skill() -> dict[str, Any]:
    return {
        "name": "minimax-h3-prompt",
        "model": "MiniMax-H3",
        "stages": ("t2va", "ref2va"),
        "describe_fn": describe,
        "author_fn": author,
    }


def describe(stage: str) -> dict[str, Any]:
    if stage not in {"t2va", "ref2va"}:
        raise ValueError("minimax-h3-prompt supports 't2va' and 'ref2va' stages")
    common = {
        "facts": {"type": "array", "items": {"$ref": "Fact"}},
        "duration_seconds": {"type": "number", "minimum": 2, "maximum": 15},
        "shot_count": {"type": "integer", "minimum": 1},
        "overall_soundscape": {"type": "array", "items": {"$ref": "AuthoredSegment"}},
        "non_diegetic_music": {"type": "array", "items": {"$ref": "AuthoredSegment"}},
    }
    if stage == "t2va":
        common["integrated_multimodal_description"] = {
            "type": "array", "items": {"$ref": "AuthoredSegment"}
        }
        required = ["facts", "duration_seconds", "shot_count", "integrated_multimodal_description"]
    else:
        common.update({
            "references": {"type": "array", "items": {"$ref": "H3ReferenceImage"}},
            "subject_definitions": {"type": "array", "items": {"$ref": "AuthoredSegment"}},
            "summary": {"type": "array", "items": {"$ref": "AuthoredSegment"}},
            "retention_analysis": {"type": "array", "items": {"$ref": "AuthoredSegment"}},
            "detailed_description": {"type": "array", "items": {"$ref": "AuthoredSegment"}},
        })
        required = [
            "facts", "duration_seconds", "shot_count", "references",
            "subject_definitions", "summary", "retention_analysis", "detailed_description",
        ]
    return {
        "skill": "minimax-h3-prompt",
        "stage": stage,
        "model": "MiniMax-H3",
        "description": "Run the audited MiniMax-H3 prompt authoring workflow.",
        "request": {"type": "object", "required": required, "properties": common},
        "definitions": {
            "Fact": {
                "type": "object",
                "required": ["fact_id", "value", "origin", "locked", "owner", "dimension"],
                "properties": {
                    "fact_id": {"type": "string"}, "value": {"type": "string"},
                    "origin": {"type": "string"}, "locked": {"type": "boolean"},
                    "owner": {"type": "string"}, "dimension": {"type": "string"},
                },
            },
            "AuthoredSegment": {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "segment_id": {"type": "string"}, "field": {"type": "string"},
                    "text": {"type": "string"}, "fact_ids": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "number"}, "adherence_risk": {"type": "number"},
                    "source_confidence": {"type": "number"},
                },
            },
            "H3ReferenceImage": {
                "type": "object",
                "required": ["reference_id", "owner", "resized_width", "resized_height"],
                "properties": {
                    "reference_id": {"type": "string"}, "owner": {"type": "string"},
                    "resized_width": {"type": "integer"}, "resized_height": {"type": "integer"},
                },
            },
        },
        "output": {
            "prompt": {"text": "string"},
            "findings": "array[string]",
        },
    }


def author(stage: str, request: dict[str, Any]) -> dict[str, Any]:
    if stage == "t2va":
        result = author_h3_t2va_prompt(_coerce_t2va(request))
    elif stage == "ref2va":
        result = author_h3_ref2va_prompt(_coerce_ref2va(request))
    else:
        raise ValueError("minimax-h3-prompt supports 't2va' and 'ref2va' stages")
    return {
        "skill": "minimax-h3-prompt",
        "stage": stage,
        "prompt": {"text": result.text},
        "findings": list(result.findings),
        "advisories": list(result.findings),
    }


def _coerce_t2va(request: Any) -> H3T2VAAuthoringRequest:
    item = _request(request, ("facts", "duration_seconds", "shot_count", "integrated_multimodal_description"))
    facts = _coerce_facts(item["facts"])
    fact_ids = tuple(fact.fact_id for fact in facts)
    return H3T2VAAuthoringRequest(
        facts=facts,
        duration_seconds=float(item["duration_seconds"]),
        shot_count=int(item["shot_count"]),
        integrated_multimodal_description=_coerce_segments(item["integrated_multimodal_description"], "integrated_multimodal_description", fact_ids),
        overall_soundscape=_coerce_segments(item.get("overall_soundscape", ()), "overall_soundscape", fact_ids),
        non_diegetic_music=_coerce_segments(item.get("non_diegetic_music", ()), "non_diegetic_music", fact_ids),
    )


def _coerce_ref2va(request: Any) -> H3Ref2VAAuthoringRequest:
    item = _request(request, (
        "facts", "duration_seconds", "shot_count", "references",
        "subject_definitions", "summary", "retention_analysis", "detailed_description",
    ))
    facts = _coerce_facts(item["facts"])
    fact_ids = tuple(fact.fact_id for fact in facts)
    return H3Ref2VAAuthoringRequest(
        facts=facts,
        duration_seconds=float(item["duration_seconds"]),
        shot_count=int(item["shot_count"]),
        references=_coerce_references(item["references"]),
        subject_definitions=_coerce_segments(item["subject_definitions"], "subject_definitions", fact_ids),
        summary=_coerce_segments(item["summary"], "summary", fact_ids),
        retention_analysis=_coerce_segments(item["retention_analysis"], "retention_analysis", fact_ids),
        detailed_description=_coerce_segments(item["detailed_description"], "detailed_description", fact_ids),
        overall_soundscape=_coerce_segments(item.get("overall_soundscape", ()), "overall_soundscape", fact_ids),
        non_diegetic_music=_coerce_segments(item.get("non_diegetic_music", ()), "non_diegetic_music", fact_ids),
    )


def _request(value: Any, required: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("request must be an object")
    missing = [field for field in required if field not in value]
    if missing:
        raise ValueError(f"request missing required fields: {', '.join(missing)}")
    return value


def _coerce_facts(value: Any) -> tuple[Fact, ...]:
    items = _array(value, "facts")
    result = []
    for index, raw in enumerate(items):
        item = _object(raw, f"facts[{index}]")
        required = ("fact_id", "value", "origin", "locked", "owner", "dimension")
        _required(item, required, f"facts[{index}]")
        result.append(Fact(
            fact_id=str(item["fact_id"]), value=str(item["value"]), origin=item["origin"],
            locked=bool(item["locked"]), owner=str(item["owner"]), dimension=str(item["dimension"]),
        ))
    return tuple(result)


def _coerce_segments(value: Any, field: str, fact_ids: tuple[str, ...]) -> tuple[AuthoredSegment, ...]:
    result = []
    for index, raw in enumerate(_array(value, field)):
        item = _object(raw, f"{field}[{index}]")
        text = str(item.get("text", "")).strip()
        if not text:
            raise ValueError(f"{field}[{index}].text must be non-empty")
        raw_fact_ids = item.get("fact_ids")
        segment_fact_ids = fact_ids if raw_fact_ids in (None, []) else tuple(str(value) for value in raw_fact_ids)
        result.append(AuthoredSegment(
            segment_id=str(item.get("segment_id", f"{field}-{index}")),
            field=str(item.get("field", field)), text=text, fact_ids=segment_fact_ids,
            priority=float(item.get("priority", 1.0)),
            adherence_risk=float(item.get("adherence_risk", 0.5)),
            source_confidence=float(item.get("source_confidence", 1.0)),
        ))
    return tuple(result)


def _coerce_references(value: Any) -> tuple[H3ReferenceImage, ...]:
    result = []
    for index, raw in enumerate(_array(value, "references")):
        item = _object(raw, f"references[{index}]")
        _required(item, ("reference_id", "owner", "resized_width", "resized_height"), f"references[{index}]")
        result.append(H3ReferenceImage(
            reference_id=str(item["reference_id"]), owner=str(item["owner"]),
            resized_width=int(item["resized_width"]), resized_height=int(item["resized_height"]),
        ))
    return tuple(result)


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field} must be an array")
    return list(value)


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field} must be an object")
    return value


def _required(item: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in item]
    if missing:
        raise ValueError(f"{label} missing required fields: {', '.join(missing)}")
