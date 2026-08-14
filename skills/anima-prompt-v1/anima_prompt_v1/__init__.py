"""Clean-room Anima prompt authoring package for the v1 skill."""

from .domain import Fact, LockedSegment, PromptBrief, RelationClaim, Subject
from .draft import PromptDraft, PromptPlan, PromptSegment, build_draft
from .authoring import (
    GraphAdvisory, GraphEdge, GraphNode, IntentClause, IntentParser,
    ModelProfile, RelationSubmission, RelationValidator, RouteDecision,
    VisualRelationGraph, build_relation_graph, choose_route,
    default_model_profile, submit_relation_payload,
)
from .output import PromptOutput, attach_relation_submission, output_from_draft, to_json_output, to_text_output

__all__ = [
    "Fact",
    "GraphAdvisory",
    "GraphEdge",
    "GraphNode",
    "IntentClause",
    "IntentParser",
    "LockedSegment",
    "ModelProfile",
    "PromptBrief",
    "PromptDraft",
    "PromptPlan",
    "PromptSegment",
    "PromptOutput",
    "RelationSubmission",
    "RelationValidator",
    "RelationClaim",
    "RouteDecision",
    "Subject",
    "VisualRelationGraph",
    "build_draft",
    "build_relation_graph",
    "attach_relation_submission",
    "choose_route",
    "default_model_profile",
    "submit_relation_payload",
    "output_from_draft",
    "to_json_output",
    "to_text_output",
]
