from anima_prompt_v1.authoring.relation_graph import build_relation_graph
from anima_prompt_v1.authoring.routing import choose_route, default_model_profile
from anima_prompt_v1.domain import Fact, PromptBrief, Subject


def test_profile_and_user_route_are_explicit():
    brief = PromptBrief(
        facts=(Fact("fact:scene", "ruined station", "scene", "explicit", "user"),),
        subjects=(Subject("subject:0", "adult woman"),),
    )
    graph = build_relation_graph(brief)
    assert choose_route(brief, graph, requested="tag-led").route == "tag-led"
    assert choose_route(brief, graph, profile=default_model_profile("aesthetic")).route == "natural-language-led"


def test_default_profile_requires_anima_quality_contract():
    profile = default_model_profile()
    assert profile.variant == "base"
    assert profile.quality_tag_policy == "required"
    try:
        default_model_profile("custom")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported model variants must be rejected")
