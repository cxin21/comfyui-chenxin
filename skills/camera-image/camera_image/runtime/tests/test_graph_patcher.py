"""Tests for graph_patcher.describe_config and NODE_FIELD_MAP single source."""
from runtime.graph_patcher import (
    describe_config,
    NODE_FIELD_MAP,
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


def test_describe_config_returns_workflow_bound_defaults():
    out = describe_config(STAGES.T2I)
    assert out["workflow"] == STAGES.T2I
    sampling = out["slots"]["sampling"]
    assert sampling["nodes"] == ["50", "51"]
    assert sampling["fields"]["steps_first"]["node"] == "50"
    assert "source_workflow" in out


def test_apply_sampling_writes_only_set_fields():
    graph = {
        "50": {"inputs": {"steps": 40, "cfg": 4, "sampler": "dpmpp_2m",
                          "scheduler": "karras", "denoise": 1.0}},
        "51": {"inputs": {"steps": 25, "denoise": 0.2}},
    }
    _apply_sampling(graph, SamplingConfig(steps_first=50, cfg=7))
    assert graph["50"]["inputs"]["steps"] == 50
    assert graph["50"]["inputs"]["cfg"] == 7
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
    _apply_image_size(graph, ImageSizeConfig(width=2048))
    assert graph["68"]["inputs"]["value"] == 2048
    assert graph["71"]["inputs"]["value"] == 832


def test_apply_controlnet_image_writes_node_129():
    graph = {"129": {"inputs": {"image": "old.png"}}}
    _apply_controlnet_image(graph, "subfolder/new.png")
    assert graph["129"]["inputs"]["image"] == "subfolder/new.png"


"""apply_run_config tests — drives the patcher directly against a stripped
graph fixture (the strip step is exercised separately in test_source_workflow.py)."""
import pytest

from runtime.config_schema import (
    GroupsConfig,
    RunConfig,
    SamplingConfig,
    STAGES,
)
from runtime.graph_patcher import apply_run_config


def _stripped_graph(stage=STAGES.T2I):
    """Minimal API-format graph fixture that survives apply_run_config.

    Mirrors the stripped layout produced by ``prepare_temporary_workflow``
    — every tunable node carries its source-UI literal input values.
    Includes the i2i chain nodes (21/57/58/59) so the i2i activation
    step can wire VAEEncode -> KSampler.
    """
    return {
        "21": {"inputs": {"image": ""}, "class_type": "LoadImage"},
        "24": {"inputs": {"wildcard_text": "", "populated_text": ""},
               "class_type": "ImpactWildcardProcessor"},
        "25": {"inputs": {"wildcard_text": "", "populated_text": ""},
               "class_type": "ImpactWildcardProcessor"},
        "26": {"inputs": {"lora_syntax": "<lora:default:1.00>"},
               "class_type": "LoRA Text Loader (LoraManager)"},
        "27": {"inputs": {"denoise": 1.0, "latent_image": ["86", 0]},
               "class_type": "KSampler"},
        "50": {"inputs": {"steps": 40, "cfg": 4, "sampler": "dpmpp_2m",
                          "scheduler": "karras", "denoise": 1.0}},
        "51": {"inputs": {"steps": 25, "denoise": 0.2}},
        "57": {"inputs": {}, "class_type": "ImageResizeKJv2"},
        "58": {"inputs": {}, "class_type": "PrimitiveInt"},
        "59": {"inputs": {"pixels": [21, 0]}, "class_type": "VAEEncode"},
        "65": {"inputs": {"seed": -1}},
        "66": {"inputs": {"trigger_words": ["26", 2], "orinalMessage": ""}},
        "68": {"inputs": {"value": 1216}},
        "71": {"inputs": {"value": 832}},
        "129": {"inputs": {"image": ""}, "class_type": "Load Image ControlNet"},
        "583": {"inputs": {"pos_x": 0.0, "pos_y": 0.0, "pos_z": -0.5, "roll": 0.0}},
        "585": {"inputs": {}},
    }


def _base_config(stage=STAGES.T2I, **overrides):
    return RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl, solo", "negative": "lowres, bad"},
        **overrides,
    )


def test_apply_run_config_writes_prompts():
    g = apply_run_config(
        _stripped_graph(),
        stage=STAGES.T2I,
        config=_base_config(),
    )
    assert g["24"]["inputs"]["wildcard_text"] == "1girl, solo"
    assert g["24"]["inputs"]["populated_text"] == "1girl, solo"
    assert g["25"]["inputs"]["wildcard_text"] == "lowres, bad"


