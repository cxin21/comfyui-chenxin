"""Diagnostic: verify the LoRA list widget fix produces the correct API graph.

Simulates the strip process used by ComfyUI to lift UI-format widgets_values
into the API graph. The LoraManager strip reads widgets_values[2] (the LoRA
list) and populates the API graph's node 26 inputs with the custom LoRA
selection.

Before the fix: widgets_values[2] was left untouched, so the API graph
got the source workflow's default 3-LoRA list. The custom selections
(AnimaNEWNSS8, GUOMAN_v2) never reached the API graph.

After the fix: widgets_values[2] is rewritten with the custom LoRA objects,
and the strip lifts them into the API graph correctly.
"""
from __future__ import annotations

import json
import os
import sys

# Script lives at skills/camera-image/diagnose_lora_list_widget.py.
# `runtime` is a top-level package at skills/camera-image/camera_image/runtime.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "camera_image"))
sys.path.insert(0, os.path.join(HERE, "_mcp", "src"))

from runtime.config_schema import RunConfig, STAGES
from runtime.graph_patcher import apply_run_config


def _build_ui_graph():
    """UI-format graph fixture with source's default 3-LoRA list."""
    return {
        "nodes": [
            {"id": 24, "type": "ImpactWildcardProcessor", "inputs": [],
             "widgets_values": ["pos", "pos"]},
            {"id": 25, "type": "ImpactWildcardProcessor", "inputs": [],
             "widgets_values": ["neg", "neg"]},
            # Source's literal default 3-LoRA list.
            {"id": 26, "type": "Lora Loader (LoraManager)", "inputs": [],
             "widgets_values": [
                {"version": 1, "textWidgetName": "text"},
                "<lora:anima-base-1-masterpiece-v51:1.00>"
                "<lora:add_detail:1.00>"
                "<lora:gpt-image-2_anima-base1_v1-1:1.00>",
                [
                    {"name": "anima-base-1-masterpiece-v51",
                     "strength": 1, "active": True, "expanded": False,
                     "clipStrength": 1, "selected": False, "locked": False},
                    {"name": "gpt-image-2_anima-base1_v1-1",
                     "strength": 1, "active": True, "expanded": False,
                     "clipStrength": 1, "selected": False, "locked": False},
                    {"name": "add_detail",
                     "strength": 1, "active": True, "expanded": False,
                     "clipStrength": 1, "selected": False, "locked": False},
                ],
            ]},
            {"id": 66, "type": "TriggerWord Toggle (LoraManager)", "inputs": [],
             "widgets_values": [True, True, False, [], ""]},
            {"id": 50, "type": "KSampler", "inputs": [],
             "widgets_values": [-1, "fixed", 40, 4, "dpmpp_2m", "karras", 1.0]},
            {"id": 51, "type": "KSampler", "inputs": [],
             "widgets_values": [-1, "fixed", 25, 4, "dpmpp_2m", "karras", 0.2]},
            {"id": 65, "type": "Seed (rgthree)", "inputs": [],
             "widgets_values": [-1]},
            {"id": 68, "type": "easy int", "inputs": [],
             "widgets_values": [1216]},
            {"id": 71, "type": "easy int", "inputs": [],
             "widgets_values": [832]},
            {"id": 583, "type": "CameraAngleNode", "inputs": [],
             "widgets_values": [0, 0, 0, 0]},
            {"id": 585, "type": "CameraExtraConfigNode", "inputs": [],
             "widgets_values": ["none"]},
        ],
        "groups": [],
        "links": [],
    }


def _simulate_strip(ui_graph):
    """Simulate ComfyUI's strip_workflow() lifting widgets_values to API inputs.

    Real LoraManager strip reads widgets_values[2] and lifts the list into
    the API graph (the lora_manager code deserializes the list and uses
    it to populate the lora_stack output and consumed adapter inputs).

    For our diagnostic, we model the lift as: node 26's API inputs["text"]
    mirrors widgets_values[1], and the LoRA list is what _was_ carried in
    widgets_values[2]. The key check: the API graph's serialization of
    node 26's LoRA state contains the custom names, not the source's
    default list.
    """
    api_graph = {}
    for node in ui_graph["nodes"]:
        inputs = {}
        widgets = node.get("widgets_values", [])
        # Mirror widgets_values[0] and [1] into inputs (text-like fields).
        if len(widgets) >= 2:
            inputs["text"] = widgets[1]
        # Lift widgets_values[2] (LoRA list) — this is the load-bearing
        # lift for LoraManager.
        if len(widgets) >= 3 and isinstance(widgets[2], list):
            inputs["__lora_list"] = widgets[2]
        api_graph[str(node["id"])] = {
            "class_type": node["type"],
            "inputs": inputs,
        }
    return api_graph


def main():
    g = _build_ui_graph()
    cfg = RunConfig(
        evidence={"locked_facts": []},
        draft={"positive": "1girl", "negative": "lowres"},
        lora={"selections": ["AnimaNEWNSS8", "GUOMAN_v2"]},
    )
    fake_inventory = {
        "loras": [
            "Anima\\AnimaNEWNSS8.safetensors",
            "Anima\\GUOMAN_v2.safetensors",
        ]
    }
    apply_run_config(
        g, stage=STAGES.T2I, config=cfg,
        mcp_list_loras=lambda: fake_inventory,
    )

    # Inspect widgets_values[2] post-patch.
    node26 = next(n for n in g["nodes"] if n["id"] == 26)
    wv2 = node26["widgets_values"][2]
    wv2_names = [l["name"] for l in wv2]

    # Simulate the strip.
    api_graph = _simulate_strip(g)
    api_lora_list = api_graph["26"]["inputs"]["__lora_list"]
    api_lora_names = [l["name"] for l in api_lora_list]

    print("=== widgets_values[2] after patch ===")
    print(json.dumps(wv2, indent=2, ensure_ascii=False))
    print()
    print("=== API graph node 26 inputs.__lora_list (after simulated strip) ===")
    print(json.dumps(api_lora_list, indent=2, ensure_ascii=False))
    print()

    # Assertions.
    print("=== VERIFICATION ===")
    checks = []
    checks.append(("widgets_values[2] is custom 2-LoRA list",
                   wv2_names == ["AnimaNEWNSS8", "GUOMAN_v2"]))
    checks.append(("API graph has custom LoRA names",
                   sorted(api_lora_names) == ["AnimaNEWNSS8", "GUOMAN_v2"]))
    checks.append(("API graph does NOT carry source default 3-LoRA list",
                   "anima-base-1-masterpiece-v51" not in api_lora_names))
    checks.append(("API graph does NOT carry source default 2",
                   "gpt-image-2_anima-base1_v1-1" not in api_lora_names))
    checks.append(("API graph does NOT carry source default 3",
                   "add_detail" not in api_lora_names))
    checks.append(("API graph has exactly 2 LoRAs",
                   len(api_lora_list) == 2))

    for label, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {label}")

    all_passed = all(p for _, p in checks)
    print()
    if all_passed:
        print("DIAGNOSTIC: All checks passed. The LoRA list widget fix is verified.")
        return 0
    else:
        print("DIAGNOSTIC: One or more checks failed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
