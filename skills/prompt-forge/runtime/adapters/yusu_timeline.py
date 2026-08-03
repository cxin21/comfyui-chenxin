"""Structured, fail-closed patching for the Yusu LTX Director timeline."""

from __future__ import annotations

import copy
import json
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


def _build_segment(image_ref: dict, prompt: str, frames: int) -> dict:
    return {
        "id": "segment-0001",
        "imageFile": image_ref["imageFile"],
        "imageB64": image_ref["imageB64"],
        "prompt": prompt,
        "start": 0,
        "length": frames,
        "type": "image",
        "isEndFrame": False,
    }


def patch_yusu_timeline(
    graph: dict,
    image_ref: dict,
    prompt: str,
    frames: int,
    fps: int,
    profile: dict,
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
    timeline["segments"] = [_build_segment(image, prompt.strip(), frames)]

    patched = copy.deepcopy(graph)
    patched_director = _node(patched, director_id, "director")
    patched_inputs = patched_director["inputs"]
    patched_inputs["timeline_data"] = canonical_json(timeline)
    patched_inputs["local_prompts"] = prompt.strip()
    patched_inputs["segment_lengths"] = str(frames)
    patched_inputs["start_second"] = 0.0
    patched_inputs["end_second"] = frames / fps
    patched_inputs["duration_seconds"] = frames / fps
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
    segments = timeline.get("segments")
    if not isinstance(segments, list) or len(segments) != 1 or not isinstance(segments[0], dict):
        raise YusuTimelineError("Yusu timeline must contain exactly one segment")
    segment = segments[0]
    if segment.get("id") != "segment-0001":
        raise YusuTimelineError("Yusu segment id is not deterministic")
    if segment.get("type") != "image" or segment.get("isEndFrame") is not False:
        raise YusuTimelineError("Yusu segment type or end-frame flag is invalid")
    if segment.get("start") != 0 or segment.get("length") != frames:
        raise YusuTimelineError("Yusu segment frame range is invalid")
    _safe_image_ref({"imageFile": segment.get("imageFile"), "imageB64": segment.get("imageB64")})
    prompt = segment.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise YusuTimelineError("Yusu segment prompt is empty")
    if inputs.get("local_prompts") != prompt:
        raise YusuTimelineError("Yusu local_prompts is out of sync")
    if inputs.get("segment_lengths") != str(frames):
        raise YusuTimelineError("Yusu segment_lengths is out of sync")
    if inputs.get("start_second") != 0.0:
        raise YusuTimelineError("Yusu start_second is out of sync")
    if inputs.get("end_second") != frames / fps or inputs.get("duration_seconds") != frames / fps:
        raise YusuTimelineError("Yusu duration seconds are out of sync")
    if inputs.get("start_frame") != 0 or inputs.get("end_frame") != frames - 1:
        raise YusuTimelineError("Yusu frame range is out of sync")
    if inputs.get("duration_frames") != frames or inputs.get("frame_rate") != fps:
        raise YusuTimelineError("Yusu duration frames or frame rate is out of sync")
