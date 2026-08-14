"""Shared MiniMax-H3 temporal, multimodal, and audio hard gates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import ceil, floor

from .contracts import H3ReferenceImage
from .facts import FactLedger
from .token_counting import TokenCounter, count_h3_text_context


H3_CONTEXT_LIMIT = 262_144
H3_MIN_PIXELS = 65_536
H3_MAX_PIXELS = 16_777_216
H3_PATCH_SIZE = 16
H3_MERGE_SIZE = 2
H3_SPATIAL_STRIDE = H3_PATCH_SIZE * H3_MERGE_SIZE


class H3AuditError(ValueError):
    """A MiniMax-H3 production hard gate failed."""


@dataclass(frozen=True)
class Shot:
    number: int
    start_seconds: float
    end_seconds: float
    opening_state: str
    actions_state_transitions: str
    camera_motion: str
    synchronous_sound_dialogue: str
    landing_state: str
    text: str


@dataclass(frozen=True)
class H3ContextPlan:
    visual_tokens: int
    chat_template_tokens: int
    special_tokens: int
    runtime_safety_margin: int
    available_tokens: int
    text_quality_limit: int
    effective_quality_limit: int


_SHOT_MARKER = re.compile(r"\[Shot ([1-9][0-9]*)\]")
_CUT_PREFIX = re.compile(r"^\s*At ([0-9]{2}):([0-9]{2})\.([0-9]{3}),\s*")
_DIALOGUE = re.compile(r"<d>\[([^\]]+)\] ([\s\S]*?)</d>")
_REFERENCE = re.compile(r"<(Subject|Picture|Video|Audio) ([1-9][0-9]*)>")


def parse_shots(
    description: str,
    *,
    duration_seconds: float,
    declared_shot_count: int,
) -> tuple[Shot, ...]:
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not 2 <= duration_seconds <= 15
    ):
        raise H3AuditError("duration_seconds must be between 2 and 15")
    if (
        isinstance(declared_shot_count, bool)
        or not isinstance(declared_shot_count, int)
        or declared_shot_count <= 0
    ):
        raise H3AuditError("declared_shot_count must be a positive integer")
    if not isinstance(description, str) or not description.strip():
        raise H3AuditError("description must be non-empty")
    markers = list(_SHOT_MARKER.finditer(description))
    numbers = [int(marker.group(1)) for marker in markers]
    if numbers != list(range(1, len(numbers) + 1)):
        raise H3AuditError("shot numbers must be sequential starting at 1")
    if len(markers) != declared_shot_count:
        raise H3AuditError("declared shot count does not match shot markers")
    max_shots = 1 + floor((duration_seconds - 1) / 3)
    if len(markers) > max_shots:
        raise H3AuditError(f"shot count exceeds max_shots {max_shots}")

    starts: list[float] = [0.0]
    bodies: list[str] = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(description)
        body = description[marker.end():end].strip()
        if index == 0:
            if _CUT_PREFIX.match(body):
                raise H3AuditError("first shot must not contain a timestamp")
        else:
            timestamp = _CUT_PREFIX.match(body)
            if timestamp is None:
                raise H3AuditError("every shot after the first requires At MM:SS.mmm")
            minutes, seconds, milliseconds = (int(value) for value in timestamp.groups())
            if seconds >= 60:
                raise H3AuditError("timestamp seconds must be below 60")
            start = minutes * 60 + seconds + milliseconds / 1000
            if start >= duration_seconds:
                raise H3AuditError("shot timestamp must fall within video duration")
            starts.append(start)
            body = body[timestamp.end():].strip()
        if not body:
            raise H3AuditError(f"Shot {index + 1} must have executable content")
        bodies.append(body)
    if any(later <= earlier for earlier, later in zip(starts, starts[1:])):
        raise H3AuditError("shot timestamps must be strictly increasing")

    shots: list[Shot] = []
    for index, body in enumerate(bodies):
        sentences = _sentences(body)
        camera = " ".join(
            sentence
            for sentence in sentences
            if re.search(
                r"\bcamera\b|\b(?:pushes|pulls|pans|trucks|tilts|tracks|zooms)\b",
                sentence,
                re.IGNORECASE,
            )
        )
        sound = " ".join(
            sentence
            for sentence in sentences
            if "<d>" in sentence
            or re.search(r"\b(?:sound|voice|says|shouts|sings|rings|footsteps)\b", sentence, re.IGNORECASE)
        )
        shots.append(
            Shot(
                number=index + 1,
                start_seconds=starts[index],
                end_seconds=(starts[index + 1] if index + 1 < len(starts) else float(duration_seconds)),
                opening_state=sentences[0],
                actions_state_transitions=body,
                camera_motion=camera,
                synchronous_sound_dialogue=sound,
                landing_state=sentences[-1],
                text=body,
            )
        )
    return tuple(shots)


def audit_dialogue_and_visible_text(text: str, ledger: FactLedger) -> None:
    dialogue_bodies = [match.group(2) for match in _DIALOGUE.finditer(text)]
    for fact in ledger.facts:
        if fact.dimension == "dialogue" and fact.value not in dialogue_bodies:
            raise H3AuditError(
                f"dialogue fact {fact.fact_id} is not preserved exactly inside <d>"
            )
        if fact.dimension == "visible_text" and f'"{fact.value}"' not in text:
            raise H3AuditError(
                f"visible text fact {fact.fact_id} is not preserved exactly in double quotes"
            )
    malformed = re.sub(_DIALOGUE, "", text)
    if "<d>" in malformed or "</d>" in malformed:
        raise H3AuditError("dialogue blocks must use <d>[Language] exact text</d>")


def audit_sound_music_separation(soundscape: str, music: str) -> None:
    if "<d>" in soundscape or "</d>" in soundscape:
        raise H3AuditError("dialogue must not be repeated in overall_soundscape")
    if re.search(r"\bnon[- ]diegetic\b|\bbackground music\b", soundscape, re.IGNORECASE):
        raise H3AuditError("non-diegetic music must not appear in overall_soundscape")
    if "<d>" in music or "</d>" in music:
        raise H3AuditError("dialogue must not appear in non_diegetic_music")


def audit_shot_execution(shots: tuple[Shot, ...], ledger: FactLedger) -> None:
    for shot in shots[1:]:
        if re.match(
            r"(?i)^(?:the camera|the shot|camera|shot)\s+"
            r"(?:cuts|transitions|changes|switches)\s+to\b",
            shot.text,
        ) is None:
            raise H3AuditError(
                f"Shot {shot.number} cut must declare a model-native transition and new view"
            )
    for previous, current in zip(shots, shots[1:]):
        if _semantic_shot(previous.text) == _semantic_shot(current.text):
            raise H3AuditError(
                f"Shot {current.number} cut adds no new information or state"
            )
    for shot in shots:
        lower = shot.camera_motion.lower()
        if "static shot" in lower and re.search(
            r"\b(?:push|pull|pan|truck|tilt|track|zoom|arc)\w*\b",
            lower,
        ):
            raise H3AuditError(
                f"Shot {shot.number} contains contradictory camera motion"
            )
    combined = " ".join(shot.text for shot in shots)
    for fact in ledger.facts:
        if fact.dimension == "action_result" and fact.value not in combined:
            raise H3AuditError(
                f"action result fact {fact.fact_id} has no explicit landing state"
            )


def visual_tokens(reference: H3ReferenceImage) -> int:
    width = reference.resized_width
    height = reference.resized_height
    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise H3AuditError("verified resized pixel dimensions must be positive integers")
    pixels = width * height
    if not H3_MIN_PIXELS <= pixels <= H3_MAX_PIXELS:
        raise H3AuditError(
            f"resized pixel area must be within {H3_MIN_PIXELS}..{H3_MAX_PIXELS}"
        )
    return ceil(width / H3_SPATIAL_STRIDE) * ceil(height / H3_SPATIAL_STRIDE)


def plan_h3_context(
    counter: TokenCounter,
    references: tuple[H3ReferenceImage, ...],
    *,
    text_quality_limit: int,
    special_tokens: int,
    runtime_safety_margin: int,
) -> H3ContextPlan:
    for name, value in {
        "text_quality_limit": text_quality_limit,
        "special_tokens": special_tokens,
        "runtime_safety_margin": runtime_safety_margin,
    }.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise H3AuditError(f"{name} must be a non-negative integer")
    visual = sum(visual_tokens(reference) for reference in references)
    chat = count_h3_text_context(counter, "", reference_count=len(references))
    available = H3_CONTEXT_LIMIT - visual - chat - special_tokens - runtime_safety_margin
    if available < 0:
        raise H3AuditError("multimodal inputs exceed the physical H3 context limit")
    return H3ContextPlan(
        visual_tokens=visual,
        chat_template_tokens=chat,
        special_tokens=special_tokens,
        runtime_safety_margin=runtime_safety_margin,
        available_tokens=available,
        text_quality_limit=text_quality_limit,
        effective_quality_limit=min(text_quality_limit, available),
    )


def audit_reference_labels(
    subject_definitions: str,
    usage_text: str,
    references: tuple[H3ReferenceImage, ...],
) -> None:
    expected = tuple(f"Picture {index}" for index in range(1, len(references) + 1))
    actual = tuple(reference.reference_id for reference in references)
    if actual != expected:
        raise H3AuditError(
            f"reference IDs must match ordered input images exactly: expected {expected!r}"
        )
    if any(not reference.owner.strip() for reference in references):
        raise H3AuditError("every ordered input reference requires an owner")
    combined = f"{subject_definitions}\n{usage_text}"
    labels = {(kind, int(index)) for kind, index in _REFERENCE.findall(combined)}
    picture_numbers = {index for kind, index in labels if kind == "Picture"}
    expected_numbers = set(range(1, len(references) + 1))
    if not picture_numbers.issubset(expected_numbers):
        raise H3AuditError("reference label does not resolve to an ordered input image")
    definition_labels = re.findall(
        r"(?m)^\s*<(Subject|Picture|Video|Audio) ([1-9][0-9]*)>\s+is\b",
        subject_definitions,
    )
    if len(definition_labels) != len(set(definition_labels)):
        raise H3AuditError("reference definition collision")
    if not expected_numbers.issubset(picture_numbers):
        raise H3AuditError("every ordered input image must be referenced")
    defined_subjects = {
        int(index) for kind, index in definition_labels if kind == "Subject"
    }
    used_subjects = {
        int(index)
        for kind, index in _REFERENCE.findall(usage_text)
        if kind == "Subject"
    }
    if not used_subjects.issubset(defined_subjects):
        raise H3AuditError("used Subject label is not defined in subject_definitions")


def _sentences(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return parts or [text.strip()]


def _semantic_shot(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))

