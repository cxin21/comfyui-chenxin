"""MCP adapter for the canonical Anima Prompt v1 workflow."""
from __future__ import annotations

from typing import Any

from .authoring.routing import default_model_profile
from .authoring.workflow import run_authoring_workflow
from .domain import Fact, LockedSegment, PromptBrief, RelationClaim, Subject


def get_prompt_skill() -> dict[str, Any]:
    return {
        "name": "anima-prompt-v1",
        "model": "Anima",
        "stages": ("author",),
        "describe_fn": describe,
        "author_fn": author,
    }


def describe(stage: str) -> dict[str, Any]:
    if stage != "author":
        raise ValueError("anima-prompt-v1 supports only the 'author' stage")
    return {
        "skill": "anima-prompt-v1",
        "stage": "author",
        "model": "Anima",
        "description": "Run the typed Anima Prompt v1 authoring workflow.",
        "request": {
            "type": "object",
            "required": ["facts", "subjects"],
            "properties": {
                "variant": {"type": "string", "enum": ["base", "aesthetic", "turbo"], "default": "base"},
                "route": {"type": "string", "enum": ["tag-led", "hybrid", "natural-language-led"]},
                "facts": {"type": "array", "items": {"$ref": "Fact"}},
                "subjects": {"type": "array", "items": {"$ref": "Subject"}},
                "relations": {"type": "array", "items": {"$ref": "RelationClaim"}},
                "exclusions": {"type": "array", "items": {"$ref": "Fact"}},
                "locked_segments": {"type": "array", "items": {"$ref": "LockedSegment"}},
                "source_priority": {"type": "array", "items": {"type": "string"}},
            },
        },
        "definitions": {
            "Fact": {
                "type": "object",
                "required": ["fact_id", "value", "domain", "kind", "source"],
                "properties": {
                    "fact_id": {"type": "string"},
                    "value": {"type": "string"},
                    "domain": {"type": "string"},
                    "kind": {"type": "string", "enum": ["explicit", "inferred", "unknown"]},
                    "source": {"type": "string", "enum": ["user", "local_model", "official", "community", "default"]},
                    "locked": {"type": "boolean", "default": False},
                    "confidence": {"type": ["number", "null"]},
                    "user_text": {"type": ["string", "null"]},
                    "subject_id": {"type": ["string", "null"]},
                    "representation_hint": {"type": "string", "enum": ["auto", "tag", "prose"], "default": "auto"},
                    "notes": {"type": "array", "items": {"type": "string"}},
                },
            },
            "Subject": {
                "type": "object",
                "required": ["subject_id", "label"],
                "properties": {"subject_id": {"type": "string"}, "label": {"type": "string"}},
            },
            "RelationClaim": {
                "type": "object",
                "required": ["relation_id", "relation_type", "from_id", "to_id", "explicit"],
                "properties": {
                    "relation_id": {"type": "string"},
                    "relation_type": {"type": "string"},
                    "from_id": {"type": "string"},
                    "to_id": {"type": "string"},
                    "explicit": {"type": "boolean"},
                    "source_fact_id": {"type": ["string", "null"]},
                },
            },
            "LockedSegment": {
                "type": "object",
                "required": ["segment_id", "text"],
                "properties": {
                    "segment_id": {"type": "string"},
                    "text": {"type": "string"},
                    "representation": {"type": "string", "default": "text"},
                },
            },
        },
        "output": {
            "prompt": {"positive": "string", "negative": "string"},
            "notes": "array[string]",
            "assumptions": "array[string]",
            "advisories": "array[string]",
        },
    }


def author(stage: str, request: dict[str, Any]) -> dict[str, Any]:
    if stage != "author":
        raise ValueError("anima-prompt-v1 supports only the 'author' stage")
    brief = _coerce_brief(request)
    profile = default_model_profile(
        request.get("variant", "base"),
        trigger_words=tuple(request.get("trigger_words", ())),
        source="mcp",
        evidence_level="caller_declared",
    )
    result = run_authoring_workflow(
        brief,
        requested_route=request.get("route"),
        profile=profile,
    )
    output = result.output
    return {
        "skill": "anima-prompt-v1",
        "stage": stage,
        "prompt": {"positive": output.positive, "negative": output.negative},
        "notes": list(output.notes),
        "assumptions": list(output.assumptions),
        "advisories": list(output.advisories),
        "metadata": {
            "variant": result.decision.profile.variant,
            "route": result.decision.route,
            "catalog_hit_count": len(result.catalog_hits),
        },
    }


def _coerce_brief(request: dict[str, Any]) -> PromptBrief:
    if not isinstance(request, dict):
        raise TypeError("request must be an object")
    for field in ("facts", "subjects"):
        if field not in request:
            raise ValueError(f"request requires {field!r}")
    return PromptBrief(
        facts=tuple(_coerce_fact(item, "facts", index) for index, item in enumerate(request["facts"])),
        subjects=tuple(_coerce_subject(item, index) for index, item in enumerate(request["subjects"])),
        relations=tuple(_coerce_relation(item, index) for index, item in enumerate(request.get("relations", ()))),
        exclusions=tuple(_coerce_fact(item, "exclusions", index) for index, item in enumerate(request.get("exclusions", ()))),
        locked_segments=tuple(_coerce_locked(item, index) for index, item in enumerate(request.get("locked_segments", ()))),
        source_priority=tuple(request.get("source_priority", ("user", "local_model", "official", "community", "default"))),
    )


def _items(value: Any, field: str) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field} must be an array")
    return list(value)


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field} items must be objects")
    return value


def _required(item: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in item]
    if missing:
        raise ValueError(f"{label} missing required fields: {', '.join(missing)}")


def _coerce_fact(value: Any, field: str, index: int) -> Fact:
    label = f"{field}[{index}]"
    item = _object(value, label)
    _required(item, ("fact_id", "value", "domain", "kind", "source"), label)
    return Fact(
        fact_id=str(item["fact_id"]),
        value=str(item["value"]),
        domain=item["domain"],
        kind=item["kind"],
        source=item["source"],
        locked=bool(item.get("locked", False)),
        confidence=item.get("confidence"),
        user_text=item.get("user_text"),
        subject_id=item.get("subject_id"),
        representation_hint=item.get("representation_hint", "auto"),
        notes=tuple(item.get("notes", ())),
    )


def _coerce_subject(value: Any, index: int) -> Subject:
    label = f"subjects[{index}]"
    item = _object(value, label)
    _required(item, ("subject_id", "label"), label)
    return Subject(str(item["subject_id"]), str(item["label"]))


def _coerce_relation(value: Any, index: int) -> RelationClaim:
    label = f"relations[{index}]"
    item = _object(value, label)
    _required(item, ("relation_id", "relation_type", "from_id", "to_id", "explicit"), label)
    return RelationClaim(
        relation_id=str(item["relation_id"]),
        relation_type=item["relation_type"],
        from_id=str(item["from_id"]),
        to_id=str(item["to_id"]),
        explicit=bool(item["explicit"]),
        source_fact_id=item.get("source_fact_id"),
    )


def _coerce_locked(value: Any, index: int) -> LockedSegment:
    label = f"locked_segments[{index}]"
    item = _object(value, label)
    _required(item, ("segment_id", "text"), label)
    return LockedSegment(str(item["segment_id"]), str(item["text"]), item.get("representation", "text"))
