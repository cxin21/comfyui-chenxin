import pytest

from runtime.contracts import (
    ContractError,
    canonical_json,
    content_hash,
    validate_task_context,
)


def valid_context():
    return {
        "schema_version": "1.0",
        "shared_known": {
            "goal": "create one character video shot",
            "background": [],
            "acceptance": ["front-facing base image"],
            "boundaries": ["local only"],
        },
        "user_known_agent_unknown": {
            "references": [],
            "aesthetic_preferences": [],
            "real_world_constraints": [],
        },
        "agent_known_user_unknown": {
            "capabilities": [],
            "risks": [],
            "alternatives": [],
        },
        "shared_unknown": {"hypotheses": [], "experiments": []},
    }


def test_context_is_copied_and_validated():
    source = valid_context()

    result = validate_task_context(source)

    assert result == source
    assert result is not source


def test_goal_is_required():
    source = valid_context()
    source["shared_known"]["goal"] = ""

    with pytest.raises(ContractError, match="goal"):
        validate_task_context(source)


def test_goal_must_be_a_non_empty_string():
    source = valid_context()
    source["shared_known"]["goal"] = None

    with pytest.raises(ContractError, match="goal"):
        validate_task_context(source)


def test_hash_ignores_dictionary_key_order():
    assert content_hash({"b": 2, "a": 1}) == content_hash({"a": 1, "b": 2})


def test_canonical_json_rejects_non_json_nan():
    with pytest.raises(ValueError):
        canonical_json(float("nan"))
