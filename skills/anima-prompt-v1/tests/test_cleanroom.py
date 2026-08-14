import json
from pathlib import Path

from anima_prompt_v1.authoring import build_prompt_plan
from anima_prompt_v1.authoring.negative import build_negative_segments
from anima_prompt_v1.catalog import Catalog
from anima_prompt_v1.domain import Fact, LockedSegment, PromptBrief, RelationClaim, Subject
from anima_prompt_v1.draft import PromptDraft, PromptSegment, build_draft
from anima_prompt_v1.authoring.relation_graph import build_relation_graph
from anima_prompt_v1.inspection import inspect_draft
from anima_prompt_v1.output import PromptOutput, output_from_draft, to_json_output, to_text_output
from anima_prompt_v1.authoring.routing import choose_route, default_model_profile


def make_brief(*, facts=(), subjects=("girl",), relations=(), exclusions=(), locked=()):
    return PromptBrief(
        facts=tuple(facts),
        subjects=tuple(Subject(f"subject:{i}", label) for i, label in enumerate(subjects)),
        relations=tuple(relations),
        exclusions=tuple(exclusions),
        locked_segments=tuple(locked),
    )


def test_typed_graph_preserves_attribute_action_and_interaction_edges():
    dress = Fact("fact:dress", "red dress", "clothing", "explicit", "user", subject_id="subject:0")
    wave = Fact("fact:wave", "wave", "action", "explicit", "user", subject_id="subject:0")
    relation = RelationClaim("rel:interaction", "interacts_with", "subject:0", "subject:1", True, "fact:wave")
    graph = build_relation_graph(make_brief(facts=(dress, wave), subjects=("girl", "boy"), relations=(relation,)))

    assert ("subject:0", "has_attribute", "fact:dress") in graph.edge_tuples()
    assert ("subject:0", "performs", "fact:wave") in graph.edge_tuples()
    assert ("subject:0", "interacts_with", "subject:1") in graph.edge_tuples()


def test_missing_relationships_are_advisories():
    action = Fact("fact:walk", "walk", "action", "explicit", "user")
    graph = build_relation_graph(make_brief(facts=(action,), subjects=("girl", "boy")))
    assert graph.actions_without_actor() == ("fact:walk",)
    assert graph.missing_multi_subject_relations() == ("subject:0", "subject:1")


def test_scene_connects_subject_style_lighting_and_camera_nodes():
    facts = (
        Fact("fact:scene", "ruined station", "scene", "explicit", "user"),
        Fact("fact:style", "cinematic", "style", "explicit", "user"),
        Fact("fact:lighting", "blue rim light", "lighting", "explicit", "user"),
        Fact("fact:camera", "three-quarter view", "camera", "explicit", "user"),
    )
    graph = build_relation_graph(make_brief(facts=facts, subjects=("girl", "boy")))

    assert ("fact:scene", "contains", "subject:0") in graph.edge_tuples()
    assert ("fact:scene", "contains", "subject:1") in graph.edge_tuples()
    assert ("fact:scene", "uses_style", "fact:style") in graph.edge_tuples()
    assert ("fact:scene", "uses_lighting", "fact:lighting") in graph.edge_tuples()
    assert ("fact:scene", "uses_camera", "fact:camera") in graph.edge_tuples()


def test_position_and_action_target_relations_are_typed_edges():
    action = Fact("fact:grab", "grab", "action", "explicit", "user", subject_id="subject:0")
    relations = (
        RelationClaim("rel:left", "left_of", "subject:0", "subject:1", True, "fact:grab"),
        RelationClaim("rel:target", "receives_or_is_target_of", "subject:1", "fact:grab", True, "fact:grab"),
    )
    graph = build_relation_graph(make_brief(facts=(action,), subjects=("girl", "boy"), relations=relations))

    assert ("subject:0", "left_of", "subject:1") in graph.edge_tuples()
    assert ("subject:1", "receives_or_is_target_of", "fact:grab") in graph.edge_tuples()


def test_explicit_visual_relations_are_rendered_as_prose_segments():
    brief = make_brief(
        subjects=("woman", "man"),
        relations=(RelationClaim("rel:left", "left_of", "subject:0", "subject:1", True),),
    )
    graph = build_relation_graph(brief)
    draft = build_draft(build_prompt_plan(brief, choose_route(brief, graph)), brief)
    assert "woman is left of man" in draft.positive_text
    assert any(segment.segment_id == "relation:rel:left" and segment.representation == "prose" for segment in draft.segments)


def test_graph_relation_advisories_are_nonblocking_and_suppressed_by_explicit_relation():
    missing = build_relation_graph(make_brief(subjects=("girl", "boy")))
    assert {item.code for item in missing.relation_advisories()} == {"missing_multi_subject_relation"}

    linked = build_relation_graph(make_brief(
        subjects=("girl", "boy"),
        relations=(RelationClaim("rel:none", "not_interacting", "subject:0", "subject:1", True),),
    ))
    assert linked.relation_advisories() == ()


