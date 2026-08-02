import json

import pytest

from runtime.errors import FaultError, make_fault


@pytest.mark.parametrize(
    "category",
    [
        "CAPABILITY_ERROR",
        "WORKFLOW_ERROR",
        "RESOURCE_ERROR",
        "POLICY_ERROR",
        "EXECUTION_ERROR",
    ],
)
def test_fault_accepts_each_supported_category(category):
    fault = make_fault(category, "preflight", "blocked", False, "stop", {})

    assert fault["category"] == category


def test_fault_has_a_complete_json_safe_contract():
    fault = make_fault(
        "WORKFLOW_ERROR",
        "preflight",
        "profile drift",
        False,
        "rediscover the workflow profile",
        {"profile_id": "camera-anima-v1"},
    )

    assert fault == {
        "schema_version": "1.0",
        "category": "WORKFLOW_ERROR",
        "stage": "preflight",
        "message": "profile drift",
        "retry_safe": False,
        "next_action": "rediscover the workflow profile",
        "evidence": {"profile_id": "camera-anima-v1"},
    }
    assert json.loads(json.dumps(fault)) == fault


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"category": "OTHER"}, "category"),
        ({"category": ["WORKFLOW_ERROR"]}, "category"),
        ({"stage": " "}, "stage"),
        ({"message": ""}, "message"),
        ({"retry_safe": 1}, "retry_safe"),
        ({"next_action": ""}, "next_action"),
        ({"evidence": []}, "evidence"),
    ],
)
def test_fault_rejects_invalid_required_fields(kwargs, match):
    values = {
        "category": "CAPABILITY_ERROR",
        "stage": "discover",
        "message": "service unavailable",
        "retry_safe": True,
        "next_action": "retry discovery",
        "evidence": {"url": "http://127.0.0.1:8188"},
    }
    values.update(kwargs)

    with pytest.raises(FaultError, match=match):
        make_fault(**values)
