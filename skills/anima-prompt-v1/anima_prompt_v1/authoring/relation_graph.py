"""Typed visual relation graph; no string marker parsing or relationship guessing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..domain import Fact, PromptBrief, RelationClaim

NodeKind = Literal["subject", "attribute", "action", "scene", "style", "lighting", "camera", "region"]

_ATTRIBUTE_DOMAINS = frozenset(("appearance", "clothing", "expression", "hair", "pose", "object", "quality", "subject"))
_NODE_FOR_DOMAIN: dict[str, NodeKind] = {
    "action": "action", "scene": "scene", "style": "style", "lighting": "lighting",
    "camera": "camera", "region": "region",
}


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    kind: NodeKind
    label: str
    subject_id: str | None = None


@dataclass(frozen=True)
class GraphEdge:
    from_id: str
    to_id: str
    relation: str
    explicit: bool
    source_fact_id: str | None = None


@dataclass(frozen=True)
class GraphAdvisory:
    code: str
    node_ids: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class VisualRelationGraph:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]

    def subject_ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.nodes if node.kind == "subject")

    def edge_tuples(self) -> tuple[tuple[str, str, str], ...]:
        return tuple((edge.from_id, edge.relation, edge.to_id) for edge in self.edges)

    def actions_without_actor(self) -> tuple[str, ...]:
        action_ids = {node.node_id for node in self.nodes if node.kind == "action"}
        actors = {edge.to_id for edge in self.edges if edge.relation == "performs" and edge.from_id in self.subject_ids()}
        return tuple(node_id for node_id in action_ids if node_id not in actors)

    def missing_multi_subject_relations(self) -> tuple[str, ...]:
        subjects = self.subject_ids()
        if len(subjects) < 2:
            return ()
        linked = {
            endpoint
            for edge in self.edges
            if edge.from_id in subjects and edge.to_id in subjects
            for endpoint in (edge.from_id, edge.to_id)
        }
        return tuple(subject_id for subject_id in subjects if subject_id not in linked)

    def relation_advisories(self) -> tuple[GraphAdvisory, ...]:
        missing = self.missing_multi_subject_relations()
        if not missing:
            return ()
        return (GraphAdvisory(
            "missing_multi_subject_relation",
            missing,
            "multiple subjects have no explicit spatial, action, interaction, or non-interaction relation",
        ),)


def build_relation_graph(brief: PromptBrief) -> VisualRelationGraph:
    brief.validate()
    nodes: list[GraphNode] = [GraphNode(subject.subject_id, "subject", subject.label) for subject in brief.subjects]
    for fact in brief.facts:
        kind: NodeKind = "attribute" if fact.domain in _ATTRIBUTE_DOMAINS else _NODE_FOR_DOMAIN.get(fact.domain, "attribute")
        nodes.append(GraphNode(fact.fact_id, kind, fact.value, fact.subject_id))

    known = {node.node_id for node in nodes}
    edges: list[GraphEdge] = []
    for fact in brief.facts:
        if fact.subject_id is None:
            continue
        relation = "performs" if fact.domain == "action" else "located_at" if fact.domain == "region" else "has_attribute"
        edges.append(GraphEdge(fact.subject_id, fact.fact_id, relation, fact.kind == "explicit", fact.fact_id))
    scene_facts = tuple(fact for fact in brief.facts if fact.domain == "scene")
    if scene_facts:
        scene = scene_facts[0]
        for subject in brief.subjects:
            edges.append(GraphEdge(scene.fact_id, subject.subject_id, "contains", scene.kind == "explicit", scene.fact_id))
        for fact in brief.facts:
            relation = {"style": "uses_style", "lighting": "uses_lighting", "camera": "uses_camera"}.get(fact.domain)
            if relation is not None:
                edges.append(GraphEdge(scene.fact_id, fact.fact_id, relation, fact.kind == "explicit", fact.fact_id))
    for claim in brief.relations:
        _append_claim(edges, claim, known)
    return VisualRelationGraph(tuple(nodes), tuple(edges))


def _append_claim(edges: list[GraphEdge], claim: RelationClaim, known: set[str]) -> None:
    if claim.from_id in known and claim.to_id in known:
        edges.append(GraphEdge(claim.from_id, claim.to_id, claim.relation_type, claim.explicit, claim.source_fact_id))