def test_route_changes_auto_representation_without_changing_fact_text():
    facts = (
        Fact("fact:coat", "black coat", "clothing", "explicit", "user"),
        Fact("fact:walk", "walks through the station", "action", "explicit", "user"),
    )
    brief = make_brief(facts=facts)
    graph = build_relation_graph(brief)
    tag_plan = build_prompt_plan(brief, choose_route(brief, graph, requested="tag-led"))
    prose_plan = build_prompt_plan(brief, choose_route(brief, graph, requested="natural-language-led"))

    tag_segments = {segment.segment_id: segment for segment in tag_plan.segments}
    prose_segments = {segment.segment_id: segment for segment in prose_plan.segments}
    assert tag_segments["fact:coat"].representation == "tag"
    assert tag_segments["fact:walk"].representation == "prose"
    assert prose_segments["fact:coat"].representation == "prose"
    assert prose_segments["fact:walk"].representation == "prose"
    assert prose_segments["fact:coat"].text == tag_segments["fact:coat"].text == "black coat"


def test_source_priority_controls_same_domain_order_without_rewriting_facts():
    brief = make_brief(facts=(
        Fact("fact:local", "local detail", "appearance", "inferred", "local_model"),
        Fact("fact:user", "user detail", "appearance", "explicit", "user"),
    ))
    graph = build_relation_graph(brief)
    draft = build_draft(build_prompt_plan(brief, choose_route(brief, graph)), brief)
    assert draft.positive_text == "girl, user detail, local detail"


def test_model_profile_policies_participate_in_nonblocking_inspection():
    brief = make_brief(
        facts=(Fact("fact:coat", "black coat", "clothing", "explicit", "user"),),
        exclusions=tuple(Fact(f"fact:bad:{i}", f"bad detail {i}", "quality", "explicit", "user") for i in range(9)),
    )
    graph = build_relation_graph(brief)
    profile = default_model_profile("turbo", trigger_words=("model_trigger",))
    profile = profile.__class__(
        profile.variant, profile.tag_preference, profile.natural_language_preference,
        profile.negative_tolerance, "required", profile.trigger_words,
        3, profile.source, profile.evidence_level,
    )
    decision = choose_route(brief, graph, profile=profile)
    draft = build_draft(build_prompt_plan(brief, decision), brief)
    report = inspect_draft(draft, brief=brief, graph=graph, tokenizer=lambda text: len(text.split()))
    codes = {issue.code for issue in report.issues}
    assert {"missing_model_trigger", "missing_required_positive_quality", "missing_required_negative_quality", "token_limit_exceeded", "negative_too_long"} <= codes


def test_model_profile_preferences_participate_in_auto_route():
    scene_brief = make_brief(facts=(Fact("fact:scene", "a long spatial description", "scene", "explicit", "user"),))
    scene_graph = build_relation_graph(scene_brief)
    aesthetic = default_model_profile("aesthetic")
    assert choose_route(scene_brief, scene_graph, profile=aesthetic).route == "natural-language-led"

    tag_brief = make_brief(facts=(Fact("fact:coat", "black coat", "clothing", "explicit", "user", representation_hint="tag"),))
    tag_graph = build_relation_graph(tag_brief)
    turbo = default_model_profile("turbo")
    assert choose_route(tag_brief, tag_graph, profile=turbo).route == "tag-led"


def test_negative_author_preserves_required_quality_before_explicit_layers():
    brief = make_brief(exclusions=(
        Fact("quality:base:negative:low-quality", "low quality", "quality", "explicit", "official", notes=("required_by_anima_variant",)),
        Fact("fact:exclude", "blurry", "quality", "explicit", "user"),
    ))
    structural = PromptSegment("structural:anatomy", "negative", "bad anatomy", "model", "prose")
    catalog = Catalog()
    result = build_negative_segments(brief, catalog, "hybrid", structural_defects=(structural,))
    assert [segment.text for segment in result] == ["low quality", "blurry", "bad anatomy"]


def test_action_segment_keeps_relation_provenance():
    action = Fact("fact:grab", "grab", "action", "explicit", "user", subject_id="subject:0")
    relation = RelationClaim("rel:target", "receives_or_is_target_of", "subject:1", "fact:grab", True, "fact:grab")
    brief = make_brief(facts=(action,), subjects=("girl", "boy"), relations=(relation,))
    graph = build_relation_graph(brief)
    draft = build_draft(build_prompt_plan(brief, choose_route(brief, graph)), brief)
    segment = next(item for item in draft.segments if item.fact_id == "fact:grab")
    assert segment.subject_id == "subject:0"
    assert segment.relation_ids == ("rel:target",)


def test_brief_rejects_duplicate_ids():
    try:
        make_brief(facts=(
            Fact("same", "a", "appearance", "explicit", "user"),
            Fact("same", "b", "appearance", "explicit", "user"),
        ))
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate fact ids must be rejected")


