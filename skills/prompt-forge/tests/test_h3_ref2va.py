from __future__ import annotations

import pytest

from prompt_forge import author_h3_ref2va_prompt
from prompt_forge.contracts import (
    AuthoredSegment,
    Fact,
    H3Ref2VAAuthoringRequest,
    H3ReferenceImage,
)
from prompt_forge.h3.common import (
    H3AuditError,
    audit_reference_labels,
    plan_h3_context,
    visual_tokens,
)


class FixedCounter:
    snapshot_id = "h3-qwen3-vl"

    def count(self, text: str) -> int:
        return len(text)


def reference(index: int, width: int = 1024, height: int = 1024) -> H3ReferenceImage:
    return H3ReferenceImage(f"Picture {index}", f"subject_{index}", width, height)


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (256, 256, 64),
        (1024, 1024, 1024),
        (1025, 1025, 1089),
        (4096, 4096, 16384),
    ],
)
def test_visual_tokens_match_patch16_merge2_accounting(
    width: int,
    height: int,
    expected: int,
) -> None:
    assert visual_tokens(reference(1, width, height)) == expected


@pytest.mark.parametrize(
    ("width", "height"),
    [(255, 255), (4097, 4096), (0, 1024), (1024, -1)],
)
def test_visual_dimensions_must_be_verified_processor_outputs(
    width: int,
    height: int,
) -> None:
    with pytest.raises(H3AuditError, match="pixel"):
        visual_tokens(reference(1, width, height))


def test_context_budget_subtracts_visual_chat_special_and_margin_exactly() -> None:
    counter = FixedCounter()
    refs = (reference(1, 1024, 1024), reference(2, 1024, 1024))
    context = plan_h3_context(
        counter,  # type: ignore[arg-type]
        refs,
        text_quality_limit=2400,
        special_tokens=7,
        runtime_safety_margin=4096,
    )
    expected_chat = len(
        "<|im_start|>user\n"
        "Picture 1: <|vision_start|><|image_pad|><|vision_end|>\n"
        "Picture 2: <|vision_start|><|image_pad|><|vision_end|>\n"
        "<|im_end|>\n"
    )
    assert context.visual_tokens == 2048
    assert context.chat_template_tokens == expected_chat
    assert context.available_tokens == 262_144 - 2048 - expected_chat - 7 - 4096
    assert context.effective_quality_limit == 2400


def test_available_context_never_increases_text_quality_limit() -> None:
    context = plan_h3_context(
        FixedCounter(),  # type: ignore[arg-type]
        (reference(1),),
        text_quality_limit=650,
        special_tokens=0,
        runtime_safety_margin=0,
    )
    assert context.effective_quality_limit == 650


def test_reference_labels_are_sequential_defined_and_owned() -> None:
    refs = (reference(1), reference(2))
    definitions = (
        "<Subject 1> is the woman in <Picture 1>.\n"
        "<Subject 2> is the café in <Picture 2>."
    )
    usage = "<Subject 1> enters <Subject 2>, following <Picture 2>."
    audit_reference_labels(definitions, usage, refs)
    with pytest.raises(H3AuditError, match="ordered input"):
        audit_reference_labels(definitions, usage + " <Picture 3>", refs)
    with pytest.raises(H3AuditError, match="collision"):
        audit_reference_labels(
            "<Subject 1> is person A.\n<Subject 1> is person B.",
            "<Subject 1> moves.",
            refs,
        )


def authored(
    segment_id: str,
    field: str,
    text: str,
    *fact_ids: str,
) -> AuthoredSegment:
    return AuthoredSegment(segment_id, field, text, tuple(fact_ids), 5, 2, 1)


def ref_fact(
    fact_id: str,
    value: str,
    *,
    owner: str = "subject_1",
    dimension: str = "reference_relation",
    origin: str = "user_explicit",
) -> Fact:
    return Fact(
        fact_id,
        value,
        origin,  # type: ignore[arg-type]
        origin == "user_locked",
        owner,
        dimension,
    )


def ref_request(
    facts: tuple[Fact, ...],
    refs: tuple[H3ReferenceImage, ...],
    definitions: tuple[AuthoredSegment, ...],
    summary: tuple[AuthoredSegment, ...],
    retention: tuple[AuthoredSegment, ...],
    detail: tuple[AuthoredSegment, ...],
    *,
    duration: float = 5,
    shots: int = 1,
    soundscape: tuple[AuthoredSegment, ...] = (),
    music: tuple[AuthoredSegment, ...] = (),
) -> H3Ref2VAAuthoringRequest:
    return H3Ref2VAAuthoringRequest(
        facts,
        duration,
        shots,
        refs,
        definitions,
        summary,
        retention,
        detail,
        soundscape,
        music,
    )


def one_reference_request() -> H3Ref2VAAuthoringRequest:
    facts = (
        ref_fact("definition", "woman from Picture 1", dimension="stable_appearance"),
        ref_fact("summary", "reference generation", dimension="task_summary"),
        ref_fact("retention", "fully preserved", dimension="retention"),
        ref_fact("action", "raises the umbrella and settles", dimension="action_result"),
    )
    return ref_request(
        facts,
        (reference(1),),
        (
            authored(
                "definition",
                "subject_definitions",
                "<Subject 1> is the woman in <Picture 1>, with long dark hair and a blue coat.",
                "definition",
            ),
        ),
        (
            authored(
                "summary",
                "summary",
                "[reference generation] <Subject 1> performs one continuous action.",
                "summary",
            ),
        ),
        (
            authored(
                "retention",
                "retention_analysis",
                "<Subject 1> (appears in [Shot 1]): fully_preserved - appearance remains tied to <Picture 1>.",
                "retention",
            ),
        ),
        (
            authored(
                "action",
                "detailed_description",
                "Cinematic 2D animation with soft daylight. [Shot 1] <Subject 1> raises the umbrella and settles into a stable pose.",
                "action",
            ),
        ),
    )


