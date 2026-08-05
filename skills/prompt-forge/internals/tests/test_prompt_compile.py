import sys
from pathlib import Path

import pytest

PROMPT_FORGE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROMPT_FORGE))
from internals.prompt_compile import compile_payload, compile_prompt  # noqa: E402


def _evidence():
    return {
        "shared_known": [{"value": "a swordsman in a red robe", "origin": "explicit"}],
        "locked_facts": ["a swordsman in a red robe"],
        "continuity_locks": {"identity": ["red robe"]},
        "assistant_known_user_unknown": [],
        "uncertainty": [],
    }


def test_compile_prompt_requires_caller_authored_draft():
    with pytest.raises(ValueError):
        compile_prompt(_evidence(), dialect_id="anima")


def test_compile_prompt_preserves_image_draft_without_prose_fallback():
    draft = {
        "positive": "a swordsman in a red robe, drawing a sword",
        "negative": "watermark",
    }
    package = compile_prompt(_evidence(), draft=draft, dialect_id="anima")

    assert package["positive"] == draft["positive"]
    assert package["negative"] == draft["negative"]
    assert "global_prompt" not in package
    assert "timeline_segments" not in package
    assert package["quality"]["ready_for_review"] is True


def test_compile_prompt_rejects_runtime_metadata_at_any_depth():
    evidence = _evidence()
    evidence["asset_refs"] = [{"id": "hero", "meta": {"workflow_hash": "x"}}]
    with pytest.raises(ValueError):
        compile_prompt(
            evidence,
            draft={"positive": "a swordsman in a red robe", "settings": {"gpu": "24GB"}},
            dialect_id="anima",
        )


def test_compile_payload_requires_explicit_envelope_and_dialect():
    with pytest.raises(ValueError):
        compile_payload({"evidence": _evidence(), "draft": {"positive": "red robe"}})
    package = compile_payload(
        {
            "evidence": _evidence(),
            "draft": {"positive": "a swordsman in a red robe"},
            "dialect_id": "flux",
        }
    )
    assert package["dialect"] == "flux"
    assert "negative" not in package


def test_compile_payload_rejects_root_execution_metadata_before_field_filtering():
    payload = {
        "evidence": _evidence(),
        "draft": {"positive": "a swordsman in a red robe"},
        "dialect_id": "flux",
        "metadata": {"nested": {"workflowHash": "forbidden"}},
    }
    with pytest.raises(ValueError):
        compile_payload(payload)


def test_compile_payload_rejects_unexpected_safe_top_level_keys():
    payload = {
        "evidence": {**_evidence(), "model_id": "flux-dev"},
        "draft": {"positive": "a swordsman in a red robe"},
        "dialect_id": "flux",
        "notes": "unexpected envelope field",
    }
    with pytest.raises(ValueError):
        compile_payload(payload)


def test_compile_payload_allows_model_id_inside_evidence():
    package = compile_payload({
        "evidence": {**_evidence(), "model_id": "flux-dev"},
        "draft": {"positive": "a swordsman in a red robe"},
        "dialect_id": "flux",
    })
    assert package["quality"]["ready_for_review"] is True