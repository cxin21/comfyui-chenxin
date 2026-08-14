from anima_prompt_v1.authoring.relation_graph import build_relation_graph
from anima_prompt_v1.domain import Fact, PromptBrief, RelationClaim, Subject


def test_graph_preserves_explicit_spatial_relation_and_scene_edges():
    brief = PromptBrief(
        facts=(Fact("fact:scene", "station", "scene", "explicit", "user"),),
        subjects=(Subject("subject:0", "woman"), Subject("subject:1", "man")),
        relations=(RelationClaim("rel:near", "near", "subject:0", "subject:1", True),),
    )
    graph = build_relation_graph(brief)
    assert ("fact:scene", "contains", "subject:0") in graph.edge_tuples()
    assert ("subject:0", "near", "subject:1") in graph.edge_tuples()
    assert graph.relation_advisories() == ()
