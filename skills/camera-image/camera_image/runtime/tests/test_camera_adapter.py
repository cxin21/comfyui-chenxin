import copy
import json
from pathlib import Path

import pytest

import runtime.adapters.camera as camera_module
from runtime.adapters.camera import (
    CameraAdapterError,
    is_pinned_camera_normalization_profile,
    patch_character_base,
)
from runtime.execution import ExecutionError


FIXTURE = Path(__file__).parent / "fixtures" / "camera-api-minimal.json"
PROFILE_DIR = Path(__file__).parents[1] / "profiles"


def ready_build():
    return {
        "schema_version": "1.0",
        "model_id": "anima",
        "dialect": "tags",
        "prompt": "score_9, 1girl, solo, from_front, full_body",
        "negative_prompt": "worst quality, low quality, watermark",
        "validated_tags": ["1girl", "solo", "from_front", "full_body"],
        "rejected_tags": [],
        "recipe_control_tokens": ["score_9"],
        "locked_facts": ["1girl"],
        "ready_to_execute": True,
        "execution": {"requested": True, "performed": False},
    }


def load_graph():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_patch_updates_only_both_prompt_fields_and_deep_copies():
    graph = load_graph()
    original = copy.deepcopy(graph)

    patched = patch_character_base(
        graph, ready_build(), {"positive_prompt": 24, "negative_prompt": 25}
    )

    assert patched["24"]["inputs"]["wildcard_text"] == ready_build()["prompt"]
    assert patched["24"]["inputs"]["populated_text"] == ready_build()["prompt"]
    assert patched["25"]["inputs"]["wildcard_text"] == ready_build()["negative_prompt"]
    assert patched["25"]["inputs"]["populated_text"] == ready_build()["negative_prompt"]
    assert graph == original
    assert patched["24"]["inputs"]["seed"] == 101
    assert patched["583"] == original["583"]
    assert patched["900"] == original["900"]


@pytest.mark.parametrize(
    "slots, match",
    [
        ({"positive_prompt": 24}, "negative_prompt"),
        ({"positive_prompt": 999, "negative_prompt": 25}, "missing"),
        ({"positive_prompt": True, "negative_prompt": 25}, "integer"),
        (
            {"positive_prompt": 24, "negative_prompt": 25, "seed": 24},
            "unexpected",
        ),
    ],
)
def test_patch_rejects_missing_invalid_or_out_of_allowlist_slots(slots, match):
    with pytest.raises(ExecutionError, match=match):
        patch_character_base(load_graph(), ready_build(), slots)


@pytest.mark.parametrize(
    "slots",
    [
        {"positive_prompt": 25, "negative_prompt": 24},
        {"positive_prompt": 24, "negative_prompt": 24},
    ],
)
def test_character_base_rejects_noncanonical_or_aliased_slots(slots):
    with pytest.raises(ExecutionError, match="fixed.*slot"):
        patch_character_base(load_graph(), ready_build(), slots)


def test_patch_rejects_missing_or_wrong_typed_allowlisted_inputs():
    missing = load_graph()
    del missing["24"]["inputs"]["populated_text"]
    with pytest.raises(ExecutionError, match="populated_text"):
        patch_character_base(missing, ready_build(), {"positive_prompt": 24, "negative_prompt": 25})

    wrong_type = load_graph()
    wrong_type["25"]["inputs"]["wildcard_text"] = 123
    with pytest.raises(ExecutionError, match="string"):
        patch_character_base(wrong_type, ready_build(), {"positive_prompt": 24, "negative_prompt": 25})


def test_patch_rejects_wrong_node_class_and_invalid_build_prompts():
    graph = load_graph()
    graph["24"]["class_type"] = "CLIPTextEncode"
    with pytest.raises(ExecutionError, match="class_type"):
        patch_character_base(graph, ready_build(), {"positive_prompt": 24, "negative_prompt": 25})

    build = ready_build()
    build["negative_prompt"] = ""
    with pytest.raises(ExecutionError, match="negative_prompt"):
        patch_character_base(load_graph(), build, {"positive_prompt": 24, "negative_prompt": 25})


