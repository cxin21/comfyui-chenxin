"""Authoring pipeline with independent positive and negative channel authors."""

from __future__ import annotations

def build_prompt_plan(
    brief,
    decision,
    *,
    catalog=None,
    provenance: tuple[str, ...] = (),
    structural_defects=(),
) :
    from ..catalog import Catalog
    from ..draft import PromptPlan
    from .negative import build_negative_segments
    from .positive import build_positive_segments

    catalog = catalog or Catalog()
    positive = build_positive_segments(brief, catalog, decision.route)
    negative = build_negative_segments(
        brief,
        catalog,
        decision.route,
        structural_defects=tuple(structural_defects),
    )
    return PromptPlan((*positive, *negative), decision.route, decision.profile, tuple(provenance))


def __getattr__(name: str):
    """Load canonical submodule symbols lazily to keep draft imports acyclic."""
    from importlib import import_module

    modules = {
        "build_negative_segments": (".negative", "build_negative_segments"),
        "select_negative_segments": (".negative", "select_negative_segments"),
        "build_positive_segments": (".positive", "build_positive_segments"),
        "GraphAdvisory": (".relation_graph", "GraphAdvisory"),
        "GraphEdge": (".relation_graph", "GraphEdge"),
        "GraphNode": (".relation_graph", "GraphNode"),
        "VisualRelationGraph": (".relation_graph", "VisualRelationGraph"),
        "build_relation_graph": (".relation_graph", "build_relation_graph"),
        "IntentClause": (".intent", "IntentClause"),
        "IntentParser": (".intent", "IntentParser"),
        "ModelProfile": (".routing", "ModelProfile"),
        "RouteDecision": (".routing", "RouteDecision"),
        "choose_route": (".routing", "choose_route"),
        "default_model_profile": (".routing", "default_model_profile"),
        "RelationSubmission": (".relation_submission", "RelationSubmission"),
        "RelationValidator": (".relation_submission", "RelationValidator"),
        "relation_record_ids_from_hits": (".relation_submission", "relation_record_ids_from_hits"),
        "submit_relation_payload": (".relation_submission", "submit_relation_payload"),
        "WorkflowResult": (".workflow", "WorkflowResult"),
        "run_authoring_workflow": (".workflow", "run_authoring_workflow"),
    }
    if name not in modules:
        raise AttributeError(name)
    module_name, attribute = modules[name]
    return getattr(import_module(module_name, __name__), attribute)


__all__ = [
    "RelationSubmission", "RelationValidator", "WorkflowResult", "build_negative_segments",
    "build_positive_segments", "build_prompt_plan", "run_authoring_workflow",
    "relation_record_ids_from_hits", "select_negative_segments", "submit_relation_payload",
]
