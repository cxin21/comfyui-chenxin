"""Structured, fail-closed patching for the Yusu LTX Director timeline."""

from __future__ import annotations

import copy
import json
import math
import numbers
from pathlib import PurePosixPath

from ..contracts import canonical_json


class YusuTimelineError(ValueError):
    """Raised when a Yusu timeline cannot be parsed or synchronized."""


_ALLOWED_DIRECTOR_FIELDS = frozenset(
    {
        "timeline_data",
        "local_prompts",
        "segment_lengths",
        "guide_strength",
        "transition_smoothness",
        "start_second",
        "end_second",
        "duration_seconds",
        "start_frame",
        "end_frame",
        "duration_frames",
        "frame_rate",
    }
)


def _profile_ids(profile: object) -> tuple[int, int, int, int]:
    if not isinstance(profile, dict):
        raise YusuTimelineError("Yusu profile must be an object")
    director_id = profile.get("director_node_id")
    negative_id = profile.get("negative_node_id")
    if not isinstance(director_id, int) or isinstance(director_id, bool):
        raise YusuTimelineError("Yusu profile director_node_id is invalid")
    if not isinstance(negative_id, int) or isinstance(negative_id, bool):
        raise YusuTimelineError("Yusu profile negative_node_id is invalid")
    frames = profile.get("baseline_frames", 24)
    fps = profile.get("baseline_fps", 24)
    if not isinstance(frames, int) or isinstance(frames, bool) or frames <= 0:
        raise YusuTimelineError("Yusu baseline frames must be a positive integer")
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:
        raise YusuTimelineError("Yusu baseline fps must be a positive integer")
    return director_id, negative_id, frames, fps


def profile_duration_seconds(profile: object) -> float:
    """Return the selected profile's single authoritative duration."""
    if not isinstance(profile, dict):
        raise YusuTimelineError("Yusu profile must be an object")
    _, _, frames, fps = _profile_ids(profile)
    duration = profile.get("duration_seconds", frames / fps)
    if (
        isinstance(duration, bool)
        or not isinstance(duration, numbers.Real)
        or not math.isfinite(float(duration))
        or float(duration) <= 0
    ):
        raise YusuTimelineError("Yusu profile duration_seconds is invalid")
    expected = frames / fps
    if not math.isclose(float(duration), expected, rel_tol=0.0, abs_tol=1e-9):
        raise YusuTimelineError(
            "Yusu profile duration_seconds must equal baseline_frames / baseline_fps"
        )
    return float(duration)


def _node(graph: dict, node_id: int, label: str) -> dict:
    value = graph.get(str(node_id))
    if not isinstance(value, dict) or not isinstance(value.get("inputs"), dict):
        raise YusuTimelineError(f"Yusu {label} node {node_id} is missing or malformed")
    return value


def _immutable_values_match(actual: object, expected: object) -> bool:
    """Compare pinned inputs while accepting JSON's int/float equivalence."""
    if (
        isinstance(actual, numbers.Real)
        and not isinstance(actual, bool)
        and isinstance(expected, numbers.Real)
        and not isinstance(expected, bool)
    ):
        return actual == expected
    try:
        return canonical_json(actual) == canonical_json(expected)
    except (TypeError, ValueError) as exc:
        raise YusuTimelineError("Yusu immutable input is not canonical JSON") from exc