def _board_profile(role):
    return {
        "schema_version": "1.0",
        "profile_id": f"camera-anima-asset-board-{role}-v1",
        "board_role": role,
        "workflow_fingerprint": "a" * 64,
        "slots": {
            "positive_prompt": {"id": 24, "type": "ImpactWildcardProcessor", "title": "POSITIVE"},
            "negative_prompt": {"id": 25, "type": "ImpactWildcardProcessor", "title": "NEGATIVE"},
        },
        "forbidden_positive_terms": {"character": ["scene", "background", "prop"], "environment": ["person", "people", "human"], "prop": ["person", "people", "human", "hand"]}[role],
        "negative_constraints": {"character": ["scene", "background", "props"], "environment": ["people", "human figures"], "prop": ["people", "human figures", "hands"]}[role],
        "enabled_groups": [],
        "enabled_optional_branches": [],
        "allowed_mutations": ["positive_prompt.wildcard_text", "positive_prompt.populated_text", "negative_prompt.wildcard_text", "negative_prompt.populated_text"],
        "expected_outputs": ["image/png"],
    }


def test_character_board_profile_rejects_scene_reference_role():
    with pytest.raises(CameraAdapterError, match="character board"):
        camera_module.patch_asset_board_prompt(load_graph(), "single character; scene background", "", _board_profile("character"))


def test_asset_board_prompt_patches_only_profiled_slots_and_preserves_profile():
    graph = load_graph()
    source = copy.deepcopy(graph)
    selected_profile = _board_profile("environment")
    original_profile = copy.deepcopy(selected_profile)
    patched = camera_module.patch_asset_board_prompt(graph, "empty workshop panorama", "watermark", selected_profile)
    assert patched["24"]["inputs"]["wildcard_text"] == "empty workshop panorama"
    assert patched["25"]["inputs"]["wildcard_text"] == "watermark, people, human figures"
    assert patched["583"] == source["583"]
    assert patched["585"] == source["585"]
    assert graph == source
    assert selected_profile == original_profile


def test_camera_extra_patch_changes_only_declared_angle_and_extra_fields():
    graph = load_graph()
    graph["583"]["inputs"] = {"pos_x": 0.0, "pos_y": 0.0, "pos_z": 1.0, "roll": 0.0, "immutable": "angle-lock"}
    graph["585"]["inputs"] = {
        "extreme_type": "none", "extreme_weight": 0.0,
        "lens_enabled": False, "lens_value": "", "dof_enabled": False,
        "dof_value": "", "dof_weight": 0.0, "movement_enabled": False,
        "movement_value": "", "composition_enabled": False,
        "composition_value": "", "style_enabled": False, "style_value": "",
        "immutable": "extra-lock",
    }
    profile = {
        "workflow_fingerprint": "7fa7a85e005182c6be42a3f3193add3fb41531ef0fae28e1cbd54a791e72e20a",
        "slots": {"camera_angle": {"id": 583, "type": "CameraAngleNode"}, "camera_extra": {"id": 585, "type": "CameraExtraConfigNode"}},
        "camera_angle_allowlist": ["pos_x", "pos_y", "pos_z", "roll"],
        "camera_extra_allowlist": ["extreme_type", "extreme_weight", "lens_enabled", "lens_value", "dof_enabled", "dof_value", "dof_weight", "movement_enabled", "movement_value", "composition_enabled", "composition_value", "style_enabled", "style_value"],
        "output_topology": [{"id": 900, "type": "SaveImage"}],
        "expected_outputs": ["image/png"],
    }
    patched = camera_module.patch_camera_controls(
        graph,
        camera={"direction": "right_45", "elevation": "eye-level", "distance": "medium", "roll": 0.0},
        camera_extra={"extreme_type": "none", "extreme_weight": 0.0, "lens_enabled": True, "lens_value": "50mm lens", "dof_enabled": True, "dof_value": "shallow depth of field", "dof_weight": 1.0, "movement_enabled": False, "movement_value": "", "composition_enabled": True, "composition_value": "rule of thirds", "style_enabled": False, "style_value": ""},
        profile=profile,
        workflow_fingerprint=profile["workflow_fingerprint"],
    )
    assert patched["583"]["inputs"]["pos_x"] == 0.25
    assert patched["585"]["inputs"]["lens_value"] == "50mm lens"
    assert patched["583"]["inputs"]["immutable"] == "angle-lock"
    assert patched["585"]["inputs"]["immutable"] == "extra-lock"
    assert graph["583"]["inputs"]["pos_x"] == 0.0
    assert graph["585"]["inputs"]["lens_enabled"] is False


@pytest.mark.parametrize(
    "role, contamination",
    [
        ("environment", "1girl"),
        ("environment", "empty room background"),
        ("environment", "discarded weapon"),
        ("prop", "character hands"),
        ("prop", "sword weapon"),
        ("character", "room background"),
        ("character", "sword weapon"),
    ],
)
def test_asset_board_roles_reject_semantic_contamination_and_numeric_prefixes(
    role, contamination
):
    selected_profile = json.loads(
        (PROFILE_DIR / f"camera-anima-asset-board-{role}.json").read_text(encoding="utf-8")
    )
    with pytest.raises(CameraAdapterError, match=f"{role} board"):
        camera_module.patch_asset_board_prompt(
            load_graph(), contamination, "watermark", selected_profile
        )


