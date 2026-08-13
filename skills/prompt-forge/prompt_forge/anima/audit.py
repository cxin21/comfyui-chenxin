"""Objective Anima dialect audit with fact-level traceability."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ..facts import FactLedger
from .dictionary import AnimaTagDictionary
from .protocol import deweight, semantic_form


TagStatus = Literal[
    "canonical",
    "known_alias",
    "unverified",
    "invalid_protocol_tag",
    "wrong_underscore_form",
    "artist_prefix_missing",
]
Severity = Literal["warning", "error"]


@dataclass(frozen=True)
class TagAuditEntry:
    index: int
    tag: str
    status: TagStatus
    canonical: str | None
    category: str | None
    source: str | None
    verification_status: str | None
    fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class AnimaAuditFinding:
    code: Literal[
        "unverified",
        "invalid_protocol_tag",
        "wrong_underscore_form",
        "artist_prefix_missing",
        "duplicate_semantics",
        "possible_binding_conflict",
    ]
    severity: Severity
    message: str
    tag_index: int | None
    tag: str | None
    fact_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnimaAuditReport:
    tags: tuple[str, ...]
    natural_language: str
    entries: tuple[TagAuditEntry, ...]
    findings: tuple[AnimaAuditFinding, ...]

    @property
    def release_blocking(self) -> bool:
        return any(finding.severity == "error" for finding in self.findings)


def audit_anima_prompt(
    tags: tuple[str, ...],
    natural_language: str,
    ledger: FactLedger,
) -> AnimaAuditReport:
    if not isinstance(tags, tuple) or not all(isinstance(tag, str) for tag in tags):
        raise TypeError("tags must be a tuple of strings")
    if not isinstance(natural_language, str):
        raise TypeError("natural_language must be a string")

    dictionary = AnimaTagDictionary()
    entries: list[TagAuditEntry] = []
    findings: list[AnimaAuditFinding] = []
    resolved: dict[str, int] = {}
    fact_semantics = {
        fact.fact_id: semantic_form(fact.value)
        for fact in ledger.facts
    }

    resolved_tags = dictionary.resolve_many(tuple(deweight(raw_tag.strip()) for raw_tag in tags))

    for index, (raw_tag, exact) in enumerate(zip(tags, resolved_tags)):
        tag = raw_tag.strip()
        deweighted = deweight(raw_tag)
        semantic = semantic_form(tag)
        fact_ids = tuple(
            fact_id
            for fact_id, value in fact_semantics.items()
            if value == semantic
        )
        syntax = _syntax_error(tag)
        status: TagStatus
        if syntax is not None:
            status, code, message = syntax
            findings.append(
                AnimaAuditFinding(code, "error", message, index, raw_tag, fact_ids)
            )
        elif exact is None and deweighted.startswith("@"):
            status = "unverified"
            findings.append(
                AnimaAuditFinding(
                    "unverified",
                    "warning",
                    "reserved @ prefix does not resolve; treat as a style descriptor",
                    index,
                    raw_tag,
                    fact_ids,
                )
            )
        elif exact is None:
            status = "unverified"
            findings.append(
                AnimaAuditFinding(
                    "unverified",
                    "warning",
                    "ordinary semantic is not verified by the bundled Anima dictionary",
                    index,
                    raw_tag,
                    fact_ids,
                )
            )
        elif exact.category == "artist" and not deweighted.startswith("@"):
            status = "artist_prefix_missing"
            findings.append(
                AnimaAuditFinding(
                    "artist_prefix_missing",
                    "error",
                    "Anima artist tags require the @ prefix",
                    index,
                    raw_tag,
                    fact_ids,
                )
            )
        else:
            status = "known_alias" if exact.match_kind == "alias" else "canonical"

        canonical = exact.canonical if exact is not None else None
        category = exact.category if exact is not None else None
        if canonical is not None:
            previous = resolved.get(canonical)
            if previous is not None:
                findings.append(
                    AnimaAuditFinding(
                        "duplicate_semantics",
                        "error",
                        f"tag duplicates the semantic resolved at index {previous}",
                        index,
                        raw_tag,
                        fact_ids,
                    )
                )
            else:
                resolved[canonical] = index

        if semantic and _contains_semantic(natural_language, semantic):
            findings.append(
                AnimaAuditFinding(
                    "duplicate_semantics",
                    "error",
                    "the same semantic is rendered by both tags and natural language",
                    index,
                    raw_tag,
                    fact_ids,
                )
            )
        owners = {ledger.get(fact_id).owner for fact_id in fact_ids}
        if len(owners) > 1:
            findings.append(
                AnimaAuditFinding(
                    "possible_binding_conflict",
                    "warning",
                    "one unbound tag matches facts owned by multiple subjects",
                    index,
                    raw_tag,
                    fact_ids,
                )
            )
        entries.append(
            TagAuditEntry(
                index=index,
                tag=raw_tag,
                status=status,
                canonical=canonical,
                category=category,
                source=exact.source if exact is not None else None,
                verification_status=(
                    exact.verification_status if exact is not None else None
                ),
                fact_ids=fact_ids,
            )
        )
    return AnimaAuditReport(tags, natural_language, tuple(entries), tuple(findings))


def _syntax_error(
    tag: str,
) -> tuple[TagStatus, Literal["invalid_protocol_tag", "wrong_underscore_form"], str] | None:
    lowered = tag.strip().lower()
    if not lowered:
        return "invalid_protocol_tag", "invalid_protocol_tag", "tag must be non-empty"
    if lowered.startswith("score "):
        return (
            "wrong_underscore_form",
            "wrong_underscore_form",
            "score tags must retain their underscore",
        )
    if lowered.startswith("score_") and re.fullmatch(r"score_[1-9]", lowered) is None:
        return (
            "invalid_protocol_tag",
            "invalid_protocol_tag",
            "reserved score namespace only permits score_1 through score_9",
        )
    if "_" in lowered and not lowered.startswith("score_"):
        return (
            "wrong_underscore_form",
            "wrong_underscore_form",
            "ordinary Anima tags use spaces instead of underscores",
        )
    if lowered.startswith("year ") and re.fullmatch(r"year [0-9]{4}", lowered) is None:
        return (
            "invalid_protocol_tag",
            "invalid_protocol_tag",
            "reserved year namespace requires 'year ' followed by four digits",
        )
    if lowered.startswith("@"):
        return None
    return None


def _contains_semantic(natural_language: str, semantic: str) -> bool:
    normalized = semantic_form(natural_language)
    return bool(semantic and re.search(rf"(?<!\w){re.escape(semantic)}(?!\w)", normalized))
