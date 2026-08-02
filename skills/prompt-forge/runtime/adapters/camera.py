"""Strict Stage 1 patches for the verified camera API graph."""

from __future__ import annotations

import copy

from ..contracts import canonical_json
from ..execution import ExecutionError


_SLOTS = frozenset(("positive_prompt", "negative_prompt"))
_INPUTS = ("wildcard_text", "populated_text")
_NODE_CLASS = "ImpactWildcardProcessor"
_REMOVED = "__PROMPT_FORGE_ALLOWLISTED_VALUE__"


def _node_for_slot(graph: dict, slot_name: str, node_id: object) -> dict:
    if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id < 0:
        raise ExecutionError(f"slot '{slot_name}' node id must be a non-negative integer")
    node = graph.get(str(node_id))
    if not isinstance(node, dict):
        raise ExecutionError(f"slot '{slot_name}' references a missing API node")
    if node.get("class_type") != _NODE_CLASS:
        raise ExecutionError(f"slot '{slot_name}' has unexpected class_type")
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        raise ExecutionError(f"slot '{slot_name}' requires an inputs object")
    for input_name in _INPUTS:
        if input_name not in inputs:
            raise ExecutionError(f"slot '{slot_name}' is missing input '{input_name}'")
        if not isinstance(inputs[input_name], str):
            raise ExecutionError(f"slot '{slot_name}' input '{input_name}' must be a string")
    return node


def _without_allowlisted_values(graph: dict, slots: dict[str, int]) -> dict:
    normalized = copy.deepcopy(graph)
    for slot_name in _SLOTS:
        node = normalized[str(slots[slot_name])]
        for input_name in _INPUTS:
            node["inputs"][input_name] = _REMOVED
    return normalized


def patch_character_base(graph: dict, prompt_build: dict, slots: dict[str, int]) -> dict:
    """Deep-copy and patch exactly four prompt inputs in a camera API graph."""
    if not isinstance(graph, dict):
        raise ExecutionError("API graph must be an object")
    if not isinstance(prompt_build, dict):
        raise ExecutionError("PromptBuild must be an object")
    if not isinstance(slots, dict):
        raise ExecutionError("resolved slots must be an object")
    missing = sorted(_SLOTS.difference(slots))
    if missing:
        raise ExecutionError("resolved slots are missing: " + ", ".join(missing))
    unexpected = sorted(set(slots).difference(_SLOTS))
    if unexpected:
        raise ExecutionError("resolved slots contain unexpected entries: " + ", ".join(unexpected))

    prompt = prompt_build.get("prompt")
    negative_prompt = prompt_build.get("negative_prompt")
    if not isinstance(prompt, str) or not prompt:
        raise ExecutionError("PromptBuild prompt must be a non-empty string")
    if not isinstance(negative_prompt, str) or not negative_prompt:
        raise ExecutionError("PromptBuild negative_prompt must be a non-empty string")

    _node_for_slot(graph, "positive_prompt", slots["positive_prompt"])
    _node_for_slot(graph, "negative_prompt", slots["negative_prompt"])
    patched = copy.deepcopy(graph)
    positive = _node_for_slot(patched, "positive_prompt", slots["positive_prompt"])
    negative = _node_for_slot(patched, "negative_prompt", slots["negative_prompt"])
    for input_name in _INPUTS:
        positive["inputs"][input_name] = prompt
        negative["inputs"][input_name] = negative_prompt

    try:
        source_identity = canonical_json(_without_allowlisted_values(graph, slots))
        patched_identity = canonical_json(_without_allowlisted_values(patched, slots))
    except (KeyError, TypeError, ValueError) as exc:
        raise ExecutionError(f"API graph must be canonical JSON: {exc}") from exc
    if source_identity != patched_identity:
        raise ExecutionError("camera patch changed data outside the allowlist")
    return patched
