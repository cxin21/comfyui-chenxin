from __future__ import annotations

from runtime.workflow_assets import (
    asset_descriptor,
    asset_for_stage,
    load_fixed_api_workflow,
    load_fixed_workflow,
)


def test_bundled_workflow_assets_are_real_comfyui_ui_workflows():
    for stage in ("character-base", "multiview", "video"):
        name = asset_for_stage(stage)
        workflow = load_fixed_workflow(name)
        assert workflow["nodes"]



def test_fixed_asset_descriptor_contains_workflow_identity_and_surface_policy():
    for stage in ("character-base", "multiview", "video"):
        name = asset_for_stage(stage)
        descriptor = asset_descriptor(name)
        assert descriptor["workflow_id"]
        assert descriptor["workflow_schema_version"] == "comfyui-ui-v1"
        assert descriptor["workflow_fingerprint"]
        assert stage in descriptor["config_surface_stages"]
        assert set(descriptor["forbidden_inputs"]) >= {"seed", "sampler_name", "scheduler"}

def test_character_base_has_a_fixed_api_workflow_for_execution_without_workflow_mcp():
    workflow = load_fixed_api_workflow("camera-anima.json")

    assert workflow["24"]["class_type"] == "ImpactWildcardProcessor"
    assert workflow["25"]["class_type"] == "ImpactWildcardProcessor"
    assert workflow["35"]["class_type"] == "Image Saver Simple"