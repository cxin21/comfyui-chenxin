from __future__ import annotations

import pytest

from prompt_forge.contracts import H3ReferenceImage
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
