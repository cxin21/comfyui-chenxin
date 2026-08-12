from __future__ import annotations

import pytest

from prompt_forge.contracts import AuthoredSegment, Fact
from prompt_forge.facts import FactLedger, FactLedgerError, trace_rendering


def fact(
    fact_id: str,
    *,
    value: str = "blonde",
    origin: str = "user_explicit",
    locked: bool = False,
    owner: str = "subject_1",
    dimension: str = "appearance",
) -> Fact:
    return Fact(
        fact_id=fact_id,
        value=value,
        origin=origin,  # type: ignore[arg-type]
        locked=locked,
        owner=owner,
        dimension=dimension,
    )


def segment(
    segment_id: str,
    *fact_ids: str,
    text: str = "blonde hair",
    field: str = "appearance",
) -> AuthoredSegment:
    return AuthoredSegment(
        segment_id=segment_id,
        field=field,
        text=text,
        fact_ids=tuple(fact_ids),
        priority=4.0,
        adherence_risk=1.5,
        source_confidence=1.0,
    )


@pytest.mark.parametrize("attribute", ["fact_id", "value", "owner", "dimension"])
def test_fact_fields_must_be_non_empty(attribute: str) -> None:
    values = {
        "fact_id": "subject_1.hair.color",
        "value": "blonde",
        "owner": "subject_1",
        "dimension": "appearance",
    }
    values[attribute] = "  "
    with pytest.raises(FactLedgerError, match=attribute):
        FactLedger((Fact(origin="user_explicit", locked=False, **values),))


def test_fact_ids_are_unique() -> None:
    duplicate = fact("subject_1.hair.color")
    with pytest.raises(FactLedgerError, match="duplicate fact_id"):
        FactLedger((duplicate, duplicate))


@pytest.mark.parametrize(
    ("origin", "locked"),
    [
        ("user_locked", False),
        ("user_explicit", True),
        ("necessary_inference", True),
        ("agent_embellishment", True),
        ("unknown", False),
    ],
)
def test_origin_and_lock_consistency(origin: str, locked: bool) -> None:
    with pytest.raises(FactLedgerError):
        FactLedger((fact("subject_1.hair.color", origin=origin, locked=locked),))


def test_only_agent_embellishment_is_removable() -> None:
    ledger = FactLedger(
        (
            fact("locked", origin="user_locked", locked=True),
            fact("explicit"),
            fact("inferred", origin="necessary_inference"),
            fact("optional", origin="agent_embellishment"),
        )
    )
    assert ledger.protected_fact_ids() == frozenset({"locked", "explicit", "inferred"})
    assert ledger.removable_fact_ids() == frozenset({"optional"})


def test_segments_must_be_non_empty_unique_and_reference_known_facts() -> None:
    ledger = FactLedger((fact("known"),))
    with pytest.raises(FactLedgerError, match="fact_ids"):
        ledger.validate_segments((segment("empty"),))
    with pytest.raises(FactLedgerError, match="unknown fact_id"):
        ledger.validate_segments((segment("unknown", "missing"),))
    duplicate = segment("same", "known")
    with pytest.raises(FactLedgerError, match="duplicate segment_id"):
        ledger.validate_segments((duplicate, duplicate))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"segment_id": " "}, "segment_id"),
        ({"field": " "}, "field"),
        ({"text": " "}, "text"),
        ({"fact_ids": ("known", "known")}, "duplicate fact_ids"),
        ({"priority": 0.0}, "priority"),
        ({"source_confidence": 1.1}, "source_confidence"),
    ],
)
def test_segment_metadata_is_strict(changes: dict[str, object], message: str) -> None:
    ledger = FactLedger((fact("known"),))
    values: dict[str, object] = {
        "segment_id": "segment_1",
        "field": "appearance",
        "text": "blonde hair",
        "fact_ids": ("known",),
        "priority": 4.0,
        "adherence_risk": 1.5,
        "source_confidence": 1.0,
    }
    values.update(changes)
    with pytest.raises(FactLedgerError, match=message):
        ledger.validate_segments((AuthoredSegment(**values),))  # type: ignore[arg-type]


def test_trace_requires_every_protected_fact_and_maps_owners_independently() -> None:
    ledger = FactLedger(
        (
            fact("subject_1.hair.color", value="blonde", owner="subject_1"),
            fact("subject_2.hair.color", value="black", owner="subject_2"),
            fact("lighting.optional", origin="agent_embellishment", owner="scene"),
        )
    )
    segments = (
        segment("s1", "subject_1.hair.color", text="subject 1 has blonde hair"),
        segment("s2", "subject_2.hair.color", text="subject 2 has black hair"),
    )
    assert trace_rendering(ledger, segments) == {
        "subject_1.hair.color": ("s1",),
        "subject_2.hair.color": ("s2",),
        "lighting.optional": (),
    }

    with pytest.raises(FactLedgerError, match="protected facts are not rendered"):
        trace_rendering(ledger, segments[:1])


def test_get_returns_exact_fact_and_rejects_unknown_id() -> None:
    expected = fact("subject_1.hair.color")
    ledger = FactLedger((expected,))
    assert ledger.get(expected.fact_id) is expected
    with pytest.raises(FactLedgerError, match="unknown fact_id"):
        ledger.get("missing")
