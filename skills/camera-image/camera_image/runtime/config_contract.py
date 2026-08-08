"""Declarative stage configuration contracts.

The workflow graph is an execution asset. This module exposes only declared
slots and compiles a local patch without treating graph internals as config.
"""

from __future__ import annotations

import copy


class ConfigContractError(ValueError):
    """Raised when a declared configuration contract cannot be trusted."""


_STAGES = frozenset({"character-base", "shot-image", "multiview", "video"})
_SLOT_KEYS = frozenset({"node_id", "input", "type", "class_type"})
_TYPES = frozenset({"text", "image", "boolean", "number", "integer", "string", "json"})
_KNOWN_TYPES = {
    "text": frozenset({"CLIPTextEncode", "ImpactWildcardProcessor", "CR Text", "ShowText|pysssss"}),
    "image": frozenset({"LoadImage", "LoadImageOutput"}),
}


def _node(graph: object, node_id: int, slot: str) -> dict:
    if not isinstance(graph, dict):
        raise ConfigContractError("API graph must be an object")
    value = graph.get(str(node_id))
    if not isinstance(value, dict) or not isinstance(value.get("inputs"), dict):
        raise ConfigContractError(f"slot '{slot}' references a node without inputs")
    return value


def validate_config_contract(contract: object) -> dict:
    if not isinstance(contract, dict) or set(contract) != {"schema_version", "stage", "slots", "forbidden_inputs"}:
        raise ConfigContractError("config contract has unexpected or missing fields")
    if contract["schema_version"] != "1.0" or contract["stage"] not in _STAGES:
        raise ConfigContractError("config contract identity is unsupported")
    slots = contract["slots"]
    if not isinstance(slots, dict) or not slots:
        raise ConfigContractError("config contract slots must be a non-empty object")
    for name, descriptor in slots.items():
        if not isinstance(name, str) or not name:
            raise ConfigContractError("config slot names must be non-empty strings")
        if not isinstance(descriptor, dict) or set(descriptor) not in ({"node_id", "input", "type"}, _SLOT_KEYS):
            raise ConfigContractError(f"config slot '{name}' is incomplete")
        if not isinstance(descriptor["node_id"], int) or isinstance(descriptor["node_id"], bool) or descriptor["node_id"] < 0:
            raise ConfigContractError(f"config slot '{name}' node_id is invalid")
        if not isinstance(descriptor["input"], str) or not descriptor["input"] or descriptor["type"] not in _TYPES:
            raise ConfigContractError(f"config slot '{name}' type is invalid")
        if "class_type" in descriptor and (not isinstance(descriptor["class_type"], str) or not descriptor["class_type"]):
            raise ConfigContractError(f"config slot '{name}' class_type is invalid")
    forbidden = contract["forbidden_inputs"]
    if not isinstance(forbidden, list) or not forbidden or any(not isinstance(value, str) or not value for value in forbidden):
        raise ConfigContractError("forbidden_inputs must be a non-empty string list")
    if len(set(forbidden)) != len(forbidden):
        raise ConfigContractError("forbidden_inputs contains duplicates")
    return copy.deepcopy(contract)


def _validate_node_for_slot(graph: object, name: str, descriptor: dict) -> dict:
    node = _node(graph, descriptor["node_id"], name)
    expected = descriptor.get("class_type")
    if expected is None and descriptor["type"] in _KNOWN_TYPES and node.get("class_type") not in _KNOWN_TYPES[descriptor["type"]]:
        raise ConfigContractError(f"slot '{name}' class_type is not trusted")
    if expected is not None and node.get("class_type") != expected:
        raise ConfigContractError(f"slot '{name}' class_type drifted")
    if descriptor["input"] not in node["inputs"]:
        raise ConfigContractError(f"slot '{name}' input is missing")
    return node


def read_config_surface(graph: object, contract: object) -> dict:
    checked = validate_config_contract(contract)
    return {
        name: copy.deepcopy(_validate_node_for_slot(graph, name, descriptor)["inputs"][descriptor["input"]])
        for name, descriptor in checked["slots"].items()
    }


def apply_config_patch(graph: object, contract: object, patch: object) -> dict:
    checked = validate_config_contract(contract)
    if not isinstance(patch, dict):
        raise ConfigContractError("config patch must be an object")
    unknown = sorted(set(patch) - set(checked["slots"]))
    if unknown:
        raise ConfigContractError("patch field is not declared: " + ", ".join(unknown))
    if set(patch).intersection(checked["forbidden_inputs"]):
        raise ConfigContractError("patch contains forbidden internal execution fields")
    result = copy.deepcopy(graph)
    for name, value in patch.items():
        descriptor = checked["slots"][name]
        if descriptor["input"] in checked["forbidden_inputs"]:
            raise ConfigContractError(f"slot '{name}' exposes a forbidden internal input")
        node = _validate_node_for_slot(result, name, descriptor)
        kind = descriptor["type"]
        if kind in {"text", "image", "string"} and not isinstance(value, str):
            raise ConfigContractError(f"slot '{name}' requires a string value")
        if kind == "boolean" and not isinstance(value, bool):
            raise ConfigContractError(f"slot '{name}' requires a boolean value")
        if kind == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ConfigContractError(f"slot '{name}' requires an integer value")
        if kind == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise ConfigContractError(f"slot '{name}' requires a numeric value")
        node["inputs"][descriptor["input"]] = copy.deepcopy(value)
    return result
