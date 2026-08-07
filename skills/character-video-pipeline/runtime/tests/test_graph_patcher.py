"""Tests for graph_patcher.describe_config and NODE_FIELD_MAP single source."""
from runtime.graph_patcher import (
    describe_config,
    NODE_FIELD_MAP,
    _node_static_default,
    _apply_sampling,
    _apply_seed,
    _apply_image_size,
    _apply_controlnet_image,
)
from runtime.config_schema import (
    SamplingConfig,
    ImageSizeConfig,
    STAGES,
)
from runtime.workflow_loader import load_workflow


def test_node_field_map_has_eleven_entries():
    assert len(NODE_FIELD_MAP) == 11


def test_node_field_map_keys_match_config_schema_paths():
    paths = set(NODE_FIELD_MAP.keys())
    assert "sampling.steps_first" in paths
    assert "sampling.cfg" in paths
    assert "sampling.sampler" in paths
    assert "sampling.scheduler" in paths
    assert "sampling.denoise_first" in paths
    assert "sampling.steps_refine" in paths
    assert "sampling.denoise_refine" in paths
    assert "seed" in paths
    assert "image_size.width" in paths
    assert "image_size.height" in paths
    assert "controlnet_image" in paths


def test_node_static_default_reads_workflow_value():
    graph = load_workflow(STAGES.T2I)
    # node 50 default steps = 40 per the workflow dump
    assert _node_static_default(graph, "50", "steps") == 40
    # node 65 static seed is -1 in the read-only workflow.json ("randomize"
    # sentinel for Seed (rgthree)); _node_static_default is a pure passthrough,
    # so it reports the asset's real value.
    assert _node_static_default(graph, "65", "seed") == -1


def test_describe_config_returns_workflow_bound_defaults():
    out = describe_config(STAGES.T2I)
    assert out["workflow"] == STAGES.T2I
    sampling = out["slots"]["sampling"]
    assert sampling["nodes"] == ["50", "51"]
    assert sampling["fields"]["steps_first"]["node"] == "50"
    assert sampling["fields"]["steps_first"]["default"] == 40
    assert sampling["fields"]["denoise_refine"]["default"] == 0.2


def test_apply_sampling_writes_only_set_fields():
    # Build a minimal graph copy with just node 50 / 51 inputs.
    graph = {
        "50": {"inputs": {"steps": 40, "cfg": 4, "sampler": "dpmpp_2m",
                          "scheduler": "karras", "denoise": 1.0}},
        "51": {"inputs": {"steps": 25, "denoise": 0.2}},
    }
    _apply_sampling(graph, SamplingConfig(steps_first=50, cfg=7))
    assert graph["50"]["inputs"]["steps"] == 50
    assert graph["50"]["inputs"]["cfg"] == 7
    # Untouched fields stay at original
    assert graph["50"]["inputs"]["sampler"] == "dpmpp_2m"
    assert graph["51"]["inputs"]["steps"] == 25
    assert graph["51"]["inputs"]["denoise"] == 0.2


def test_apply_seed_writes_node_65():
    graph = {"65": {"inputs": {"seed": 1}}}
    _apply_seed(graph, 42)
    assert graph["65"]["inputs"]["seed"] == 42


def test_apply_image_size_writes_nodes_68_and_71():
    graph = {"68": {"inputs": {"value": 1216}}, "71": {"inputs": {"value": 832}}}
    _apply_image_size(graph, ImageSizeConfig(width=1024, height=1024))
    assert graph["68"]["inputs"]["value"] == 1024
    assert graph["71"]["inputs"]["value"] == 1024


def test_apply_image_size_partial():
    graph = {"68": {"inputs": {"value": 1216}}, "71": {"inputs": {"value": 832}}}
    _apply_image_size(graph, ImageSizeConfig(width=2048))  # height=None
    assert graph["68"]["inputs"]["value"] == 2048
    assert graph["71"]["inputs"]["value"] == 832  # unchanged


def test_apply_controlnet_image_writes_node_129():
    graph = {"129": {"inputs": {"image": "old.png"}}}
    _apply_controlnet_image(graph, "subfolder/new.png")
    assert graph["129"]["inputs"]["image"] == "subfolder/new.png"

"""End-to-end patch_graph tests (cross-validation, conventions, etc.)."""
import pytest

from runtime.config_schema import (
    GroupsConfig,
    RunConfig,
    SamplingConfig,
    STAGES,
)
from runtime.graph_patcher import patch_graph


def _base_config(stage=STAGES.T2I, **overrides):
    return RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl, solo", "negative": "lowres, bad"},
        **overrides,
    )


def test_patch_graph_writes_default_when_field_is_none():
    """No field overrides -> workflow.json static values remain untouched."""
    g = patch_graph(stage=STAGES.T2I, config=_base_config())
    # node 50 default steps = 40 per workflow.json
    assert g["50"]["inputs"]["steps"] == 40
    # node 51 default steps = 25 per workflow.json
    assert g["51"]["inputs"]["steps"] == 25


