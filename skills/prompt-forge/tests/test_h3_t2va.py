from __future__ import annotations

import pytest

from prompt_forge.contracts import Fact
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

