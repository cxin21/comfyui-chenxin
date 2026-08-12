from __future__ import annotations

import pytest

from camera_image.runtime.config_schema import RunConfig as ImageConfig
from camera_image.skill_data import compile_prompt_gate as image_gate
from camera_video.runtime.config_schema import RunConfig as VideoConfig
from camera_video.skill_data import compile_prompt_gate as video_gate
from prompt_forge import author_anima_prompt, author_h3_ref2va_prompt, author_h3_t2va_prompt
from prompt_forge.contracts import (
    AnimaAuthoringRequest,
    AuthoredSegment,
    Complexity,
    Fact,
    H3Ref2VAAuthoringRequest,
    H3ReferenceImage,
    H3T2VAAuthoringRequest,
)


def fact(
    fact_id: str,
    value: str,
    *,
    owner: str = "subject_1",
    dimension: str = "appearance",
) -> Fact:
    return Fact(fact_id, value, "user_explicit", False, owner, dimension)


def segment(segment_id: str, field: str, text: str, *fact_ids: str) -> AuthoredSegment:
    return AuthoredSegment(segment_id, field, text, tuple(fact_ids), 5, 2, 1)


def anima_artifact() -> dict:
    request = AnimaAuthoringRequest(
        (fact("count", "1girl", dimension="count"), fact("hair", "blue hair")),
        (
            segment("count", "count", "1girl", "count"),
            segment("hair", "general", "blue hair", "hair"),
        ),
        Complexity(1, 0, 0, 0, 0),
    )
    return author_anima_prompt(request).to_dict()


def t2va_artifact() -> dict:
    request = H3T2VAAuthoringRequest(
        (fact("action", "the ball rolls and stops", dimension="action_result"),),
        5,
        1,
        (
            segment(
                "action",
                "integrated_multimodal_description",
                "[Shot 1] A red ball crosses the floor; the ball rolls and stops beside the wall.",
                "action",
            ),
        ),
    )
    return author_h3_t2va_prompt(request).to_dict()


def ref2va_artifact(reference_count: int) -> dict:
    references = tuple(
        H3ReferenceImage(f"Picture {index}", f"subject_{index}", 1024, 1024)
        for index in range(1, reference_count + 1)
    )
    definitions_facts = tuple(
        fact(
            f"definition_{index}",
            f"subject {index}",
            owner=f"subject_{index}",
            dimension="stable_appearance",
        )
        for index in range(1, reference_count + 1)
    )
    facts = definitions_facts + (
        fact("summary", "reference generation", dimension="task_summary"),
        fact("retention", "all references retained", dimension="retention"),
        fact("action", "all subjects stop", dimension="action_result"),
    )
    subjects = ", ".join(f"<Subject {index}>" for index in range(1, reference_count + 1))
    definitions = tuple(
        segment(
            f"definition_{index}",
            "subject_definitions",
            f"<Subject {index}> is subject {index} from <Picture {index}>.",
            f"definition_{index}",
        )
        for index in range(1, reference_count + 1)
    )
    retention = ", ".join(
        f"<Subject {index}> from <Picture {index}>"
        for index in range(1, reference_count + 1)
    )
    request = H3Ref2VAAuthoringRequest(
        facts,
        5,
        1,
        references,
        definitions,
        (segment("summary", "summary", f"[reference generation] {subjects} share one shot.", "summary"),),
        (segment("retention", "retention_analysis", f"{retention} remain fully_preserved.", "retention"),),
        (
            segment(
                "action",
                "detailed_description",
                f"[Shot 1] {subjects} walk forward and all subjects stop.",
                "action",
            ),
        ),
    )
    return author_h3_ref2va_prompt(request).to_dict()


def test_camera_image_t2i_and_i2i_consume_real_anima_artifact() -> None:
    artifact = anima_artifact()
    assert image_gate(ImageConfig.from_envelope({"prompt_artifact": artifact}))["status"] == "production_ready"
    assert image_gate(
        ImageConfig.from_envelope(
            {"prompt_artifact": artifact}, reference_image="reference.png"
        )
    )["task"] == "anima"


@pytest.mark.parametrize(
    ("reference_count", "images"),
    [
        (0, {}),
        (1, {"reference_image_1": "one.png"}),
        (
            3,
            {
                "reference_image_1": "one.png",
                "reference_image_2": "two.png",
                "reference_image_3": "three.png",
            },
        ),
    ],
)
def test_camera_video_consumes_real_task_matched_artifacts(
    reference_count: int,
    images: dict[str, str],
) -> None:
    artifact = t2va_artifact() if reference_count == 0 else ref2va_artifact(reference_count)
    config = VideoConfig.from_envelope(
        {"prompt_artifact": artifact}, duration=5, **images
    )
    assert video_gate(config)["status"] == "production_ready"


def test_camera_video_rejects_execution_duration_change() -> None:
    config = VideoConfig.from_envelope(
        {"prompt_artifact": t2va_artifact()}, duration=8
    )
    with pytest.raises(ValueError, match="duration"):
        video_gate(config)
