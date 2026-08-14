from anima_prompt_v1.authoring.relation_graph import build_relation_graph
from anima_prompt_v1.authoring.routing import choose_route
from anima_prompt_v1.domain import Fact, PromptBrief, Subject
from anima_prompt_v1.draft import PromptDraft, PromptSegment
from anima_prompt_v1.inspection import inspect_draft


def test_inspection_is_read_only_and_non_blocking():
    brief = PromptBrief(facts=(Fact("fact:bad", "bad", "quality", "explicit", "user"),), subjects=(Subject("subject:0", "woman"),))
    graph = build_relation_graph(brief)
    decision = choose_route(brief, graph)
    draft = PromptDraft((PromptSegment("fact:bad", "positive", "bad", "user", "tag", fact_id="fact:bad"),), "bad", "", decision.route, decision.profile)
    report = inspect_draft(draft, brief=brief, graph=graph, tokenizer=lambda text: len(text.split()))
    assert report.token_estimate == 1
    assert draft.positive_text == "bad"
