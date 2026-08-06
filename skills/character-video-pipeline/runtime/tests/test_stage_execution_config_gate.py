"""P4 tests: config-surface draft gates and pre-submission LoRA presence.

New file per the P4 slice of docs/superpowers/specs/2026-08-05-config-surface-
lora-unit-design.md; existing test files stay untouched.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

import runtime.stage_execution as stage_execution
from runtime.config_surface import build_stage_config
from runtime.contracts import content_hash
from runtime.local_orchestrator import (
    submit_character_base_via_local_rest,
    submit_stage_via_local_rest,
)
from runtime.lora_discovery import (
    LoraDiscoveryError,
    hash_inventory,
    verify_lora_presence,
)
from runtime.tests.test_stage_execution import (
    NOW,
    _accepted_reference,
    _camera_profile,
    _capability_report,
    _event,
    _shot_graph,
    _shot_plan,
    _shot_ui,
)

NEUTRAL_EXTRA = {
    "extreme_type": "none", "extreme_weight": 0.0,
    "lens_enabled": False, "lens_value": "",
    "dof_enabled": False, "dof_value": "", "dof_weight": 0.0,
    "movement_enabled": False, "movement_value": "",
    "composition_enabled": False, "composition_value": "",
    "style_enabled": False, "style_value": "",
}

INVENTORY = {
    "loras": [
        "Anima\\anima-base-1-masterpiece-v51.safetensors",
        "FLux\\bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors",
    ]
}


@pytest.fixture(autouse=True)
def trusted_clock(monkeypatch):
    monkeypatch.setattr(stage_execution, "_utc_now", lambda: NOW)


def _lora_plan_payload():
    return {
        "base_model": "miaomiaoHarem_anima15.safetensors",
        "selections": [
            {
                "name": "Anima\\anima-base-1-masterpiece-v51",
                "strength_model": 1.0,
                "strength_clip": 1.0,
                "active": True,
                "trigger_words": ["masterpiece"],
            }
        ],
        "inventory_hash": hash_inventory(INVENTORY),
        "recommendation_hash": "b" * 64,
    }


def _shot_stage_config(**overrides):
    payload = {
        "stage": "shot-image",
        "prompts": {"positive": "shot", "negative": ""},
        "camera": {"direction": "back", "elevation": "high", "distance": "medium", "roll": 5.0},
        "camera_extra": copy.deepcopy(NEUTRAL_EXTRA),
        "groups": {"enabled_g1": [], "enabled_g2": ["\u5bf9\u6bd4\u5ea6\uff08G2\uff09"]},
        "lora_plan": _lora_plan_payload(),
        "reference_image": "reference.png",
    }
    payload.update(overrides)
    return build_stage_config(**payload)


def _draft(report, *, stage_config=None):
    return stage_execution.build_stage_execution_draft(
        _shot_plan(report),
        _shot_graph(),
        _camera_profile(),
        report,
        ui_workflow=_shot_ui(),
        image_name="runs/lineage/ref.png",
        reference_artifact=_accepted_reference(),
        stage_config=stage_config,
    )


def test_verify_lora_presence_accepts_current_inventory():
    resolved = verify_lora_presence(INVENTORY, _lora_plan_payload()["selections"])
    assert resolved == ["Anima\\anima-base-1-masterpiece-v51.safetensors"]


def test_verify_lora_presence_rejects_missing_selection():
    with pytest.raises(LoraDiscoveryError, match="missing from inventory"):
        verify_lora_presence({"loras": []}, _lora_plan_payload()["selections"])


def test_verify_lora_presence_rejects_bad_shapes():
    with pytest.raises(LoraDiscoveryError):
        verify_lora_presence(INVENTORY, [])
    with pytest.raises(LoraDiscoveryError):
        verify_lora_presence(INVENTORY, [{"strength_model": 1.0}])


def test_draft_with_stage_config_carries_config_gate_hashes():
    config = _shot_stage_config()
    draft = _draft(_capability_report(), stage_config=config)
    assert draft["config_hash"] == config["config_hash"]
    assert draft["lora_recommendation_hash"] == config["lora_plan"]["recommendation_hash"]
    assert draft["lora_inventory_hash"] == config["lora_plan"]["inventory_hash"]
    unsigned = dict(draft)
    unsigned.pop("draft_hash")
    assert draft["draft_hash"] == content_hash(unsigned)
    assert stage_execution._validate_stage_draft(draft)["config_hash"] == config["config_hash"]


def test_legacy_draft_schema_still_validates():
    draft = _draft(_capability_report())
    for key in ("config_hash", "lora_recommendation_hash", "lora_inventory_hash"):
        assert key not in draft
    assert stage_execution._validate_stage_draft(draft)["draft_hash"] == draft["draft_hash"]


def test_draft_rejects_partial_config_gate_keys():
    draft = _draft(_capability_report(), stage_config=_shot_stage_config())
    draft.pop("lora_inventory_hash")
    unsigned = dict(draft)
    unsigned.pop("draft_hash")
    draft["draft_hash"] = content_hash(unsigned)
    with pytest.raises(stage_execution.StageExecutionError):
        stage_execution._validate_stage_draft(draft)


def test_draft_rejects_stage_config_stage_mismatch():
    config = build_stage_config(
        stage="character-base",
        prompts={"positive": "hero", "negative": ""},
        camera={"direction": "front", "elevation": "eye-level", "distance": "full_body", "roll": 0.0},
        camera_extra=copy.deepcopy(NEUTRAL_EXTRA),
        groups={"enabled_g1": [], "enabled_g2": ["\u5bf9\u6bd4\u5ea6\uff08G2\uff09"]},
        lora_plan=_lora_plan_payload(),
    )
    with pytest.raises(stage_execution.StageExecutionError, match="stage"):
        _draft(_capability_report(), stage_config=config)


def test_draft_rejects_tampered_stage_config():
    config = _shot_stage_config()
    config["prompts"]["positive"] = "tampered"
    with pytest.raises(stage_execution.StageExecutionError):
        _draft(_capability_report(), stage_config=config)


def test_config_gated_draft_approval_keeps_lineage(tmp_path):
    config = _shot_stage_config()
    draft = _draft(_capability_report(), stage_config=config)
    approved = stage_execution.approve_stage_execution_draft(
        draft, _event(draft, tmp_path), tmp_path
    )
    assert approved["config_hash"] == config["config_hash"]
    assert approved["lora_inventory_hash"] == config["lora_plan"]["inventory_hash"]
    assert approved["execution_plan_hash"]


def test_submit_rejects_lora_missing_from_fresh_inventory():
    with pytest.raises(stage_execution.StageExecutionError, match="presence"):
        submit_stage_via_local_rest(
            {},
            {},
            {},
            "unused",
            profile={},
            capability_report={},
            lora_inventory={"loras": []},
            lora_plan=_lora_plan_payload(),
        )


def test_submit_rejects_stale_inventory_hash():
    approved_plan = {"lora_inventory_hash": "f" * 64}
    with pytest.raises(stage_execution.StageExecutionError, match="inventory"):
        submit_stage_via_local_rest(
            approved_plan,
            {},
            {},
            "unused",
            profile={},
            capability_report={},
            lora_inventory=INVENTORY,
            lora_plan=_lora_plan_payload(),
        )


def test_submit_requires_both_lora_evidence_or_neither():
    with pytest.raises(stage_execution.StageExecutionError, match="both"):
        submit_stage_via_local_rest(
            {},
            {},
            {},
            "unused",
            profile={},
            capability_report={},
            lora_inventory=INVENTORY,
        )


def test_submit_character_base_rejects_lora_missing():
    with pytest.raises(stage_execution.StageExecutionError, match="presence"):
        submit_character_base_via_local_rest(
            {},
            {},
            {},
            {},
            "unused",
            lora_inventory={"loras": []},
            lora_plan=_lora_plan_payload(),
        )