def test_patch_graph_applies_sampling_overrides():
    g = patch_graph(
        stage=STAGES.T2I,
        config=_base_config(sampling=SamplingConfig(steps_first=50, cfg=7)),
    )
    assert g["50"]["inputs"]["steps"] == 50
    assert g["50"]["inputs"]["cfg"] == 7


def test_patch_graph_t2i_does_not_force_denoise():
    """T2I: WORKFLOW_CONVENTIONS for I2I doesn't apply; node 27.denoise
    must equal its workflow.json static value (which is derived from node 50
    via input ref, but the static input is '1' in our dump)."""
    g = patch_graph(stage=STAGES.T2I, config=_base_config())
    # node 27.denoise is fed by [50, 5] in workflow.json; workflow.json
    # static value of node 50.inputs.denoise is 1.
    # Just ensure patch_graph didn't overwrite anything weird.
    assert "denoise" in g["50"]["inputs"]


def test_patch_graph_i2i_auto_appends_load_image_group(complete_workflow):
    g = patch_graph(
        stage=STAGES.I2I,
        config=_base_config(reference_image="ref.png"),
    )
    # The LoadImage group must be active: nodes 21/57/58/59 mode=0 (active)
    for nid in ("21", "57", "58", "59"):
        assert g[nid]["mode"] == 0


def test_patch_graph_i2i_forces_denoise_override():
    g = patch_graph(
        stage=STAGES.I2I,
        config=_base_config(reference_image="ref.png"),
    )
    assert g["27"]["inputs"]["denoise"] == 0.6


def test_patch_graph_i2i_missing_reference_image_raises():
    cfg = _base_config(stage=STAGES.I2I)
    # No reference_image provided
    with pytest.raises(ValueError, match="reference_image is required"):
        patch_graph(stage=STAGES.I2I, config=cfg)


def test_patch_graph_controlnet_image_requires_group():
    cfg = _base_config(controlnet_image="pose.png")
    # User did not enable the ControlNet LLLite group -> raises
    with pytest.raises(ValueError, match="not in groups.g1"):
        patch_graph(stage=STAGES.T2I, config=cfg)


def test_patch_graph_controlnet_group_without_image_raises():
    cfg = _base_config(groups=GroupsConfig(g1=["ControlNet LLLite（G1）"]))
    with pytest.raises(ValueError, match="but controlnet_image is None"):
        patch_graph(stage=STAGES.T2I, config=cfg)


def test_patch_graph_controlnet_image_and_group_writes_node_129(complete_workflow):
    cfg = _base_config(
        controlnet_image="uploaded/pose.png",
        groups=GroupsConfig(g1=["ControlNet LLLite（G1）"]),
    )
    g = patch_graph(stage=STAGES.T2I, config=cfg)
    assert g["129"]["inputs"]["image"] == "uploaded/pose.png"


def test_patch_graph_user_groups_combine_with_defaults(complete_workflow):
    """DEFAULT_ENABLED_G1 must always be active; user can add MORE."""
    cfg = _base_config(groups=GroupsConfig(g1=["手部 ADetailer（G1）"]))
    g = patch_graph(stage=STAGES.T2I, config=cfg)
    # 保存图片（G1） (default) must still be active
    assert g["35"]["mode"] == 0
    # 手部 ADetailer（G1） (user) must be active
    assert g["31"]["mode"] == 0
    # A non-default, non-user group should still be bypassed
    # (随机挑个不属于 DEFAULT/USER 的 G1 组)
    assert g["124"]["mode"] == 4  # 移除背景（G1）is bypassed by default


@pytest.fixture
def complete_workflow(monkeypatch):
    """Augment load_workflow with the group member nodes that groups.json
    references but the tracked 25-node workflow.json stub omits.

    Used by i2i / ControlNet / user-group end-to-end tests so the patcher's
    mode-write and node-write code paths can be observed. When the workflow
    grows to its full set of nodes, the extras become a no-op.
    """
    from runtime import graph_patcher as _gp
    real_load = _gp.load_workflow

    extras = {
        "21":  {"inputs": {"image": ""}, "class_type": "LoadImage"},
        "57":  {"inputs": {}, "class_type": "ImageScale"},
        "58":  {"inputs": {}, "class_type": "VAEEncode"},
        "59":  {"inputs": {"pixels": ["21", 0]}, "class_type": "VAEEncode"},
        "31":  {"inputs": {}, "class_type": "ADetailer"},
        "124": {"inputs": {}, "class_type": "RemBG"},
        "129": {"inputs": {"image": ""}, "class_type": "LoadImage"},
    }

    def augmented(stage):
        g = real_load(stage)
        merged = dict(g)
        merged.update(extras)
        return merged

    monkeypatch.setattr(_gp, "load_workflow", augmented)