def validate_yusu_immutable_inputs(graph: dict, profile: dict) -> None:
    """Reject drift in the profiled model, LoRA, sampler, scheduler, and resolution nodes."""
    if not isinstance(graph, dict):
        raise YusuTimelineError("Yusu API graph must be an object")
    if not isinstance(profile, dict):
        raise YusuTimelineError("Yusu profile must be an object")
    contracts = profile.get("immutable_node_inputs")
    director_contract = profile.get("director_immutable_inputs")
    if contracts is None and director_contract is None:
        return
    director_id, _, _, _ = _profile_ids(profile)
    if contracts is None:
        contracts = {}
    if not isinstance(contracts, dict):
        raise YusuTimelineError("Yusu immutable_node_inputs must be a non-empty object")
    for node_id, expected in contracts.items():
        node = graph.get(str(node_id))
        if not isinstance(expected, dict):
            raise YusuTimelineError(f"Yusu immutable node {node_id} contract is malformed")
        expected_type = expected.get("class_type")
        expected_inputs = expected.get("inputs")
        if not isinstance(expected_type, str) or not expected_type or not isinstance(expected_inputs, dict):
            raise YusuTimelineError(f"Yusu immutable node {node_id} contract is malformed")
        if not isinstance(node, dict) or node.get("class_type") != expected_type:
            raise YusuTimelineError(f"Yusu immutable node {node_id} class_type drifted")
        actual_inputs = node.get("inputs")
        if not isinstance(actual_inputs, dict):
            raise YusuTimelineError(f"Yusu immutable node {node_id} inputs are malformed")
        for input_name, expected_value in expected_inputs.items():
            if input_name not in actual_inputs:
                raise YusuTimelineError(f"Yusu immutable node {node_id} input {input_name} drifted")
            try:
                matches = _immutable_values_match(actual_inputs[input_name], expected_value)
            except YusuTimelineError as exc:
                raise YusuTimelineError(
                    f"Yusu immutable node {node_id} input {input_name} is not canonical JSON"
                ) from exc
            if not matches:
                raise YusuTimelineError(f"Yusu immutable node {node_id} input {input_name} drifted")

    if director_contract is not None:
        if not isinstance(director_contract, dict) or not director_contract:
            raise YusuTimelineError("Yusu director_immutable_inputs must be a non-empty object")
        director = _node(graph, director_id, "director")
        for input_name, expected_value in director_contract.items():
            if not isinstance(input_name, str) or not input_name:
                raise YusuTimelineError("Yusu director immutable input name is invalid")
            if input_name not in director["inputs"]:
                raise YusuTimelineError(f"Yusu director immutable input {input_name} is missing")
            try:
                matches = _immutable_values_match(director["inputs"][input_name], expected_value)
            except YusuTimelineError as exc:
                raise YusuTimelineError(
                    f"Yusu director immutable input {input_name} is not canonical JSON"
                ) from exc
            if not matches:
                raise YusuTimelineError(f"Yusu director immutable input {input_name} drifted")


def _safe_image_ref(image_ref: object) -> dict:
    if not isinstance(image_ref, dict):
        raise YusuTimelineError("Yusu image reference must be an object")
    image_file = image_ref.get("imageFile")
    image_b64 = image_ref.get("imageB64")
    if not isinstance(image_file, str) or not image_file.strip():
        raise YusuTimelineError("Yusu imageFile is required")
    if "\\" in image_file or ":" in image_file:
        raise YusuTimelineError("Yusu imageFile must be a relative input reference")
    path = PurePosixPath(image_file)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise YusuTimelineError("Yusu imageFile must be a safe relative input reference")
    if not isinstance(image_b64, str) or not image_b64.strip():
        raise YusuTimelineError("Yusu imageB64 is required")
    return {"imageFile": image_file, "imageB64": image_b64}


def _parse_timeline(inputs: dict) -> dict:
    raw = inputs.get("timeline_data")
    if not isinstance(raw, str) or not raw.strip():
        raise YusuTimelineError("Yusu timeline_data is required")
    try:
        timeline = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise YusuTimelineError("Yusu timeline_data is invalid JSON") from exc
    if not isinstance(timeline, dict):
        raise YusuTimelineError("Yusu timeline_data must decode to an object")
    return timeline


def _without_director_fields(graph: dict, director_id: int) -> dict:
    normalized = copy.deepcopy(graph)
    director = _node(normalized, director_id, "director")
    for field in _ALLOWED_DIRECTOR_FIELDS:
        director["inputs"].pop(field, None)
    return normalized


def _build_segment(
    image_ref: dict,
    prompt: str,
    start_second: float,
    end_second: float,
    fps: int,
    segment_index: int,
) -> dict:
    start_frame = int(round(start_second * fps))
    length = max(1, int(round((end_second - start_second) * fps)))
    return {
        "id": f"segment-{segment_index:04d}",
        "imageFile": image_ref["imageFile"],
        "imageB64": image_ref["imageB64"],
        "prompt": prompt,
        "start": start_frame,
        "length": length,
        "start_second": start_second,
        "end_second": end_second,
        "type": "image",
        "isEndFrame": False,
    }


