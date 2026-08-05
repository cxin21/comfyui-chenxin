"""Contract tests for canonical CreativeEvidence normalization."""

import copy
import sys
from pathlib import Path

import pytest


PROMPT_FORGE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROMPT_FORGE))

from internals.intent_normalize import normalize_evidence  # noqa: E402


REQUIRED_KEYS = {
    "shared_known",
    "user_known_agent_unknown",
    "assistant_known_user_unknown",
    "joint_unknown",
    "locked_facts",
    "continuity_locks",
    "style_evidence",
    "asset_refs",
    "uncertainty",
}


def _payload():
    return {
        "mode": "execute",
        "workflow_hash": "f" * 64,
        "dimensions": {
            "subject": [
                {
                    "value": "a swordsman in a red robe",
                    "origin": "explicit",
                    "source_text": "red-robed swordsman",
                    "locked": True,
                }
            ],
            "lighting": [
                {
                    "value": "moonlit rim light",
                    "origin": "recipe",
                    "source_text": "dialect suggestion",
                }
            ],
            "motion": [
                {
                    "value": "cloth follows the turn",
                    "origin": "inferred",
                    "source_text": "motion inference",
                }
            ],
        },
        "explicit_evidence": ["draws his sword"],
        "reasonable_inference": ["the cloth trails behind the turn"],
        "user_known_agent_unknown": ["the exact family crest"],
        "locked_facts": ["draws his sword"],
        "continuity_locks": {"identity": ["a swordsman in a red robe"]},
        "style_suggestions": [{"id": "xianxia_cinematic", "score": 0.8}],
        "dialect_suggestions": [{"id": "wan_2_7", "score": 0.7}],
        "asset_refs": [{"asset_id": "hero-01", "role": "identity"}],
        "uncertainty": ["exact family crest"],
        "prohibited_expansion": ["modern sunglasses"],
        "joint_unknown": [
            {
                "hypothesis": "a slower turn improves cloth readability",
                "single_variable": "turn speed",
                "success_signal": "robe silhouette stays readable",
                "failure_signal": "motion feels static",
                "next_data": "compare two turn speeds",
            }
        ],
        "source_provenance": [
            {"source_id": "brief-01", "sha256": "a" * 64}
        ],
    }


def test_normalize_evidence_preserves_explicit_origin_and_source_text():
    result = normalize_evidence(_payload())

    assert REQUIRED_KEYS <= result.keys()
    subject = next(item for item in result["shared_known"] if item.get("dimension") == "subject")
    assert subject["value"] == "a swordsman in a red robe"
    assert subject["origin"] == "explicit"
    assert subject["source_text"] == "red-robed swordsman"
    assert "a swordsman in a red robe" in result["locked_facts"]


def test_inference_and_style_or_dialect_suggestions_never_become_facts():
    result = normalize_evidence(_payload())
    shared_values = {item["value"] for item in result["shared_known"]}
    inferred_values = {item["value"] for item in result["assistant_known_user_unknown"]}

    assert "moonlit rim light" not in shared_values
    assert "cloth follows the turn" in inferred_values
    assert "the cloth trails behind the turn" in inferred_values
    assert {item["kind"] for item in result["style_evidence"]} == {
        "dialect_suggestion",
        "style_suggestion",
    }


def test_prohibited_expansion_cannot_overlap_facts_or_continuity_locks():
    payload = _payload()
    payload["prohibited_expansion"] = ["A SWORDSMAN IN A RED ROBE"]

    with pytest.raises(ValueError):
        normalize_evidence(payload)


def test_joint_unknown_preserves_one_single_variable_experiment():
    payload = _payload()
    result = normalize_evidence(payload)

    assert result["joint_unknown"] == payload["joint_unknown"]
    invalid = _payload()
    invalid["joint_unknown"][0]["single_variable"] = ["speed", "camera"]
    with pytest.raises(ValueError):
        normalize_evidence(invalid)


def test_sha256_is_validated_only_inside_source_provenance():
    payload = _payload()
    payload["workflow_hash"] = "not-a-hash"
    result = normalize_evidence(payload)

    assert result["source_provenance"] == payload["source_provenance"]
    assert "workflow_hash" not in result
    assert "mode" not in result

    invalid = _payload()
    invalid["source_provenance"][0]["sha256"] = "bad"
    with pytest.raises(ValueError):
        normalize_evidence(invalid)


def test_normalization_does_not_alias_caller_data():
    payload = _payload()
    before = copy.deepcopy(payload)
    result = normalize_evidence(payload)
    result["continuity_locks"]["identity"].append("mutated")

    assert payload == before


def _forbidden_metadata_keys(value):
    forbidden = {"workflow", "node", "hash", "gpu", "execution", "mode"}
    if isinstance(value, dict):
        for key, child in value.items():
            parts = set(key.casefold().replace("-", "_").split("_"))
            if forbidden & parts or any(
                token in key.casefold() for token in ("workflow", "node", "hash", "gpu", "execution")
            ):
                yield key
            yield from _forbidden_metadata_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _forbidden_metadata_keys(child)


def test_nested_runtime_metadata_is_stripped_from_every_output_channel():
    payload = _payload()
    payload["shared_known"] = [
        {
            "value": "weathered bronze armor",
            "origin": "explicit",
            "metadata": {
                "author": "art bible",
                "workflow": {"node_id": "42", "gpu": "24GB"},
            },
            "execution_mode": "live",
        }
    ]
    payload["asset_refs"][0]["details"] = {
        "note": "identity source",
        "workflow_hash": "secret-runtime-value",
    }
    payload["style_suggestions"][0]["runtime"] = {
        "execution": {"mode": "automatic"},
        "node": "style-loader",
    }
    payload["source_provenance"][0].update(
        {
            "workflow_hash": "b" * 64,
            "metadata": {"author": "user", "node_id": "source-loader"},
        }
    )

    result = normalize_evidence(payload)

    assert list(_forbidden_metadata_keys(result)) == []
    assert result["source_provenance"][0]["sha256"] == "a" * 64
    assert result["source_provenance"][0]["metadata"] == {"author": "user"}
    shared = next(item for item in result["shared_known"] if item["value"] == "weathered bronze armor")
    assert shared["metadata"] == {"author": "art bible"}
    assert result["asset_refs"][0]["details"] == {"note": "identity source"}


def test_non_explicit_records_cannot_enter_shared_known_even_when_supplied_there():
    payload = _payload()
    payload["shared_known"] = [
        {"value": "suggested teal palette", "origin": "recipe"},
        {"value": "likely fog behind the hero", "origin": "inferred"},
        {"value": "confirmed red robe", "origin": "explicit"},
    ]
    payload["explicit_evidence"] = [
        {"value": "suggested wide lens", "origin": "recipe"},
        {"value": "confirmed sword", "origin": "explicit"},
    ]

    result = normalize_evidence(payload)
    shared = {item["value"] for item in result["shared_known"]}
    inferred = {item["value"] for item in result["assistant_known_user_unknown"]}

    assert {"confirmed red robe", "confirmed sword"} <= shared
    assert "suggested teal palette" not in shared
    assert "likely fog behind the hero" not in shared
    assert "suggested wide lens" not in shared
    assert {
        "suggested teal palette",
        "likely fog behind the hero",
        "suggested wide lens",
    } <= inferred