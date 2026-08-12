from __future__ import annotations

import pytest

from prompt_forge import author_h3_t2va_prompt
from prompt_forge.contracts import AuthoredSegment, Fact, H3T2VAAuthoringRequest
from prompt_forge.facts import FactLedger
from prompt_forge.h3.common import (
    H3AuditError,
    audit_dialogue_and_visible_text,
    audit_sound_music_separation,
    parse_shots,
)


def test_parse_single_and_multi_shot_timeline() -> None:
    single = parse_shots(
        "[Shot 1] A baker opens the shutters, then sets the loaf down.",
        duration_seconds=5,
        declared_shot_count=1,
    )
    assert [(shot.number, shot.start_seconds, shot.end_seconds) for shot in single] == [
        (1, 0.0, 5.0)
    ]

    multiple = parse_shots(
        "[Shot 1] A runner enters and stops. "
        "[Shot 2] At 00:03.500, the camera cuts to her shoes as they settle.",
        duration_seconds=8,
        declared_shot_count=2,
    )
    assert [(shot.number, shot.start_seconds, shot.end_seconds) for shot in multiple] == [
        (1, 0.0, 3.5),
        (2, 3.5, 8.0),
    ]


@pytest.mark.parametrize(
    ("description", "duration", "count", "message"),
    [
        ("[Shot 1] At 00:00.000, invalid opening.", 5, 1, "first shot"),
        ("[Shot 2] At 00:03.000, missing first.", 5, 1, "sequential"),
        (
            "[Shot 1] start [Shot 2] At 00:04.000, later "
            "[Shot 3] At 00:03.000, backward",
            10,
            3,
            "strictly increasing",
        ),
        ("[Shot 1] start [Shot 2] At 00:05.000, outside", 5, 2, "duration"),
        ("[Shot 1] start [Shot 2] At 00:03.000, too dense", 3, 2, "max_shots"),
    ],
)
def test_illegal_timeline_is_rejected(
    description: str,
    duration: float,
    count: int,
    message: str,
) -> None:
    with pytest.raises(H3AuditError, match=message):
        parse_shots(description, duration_seconds=duration, declared_shot_count=count)


def test_dialogue_and_visible_text_are_preserved_exactly() -> None:
    ledger = FactLedger(
        (
            Fact("line", "I get off here!", "user_locked", True, "S1", "dialogue"),
            Fact("sign", "营业中", "user_locked", True, "scene", "visible_text"),
        )
    )
    valid = (
        'The woman (S1) says: <d>[English] I get off here!</d> '
        'A neon sign reading "营业中" glows.'
    )
    audit_dialogue_and_visible_text(valid, ledger)
    with pytest.raises(H3AuditError, match="dialogue"):
        audit_dialogue_and_visible_text(valid.replace("here!", "there!"), ledger)
    with pytest.raises(H3AuditError, match="visible text"):
        audit_dialogue_and_visible_text(valid.replace("营业中", "OPEN"), ledger)


def test_soundscape_and_non_diegetic_music_cannot_mix_roles() -> None:
    audit_sound_music_separation(
        "Rain taps the windows while footsteps cross the floor.",
        "Sparse piano notes at a slow tempo.",
    )
    with pytest.raises(H3AuditError, match="dialogue"):
        audit_sound_music_separation("<d>[English] Hello.</d>", "N/A")
    with pytest.raises(H3AuditError, match="non-diegetic"):
        audit_sound_music_separation("Non-diegetic piano plays.", "N/A")


def authored(
    segment_id: str,
    field: str,
    text: str,
    *fact_ids: str,
) -> AuthoredSegment:
    return AuthoredSegment(segment_id, field, text, tuple(fact_ids), 5, 2, 1)


def h3_fact(
    fact_id: str,
    value: str,
    *,
    dimension: str = "action",
    origin: str = "user_explicit",
) -> Fact:
    return Fact(
        fact_id,
        value,
        origin,  # type: ignore[arg-type]
        origin == "user_locked",
        "subject_1",
        dimension,
    )


def t2va_request(
    facts: tuple[Fact, ...],
    description: tuple[AuthoredSegment, ...],
    *,
    duration: float = 5,
    shots: int = 1,
    soundscape: tuple[AuthoredSegment, ...] = (),
    music: tuple[AuthoredSegment, ...] = (),
) -> H3T2VAAuthoringRequest:
    return H3T2VAAuthoringRequest(
        facts,
        duration,
        shots,
        description,
        soundscape,
        music,
    )


