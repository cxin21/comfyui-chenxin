"""Build the reviewed Prompt Forge regression corpus from fixed original fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks" / "cases"


def fact(
    fact_id: str,
    value: str | dict[str, Any],
    *,
    owner: str = "subject_1",
    dimension: str = "appearance",
    origin: str = "user_explicit",
) -> dict[str, Any]:
    key = "value" if isinstance(value, str) else "value_spec"
    return {
        "fact_id": fact_id,
        key: value,
        "origin": origin,
        "locked": origin == "user_locked",
        "owner": owner,
        "dimension": dimension,
    }


def segment(
    segment_id: str,
    field: str,
    text: str | dict[str, Any],
    *fact_ids: str,
) -> dict[str, Any]:
    key = "text" if isinstance(text, str) else "text_spec"
    return {
        "segment_id": segment_id,
        "field": field,
        key: text,
        "fact_ids": list(fact_ids),
        "priority": 5,
        "adherence_risk": 2,
        "source_confidence": 1,
    }


def case(
    case_id: str,
    path: str,
    stratum: str,
    expected_status: str,
    facts: list[dict[str, Any]],
    request: dict[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "path": path,
        "stratum": stratum,
        "reviewed": True,
        "expected_status": expected_status,
        "facts": facts,
        "request": request,
    }


def anima_request(
    positive: list[dict[str, Any]],
    *,
    subjects: int = 1,
    relations: int = 0,
    actions: int = 0,
    environments: int = 0,
    bridges: int = 0,
    negative: list[dict[str, Any]] | None = None,
    exclusions: int = 0,
) -> dict[str, Any]:
    return {
        "positive_segments": positive,
        "negative_segments": negative or [],
        "exclusion_groups": exclusions,
        "complexity": {
            "subjects": subjects,
            "explicit_relations": relations,
            "complex_actions": actions,
            "environment_clusters": environments,
            "scene_descriptions": bridges,
        },
    }


def build_anima() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    concepts = [
        "blue hair", "red eyes", "gentle smile", "outdoors", "rainy street",
        "white dress", "side view", "soft lighting", "holding book", "city skyline",
    ]
    for index, concept in enumerate(concepts, 1):
        facts = [
            fact("count", "1girl", dimension="count"),
            fact("concept", concept),
            fact("quality", "masterpiece", dimension="quality"),
        ]
        result.append(case(
            f"anima-simple-{index:02d}", "anima", "simple", "production_ready", facts,
            anima_request([
                segment("quality", "protocol_prefix", "masterpiece", "quality"),
                segment("count", "count", "1girl", "count"),
                segment("concept", "general", concept, "concept"),
            ]),
        ))
    for index in range(1, 11):
        relation = f"Subject 1 places object {index} beside Subject 2."
        facts = [
            fact("count", "2girls", dimension="count"),
            fact("relation", relation, dimension="spatial_relation"),
            fact("exclude", f"unwanted artifact {index}", dimension="exclusion"),
            fact("quality", "masterpiece", dimension="quality"),
        ]
        result.append(case(
            f"anima-boundary-{index:02d}", "anima", "boundary", "production_ready", facts,
            anima_request(
                [
                    segment("quality", "protocol_prefix", "masterpiece", "quality"),
                    segment("count", "count", "2girls", "count"),
                    segment("bridge", "scene_description", relation, "relation"),
                ],
                subjects=2,
                relations=1,
                actions=1,
                bridges=1,
                negative=[segment("exclude", "user_exclusions", f"unwanted artifact {index}", "exclude")],
                exclusions=1,
            ),
        ))
    adversarial: list[tuple[str, list[dict[str, Any]], dict[str, Any]]] = []
    adversarial.append(("quality_rejected", [fact("hair", "blue hair")], anima_request([
        segment("hair", "general", "blue_hair", "hair")
    ])))
    adversarial.append(("quality_rejected", [fact("p", "blue hair"), fact("n", "blue hair", dimension="exclusion")], anima_request(
        [segment("p", "general", "blue hair", "p")],
        negative=[segment("n", "user_exclusions", "blue hair", "n")], exclusions=1,
    )))
    adversarial.append(("quality_rejected", [fact("relation", "holding umbrella", dimension="ownership")], anima_request(
        [
            segment("tag", "general", "holding umbrella", "relation"),
            segment("bridge", "scene_description", "The subject is holding an umbrella.", "relation"),
        ], relations=1, bridges=1,
    )))
    adversarial.append(("quality_rejected", [fact("x", "blue hair")], anima_request([
        segment("x", "future_field", "blue hair", "x")
    ])))
    adversarial.append(("quality_rejected", [fact("r", "Subject 1 follows Subject 2.", dimension="relation")], anima_request([
        segment("r", "scene_description", "Subject 1 follows Subject 2.", "r")
    ], subjects=2, relations=1, bridges=0)))
    adversarial.append(("quality_rejected", [fact("artist", "@unknownbenchmarkartist", dimension="artist")], anima_request([
        segment("artist", "artist", "@unknownbenchmarkartist", "artist")
    ])))
    adversarial.append(("quality_rejected", [fact("score", "score_10", dimension="quality")], anima_request([
        segment("score", "quality", "score_10", "score")
    ])))
    adversarial.append(("quality_rejected", [
        fact("s1", "blue hair", owner="subject_1"),
        fact("s2", "blue hair", owner="subject_2"),
    ], anima_request([segment("shared", "general", "blue hair", "s1", "s2")], subjects=2)))
    huge = {"prefix": "visibleconcept", "count": 1000, "joiner": " "}
    adversarial.append(("budget_conflict", [fact("huge", huge, origin="user_locked")], anima_request([
        segment("huge", "general", huge, "huge")
    ], subjects=20, relations=20, actions=20, environments=20)))
    adversarial.append(("quality_rejected", [
        fact("r1", "Subject 1 moves left.", dimension="relation"),
        fact("r2", "Subject 2 moves right.", dimension="relation", owner="subject_2"),
    ], anima_request([
        segment("r1", "scene_description", "Subject 1 moves left.", "r1"),
        segment("r2", "scene_description", "Subject 2 moves right.", "r2"),
    ], subjects=2, relations=2, bridges=2)))
    for index, (status, facts, request) in enumerate(adversarial, 1):
        result.append(case(f"anima-adversarial-{index:02d}", "anima", "adversarial", status, facts, request))
    return result


def t2va_request(
    facts: list[dict[str, Any]],
    description: str | dict[str, Any],
    *,
    duration: float = 5,
    shots: int = 1,
    sound: str | None = None,
    music: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    segments = [segment("description", "integrated_multimodal_description", description, *[item["fact_id"] for item in facts if item["dimension"] not in {"ambient_sound", "music"}])]
    sound_segments: list[dict[str, Any]] = []
    music_segments: list[dict[str, Any]] = []
    if sound is not None:
        sound_segments.append(segment("sound", "overall_soundscape", sound, "sound"))
    if music is not None:
        music_segments.append(segment("music", "non_diegetic_music", music, "music"))
    return facts, {
        "duration_seconds": duration,
        "shot_count": shots,
        "integrated_multimodal_description": segments,
        "overall_soundscape": sound_segments,
        "non_diegetic_music": music_segments,
    }


def build_t2va() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, duration in enumerate([2, 3, 4, 5, 6, 7, 8, 10, 12, 15], 1):
        landing = f"object {index} reaches the marker and stops"
        facts = [fact("action", landing, dimension="action_result")]
        facts, request = t2va_request(
            facts,
            f"[Shot 1] A small object rolls forward; {landing}.",
            duration=duration,
        )
        result.append(case(f"h3-t2va-simple-{index:02d}", "h3_t2va", "simple", "production_ready", facts, request))
    for index, duration in enumerate([4, 5, 6, 7, 8, 9, 10, 11, 13, 15], 1):
        line = f"Line {index}, hold position!"
        landing = f"runner {index} reaches the doorway"
        facts = [
            fact("action", landing, dimension="action_result"),
            fact("dialogue", line, dimension="dialogue", origin="user_locked"),
            fact("sound", f"Footsteps echo {index}.", dimension="ambient_sound"),
        ]
        description = (
            f"[Shot 1] Runner {index} crosses the hall and {landing}. "
            f"The runner says: <d>[English] {line}</d> "
            f"[Shot 2] At 00:03.000, the camera cuts to a low view as the shoes settle on the mat."
        )
        facts, request = t2va_request(
            facts, description, duration=duration, shots=2, sound=f"Footsteps echo {index}."
        )
        result.append(case(f"h3-t2va-boundary-{index:02d}", "h3_t2va", "boundary", "production_ready", facts, request))
    adversarial_specs: list[tuple[str, list[dict[str, Any]], str | dict[str, Any], dict[str, Any]]] = []
    adversarial_specs.append(("quality_rejected", [fact("a", "changes viewpoint", dimension="action_result")], "[Shot 1] Start and settle. [Shot 2] At 00:02.000, the camera cuts to a new view and changes viewpoint.", {"duration": 3, "shots": 2}))
    adversarial_specs.append(("quality_rejected", [fact("a", "runner remains at the door", dimension="action_result")], "[Shot 1] The runner stops at the door. [Shot 2] At 00:03.500, the runner remains at the door.", {"duration": 8, "shots": 2}))
    adversarial_specs.append(("quality_rejected", [fact("a", "subject settles", dimension="action_result")], "[Shot 1] Static shot, the camera pans left while the subject settles.", {}))
    adversarial_specs.append(("quality_rejected", [fact("a", "subject stops", dimension="action_result"), fact("d", "Hello", dimension="dialogue", origin="user_locked")], "[Shot 1] The subject says Hello and subject stops.", {}))
    adversarial_specs.append(("quality_rejected", [fact("a", "sign stops moving", dimension="action_result"), fact("v", "OPEN", dimension="visible_text", origin="user_locked")], "[Shot 1] The sign reads OPEN and the sign stops moving.", {}))
    adversarial_specs.append(("quality_rejected", [fact("a", "actor stops", dimension="action_result"), fact("sound", "background music rises", dimension="ambient_sound")], "[Shot 1] The actor stops.", {"sound": "background music rises"}))
    adversarial_specs.append(("quality_rejected", [fact("a", "actor stops", dimension="action_result"), fact("music", "<d>[English] sing</d>", dimension="music")], "[Shot 1] The actor stops.", {"music": "<d>[English] sing</d>"}))
    huge = {"prefix": "actionstate", "count": 1600, "joiner": " "}
    adversarial_specs.append(("budget_conflict", [fact("huge", huge, dimension="action_result", origin="user_locked")], {"prefix": "[Shot 1] actionstate", "count": 1600, "joiner": " "}, {"duration": 15}))
    adversarial_specs.append(("quality_rejected", [fact("a", "ball stops", dimension="action_result")], "[Shot 1] The ball stops.", {"duration": 16}))
    adversarial_specs.append(("quality_rejected", [fact("a", "ball stops", dimension="action_result")], "[Shot 1] The ball stops.", {"shots": 2}))
    for index, (status, facts, description, options) in enumerate(adversarial_specs, 1):
        facts, request = t2va_request(facts, description, **options)
        result.append(case(f"h3-t2va-adversarial-{index:02d}", "h3_t2va", "adversarial", status, facts, request))
    return result


def ref_case(
    case_id: str,
    stratum: str,
    expected_status: str,
    *,
    refs: int = 1,
    duration: float = 5,
    summary_prefix: bool = True,
    invalid_dimensions: bool = False,
    collision: bool = False,
    stable_leak: bool = False,
    missing_retention: bool = False,
    bad_owner: bool = False,
    wrong_order: bool = False,
    bad_sound: bool = False,
    bad_timeline: bool = False,
    huge: bool = False,
) -> dict[str, Any]:
    references = []
    definition_facts = []
    definitions = []
    for index in range(1, refs + 1):
        owner = f"missing_{index}" if bad_owner and index == 1 else f"subject_{index}"
        reference_id = f"Picture {refs - index + 1}" if wrong_order else f"Picture {index}"
        references.append({
            "reference_id": reference_id,
            "owner": owner,
            "resized_width": 0 if invalid_dimensions and index == 1 else 1024,
            "resized_height": 1024,
        })
        definition_facts.append(fact(
            f"definition_{index}", f"subject {index}", owner=f"subject_{index}", dimension="stable_appearance"
        ))
        definitions.append(segment(
            f"definition_{index}", "subject_definitions",
            f"<Subject {index}> is subject {index} from <Picture {index}>.",
            f"definition_{index}",
        ))
    if collision:
        definitions.append(segment("collision", "subject_definitions", "<Subject 1> is another person from <Picture 1>.", "definition_1"))
    summary_text = ("[reference generation] " if summary_prefix else "Reference generation: ") + ", ".join(f"<Subject {index}>" for index in range(1, refs + 1)) + " share one shot."
    retention_text = ", ".join(
        f"<Subject {index}> from <Picture {index}>"
        for index in range(1, refs + 1)
        if not (missing_retention and index == refs)
    ) + " remain fully_preserved."
    action_value: str | dict[str, Any] = "all subjects stop"
    detail_text: str | dict[str, Any] = (
        "[Shot 1] " + ", ".join(f"<Subject {index}>" for index in range(1, refs + 1)) + " walk forward and all subjects stop."
    )
    if bad_timeline:
        detail_text = "[Shot 1] Subjects move. [Shot 2] Subjects stop."
    if huge:
        action_value = {"prefix": "visiblechange", "count": 3000, "joiner": " "}
        detail_text = {"prefix": "[Shot 1] visiblechange", "count": 3000, "joiner": " "}
    facts = definition_facts + [
        fact("summary", "reference generation", dimension="task_summary"),
        fact("retention", "all references retained", dimension="retention"),
        fact("action", action_value, dimension="action_result", origin="user_locked" if huge else "user_explicit"),
    ]
    detail_fact_ids = ["action"]
    if stable_leak:
        detail_fact_ids.append("definition_1")
        if isinstance(detail_text, str):
            detail_text += " Subject 1 keeps the defined appearance."
    sound_segments: list[dict[str, Any]] = []
    if bad_sound:
        facts.append(fact("sound", "background music rises", dimension="ambient_sound"))
        sound_segments.append(segment("sound", "overall_soundscape", "background music rises", "sound"))
    request = {
        "duration_seconds": duration,
        "shot_count": 2 if bad_timeline else 1,
        "references": references,
        "subject_definitions": definitions,
        "summary": [segment("summary", "summary", summary_text, "summary")],
        "retention_analysis": [segment("retention", "retention_analysis", retention_text, "retention")],
        "detailed_description": [segment("action", "detailed_description", detail_text, *detail_fact_ids)],
        "overall_soundscape": sound_segments,
        "non_diegetic_music": [],
    }
    return case(case_id, "h3_ref2va", stratum, expected_status, facts, request)


def build_ref2va() -> list[dict[str, Any]]:
    result = [
        ref_case(f"h3-ref2va-simple-{index:02d}", "simple", "production_ready", refs=1, duration=duration)
        for index, duration in enumerate([2, 3, 4, 5, 6, 7, 8, 10, 12, 15], 1)
    ]
    result.extend(
        ref_case(
            f"h3-ref2va-boundary-{index:02d}", "boundary", "production_ready",
            refs=1 if index % 2 else 3,
            duration=[2, 4, 5, 6, 8, 9, 10, 12, 14, 15][index - 1],
        )
        for index in range(1, 11)
    )
    options = [
        {"stable_leak": True},
        {"collision": True},
        {"invalid_dimensions": True},
        {"wrong_order": True, "refs": 3},
        {"refs": 3, "missing_retention": True},
        {"bad_owner": True},
        {"summary_prefix": False},
        {"huge": True, "duration": 15},
        {"bad_timeline": True},
        {"bad_sound": True},
    ]
    statuses = ["quality_rejected"] * 7 + ["budget_conflict", "quality_rejected", "quality_rejected"]
    result.extend(
        ref_case(f"h3-ref2va-adversarial-{index:02d}", "adversarial", statuses[index - 1], **value)
        for index, value in enumerate(options, 1)
    )
    return result


def write_cases(name: str, values: list[dict[str, Any]]) -> None:
    if len(values) != 30:
        raise ValueError(f"{name} must contain exactly 30 cases")
    target = OUTPUT / f"{name}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for value in values
        ),
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    write_cases("anima", build_anima())
    write_cases("h3_t2va", build_t2va())
    write_cases("h3_ref2va", build_ref2va())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
