"""LoRA compiler contract tests."""

from runtime.config_schema import RunConfig, STAGES
from runtime.graph_patcher import apply_run_config


def _ui_graph():
    return {
        "nodes": [
            {"id": 24, "type": "ImpactWildcardProcessor", "inputs": [], "widgets_values": ["pos", "pos"]},
            {"id": 25, "type": "ImpactWildcardProcessor", "inputs": [], "widgets_values": ["neg", "neg"]},
            {
                "id": 26,
                "type": "LoRA Text Loader (LoraManager)",
                "inputs": [],
                "widgets_values": ["<lora:default:1.00>"],
            },
            {"id": 50, "type": "KSampler", "inputs": [], "widgets_values": [-1, "fixed", 40, 4, "dpmpp_2m", "karras", 1.0]},
            {"id": 51, "type": "KSampler", "inputs": [], "widgets_values": [-1, "fixed", 25, 4, "dpmpp_2m", "karras", 0.2]},
            {"id": 65, "type": "Seed (rgthree)", "inputs": [], "widgets_values": [-1]},
            {"id": 68, "type": "easy int", "inputs": [], "widgets_values": [1216]},
            {"id": 71, "type": "easy int", "inputs": [], "widgets_values": [832]},
            {"id": 583, "type": "CameraAngleNode", "inputs": [], "widgets_values": [0, 0, 0, 0]},
            {"id": 585, "type": "CameraExtraConfigNode", "inputs": [], "widgets_values": ["none"]},
        ],
        "groups": [],
        "links": [],
    }


def _config(**overrides):
    return RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl", "negative": "lowres"},
        **overrides,
    )


def test_default_lora_is_written_to_converter_visible_input():
    graph = apply_run_config(_ui_graph(), stage=STAGES.T2I, config=_config())
    node = next(node for node in graph["nodes"] if node["id"] == 26)
    assert node["widgets_values"] == [
        "<lora:anima-base-1-masterpiece-v51:1.00>"
        "<lora:add_detail:1.00>"
        "<lora:gpt-image-2_anima-base1_v1-1:1.00>"
    ]


def test_custom_lora_is_written_as_syntax():
    inventory = {"loras": ["Anima\\GUOMAN_v2.safetensors"]}
    graph = apply_run_config(
        _ui_graph(),
        stage=STAGES.T2I,
        config=_config(lora={"selections": ["GUOMAN_v2"]}),
        mcp_list_loras=lambda: inventory,
    )
    node = next(node for node in graph["nodes"] if node["id"] == 26)
    assert node["widgets_values"] == ["<lora:GUOMAN_v2:1.00>"]
