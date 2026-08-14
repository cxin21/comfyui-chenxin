from anima_prompt_v1.domain import Subject
from anima_prompt_v1.authoring import build_prompt_plan
from anima_prompt_v1.draft import build_draft
from anima_prompt_v1.authoring.relation_graph import build_relation_graph
from anima_prompt_v1.authoring.intent import IntentClause, IntentParser
from anima_prompt_v1.authoring.routing import choose_route


def test_intent_parser_preserves_source_state_original_text_and_notes():
    brief = IntentParser().parse(
        subjects=(Subject("subject:0", "adult woman"),),
        facts=(
            IntentClause(
                fact_id="fact:explicit",
                value="long_hair",
                domain="hair",
                kind="explicit",
                source="user",
                user_text="长发",
                subject_id="subject:0",
                representation_hint="tag",
                notes=("user requested appearance",),
            ),
            IntentClause(
                fact_id="fact:unknown",
                value="user_defined_trigger",
                domain="appearance",
                kind="unknown",
                source="user",
                user_text="用户原样触发词",
                locked=True,
                subject_id="subject:0",
            ),
        ),
    )

    assert brief.facts[0].user_text == "长发"
    assert brief.facts[0].notes == ("user requested appearance",)
    assert brief.facts[1].kind == "unknown"
    assert brief.facts[1].locked is True
    assert brief.facts[1].user_text == "用户原样触发词"
    assert brief.unknowns == (brief.facts[1],)
    assert brief.notes == ("user requested appearance",)


def test_text_parser_keeps_catalog_tags_and_unresolved_text():
    brief = IntentParser().parse_text(
        "long_hair, rain-soaked ruined platform, user_defined_trigger",
        subjects=(Subject("subject:0", "adult woman"),),
    )

    assert [fact.value for fact in brief.facts] == ["long_hair", "rain-soaked ruined platform", "user_defined_trigger"]
    assert brief.facts[0].representation_hint == "tag"
    assert brief.facts[0].user_text == "long_hair"
    assert brief.facts[1].representation_hint == "prose"
    assert brief.facts[1].kind == "explicit"
    assert brief.facts[2].representation_hint == "tag"
    assert brief.facts[2].kind == "unknown"
    assert brief.facts[2].value == "user_defined_trigger"


def test_authoring_does_not_drop_unknown_or_inferred_facts():
    brief = IntentParser().parse(
        subjects=(Subject("subject:0", "adult woman"),),
        facts=(
            IntentClause("fact:unknown", "user_defined_trigger", "appearance", "unknown", "user", locked=True),
            IntentClause("fact:inferred", "dramatic silhouette", "style", "inferred", "local_model"),
        ),
    )
    graph = build_relation_graph(brief)
    draft = build_draft(build_prompt_plan(brief, choose_route(brief, graph)), brief)
    segments = {segment.fact_id: segment for segment in draft.segments if segment.fact_id}

    assert "user_defined_trigger" in draft.positive_text
    assert "dramatic silhouette" in draft.positive_text
    assert segments["fact:unknown"].fact_kind == "unknown"
    assert segments["fact:unknown"].fact_source == "user"
    assert segments["fact:inferred"].fact_kind == "inferred"
    assert segments["fact:inferred"].fact_source == "local_model"
