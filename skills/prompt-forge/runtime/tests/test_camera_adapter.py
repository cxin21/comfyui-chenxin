import copy
import json
from pathlib import Path

import pytest

from runtime.adapters.camera import patch_character_base
from runtime.execution import ExecutionError


FIXTURE = Path(__file__).parent / "fixtures" / "camera-api-minimal.json"


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
