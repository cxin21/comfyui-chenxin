from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest


def test_only_three_authoring_functions_are_public() -> None:
    import prompt_forge

    assert prompt_forge.__all__ == [
        "author_anima_prompt",
        "author_h3_t2va_prompt",
        "author_h3_ref2va_prompt",
    ]
    for forbidden in ("ForgeRequest", "forge_prompt", "load_profile", "PromptPackage"):
        assert not hasattr(prompt_forge, forbidden)


def test_contracts_are_explicit_and_non_interchangeable() -> None:
    from prompt_forge.contracts import (
        AnimaAuthoringRequest,
        H3Ref2VAAuthoringRequest,
        H3T2VAAuthoringRequest,
    )

    assert [field.name for field in fields(AnimaAuthoringRequest)] == [
        "facts",
        "positive_segments",
        "complexity",
        "negative_segments",
        "exclusion_groups",
        "variant",
    ]
    assert [field.name for field in fields(H3T2VAAuthoringRequest)] == [
        "facts",
        "duration_seconds",
        "shot_count",
        "integrated_multimodal_description",
        "overall_soundscape",
        "non_diegetic_music",
    ]
    assert [field.name for field in fields(H3Ref2VAAuthoringRequest)] == [
        "facts",
        "duration_seconds",
        "shot_count",
        "references",
        "subject_definitions",
        "summary",
        "retention_analysis",
        "detailed_description",
        "overall_soundscape",
        "non_diegetic_music",
    ]
    assert not issubclass(AnimaAuthoringRequest, H3T2VAAuthoringRequest)
    assert not issubclass(H3T2VAAuthoringRequest, H3Ref2VAAuthoringRequest)


def test_contract_records_are_frozen() -> None:
    from prompt_forge.contracts import Fact

    fact = Fact(
        fact_id="subject_1.hair.color",
        value="blonde",
        origin="user_explicit",
        locked=False,
        owner="subject_1",
        dimension="appearance",
    )
    with pytest.raises(FrozenInstanceError):
        fact.value = "black"  # type: ignore[misc]


def test_runtime_source_contains_no_legacy_dispatch_concepts() -> None:
    package_root = Path(__file__).resolve().parents[1] / "prompt_forge"
    forbidden = (
        "profile" + "_id",
        "dialect" + "_id",
        "Prompt" + "Package",
        "adapter" + "_manifest",
    )

    violations: list[str] = []
    for path in sorted(package_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                violations.append(f"{path.relative_to(package_root)}:{token}")

    assert violations == []
