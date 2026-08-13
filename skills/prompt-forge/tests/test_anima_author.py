from __future__ import annotations

from prompt_forge import author_anima_prompt
from prompt_forge.contracts import (
    AnimaAuthoringRequest,
    AuthoredSegment,
    Complexity,
    Fact,
)


def fact(
    fact_id: str,
    value: str,
    *,
    dimension: str = "appearance",
    origin: str = "user_explicit",
    owner: str = "subject_1",
) -> Fact:
    return Fact(
        fact_id,
        value,
        origin,  # type: ignore[arg-type]
        origin == "user_locked",
        owner,
        dimension,
    )


def segment(
    segment_id: str,
    field: str,
    text: str,
    *fact_ids: str,
) -> AuthoredSegment:
    return AuthoredSegment(segment_id, field, text, tuple(fact_ids), 5, 2, 1)


def request(
    facts: tuple[Fact, ...],
    positive: tuple[AuthoredSegment, ...],
    *,
    complexity: Complexity | None = None,
    negative: tuple[AuthoredSegment, ...] = (),
    exclusions: int = 0,
) -> AnimaAuthoringRequest:
    return AnimaAuthoringRequest(
        facts=facts,
        positive_segments=positive,
        complexity=complexity or Complexity(1, 0, 0, 0, 0),
        negative_segments=negative,
        exclusion_groups=exclusions,
    )


def test_tag_only_output_uses_official_field_order() -> None:
    facts = (
        fact("protocol", "masterpiece", dimension="quality"),
        fact("count", "1girl", dimension="count"),
        fact("character", "hatsune miku", dimension="identity"),
        fact("series", "vocaloid", dimension="series"),
        fact("artist", "@kantoku", dimension="artist"),
        fact("appearance", "blue hair"),
    )
    positive = (
        segment("appearance", "appearance", "blue hair", "appearance"),
        segment("artist", "artist", "@kantoku", "artist"),
        segment("series", "series", "vocaloid", "series"),
        segment("character", "character", "hatsune miku", "character"),
        segment("count", "count", "1girl", "count"),
        segment("protocol", "protocol_prefix", "masterpiece", "protocol"),
    )
    artifact = author_anima_prompt(request(facts, positive))
    assert artifact.status == "production_ready"
    assert artifact.prompt == {
        "positive": "masterpiece, 1girl, hatsune miku, vocaloid, @kantoku, blue hair",
        "negative": "",
    }
    assert artifact.sacrificed_facts == ()
    assert artifact.token_count_verified


def test_hybrid_output_allows_exactly_one_necessary_binding_bridge() -> None:
    facts = (
        fact("protocol", "masterpiece", dimension="quality"),
        fact("count", "2girls", dimension="count"),
        fact("relation", "subject 1 holds subject 2's umbrella", dimension="ownership"),
    )
    artifact = author_anima_prompt(
        request(
            facts,
            (
                segment("protocol", "protocol_prefix", "masterpiece", "protocol"),
                segment("count", "count", "2girls", "count"),
                segment(
                    "bridge",
                    "scene_description",
                    "Subject 1 holds Subject 2's umbrella.",
                    "relation",
                ),
            ),
            complexity=Complexity(2, 1, 1, 0, 1),
        )
    )
    assert artifact.status == "production_ready"
    assert artifact.prompt is not None
    assert artifact.prompt["positive"] == (
        "masterpiece, 2girls. Subject 1 holds Subject 2's umbrella."
    )


def test_tag_and_bridge_cannot_render_the_same_fact() -> None:
    facts = (fact("relation", "holding umbrella", dimension="ownership"),)
    artifact = author_anima_prompt(
        request(
            facts,
            (
                segment("tag", "general", "holding umbrella", "relation"),
                segment(
                    "bridge",
                    "scene_description",
                    "The subject is holding an umbrella.",
                    "relation",
                ),
            ),
            complexity=Complexity(1, 1, 1, 0, 1),
        )
    )
    assert artifact.status == "quality_rejected"
    assert artifact.prompt is None
    assert "tag_bridge_fact_overlap" in artifact.audit["hard_gate_codes"]