def test_t2va_golden_single_shot_uses_exact_three_field_order() -> None:
    facts = (
        h3_fact("action", "opens the shutters and sets the loaf down"),
        h3_fact("sound", "Wood scrapes while trays clink.", dimension="ambient_sound"),
    )
    artifact = author_h3_t2va_prompt(
        t2va_request(
            facts,
            (
                authored(
                    "shot",
                    "integrated_multimodal_description",
                    "[Shot 1] Live-action, a baker opens the shutters and sets the loaf down.",
                    "action",
                ),
            ),
            soundscape=(
                authored("sound", "overall_soundscape", "Wood scrapes while trays clink.", "sound"),
            ),
        )
    )
    assert artifact.status == "production_ready"
    assert artifact.prompt is not None
    assert artifact.prompt["text"] == (
        "integrated_multimodal_description: [Shot 1] Live-action, a baker opens the shutters and sets the loaf down.\n\n"
        "overall_soundscape: Wood scrapes while trays clink.\n\n"
        "non_diegetic_music: N/A"
    )


def test_t2va_legal_multi_shot_and_dialogue_are_preserved() -> None:
    line = "Wait for me!"
    facts = (
        h3_fact("timeline", "runner reaches the doorway"),
        h3_fact("line", line, dimension="dialogue", origin="user_locked"),
    )
    description = (
        "[Shot 1] A runner crosses the hall and reaches the doorway. "
        "The young runner (S1) says: <d>[English] Wait for me!</d> "
        "[Shot 2] At 00:03.500, the camera cuts to her shoes as they stop on the mat."
    )
    artifact = author_h3_t2va_prompt(
        t2va_request(
            facts,
            (authored("timeline", "integrated_multimodal_description", description, "timeline", "line"),),
            duration=8,
            shots=2,
        )
    )
    assert artifact.status == "production_ready"
    assert artifact.prompt is not None and f"<d>[English] {line}</d>" in artifact.prompt["text"]
    assert artifact.token_report["text"]["target"] > 300


def test_t2va_over_dense_plan_is_quality_rejected() -> None:
    artifact = author_h3_t2va_prompt(
        t2va_request(
            (h3_fact("action", "changes viewpoint"),),
            (
                authored(
                    "timeline",
                    "integrated_multimodal_description",
                    "[Shot 1] Start and settle. [Shot 2] At 00:02.000, the camera cuts to a new view.",
                    "action",
                ),
            ),
            duration=3,
            shots=2,
        )
    )
    assert artifact.status == "quality_rejected"
    assert artifact.prompt is None
    assert "timeline" in artifact.audit["hard_gate_codes"]


def test_t2va_rejects_a_cut_without_model_native_transition() -> None:
    artifact = author_h3_t2va_prompt(
        t2va_request(
            (h3_fact("action", "changes viewpoint"),),
            (
                authored(
                    "timeline",
                    "integrated_multimodal_description",
                    "[Shot 1] The runner stops at the door. "
                    "[Shot 2] At 00:03.500, the runner is still at the door.",
                    "action",
                ),
            ),
            duration=8,
            shots=2,
        )
    )
    assert artifact.status == "quality_rejected"
    assert "timeline" in artifact.audit["hard_gate_codes"]


def test_t2va_protected_temporal_text_over_1200_tokens_conflicts() -> None:
    huge = " ".join(f"actionstate{i}" for i in range(1600))
    artifact = author_h3_t2va_prompt(
        t2va_request(
            (h3_fact("huge", huge, origin="user_locked"),),
            (
                authored(
                    "huge",
                    "integrated_multimodal_description",
                    f"[Shot 1] {huge}",
                    "huge",
                ),
            ),
            duration=15,
        )
    )
    assert artifact.status == "budget_conflict"
    assert artifact.prompt is None
    assert artifact.conflict is not None
    assert artifact.conflict["actual_tokens"] > 1200


@pytest.mark.parametrize("duration", [2, 5, 10, 15])
def test_t2va_duration_strata_use_dynamic_budgets(duration: int) -> None:
    artifact = author_h3_t2va_prompt(
        t2va_request(
            (h3_fact("action", "ball rolls and stops"),),
            (
                authored(
                    "action",
                    "integrated_multimodal_description",
                    "[Shot 1] A ball rolls across the floor and stops beside the wall.",
                    "action",
                ),
            ),
            duration=duration,
        )
    )
    assert artifact.status == "production_ready"
    assert artifact.token_report["text"]["target"] >= 180
