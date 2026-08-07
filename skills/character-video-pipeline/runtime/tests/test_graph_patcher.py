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
    # node 65 default seed = 665005389889224
    assert _node_static_default(graph, "65", "seed") == 665005389889224


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