def test_malformed_protocol_tag_is_quality_rejected_without_prompt() -> None:
    artifact = author_anima_prompt(
        request(
            (fact("hair", "blue hair"),),
            (segment("hair", "general", "blue_hair", "hair"),),
        )
    )
    assert artifact.status == "quality_rejected"
    assert artifact.prompt is None
    assert "wrong_underscore_form" in artifact.audit["hard_gate_codes"]


def test_positive_negative_contradiction_is_rejected() -> None:
    facts = (
        fact("positive", "blue hair"),
        fact("negative", "blue hair", dimension="exclusion"),
    )
    artifact = author_anima_prompt(
        request(
            facts,
            (segment("positive", "general", "blue hair", "positive"),),
            negative=(segment("negative", "user_exclusions", "blue hair", "negative"),),
            exclusions=1,
        )
    )
    assert artifact.status == "quality_rejected"
    assert artifact.prompt is None
    assert "positive_negative_contradiction" in artifact.audit["hard_gate_codes"]


def test_protected_content_over_quality_limit_returns_budget_conflict() -> None:
    huge = " ".join(f"visibleconcept{i}" for i in range(1000))
    artifact = author_anima_prompt(
        request(
            (fact("huge", huge, origin="user_locked"),),
            (segment("huge", "general", huge, "huge"),),
            complexity=Complexity(20, 20, 20, 20, 0),
        )
    )
    assert artifact.status == "budget_conflict"
    assert artifact.prompt is None
    assert artifact.conflict is not None
    assert artifact.conflict["actual_tokens"] > 768
    assert artifact.sacrificed_facts == ()


def test_budget_conflict_surfaces_protocol_errors_in_one_pass() -> None:
    huge = " ".join(f"visibleconcept{i}" for i in range(1000))
    artifact = author_anima_prompt(
        request(
            (
                fact("huge", huge, origin="user_locked"),
                fact("style", "style", origin="user_locked"),
            ),
            (segment("huge", "general", huge, "huge"),),
            complexity=Complexity(20, 20, 20, 20, 0),
            negative=(
                AuthoredSegment(
                    "neg_bad", "quality_baseline",
                    "score_4, score_5", ("style",), 5, 2, 1,
                ),
            ),
        )
    )
    assert artifact.status == "budget_conflict"
    assert artifact.prompt is None
    codes = set(artifact.audit["hard_gate_codes"])
    assert "token_quality_limit" in codes
    assert "invalid_protocol_tag" in codes
    assert artifact.audit["negative"] is not None
    assert any(
        finding["code"] == "invalid_protocol_tag"
        for finding in artifact.audit["negative"]["findings"]
    )


def test_budget_conflict_reports_preflight_field_errors() -> None:
    huge = " ".join(f"visibleconcept{i}" for i in range(1000))
    artifact = author_anima_prompt(
        request(
            (
                fact("huge", huge, origin="user_locked"),
                fact("style", "style", origin="user_locked"),
            ),
            (
                segment("huge", "general", huge, "huge"),
                segment("badfield", "bogus_field", "scar", "style"),
            ),
            complexity=Complexity(20, 20, 20, 20, 0),
        )
    )
    assert artifact.status == "budget_conflict"
    codes = set(artifact.audit["hard_gate_codes"])
    assert "token_quality_limit" in codes
    assert "unsupported_positive_field" in codes


