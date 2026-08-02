import copy
import json
from pathlib import Path

import pytest

from runtime.workflow_profile import ProfileError, resolve_slots, structure_fingerprint


FIXTURE = Path(__file__).parent / "fixtures" / "camera-ui-minimal.json"
PROFILE = Path(__file__).parents[1] / "profiles" / "camera-anima.json"


def load_workflow():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_camera_profile_is_utf8_and_names_verified_workflow():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert profile["workflow_name"] == "文生图相机视角.json"


def test_prompt_change_does_not_change_structure():
    workflow = load_workflow()
    changed = copy.deepcopy(workflow)
    changed["nodes"][0]["widgets_values"][0] = "different prompt"
    assert structure_fingerprint(workflow) == structure_fingerprint(changed)


def test_node_type_change_changes_structure():
    workflow = load_workflow()
    changed = copy.deepcopy(workflow)
    changed["nodes"][0]["type"] = "DifferentNode"
    assert structure_fingerprint(workflow) != structure_fingerprint(changed)


def test_slots_resolve_by_type_and_title():
    workflow = load_workflow()
    profile = {"slots": {
        "positive_prompt": {"type": "ImpactWildcardProcessor", "title": "POSITIVE"},
        "negative_prompt": {"type": "ImpactWildcardProcessor", "title": "NEGATIVE"},
    }}
    assert resolve_slots(workflow, profile) == {
        "positive_prompt": 24,
        "negative_prompt": 25,
    }


def test_slots_resolve_by_explicit_node_id():
    assert resolve_slots(load_workflow(), {"slots": {
        "camera_angle": {"id": 583, "type": "CameraAngleNode"},
    }}) == {"camera_angle": 583}


def test_ambiguous_slot_stops():
    workflow = load_workflow()
    duplicate = copy.deepcopy(workflow["nodes"][0])
    duplicate["id"] = 240
    workflow["nodes"].append(duplicate)
    with pytest.raises(ProfileError, match="exactly one"):
        resolve_slots(workflow, {"slots": {
            "positive": {"type": "ImpactWildcardProcessor", "title": "POSITIVE"},
        }})


def test_missing_slot_stops():
    with pytest.raises(ProfileError, match="exactly one"):
        resolve_slots(load_workflow(), {"slots": {
            "missing": {"type": "MissingNode"},
        }})


def test_slot_without_explicit_node_constraints_stops():
    with pytest.raises(ProfileError, match="at least one"):
        resolve_slots(load_workflow(), {"slots": {"unsafe": {}}})
