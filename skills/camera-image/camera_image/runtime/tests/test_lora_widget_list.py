"""TDD tests for _set_lora LoRA list widget (widgets_values[2]).

The LoraManager node (id 26) has three widgets_values slots:
- [0] version dict (e.g. {"version": 1, "textWidgetName": "text"})
- [1] the LoRA stack text ("<lora:...:1.00>...")
- [2] the LoRA object list (each entry is a dict with name/strength/active/...)

ComfyUI's strip step reads widgets_values[2] (the LoRA list) to populate
the API graph's node 26 inputs. Previously the patcher only updated
widgets_values[1] (the text), so the strip fell back to the source's
literal default 3-LoRA list instead of the custom selection.

These tests verify the patcher writes BOTH widgets_values[1] AND
widgets_values[2] when patching a UI-format graph.
"""
from __future__ import annotations

import pytest

from runtime.config_schema import (
    GroupsConfig,
    RunConfig,
    STAGES,
)
from runtime.graph_patcher import apply_run_config


def _ui_graph_with_lora_manager():
    """UI-format graph carrying the 3 default LoRA objects in node 26."""
    return {
        "nodes": [
            {
                "id": 24,
                "type": "ImpactWildcardProcessor",
                "inputs": [],
                "widgets_values": ["pos", "pos"],
            },
            {
                "id": 25,
                "type": "ImpactWildcardProcessor",
                "inputs": [],
                "widgets_values": ["neg", "neg"],
            },
            # Source's literal default 3-LoRA list. Strip reads this if
            # the patcher doesn't overwrite it.
            {
                "id": 26,
                "type": "Lora Loader (LoraManager)",
                "inputs": [],
                "widgets_values": [
                    {"version": 1, "textWidgetName": "text"},
                    "<lora:anima-base-1-masterpiece-v51:1.00>"
                    "<lora:add_detail:1.00>"
                    "<lora:gpt-image-2_anima-base1_v1-1:1.00>",
                    [
                        {
                            "name": "anima-base-1-masterpiece-v51",
                            "strength": 1,
                            "active": True,
                            "expanded": False,
                            "clipStrength": 1,
                            "selected": False,
                            "locked": False,
                        },
                        {
                            "name": "gpt-image-2_anima-base1_v1-1",
                            "strength": 1,
                            "active": True,
                            "expanded": False,
                            "clipStrength": 1,
                            "selected": False,
                            "locked": False,
                        },
                        {
                            "name": "add_detail",
                            "strength": 1,
                            "active": True,
                            "expanded": False,
                            "clipStrength": 1,
                            "selected": False,
                            "locked": False,
                        },
                    ],
                ],
            },
            {
                "id": 66,
                "type": "TriggerWord Toggle (LoraManager)",
                "inputs": [],
                "widgets_values": [True, True, False, [], ""],
            },
            {
                "id": 50,
                "type": "KSampler",
                "inputs": [],
                "widgets_values": [-1, "fixed", 40, 4, "dpmpp_2m", "karras", 1.0],
            },
            {
                "id": 51,
                "type": "KSampler",
                "inputs": [],
                "widgets_values": [-1, "fixed", 25, 4, "dpmpp_2m", "karras", 0.2],
            },
            {
                "id": 65,
                "type": "Seed (rgthree)",
                "inputs": [],
                "widgets_values": [-1],
            },
            {
                "id": 68,
                "type": "easy int",
                "inputs": [],
                "widgets_values": [1216],
            },
            {
                "id": 71,
                "type": "easy int",
                "inputs": [],
                "widgets_values": [832],
            },
            {
                "id": 583,
                "type": "CameraAngleNode",
                "inputs": [],
                "widgets_values": [0, 0, 0, 0],
            },
            {
                "id": 585,
                "type": "CameraExtraConfigNode",
                "inputs": [],
                "widgets_values": ["none"],
            },
        ],
        "groups": [],
        "links": [],
    }


def _node(workflow, node_id):
    return next(n for n in workflow["nodes"] if n["id"] == node_id)


def _find_lora(graph, name):
    """Return the LoRA object in node 26's widgets_values[2] matching `name`,
    or None. Searches the *post-patch* list."""
    widgets = _node(graph, 26)["widgets_values"]
    assert len(widgets) >= 3, (
        f"node 26 widgets_values should have >= 3 slots (version, text, list), "
        f"got {len(widgets)}"
    )
    lora_list = widgets[2]
    assert isinstance(lora_list, list), (
        f"node 26 widgets_values[2] should be a list of LoRA objects, "
        f"got {type(lora_list).__name__}"
    )
    for lora in lora_list:
        if lora["name"] == name:
            return lora
    return None