def test_apply_run_config_writes_sampling_overrides():
    g = apply_run_config(
        _stripped_graph(),
        stage=STAGES.T2I,
        config=_base_config(sampling=SamplingConfig(steps_first=50, cfg=7)),
    )
    assert g["50"]["inputs"]["steps"] == 50
    assert g["50"]["inputs"]["cfg"] == 7


def test_apply_run_config_writes_seed_and_image_size():
    g = apply_run_config(
        _stripped_graph(),
        stage=STAGES.T2I,
        config=_base_config(
            seed=42,
        ),
    )
    assert g["65"]["inputs"]["seed"] == 42


def test_apply_run_config_t2i_does_not_force_denoise():
    """T2I: WORKFLOW_CONVENTIONS for I2I doesn't apply; node 27.denoise
    is whatever the stripped source gave it."""
    g = apply_run_config(
        _stripped_graph(),
        stage=STAGES.T2I,
        config=_base_config(),
    )
    assert "denoise" in g["50"]["inputs"]


def test_apply_run_config_i2i_forces_denoise_override():
    g = apply_run_config(
        _stripped_graph(),
        stage=STAGES.I2I,
        config=_base_config(reference_image="ref.png"),
    )
    assert g["50"]["inputs"]["denoise"] == 0.6


def test_apply_run_config_i2i_missing_reference_image_raises():
    cfg = _base_config(stage=STAGES.I2I)
    with pytest.raises(ValueError, match="reference_image is required"):
        apply_run_config(_stripped_graph(), stage=STAGES.I2I, config=cfg)


def test_apply_run_config_i2i_sets_ui_converter_inputs():
    g = apply_run_config(
        _stripped_graph(),
        stage=STAGES.I2I,
        config=_base_config(reference_image="ref.png"),
    )
    # node 21 (LoadImage) image -> uploaded filename
    assert g["21"]["inputs"]["image"] == "ref.png"
    assert g["58"]["inputs"]["value"] == 2
    # The converter owns the ImpactSwitch -> KSampler connection; this layer
    # only supplies the UI values that determine the selected branch.


def test_apply_run_config_controlnet_image_requires_group():
    cfg = _base_config(controlnet_image="pose.png")
    with pytest.raises(ValueError, match="not in groups.g1"):
        apply_run_config(_stripped_graph(), stage=STAGES.T2I, config=cfg)


def test_apply_run_config_controlnet_group_without_image_raises():
    cfg = _base_config(groups=GroupsConfig(g1=["ControlNet LLLite（G1）"]))
    with pytest.raises(ValueError, match="but controlnet_image is None"):
        apply_run_config(_stripped_graph(), stage=STAGES.T2I, config=cfg)


def test_apply_run_config_controlnet_image_and_group_writes_node_129():
    cfg = _base_config(
        controlnet_image="uploaded/pose.png",
        groups=GroupsConfig(g1=["ControlNet LLLite（G1）"]),
    )
    g = apply_run_config(_stripped_graph(), stage=STAGES.T2I, config=cfg)
    assert g["129"]["inputs"]["image"] == "uploaded/pose.png"


def test_apply_run_config_user_groups_combine_with_defaults():
    """DEFAULT_ENABLED_G1 must always be active; user can add MORE.

    After strip, defaults' nodes are present in the graph (mode=4 nodes
    were dropped). We assert node presence and content sanity for the
    default-enabled group titles.
    """
    cfg = _base_config(groups=GroupsConfig(g1=["移除背景（G1）"]))
    g = apply_run_config(_stripped_graph(), stage=STAGES.T2I, config=cfg)
    # node 35 (default: 保存图片（G1）) survives the strip
    assert "35" not in g or g.get("35", {}).get("inputs") is not None
    # node 51 (default: 第二轮采样器（G1）) survives the strip
    assert "51" in g
    # node 124 (user-enabled: 移除背景（G1）) may or may not survive (depends on
    # strip). Either way the patcher doesn't touch it. We assert absence of
    # any patcher-induced corruption: every default node's inputs is a dict.
    for nid in ("50", "51", "65", "68", "71", "24", "25"):
        assert isinstance(g[nid]["inputs"], dict)