def test_camera_controls_reject_profile_slot_alias_and_output_topology_drift():
    graph = load_graph()
    graph["583"]["inputs"] = {
        "pos_x": 0.0,
        "pos_y": 0.0,
        "pos_z": 1.0,
        "roll": 0.0,
    }
    graph["585"]["inputs"] = {
        "extreme_type": "none", "extreme_weight": 0.0,
        "lens_enabled": False, "lens_value": "", "dof_enabled": False,
        "dof_value": "", "dof_weight": 0.0, "movement_enabled": False,
        "movement_value": "", "composition_enabled": False,
        "composition_value": "", "style_enabled": False, "style_value": "",
    }
    selected_profile = {
        "workflow_fingerprint": "7fa7a85e005182c6be42a3f3193add3fb41531ef0fae28e1cbd54a791e72e20a",
        "slots": {
            "camera_angle": {"id": 900, "type": "SaveImage"},
            "camera_extra": {"id": 585, "type": "CameraExtraConfigNode"},
        },
        "camera_angle_allowlist": ["pos_x", "pos_y", "pos_z", "roll"],
        "camera_extra_allowlist": ["extreme_type", "extreme_weight", "lens_enabled", "lens_value", "dof_enabled", "dof_value", "dof_weight", "movement_enabled", "movement_value", "composition_enabled", "composition_value", "style_enabled", "style_value"],
        "output_topology": [{"id": 900, "type": "SaveImage"}],
        "expected_outputs": ["image/png"],
    }
    camera = {"direction": "front", "elevation": "eye-level", "distance": "medium", "roll": 0.0}
    camera_extra = {key: graph["585"]["inputs"][key] for key in selected_profile["camera_extra_allowlist"]}
    with pytest.raises(CameraAdapterError, match="583"):
        camera_module.patch_camera_controls(
            graph, camera=camera, camera_extra=camera_extra,
            profile=selected_profile,
            workflow_fingerprint=selected_profile["workflow_fingerprint"],
        )

    selected_profile["slots"]["camera_angle"] = {"id": 583, "type": "CameraAngleNode"}
    selected_profile["output_topology"] = [{"id": 999, "type": "SaveImage"}]
    with pytest.raises(CameraAdapterError, match="topology"):
        camera_module.patch_camera_controls(
            graph, camera=camera, camera_extra=camera_extra,
            profile=selected_profile,
            workflow_fingerprint=selected_profile["workflow_fingerprint"],
        )


def test_camera_profile_aliases_share_only_the_pinned_normalization_contract():
    for name in (
        "camera-anima-base.json",
        "camera-anima-asset-board-environment.json",
        "camera-anima-asset-board-character.json",
        "camera-anima-asset-board-prop.json",
    ):
        selected_profile = json.loads((PROFILE_DIR / name).read_text(encoding="utf-8"))
        assert is_pinned_camera_normalization_profile(selected_profile) is True


@pytest.mark.parametrize("role, artifact_type", [("environment", "EnvironmentBoard"), ("character", "CharacterBoard"), ("prop", "PropBoard")])
def test_asset_board_profiles_pin_role_and_keep_optional_branches_off(role, artifact_type):
    selected_profile = json.loads((PROFILE_DIR / f"camera-anima-asset-board-{role}.json").read_text(encoding="utf-8"))
    assert selected_profile["profile_id"] == f"camera-anima-asset-board-{role}-v1"
    assert selected_profile["board_role"] == role
    assert selected_profile["expected_artifact_type"] == artifact_type
    assert selected_profile["enabled_groups"] == []
    assert selected_profile["enabled_optional_branches"] == []


def test_character_base_profile_is_clean_and_neutral():
    selected_profile = json.loads((PROFILE_DIR / "camera-anima-base.json").read_text(encoding="utf-8"))
    assert selected_profile["profile_id"] == "camera-anima-base-v1"
    assert selected_profile["camera_defaults"] == {"direction": "front", "elevation": "eye-level", "distance": "full_body", "roll": 0.0}
    assert selected_profile["camera_extra_defaults"]["lens_enabled"] is False
    assert selected_profile["camera_extra_defaults"]["dof_enabled"] is False
    assert selected_profile["enabled_groups"] == []
    assert selected_profile["enabled_optional_branches"] == []
