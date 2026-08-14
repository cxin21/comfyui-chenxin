"""Copyable text and machine-readable output, with diagnostics kept separate."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .draft import PromptDraft
from .inspection import InspectionReport
from .catalog.relations import RelationProposal
from .authoring.relation_submission import RelationSubmission


@dataclass(frozen=True)
class PromptOutput:
    positive: str
    negative: str
    notes: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    advisories: tuple[str, ...] = ()


def output_from_draft(
    draft: PromptDraft,
    report: InspectionReport | None = None,
    *,
    accepted_relations: tuple[RelationProposal, ...] = (),
) -> PromptOutput:
    notes: list[str] = []
    assumptions: list[str] = []
    for provenance in draft.provenance:
        if provenance.startswith("assumption:"):
            assumptions.append(provenance.removeprefix("assumption:"))
        else:
            notes.append(provenance)
    for segment in draft.segments:
        if segment.catalog_match_type is not None:
            notes.append(
                f"catalog:{segment.segment_id}:match={segment.catalog_match_type}:"
                f"canonical={segment.catalog_canonical}:source={segment.catalog_source}:score={segment.catalog_score}"
            )
        if segment.catalog_provenance:
            notes.append(
                f"catalog_provenance:{segment.segment_id}="
                f"{'|'.join(segment.catalog_provenance)}"
            )
        if segment.relation_ids:
            notes.append(f"relations:{segment.segment_id}={','.join(segment.relation_ids)}")
        if segment.fact_kind in {"unknown", "inferred"}:
            assumptions.append(f"{segment.fact_kind}:{segment.segment_id}:{segment.text}")
    for relation in accepted_relations:
        notes.append(_relation_note(relation))
    advisories = tuple(
        f"[{issue.severity}] {issue.code}: {issue.message}"
        for issue in (report.issues if report is not None else ())
    )
    return PromptOutput(draft.positive_text, draft.negative_text, tuple(notes), tuple(assumptions), advisories)


def attach_relation_submission(output: PromptOutput, submission: RelationSubmission) -> PromptOutput:
    """Add post-authoring relation provenance without changing either prompt channel."""

    assumptions = list(output.assumptions)
    assumptions.extend(_relation_candidate(item) for item in submission.proposals if item.status != "accepted")
    advisories = list(output.advisories)
    advisories.extend(f"[warning] relation_submission: {issue}" for issue in submission.issues)
    return PromptOutput(output.positive, output.negative, output.notes, tuple(assumptions), tuple(advisories))


def _relation_note(relation: RelationProposal) -> str:
    evidence = "|".join(relation.evidence)
    return (
        f"accepted_relation:{relation.proposal_id}:type={relation.relation_type}:source={relation.source}:"
        f"model={relation.model or 'unknown'}:confidence={relation.confidence}:"
        f"rationale={relation.rationale}:evidence={evidence}"
    )


def _relation_candidate(relation: RelationProposal) -> str:
    return (
        f"relation_candidate:{relation.proposal_id}:type={relation.relation_type}:"
        f"source={relation.source}:model={relation.model or 'unknown'}:confidence={relation.confidence}"
    )


def to_text_output(output: PromptOutput) -> str:
    return f"POSITIVE:\n{output.positive}\n\nNEGATIVE:\n{output.negative}"


def to_json_output(output: PromptOutput) -> str:
    return json.dumps(
        {
            "positive": output.positive,
            "negative": output.negative,
            "notes": list(output.notes),
            "assumptions": list(output.assumptions),
            "advisories": list(output.advisories),
        },
        ensure_ascii=False,
    )