def test_ref2va_one_reference_golden_uses_exact_six_field_order() -> None:
    artifact = author_h3_ref2va_prompt(one_reference_request())
    assert artifact.status == "production_ready"
    assert artifact.prompt is not None
    text = artifact.prompt["text"]
    labels = [
        "subject_definitions:",
        "summary:",
        "retention_analysis:",
        "detailed_description:",
        "overall_soundscape:",
        "non_diegetic_music:",
    ]
    assert [text.index(label) for label in labels] == sorted(text.index(label) for label in labels)
    assert text.endswith("non_diegetic_music: N/A")
    assert artifact.token_report["context"]["visual_tokens"] == 1024


def test_ref2va_three_references_preserve_order_and_ownership() -> None:
    refs = tuple(reference(index) for index in range(1, 4))
    facts = tuple(
        ref_fact(
            f"definition_{index}",
            f"subject {index}",
            owner=f"subject_{index}",
            dimension="stable_appearance",
        )
        for index in range(1, 4)
    ) + (
        ref_fact("summary", "reference generation", dimension="task_summary"),
        ref_fact("retention", "all retained", dimension="retention"),
        ref_fact("action", "all three subjects stop", dimension="action_result"),
    )
    definitions = tuple(
        authored(
            f"definition_{index}",
            "subject_definitions",
            f"<Subject {index}> is subject {index} from <Picture {index}>.",
            f"definition_{index}",
        )
        for index in range(1, 4)
    )
    artifact = author_h3_ref2va_prompt(
        ref_request(
            facts,
            refs,
            definitions,
            (
                authored(
                    "summary",
                    "summary",
                    "[reference generation] <Subject 1>, <Subject 2>, and <Subject 3> share one shot.",
                    "summary",
                ),
            ),
            (
                authored(
                    "retention",
                    "retention_analysis",
                    "<Subject 1> from <Picture 1>, <Subject 2> from <Picture 2>, and <Subject 3> from <Picture 3> are fully_preserved.",
                    "retention",
                ),
            ),
            (
                authored(
                    "action",
                    "detailed_description",
                    "Cinematic animation. [Shot 1] <Subject 1>, <Subject 2>, and <Subject 3> walk forward and all three subjects stop.",
                    "action",
                ),
            ),
        )
    )
    assert artifact.status == "production_ready"
    assert artifact.token_report["context"]["visual_tokens"] == 3072
    assert artifact.token_report["text"]["target"] >= 650


def test_ref2va_stable_appearance_must_only_be_defined_once() -> None:
    base = one_reference_request()
    duplicated = authored(
        "duplicate",
        "detailed_description",
        "[Shot 1] The woman has long dark hair and a blue coat.",
        "definition",
    )
    artifact = author_h3_ref2va_prompt(
        H3Ref2VAAuthoringRequest(
            base.facts,
            base.duration_seconds,
            base.shot_count,
            base.references,
            base.subject_definitions,
            base.summary,
            base.retention_analysis,
            base.detailed_description + (duplicated,),
        )
    )
    assert artifact.status == "quality_rejected"
    assert artifact.prompt is None
    assert "stable_appearance_scope" in artifact.audit["hard_gate_codes"]


def test_ref2va_reference_collision_is_rejected() -> None:
    base = one_reference_request()
    collision = authored(
        "collision",
        "subject_definitions",
        "<Subject 1> is a different person from <Picture 1>.",
        "definition",
    )
    artifact = author_h3_ref2va_prompt(
        H3Ref2VAAuthoringRequest(
            base.facts,
            base.duration_seconds,
            base.shot_count,
            base.references,
            base.subject_definitions + (collision,),
            base.summary,
            base.retention_analysis,
            base.detailed_description,
        )
    )
    assert artifact.status == "quality_rejected"
    assert "reference_binding" in artifact.audit["hard_gate_codes"]


def test_ref2va_missing_verified_dimensions_is_rejected() -> None:
    base = one_reference_request()
    invalid_ref = H3ReferenceImage("Picture 1", "subject_1", 0, 1024)
    artifact = author_h3_ref2va_prompt(
        H3Ref2VAAuthoringRequest(
            base.facts,
            base.duration_seconds,
            base.shot_count,
            (invalid_ref,),
            base.subject_definitions,
            base.summary,
            base.retention_analysis,
            base.detailed_description,
        )
    )
    assert artifact.status == "quality_rejected"
    assert artifact.prompt is None
    assert "context_verification" in artifact.audit["hard_gate_codes"]


def test_ref2va_protected_content_over_2400_tokens_conflicts() -> None:
    huge = " ".join(f"visiblechange{i}" for i in range(3000))
    base = one_reference_request()
    huge_fact = ref_fact("huge", huge, dimension="action_result", origin="user_locked")
    huge_detail = authored(
        "huge",
        "detailed_description",
        f"[Shot 1] {huge}",
        "huge",
    )
    artifact = author_h3_ref2va_prompt(
        H3Ref2VAAuthoringRequest(
            (huge_fact,),
            15,
            1,
            base.references,
            (
                authored(
                    "definition",
                    "subject_definitions",
                    "<Subject 1> is the subject from <Picture 1>.",
                    "huge",
                ),
            ),
            (authored("summary", "summary", "[reference generation] <Subject 1>.", "huge"),),
            (
                authored(
                    "retention",
                    "retention_analysis",
                    "<Subject 1> from <Picture 1> is fully_preserved.",
                    "huge",
                ),
            ),
            (huge_detail,),
        )
    )
    assert artifact.status == "budget_conflict"
    assert artifact.prompt is None
    assert artifact.conflict is not None