def test_draft_contains_both_channels_and_keeps_special_syntax():
    brief = make_brief(
        facts=(Fact("fact:subject", "girl", "subject", "explicit", "user"),),
        exclusions=(Fact("fact:exclude", "blurry", "quality", "explicit", "user"),),
        locked=(
            LockedSegment("lock:trigger", "<lora:detail:1>", "trigger"),
            LockedSegment("lock:wildcard", "{character}", "wildcard"),
            LockedSegment("lock:weight", "(cinematic:1.2)", "weight"),
        ),
    )
    graph = build_relation_graph(brief)
    decision = choose_route(brief, graph)
    draft = build_draft(build_prompt_plan(brief, decision), brief)

    assert draft.positive_text == "<lora:detail:1>, {character}, (cinematic:1.2), girl"
    assert draft.negative_text == "blurry"
    assert {segment.text for segment in draft.segments} >= {"<lora:detail:1>", "{character}", "(cinematic:1.2)", "blurry"}


def test_inspector_is_read_only_and_non_blocking():
    brief = make_brief(
        facts=(Fact("fact:walk", "walk", "action", "explicit", "user"),),
        subjects=("girl", "boy"),
        exclusions=(Fact("fact:exclude", "girl", "subject", "explicit", "user"),),
    )
    graph = build_relation_graph(brief)
    decision = choose_route(brief, graph)
    draft = build_draft(build_prompt_plan(brief, decision), brief)
    report = inspect_draft(draft, brief=brief, graph=graph, tokenizer=lambda text: len(text.split()))

    assert report.token_estimate is not None
    assert {issue.code for issue in report.issues} >= {"positive_negative_conflict", "action_without_actor", "missing_multi_subject_relation"}
    assert draft.positive_text == "girl, boy, walk"


def test_inspector_reports_missing_relation_provenance_without_mutating_draft():
    action = Fact("fact:grab", "grab", "action", "explicit", "user", subject_id="subject:0")
    relation = RelationClaim("rel:target", "receives_or_is_target_of", "subject:1", "fact:grab", True, "fact:grab")
    brief = make_brief(facts=(action,), subjects=("girl", "boy"), relations=(relation,))
    graph = build_relation_graph(brief)
    decision = choose_route(brief, graph)
    segment = PromptSegment("fact:grab", "positive", "grab", "user", "prose", fact_id="fact:grab", subject_id="subject:0")
    draft = PromptDraft((segment,), "grab", "", decision.route, decision.profile)
    report = inspect_draft(draft, brief=brief, graph=graph)
    assert any(issue.code == "relation_provenance_missing" for issue in report.issues)
    assert draft.positive_text == "grab"


def test_locked_segment_mismatch_is_nonblocking_advisory():
    brief = make_brief(locked=(LockedSegment("lock:trigger", "<lora:detail:1>", "trigger"),))
    graph = build_relation_graph(brief)
    decision = choose_route(brief, graph)
    draft = PromptDraft((PromptSegment("other", "positive", "girl", "user", "tag"),), "girl", "", decision.route, decision.profile)
    report = inspect_draft(draft, brief=brief, graph=graph)
    assert any(issue.code == "locked_segment_missing" for issue in report.issues)
    assert draft.positive_text == "girl"


def test_output_has_exactly_five_machine_fields():
    output = PromptOutput("girl", "blurry", notes=("source:user",), assumptions=("none",), advisories=("warning:x",))
    assert "POSITIVE:" in to_text_output(output)
    assert "NEGATIVE:" in to_text_output(output)
    payload = json.loads(to_json_output(output))
    assert tuple(payload) == ("positive", "negative", "notes", "assumptions", "advisories")


def test_output_keeps_catalog_trace_and_unknown_assumptions_outside_copyable_prompt():
    brief = make_brief(facts=(
        Fact("fact:hair", "long_hair", "hair", "explicit", "user", representation_hint="tag"),
        Fact("fact:unknown", "user_defined_trigger", "appearance", "unknown", "user"),
    ))
    graph = build_relation_graph(brief)
    draft = build_draft(build_prompt_plan(brief, choose_route(brief, graph), catalog=Catalog()), brief)
    output = output_from_draft(draft)
    assert "long_hair" in output.positive
    assert any(item.startswith("catalog:fact:hair:") for item in output.notes)
    assert output.assumptions == ("unknown:fact:unknown:user_defined_trigger",)


def test_catalog_search_is_explainable_and_read_only():
    catalog = Catalog(Path(__file__).parents[1] / "knowledge" / "tag-catalog.sqlite")
    hit = catalog.search("longhair", mode="alias", limit=1)[0]
    assert hit.match_type == "alias"
    assert hit.matched_name == "longhair"
    assert hit.score > 0
    assert catalog.search("nude", mode="prefix", facets=("nsfw",), limit=1)
