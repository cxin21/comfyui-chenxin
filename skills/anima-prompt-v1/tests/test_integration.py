from anima_prompt_v1.authoring import build_prompt_plan
from anima_prompt_v1.authoring.intent import IntentParser
from anima_prompt_v1.authoring.relation_graph import build_relation_graph
from anima_prompt_v1.authoring.routing import choose_route
from anima_prompt_v1.draft import build_draft
from anima_prompt_v1.inspection import inspect_draft
from anima_prompt_v1.output import output_from_draft


def test_end_to_end_intent_to_output_keeps_unknown_text():
    brief = IntentParser().parse_text("long_hair, user_defined_trigger")
    graph = build_relation_graph(brief)
    draft = build_draft(build_prompt_plan(brief, choose_route(brief, graph)), brief)
    report = inspect_draft(draft, brief=brief, graph=graph)
    output = output_from_draft(draft, report)
    assert "long_hair" in output.positive
    assert "user_defined_trigger" in output.positive
    assert output.assumptions == ("unknown:fact:text:1:user_defined_trigger",)
