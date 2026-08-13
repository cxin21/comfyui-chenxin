from __future__ import annotations

import pytest

from prompt_forge.compression import compress_to_budget
from prompt_forge.contracts import AuthoredSegment, Fact
from prompt_forge.facts import FactLedger


class WordCounter:
    def count(self, text: str) -> int:
        return len(text.replace(",", " ").split())


def fact(
    fact_id: str,
    *,
    value: str | None = None,
    origin: str = "user_explicit",
    dimension: str = "appearance",
) -> Fact:
    return Fact(
        fact_id,
        value or fact_id.replace("_", " "),
        origin,  # type: ignore[arg-type]
        origin == "user_locked",
        "subject_1",
        dimension,
    )


def segment(
    segment_id: str,
    text: str,
    *fact_ids: str,
    field: str = "general",
    priority: float = 1.0,
) -> AuthoredSegment:
    return AuthoredSegment(
        segment_id,
        field,
        text,
        tuple(fact_ids),
        priority,
        1.0,
        1.0,
    )


def test_exact_and_semantic_dedupe_preserve_fact_trace() -> None:
    ledger = FactLedger((fact("hair", value="blue hair"),))
    result = compress_to_budget(
        segments=(
            segment("one", "blue hair", "hair"),
            segment("two", "blue hair", "hair"),
            segment("three", "the blue hair", "hair"),
        ),
        ledger=ledger,
        counter=WordCounter(),  # type: ignore[arg-type]
        soft_limit=1,
        quality_limit=3,
        structure="anima",
    )
    assert result.status == "within_budget"
    assert result.sacrificed_facts == ()
    assert {operation.pass_name for operation in result.operations} >= {
        "exact_dedupe",
        "semantic_dedupe",
    }
    assert result.segments[0].fact_ids == ("hair",)


@pytest.mark.parametrize(
    ("structure", "field", "expected"),
    [
        ("h3_ref2va", "detailed_stable_appearance", "subject_definitions"),
        ("h3_t2va", "shot_global_soundscape", "overall_soundscape"),
        ("h3_ref2va", "shot_non_diegetic_music", "non_diegetic_music"),
    ],
)
def test_h3_structure_extraction_uses_fixed_dialects(
    structure: str,
    field: str,
    expected: str,
) -> None:
    ledger = FactLedger((fact("inferred", origin="necessary_inference"),))
    result = compress_to_budget(
        segments=(segment("one", "stable concise fact", "inferred", field=field),),
        ledger=ledger,
        counter=WordCounter(),  # type: ignore[arg-type]
        soft_limit=1,
        quality_limit=10,
        structure=structure,  # type: ignore[arg-type]
    )
    assert result.segments[0].field == expected
    assert result.operations[0].pass_name == "structure_extraction"


def test_anima_does_not_extract_structure_fields() -> None:
    # Ruling 1: the legacy natural_language_stable_attribute -> tag mapping is
    # gone; the anima dialect has no model-native structure fields to extract.
    ledger = FactLedger((fact("inferred", origin="necessary_inference"),))
    result = compress_to_budget(
        segments=(
            segment("one", "stable concise fact", "inferred", field="natural_language_stable_attribute"),
        ),
        ledger=ledger,
        counter=WordCounter(),  # type: ignore[arg-type]
        soft_limit=1,
        quality_limit=10,
        structure="anima",
    )
    assert result.segments[0].field == "natural_language_stable_attribute"
    assert not any(op.pass_name == "structure_extraction" for op in result.operations)


def test_lexical_compression_then_agent_deletion_are_ordered() -> None:
    ledger = FactLedger(
        (
            fact("required", value="red coat"),
            fact("flourish", origin="agent_embellishment"),
            fact("background", origin="agent_embellishment"),
        )
    )
    result = compress_to_budget(
        segments=(
            segment("required", "red coat", "required", priority=9),
            segment(
                "flourish",
                "beautiful highly detailed atmospheric flourish",
                "flourish",
                priority=2,
            ),
            segment("background", "minor decorative background", "background"),
        ),
        ledger=ledger,
        counter=WordCounter(),  # type: ignore[arg-type]
        soft_limit=3,
        quality_limit=4,
        structure="anima",
    )
    names = [operation.pass_name for operation in result.operations]
    assert "lexical_compression" in names
    assert "delete_agent_embellishment" in names
    assert names.index("lexical_compression") < names.index("delete_agent_embellishment")
    assert result.sacrificed_facts == ()


@pytest.mark.parametrize(
    "dimension",
    [
        "dialogue",
        "visible_text",
        "count",
        "negation",
        "timestamp",
        "subject_id",
        "reference_id",
        "position",
        "color",
        "ownership",
        "action_result",
    ],
)
def test_protected_dimensions_are_never_lexically_compressed(dimension: str) -> None:
    protected = fact("protected", value="the exact protected wording", dimension=dimension)
    ledger = FactLedger((protected,))
    original = segment("protected", "the exact protected wording", "protected")
    result = compress_to_budget(
        segments=(original,),
        ledger=ledger,
        counter=WordCounter(),  # type: ignore[arg-type]
        soft_limit=1,
        quality_limit=2,
        structure="anima",
    )
    assert result.status == "budget_conflict"
    assert result.segments == (original,)
    assert not any(op.pass_name == "lexical_compression" for op in result.operations)
    assert result.conflict is not None
    assert result.conflict.sacrificed_facts == ()


