from runtime.result_manifest import build_effective_camera_result


def test_effective_camera_result_contains_config_and_lora_snapshot():
    graph = {
        "24": {"class_type": "ImpactWildcardProcessor", "inputs": {"wildcard_text": "positive", "populated_text": "positive-rendered"}},
        "25": {"class_type": "ImpactWildcardProcessor", "inputs": {"wildcard_text": "negative", "populated_text": "negative-rendered"}},
        "26": {"class_type": "Lora Loader (LoraManager)", "inputs": {"text": "<lora:Anima\\hero:1.00>", "loras": {"__value__": [{"name": "Anima\\hero", "strength": 1.0}]} }},
        "66": {"class_type": "TriggerWord Toggle (LoraManager)", "inputs": {"toggle_trigger_words": "hero", "orinalMessage": "masterpiece", "trigger_words": ["26", 2]}},
        "583": {"class_type": "CameraAngleNode", "inputs": {"pos_x": 0.25, "pos_y": 0.5, "pos_z": -0.5, "roll": 0}},
        "585": {"class_type": "CameraExtraConfigNode", "inputs": {"lens_enabled": True, "lens_value": "85mm lens"}},
    }

    result = build_effective_camera_result(graph)

    assert result["config"]["prompts"] == {
        "positive": "positive-rendered",
        "negative": "negative-rendered",
    }
    assert result["lora"]["stack_text"] == "<lora:Anima\\hero:1.00>"
    assert result["lora"]["loader"]["loras"]["__value__"][0]["name"] == "Anima\\hero"
    assert result["lora"]["trigger_word_toggle"]["trigger_words"] == ["26", 2]
    assert result["config"]["camera_angle"]["pos_y"] == 0.5
    assert result["config_hash"]