def _normalize_segments(
    image_ref: dict,
    prompt: str,
    fps: int,
    duration: float,
    timeline_segments: object,
) -> list[dict]:
    if timeline_segments is None:
        timeline_segments = [
            {"start_second": 0.0, "end_second": duration, "prompt": prompt.strip()}
        ]
    if not isinstance(timeline_segments, list) or not timeline_segments:
        raise YusuTimelineError("Yusu timeline_segments must be a non-empty list")
    normalized: list[dict] = []
    previous_end = 0.0
    for index, raw in enumerate(timeline_segments, 1):
        if not isinstance(raw, dict):
            raise YusuTimelineError("Yusu timeline segment must be an object")
        start = raw.get("start_second")
        end = raw.get("end_second")
        segment_prompt = raw.get("prompt")
        if (
            isinstance(start, bool)
            or not isinstance(start, numbers.Real)
            or not math.isfinite(float(start))
            or isinstance(end, bool)
            or not isinstance(end, numbers.Real)
            or not math.isfinite(float(end))
            or not isinstance(segment_prompt, str)
            or not segment_prompt.strip()
        ):
            raise YusuTimelineError("Yusu timeline segment seconds or prompt are invalid")
        start = float(start)
        end = float(end)
        if start < 0 or end <= start or end > duration + 1e-9:
            raise YusuTimelineError("Yusu timeline segment is outside the profile duration")
        if index == 1 and not math.isclose(start, 0.0, abs_tol=1e-9):
            raise YusuTimelineError("Yusu timeline must start at zero")
        if index > 1 and not math.isclose(start, previous_end, abs_tol=1e-9):
            raise YusuTimelineError("Yusu timeline segments must be contiguous")
        normalized.append(_build_segment(image_ref, segment_prompt.strip(), start, end, fps, index))
        previous_end = end
    if not math.isclose(previous_end, duration, abs_tol=1e-9):
        raise YusuTimelineError("Yusu timeline must cover profile duration")
    expected_frames = int(round(duration * fps))
    if sum(segment["length"] for segment in normalized) != expected_frames:
        raise YusuTimelineError(
            "Yusu timeline segment frame lengths do not cover profile frame budget"
        )
    return normalized


def patch_yusu_timeline(
    graph: dict,
    image_ref: dict,
    prompt: str,
    frames: int,
    fps: int,
    profile: dict,
    *,
    timeline_segments: list[dict] | None = None,
) -> dict:
    """Patch one image segment and all Yusu derived fields atomically."""
    if not isinstance(graph, dict):
        raise YusuTimelineError("Yusu API graph must be an object")
    if not isinstance(prompt, str) or not prompt.strip():
        raise YusuTimelineError("Yusu segment prompt is required")
    if not isinstance(frames, int) or isinstance(frames, bool) or frames <= 0:
        raise YusuTimelineError("Yusu frames must be a positive integer")
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:
        raise YusuTimelineError("Yusu fps must be a positive integer")
    image = _safe_image_ref(image_ref)
    director_id, negative_id, baseline_frames, baseline_fps = _profile_ids(profile)
    duration = profile_duration_seconds(profile)
    validate_yusu_immutable_inputs(graph, profile)
    if frames != baseline_frames or fps != baseline_fps:
        raise YusuTimelineError("Yusu timeline must use the profiled baseline frame rate and length")
    director = _node(graph, director_id, "director")
    if director.get("class_type") != "YusuLTXDirector":
        raise YusuTimelineError("Yusu director node has an unexpected class_type")
    negative = _node(graph, negative_id, "negative")
    if negative.get("class_type") != "CLIPTextEncode":
        raise YusuTimelineError("Yusu negative node has an unexpected class_type")
    timeline = _parse_timeline(director["inputs"])
    segments = _normalize_segments(image, prompt, fps, duration, timeline_segments)
    timeline["segments"] = segments
    timeline["duration_seconds"] = duration

    patched = copy.deepcopy(graph)
    patched_director = _node(patched, director_id, "director")
    patched_inputs = patched_director["inputs"]
    patched_inputs["timeline_data"] = canonical_json(timeline)
    patched_inputs["local_prompts"] = "\n".join(segment["prompt"] for segment in segments)
    patched_inputs["segment_lengths"] = ",".join(str(segment["length"]) for segment in segments)
    patched_inputs["start_second"] = 0.0
    patched_inputs["end_second"] = duration
    patched_inputs["duration_seconds"] = duration
    patched_inputs["start_frame"] = 0
    patched_inputs["end_frame"] = frames - 1
    patched_inputs["duration_frames"] = frames
    patched_inputs["frame_rate"] = fps
    validate_yusu_sync(patched, profile)

    try:
        source_identity = canonical_json(_without_director_fields(graph, director_id))
        patched_identity = canonical_json(_without_director_fields(patched, director_id))
    except (TypeError, ValueError) as exc:
        raise YusuTimelineError(f"Yusu API graph must be canonical JSON: {exc}") from exc
    if source_identity != patched_identity:
        raise YusuTimelineError("Yusu timeline patch changed fields outside the allowlist")
    if patched[str(negative_id)] != graph[str(negative_id)]:
        raise YusuTimelineError("Yusu workflow-owned negative node was changed")
    return patched