def test_apply_run_config_default_lora_does_not_change_list_widget():
    """When the user does not pass a custom LoRA selection, the patcher
    builds the default 3-LoRA plan and the widgets_values[2] list must
    contain the 3 default LoRAs (not whatever the source happened to have).

    Acting on the source's literal list is the original bug — the default
    plan must be written explicitly so the strip lift reflects the patcher's
    intent.
    """
    g = _ui_graph_with_lora_manager()
    cfg = RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl", "negative": "lowres"},
    )
    apply_run_config(g, stage=STAGES.T2I, config=cfg)
    list_widget = _node(g, 26)["widgets_values"][2]
    names = [lora["name"] for lora in list_widget]
    # Order matches `default_lora_plan()` in lora_resolver.py — the test
    # asserts the patcher writes the resolver's plan, not whatever the
    # source happened to carry.
    assert names == [
        "anima-base-1-masterpiece-v51",
        "add_detail",
        "gpt-image-2_anima-base1_v1-1",
    ]


def test_apply_run_config_custom_lora_writes_widgets_values_2():
    """With a custom LoRA selection, widgets_values[2] must contain the
    custom LoRA objects (with all required keys) — not the source's
    default 3-LoRA list.
    """
    g = _ui_graph_with_lora_manager()
    # Mock MCP resolver returning just our two LoRAs.
    fake_inventory = {
        "loras": [
            "Anima\\GUOMAN_v2.safetensors",
            "Anima\\AnimaNEWNSS8.safetensors",
        ]
    }
    cfg = RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl", "negative": "lowres"},
        lora={
            "selections": ["AnimaNEWNSS8", "GUOMAN_v2"],
        },
    )
    apply_run_config(
        g,
        stage=STAGES.T2I,
        config=cfg,
        mcp_list_loras=lambda: fake_inventory,
    )
    list_widget = _node(g, 26)["widgets_values"][2]
    names = [lora["name"] for lora in list_widget]
    assert names == ["AnimaNEWNSS8", "GUOMAN_v2"], (
        f"Expected widgets_values[2] to be the custom 2-LoRA list, got {names}"
    )


def test_apply_run_config_custom_lora_widget_has_required_keys():
    """Each LoRA object in widgets_values[2] must carry the keys LoraManager
    expects: name, strength, active, expanded, clipStrength, selected, locked.
    Missing keys would cause the strip to fall back to the source literal.
    """
    g = _ui_graph_with_lora_manager()
    fake_inventory = {
        "loras": ["Anima\\GUOMAN_v2.safetensors"]
    }
    cfg = RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl", "negative": "lowres"},
        lora={"selections": ["GUOMAN_v2"]},
    )
    apply_run_config(
        g, stage=STAGES.T2I, config=cfg,
        mcp_list_loras=lambda: fake_inventory,
    )
    lora = _find_lora(g, "GUOMAN_v2")
    assert lora is not None, "GUOMAN_v2 should appear in widgets_values[2]"
    for key in ("name", "strength", "active", "expanded",
                "clipStrength", "selected", "locked"):
        assert key in lora, f"LoRA object missing required key {key!r}: {lora}"


def test_apply_run_config_custom_lora_widget_strength_defaults():
    """When the selection has no explicit strength, widgets_values[2] entries
    should default to strength=1, clipStrength=1, active=True.
    """
    g = _ui_graph_with_lora_manager()
    fake_inventory = {
        "loras": ["Anima\\GUOMAN_v2.safetensors"]
    }
    cfg = RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl", "negative": "lowres"},
        lora={"selections": ["GUOMAN_v2"]},
    )
    apply_run_config(
        g, stage=STAGES.T2I, config=cfg,
        mcp_list_loras=lambda: fake_inventory,
    )
    lora = _find_lora(g, "GUOMAN_v2")
    assert lora["strength"] == 1.0
    assert lora["clipStrength"] == 1.0
    assert lora["active"] is True
    assert lora["expanded"] is False
    assert lora["selected"] is False
    assert lora["locked"] is False


def test_apply_run_config_lora_text_widget_still_updated():
    """Regression guard: the text widget (widgets_values[1]) must still be
    updated alongside the list widget (widgets_values[2])."""
    g = _ui_graph_with_lora_manager()
    fake_inventory = {
        "loras": ["Anima\\GUOMAN_v2.safetensors"]
    }
    cfg = RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl", "negative": "lowres"},
        lora={"selections": ["GUOMAN_v2"]},
    )
    apply_run_config(
        g, stage=STAGES.T2I, config=cfg,
        mcp_list_loras=lambda: fake_inventory,
    )
    widgets = _node(g, 26)["widgets_values"]
    assert widgets[1] == "<lora:GUOMAN_v2:1.00>"