def test_negative_prompt_uses_its_own_budget_and_token_report() -> None:
    facts = (
        fact("protocol", "masterpiece", dimension="quality"),
        fact("positive", "1girl", dimension="count"),
        fact("negative", "blurry", dimension="technical_defect"),
    )
    artifact = author_anima_prompt(
        request(
            facts,
            (
                segment("protocol", "protocol_prefix", "masterpiece", "protocol"),
                segment("positive", "count", "1girl", "positive"),
            ),
            negative=(
                segment("negative", "technical_defects", "blurry", "negative"),
            ),
            exclusions=1,
        )
    )
    assert artifact.status == "production_ready"
    assert artifact.prompt == {"positive": "masterpiece, 1girl", "negative": "blurry"}
    assert artifact.token_report["negative"]["target"] == 40
    assert artifact.token_report["negative"]["actual"] > 0


def test_segment_render_weight_defaults_none():
    from prompt_forge.contracts import AuthoredSegment
    seg = AuthoredSegment(
        segment_id="s1", field="general", text="smile",
        fact_ids=("f1",), priority=1.0, adherence_risk=1.0, source_confidence=1.0,
    )
    assert seg.render_weight is None


def test_anima_request_variant_defaults_base():
    from prompt_forge.contracts import AnimaAuthoringRequest, Complexity
    req = AnimaAuthoringRequest(
        facts=(), positive_segments=(), complexity=Complexity(1, 0, 0, 0, 0),
    )
    assert req.variant == "base"


def test_unresolvable_at_prefix_is_warning_not_error():
    from prompt_forge.anima.audit import audit_anima_prompt
    from prompt_forge.facts import FactLedger
    from prompt_forge.contracts import Fact
    ledger = FactLedger((
        Fact("f1", "@my style", "agent_embellishment", False, "s", "style"),
    ))
    report = audit_anima_prompt(("@my style",), "", ledger)
    assert all(f.severity != "error" for f in report.findings)


def test_author_renders_weighted_segment():
    from prompt_forge.anima.author import author_anima_prompt
    from prompt_forge.contracts import (
        AnimaAuthoringRequest, AuthoredSegment, Complexity, Fact,
    )
    facts = (
        Fact("f0", "masterpiece", "user_locked", True, "s", "quality"),
        Fact("f1", "smile", "agent_embellishment", False, "s", "expression"),
    )
    prefix = AuthoredSegment(
        "s0", "protocol_prefix", "masterpiece", ("f0",), 1.0, 1.0, 1.0,
    )
    seg = AuthoredSegment(
        "s1", "general", "smile", ("f1",), 1.0, 1.0, 1.0, render_weight=1.3,
    )
    req = AnimaAuthoringRequest(
        facts=facts, positive_segments=(prefix, seg),
        complexity=Complexity(1, 0, 0, 0, 0),
    )
    art = author_anima_prompt(req)
    assert art.status == "production_ready"
    assert "(smile:1.3)" in art.prompt["positive"]


def test_author_rejects_old_field_names():
    from prompt_forge.anima.author import author_anima_prompt
    from prompt_forge.contracts import (
        AnimaAuthoringRequest, AuthoredSegment, Complexity, Fact,
    )
    facts = (Fact("f1", "smile", "agent_embellishment", False, "s", "expression"),)
    seg = AuthoredSegment("s1", "composition_and_camera", "smile", ("f1",), 1.0, 1.0, 1.0)
    req = AnimaAuthoringRequest(
        facts=facts, positive_segments=(seg,),
        complexity=Complexity(1, 0, 0, 0, 0),
    )
    art = author_anima_prompt(req)
    assert art.status == "quality_rejected"
    assert "unsupported_positive_field" in art.audit["hard_gate_codes"]


def test_weighted_artist_tag_is_not_artist_prefix_missing():
    from prompt_forge.anima.audit import audit_anima_prompt
    from prompt_forge.facts import FactLedger
    from prompt_forge.contracts import Fact
    ledger = FactLedger((
        Fact("f1", "@kantoku", "user_explicit", False, "s", "artist"),
    ))
    report = audit_anima_prompt(("(@kantoku:2.0)",), "", ledger)
    assert all(f.code != "artist_prefix_missing" for f in report.findings)
