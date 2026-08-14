"""Prompt authoring orchestration.

Relation persistence is deliberately not part of this workflow.  The skill
LLM submits relations after this workflow has produced the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..catalog import Catalog
from ..domain import PromptBrief
from ..draft import PromptDraft, PromptPlan, build_draft
from ..inspection import InspectionReport, inspect_draft
from ..output import PromptOutput, output_from_draft
from .relation_graph import VisualRelationGraph, build_relation_graph
from .routing import ModelProfile, RouteDecision, Route, choose_route, default_model_profile, seed_quality_policy
from . import build_prompt_plan


@dataclass(frozen=True)
class WorkflowResult:
    brief: PromptBrief
    graph: VisualRelationGraph
    decision: RouteDecision
    plan: PromptPlan
    draft: PromptDraft
    inspection: InspectionReport
    output: PromptOutput
    catalog_hits: tuple = ()


def run_authoring_workflow(
    brief: PromptBrief,
    *,
    catalog: Catalog | None = None,
    requested_route: Route | None = None,
    profile: ModelProfile | None = None,
    tokenizer: Callable[[str], int] | None = None,
) -> WorkflowResult:
    catalog = catalog or Catalog()
    selected_profile = profile or default_model_profile("base")
    workflow_provenance = ("assumption:variant_unspecified: using Anima-Base default",) if profile is None else ()
    brief = seed_quality_policy(brief, selected_profile)
    hits = _catalog_hits(brief, catalog)
    graph = build_relation_graph(brief)
    decision = choose_route(brief, graph, requested=requested_route, profile=selected_profile)
    plan = build_prompt_plan(brief, decision, catalog=catalog, provenance=workflow_provenance)
    draft = build_draft(plan, brief)
    report = inspect_draft(draft, brief=brief, graph=graph, tokenizer=tokenizer)
    output = output_from_draft(
        draft,
        report,
        accepted_relations=_accepted_relations(brief, catalog),
    )
    return WorkflowResult(brief, graph, decision, plan, draft, report, output, hits)


def _catalog_hits(brief: PromptBrief, catalog: Catalog):
    hits = []
    seen: set[str] = set()
    for fact in (*brief.facts, *brief.exclusions):
        if fact.representation_hint == "prose":
            continue
        for hit in catalog.search(fact.value, mode="auto", limit=1):
            if hit.record_id not in seen:
                seen.add(hit.record_id)
                hits.append(hit)
    return tuple(hits)


def _accepted_relations(brief: PromptBrief, catalog: Catalog):
    relation_store = catalog.relation_overlay
    if not relation_store.path.is_file():
        return ()
    record_ids = {hit.record_id for hit in _catalog_hits(brief, catalog)}
    result = []
    for record_id in record_ids:
        result.extend(relation_store.list(status="accepted", record_id=record_id, limit=100))
    unique = {item.proposal_id: item for item in result}
    return tuple(unique.values())
