from __future__ import annotations

import copy
import pytest

from runtime.config_contract import ConfigContractError, apply_config_patch, read_config_surface, validate_config_contract


def _contract(stage="multiview"):
    return {"schema_version": "1.0", "stage": stage, "slots": {
        "positive_prompt": {"node_id": 10, "input": "text", "type": "text"},
        "reference_image": {"node_id": 11, "input": "image", "type": "image"},
    }, "forbidden_inputs": ["seed", "sampler_name", "scheduler", "steps", "cfg"]}


def _graph():
    return {"10": {"class_type": "CLIPTextEncode", "inputs": {"text": "old", "seed": 123}},
            "11": {"class_type": "LoadImage", "inputs": {"image": "old.png"}},
            "12": {"class_type": "KSampler", "inputs": {"seed": 123, "sampler_name": "euler"}}}


def test_contract_reads_only_declared_slots():
    assert read_config_surface(_graph(), validate_config_contract(_contract())) == {"positive_prompt": "old", "reference_image": "old.png"}


def test_contract_patch_changes_only_declared_slots():
    graph = _graph()
    patched = apply_config_patch(graph, _contract(), {"positive_prompt": "new", "reference_image": "fresh.png"})
    assert patched["10"]["inputs"]["text"] == "new" and patched["11"]["inputs"]["image"] == "fresh.png"
    assert patched["12"] == graph["12"]


def test_contract_rejects_internal_execution_fields_and_drift():
    with pytest.raises(ConfigContractError, match="forbidden|not declared"):
        apply_config_patch(_graph(), _contract(), {"seed": 42})
    broken = copy.deepcopy(_graph())
    broken["10"]["class_type"] = "WrongNode"
    with pytest.raises(ConfigContractError, match="class_type"):
        read_config_surface(broken, _contract())


def test_contract_requires_explicit_stage_and_policy():
    bad = _contract()
    bad.pop("stage")
    with pytest.raises(ConfigContractError):
        validate_config_contract(bad)
