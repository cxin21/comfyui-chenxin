from pathlib import Path

from anima_prompt_v1.authoring import build_prompt_plan
from anima_prompt_v1.catalog import Catalog
from anima_prompt_v1.domain import Fact, PromptBrief, Subject
from anima_prompt_v1.authoring.relation_graph import build_relation_graph
from anima_prompt_v1.authoring.routing import choose_route


def test_tag_facts_are_resolved_and_traced_without_rewriting_input():
    brief = PromptBrief(
        facts=(
            Fact("fact:alias", "smiling", "expression", "explicit", "user", representation_hint="tag"),
            Fact("fact:canonical", "long_hair", "hair", "explicit", "user", representation_hint="tag"),
            Fact("fact:unknown", "user_defined_trigger", "appearance", "explicit", "user", representation_hint="tag"),
        ),
        subjects=(Subject("subject:0", "adult woman"),),
    )
    decision = choose_route(brief, build_relation_graph(brief), requested="tag-led")
    plan = build_prompt_plan(brief, decision, catalog=Catalog(Path(__file__).parents[1] / "knowledge" / "tag-catalog.sqlite"))

    traced = {segment.text: segment for segment in plan.segments if segment.fact_id}
    assert traced["smiling"].catalog_canonical == "smile"
    assert traced["smiling"].catalog_match_type == "alias"
    assert traced["smiling"].catalog_matched_text == "smiling"
    assert traced["smiling"].catalog_source
    assert traced["smiling"].catalog_score > 0
    assert traced["long_hair"].catalog_match_type == "canonical"
    assert traced["user_defined_trigger"].catalog_canonical is None
    assert traced["user_defined_trigger"].text == "user_defined_trigger"
