"""Stable UI-workflow structure identities and fail-closed profile slots."""

from __future__ import annotations

from .contracts import canonical_json, content_hash


class ProfileError(ValueError):
    """Raised when a workflow cannot satisfy a declared profile exactly."""


_MATCH_FIELDS = frozenset(("id", "type", "title"))


def _require_workflow_nodes(workflow: object) -> list[dict]:
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise ProfileError("workflow requires a nodes list")

    nodes = workflow["nodes"]
    seen_ids: set[int] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ProfileError("workflow nodes must be objects")
        node_id = node.get("id")
        if not isinstance(node_id, int) or isinstance(node_id, bool):
            raise ProfileError("workflow nodes require integer ids")
        if node_id in seen_ids:
            raise ProfileError(f"workflow node id {node_id} is ambiguous")
        seen_ids.add(node_id)
    return nodes


def structure_fingerprint(workflow: dict) -> str:
    """Hash only graph identity, excluding mutable UI and widget state."""
    nodes = [
        {
            "id": node["id"],
            "type": node.get("type", ""),
            "title": node.get("title", ""),
            "inputs": [
                {
                    "name": item.get("name"),
                    "type": item.get("type"),
                    "link": item.get("link"),
                }
                for item in node.get("inputs", [])
            ],
            "outputs": [
                {
                    "name": item.get("name"),
                    "type": item.get("type"),
                    "links": item.get("links") or [],
                }
                for item in node.get("outputs", [])
            ],
        }
        for node in _require_workflow_nodes(workflow)
    ]
    groups = [
        {"id": group.get("id"), "title": group.get("title", "")}
        for group in workflow.get("groups", [])
    ]
    payload = {
        "nodes": sorted(nodes, key=lambda item: str(item["id"])),
        "groups": sorted(groups, key=lambda item: str(item["id"])),
        "links": sorted(workflow.get("links", []), key=canonical_json),
    }
    return content_hash(payload)


def _slot_constraints(slot_name: object, selector: object) -> dict:
    if not isinstance(slot_name, str) or not slot_name:
        raise ProfileError("profile slot names must be non-empty strings")
    if not isinstance(selector, dict):
        raise ProfileError(f"slot '{slot_name}' selector must be an object")
    unknown = sorted(set(selector) - _MATCH_FIELDS)
    if unknown:
        raise ProfileError(f"slot '{slot_name}' has unsupported constraints: {', '.join(unknown)}")
    constraints = {key: selector[key] for key in _MATCH_FIELDS if key in selector}
    if not constraints:
        raise ProfileError(f"slot '{slot_name}' requires at least one explicit node constraint")
    if "id" in constraints and (
        not isinstance(constraints["id"], int) or isinstance(constraints["id"], bool)
    ):
        raise ProfileError(f"slot '{slot_name}' id constraint must be an integer")
    for key in ("type", "title"):
        if key in constraints and (
            not isinstance(constraints[key], str) or not constraints[key]
        ):
            raise ProfileError(f"slot '{slot_name}' {key} constraint must be a non-empty string")
    return constraints


def resolve_slots(workflow: dict, profile: dict) -> dict[str, int]:
    """Resolve every profile slot to exactly one UI node or raise ProfileError."""
    nodes = _require_workflow_nodes(workflow)
    if not isinstance(profile, dict) or not isinstance(profile.get("slots"), dict):
        raise ProfileError("profile requires a slots object")

    resolved: dict[str, int] = {}
    for slot_name, selector in profile["slots"].items():
        constraints = _slot_constraints(slot_name, selector)
        matches = [
            node
            for node in nodes
            if all(node.get(field) == value for field, value in constraints.items())
        ]
        if len(matches) != 1:
            raise ProfileError(
                f"slot '{slot_name}' requires exactly one matching node (found {len(matches)})"
            )
        resolved[slot_name] = matches[0]["id"]
    return resolved