@pytest.mark.parametrize("origin", ["user_locked", "user_explicit"])
def test_all_user_origin_facts_are_immutable_even_for_unlisted_dimensions(origin: str) -> None:
    ledger = FactLedger((fact("wording", origin=origin, dimension="mood"),))
    original = segment("wording", "the beautiful exact user wording", "wording")
    result = compress_to_budget(
        segments=(original,),
        ledger=ledger,
        counter=WordCounter(),  # type: ignore[arg-type]
        soft_limit=1,
        quality_limit=2,
        structure="h3_t2va",
    )
    assert result.status == "budget_conflict"
    assert result.segments == (original,)


class TailTrapCounter(WordCounter):
    def __init__(self) -> None:
        self.originals: set[str] = set()

    def count(self, text: str) -> int:
        self.originals.add(text)
        return super().count(text)


def test_never_uses_attractive_tail_token_slicing() -> None:
    ledger = FactLedger((fact("dialogue", dimension="dialogue"),))
    original = segment("dialogue", "speaker says every exact protected word now", "dialogue")
    counter = TailTrapCounter()
    result = compress_to_budget(
        segments=(original,),
        ledger=ledger,
        counter=counter,  # type: ignore[arg-type]
        soft_limit=2,
        quality_limit=3,
        structure="h3_t2va",
    )
    assert result.status == "budget_conflict"
    assert result.segments[0].text == original.text
    assert result.conflict is not None
    assert result.conflict.actual_tokens == 7
    assert result.conflict.excess_tokens == 4


def test_budget_conflict_reports_mandatory_optional_causes_and_user_choices() -> None:
    ledger = FactLedger(
        (
            fact("identity", dimension="subject_id"),
            fact("relation", dimension="ownership"),
        )
    )
    result = compress_to_budget(
        segments=(
            segment("identity", "subject one stable identity", "identity"),
            segment("relation", "owns the bright red umbrella", "relation"),
        ),
        ledger=ledger,
        counter=WordCounter(),  # type: ignore[arg-type]
        soft_limit=3,
        quality_limit=4,
        structure="anima",
    )
    conflict = result.conflict
    assert conflict is not None
    assert conflict.actual_tokens > conflict.quality_limit
    assert conflict.mandatory_tokens == conflict.actual_tokens
    assert conflict.agent_optional_tokens == 0
    assert {cause.dimension for cause in conflict.protected_causes} == {
        "subject_id",
        "ownership",
    }
    assert conflict.user_choices
    assert all(choice.estimated_saving > 0 for choice in conflict.user_choices)
    assert conflict.sacrificed_facts == ()


def test_conflict_names_unlinkable_mixed_segments() -> None:
    ledger = FactLedger(
        (
            fact("protected_f", origin="user_locked"),
            fact("agent_f", origin="agent_embellishment"),
        )
    )
    result = compress_to_budget(
        segments=(
            segment(
                "mixed",
                "a long protected and agent bound segment that is over budget",
                "protected_f",
                "agent_f",
            ),
        ),
        ledger=ledger,
        counter=WordCounter(),  # type: ignore[arg-type]
        soft_limit=2,
        quality_limit=3,
        structure="anima",
    )
    assert result.status == "budget_conflict"
    assert result.conflict is not None
    assert result.conflict.mandatory_tokens == result.conflict.actual_tokens
    assert isinstance(result.conflict.user_choices, tuple)
    assert any(
        choice.choice == "unlink_segment_mixed_from_protected_fact"
        and choice.facts_affected == ("protected_f",)
        and choice.estimated_saving > 0
        for choice in result.conflict.user_choices
    )


def test_invalid_limits_and_structure_are_rejected() -> None:
    with pytest.raises(ValueError):
        compress_to_budget(
            segments=(),
            ledger=FactLedger(()),
            counter=WordCounter(),  # type: ignore[arg-type]
            soft_limit=5,
            quality_limit=4,
            structure="anima",
        )
    with pytest.raises(ValueError):
        compress_to_budget(
            segments=(),
            ledger=FactLedger(()),
            counter=WordCounter(),  # type: ignore[arg-type]
            soft_limit=1,
            quality_limit=2,
            structure="generic",  # type: ignore[arg-type]
        )


def test_anima_dedupes_weighted_and_bare_twin():
    from prompt_forge.compression import compress_to_budget
    from prompt_forge.facts import FactLedger
    from prompt_forge.contracts import AuthoredSegment, Fact
    from prompt_forge.token_counting import TokenCounter
    from pathlib import Path
    tokenizer_dir = Path(__file__).resolve().parents[1] / "knowledge" / "tokenizers" / "anima-qwen3-0.6b"
    ledger = FactLedger((
        Fact("f1", "smile", "user_explicit", False, "s", "expression"),
    ))
    a = AuthoredSegment("a", "general", "smile", ("f1",), 1.0, 1.0, 1.0)
    b = AuthoredSegment("b", "general", "(smile:1.3)", ("f1",), 1.0, 1.0, 1.0)
    counter = TokenCounter.load(tokenizer_dir, "anima-qwen3-0.6b")
    result = compress_to_budget(
        segments=(a, b), ledger=ledger, counter=counter,
        soft_limit=1, quality_limit=2, structure="anima",
    )
    assert len(result.segments) == 1