def validate_yusu_sync(graph: dict, profile: dict) -> None:
    """Validate timeline JSON and every derived scalar field."""
    director_id, negative_id, frames, fps = _profile_ids(profile)
    validate_yusu_immutable_inputs(graph, profile)
    director = _node(graph, director_id, "director")
    negative = _node(graph, negative_id, "negative")
    if director.get("class_type") != "YusuLTXDirector":
        raise YusuTimelineError("Yusu director node has an unexpected class_type")
    if negative.get("class_type") != "CLIPTextEncode":
        raise YusuTimelineError("Yusu negative node has an unexpected class_type")
    inputs = director["inputs"]
    timeline = _parse_timeline(inputs)
    duration = profile_duration_seconds(profile)
    segments = timeline.get("segments")
    if not isinstance(segments, list) or not segments or not all(isinstance(item, dict) for item in segments):
        raise YusuTimelineError("Yusu timeline must contain one or more segments")
    previous_end = 0.0
    expected_frame_cursor = 0
    image_identity = None
    prompts: list[str] = []
    lengths: list[str] = []
    for index, segment in enumerate(segments, 1):
        if segment.get("id") != f"segment-{index:04d}":
            raise YusuTimelineError("Yusu segment id is not deterministic")
        if segment.get("type") != "image" or segment.get("isEndFrame") is not False:
            raise YusuTimelineError("Yusu segment type or end-frame flag is invalid")
        start = segment.get("start_second")
        end = segment.get("end_second")
        if not isinstance(start, numbers.Real) or isinstance(start, bool) or not isinstance(end, numbers.Real) or isinstance(end, bool):
            raise YusuTimelineError("Yusu segment seconds are invalid")
        if index == 1 and not math.isclose(float(start), 0.0, abs_tol=1e-9):
            raise YusuTimelineError("Yusu timeline must start at zero")
        if index > 1 and not math.isclose(float(start), previous_end, abs_tol=1e-9):
            raise YusuTimelineError("Yusu timeline segments must be contiguous")
        if float(end) <= float(start) or float(end) > duration + 1e-9:
            raise YusuTimelineError("Yusu timeline segment is outside the profile duration")
        image = _safe_image_ref({"imageFile": segment.get("imageFile"), "imageB64": segment.get("imageB64")})
        identity = (image["imageFile"], image["imageB64"])
        if image_identity is None:
            image_identity = identity
        elif image_identity != identity:
            raise YusuTimelineError("Yusu timeline segments must use the same image")
        prompt = segment.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise YusuTimelineError("Yusu segment prompt is empty")
        expected_start = int(round(float(start) * fps))
        expected_length = max(1, int(round((float(end) - float(start)) * fps)))
        if expected_start != expected_frame_cursor:
            raise YusuTimelineError("Yusu segment frame ranges are not contiguous")
        if segment.get("start") != expected_start or segment.get("length") != expected_length:
            raise YusuTimelineError("Yusu segment frame range is invalid")
        prompts.append(prompt.strip())
        lengths.append(str(expected_length))
        expected_frame_cursor += expected_length
        previous_end = float(end)
    if not math.isclose(previous_end, duration, abs_tol=1e-9):
        raise YusuTimelineError("Yusu timeline must cover profile duration")
    if expected_frame_cursor != frames:
        raise YusuTimelineError("Yusu timeline frame lengths do not cover profile frame budget")
    if timeline.get("duration_seconds") != duration:
        raise YusuTimelineError("Yusu timeline duration is out of sync")
    if inputs.get("local_prompts") != "\n".join(prompts):
        raise YusuTimelineError("Yusu local_prompts is out of sync")
    if inputs.get("segment_lengths") != ",".join(lengths):
        raise YusuTimelineError("Yusu segment_lengths is out of sync")
    if inputs.get("start_second") != 0.0:
        raise YusuTimelineError("Yusu start_second is out of sync")
    if inputs.get("end_second") != duration or inputs.get("duration_seconds") != duration:
        raise YusuTimelineError("Yusu duration seconds are out of sync")
    if inputs.get("start_frame") != 0 or inputs.get("end_frame") != frames - 1:
        raise YusuTimelineError("Yusu frame range is out of sync")
    if inputs.get("duration_frames") != frames or inputs.get("frame_rate") != fps:
        raise YusuTimelineError("Yusu duration frames or frame rate is out of sync")
