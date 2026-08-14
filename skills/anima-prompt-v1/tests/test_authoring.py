from anima_prompt_v1.authoring import build_prompt_plan
from anima_prompt_v1.authoring.negative import build_negative_segments
from anima_prompt_v1.authoring.relation_graph import build_relation_graph
from anima_prompt_v1.authoring.routing import choose_route
from anima_prompt_v1.catalog import Catalog
from anima_prompt_v1.domain import Fact, PromptBrief, Subject
from anima_prompt_v1.draft import PromptSegment


def test_channels_are_independent_and_low_level_authoring_preserves_explicit_exclusions():
    brief = PromptBrief(
        facts=(Fact("fact:coat", "black coat", "clothing", "explicit", "user"),),
        subjects=(Subject("subject:0", "woman"),),
        exclusions=(Fact("fact:bad", "blurry", "quality", "explicit", "user"),),
    )
    decision = choose_route(brief, build_relation_graph(brief))
    plan = build_prompt_plan(brief, decision, catalog=Catalog())
    assert {segment.channel for segment in plan.segments} == {"positive", "negative"}
    assert [item.text for item in build_negative_segments(brief, Catalog(), "hybrid")] == ["blurry"]
