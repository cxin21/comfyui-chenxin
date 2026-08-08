"""TaskContext validation and deterministic content identity helpers."""

import copy
import hashlib
import json
import re


QUADRANTS = {
    "shared_known": ("goal", "background", "acceptance", "boundaries"),
    "user_known_agent_unknown": (
        "references",
        "aesthetic_preferences",
        "real_world_constraints",
    ),
    "agent_known_user_unknown": ("capabilities", "risks", "alternatives"),
    "shared_unknown": ("hypotheses", "experiments"),
}


SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Raised when a runtime boundary contract is invalid."""


def canonical_json(value: object) -> str:
    """Serialize JSON-compatible data into a stable, compact representation."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def validate_json_compatible(value: object, label: str = "value") -> None:
    """Raise ContractError when a contract value cannot be canonicalized as JSON."""
    try:
        canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{label} must be JSON-compatible") from exc


def content_hash(value: object) -> str:
    """Return the SHA-256 digest of a value's canonical JSON representation."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_task_context(value: dict) -> dict:
    """Validate and copy a v1 TaskContext without mutating its caller-owned data."""
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        raise ContractError("TaskContext schema_version must be '1.0'")
    for quadrant, fields in QUADRANTS.items():
        section = value.get(quadrant)
        if not isinstance(section, dict):
            raise ContractError(f"TaskContext requires object '{quadrant}'")
        for field in fields:
            if field not in section:
                raise ContractError(f"TaskContext {quadrant} requires '{field}'")
            if field != "goal" and not isinstance(section[field], list):
                raise ContractError(f"TaskContext {quadrant}.{field} must be a list")
    if not isinstance(value["shared_known"]["goal"], str) or not value[
        "shared_known"
    ]["goal"].strip():
        raise ContractError("TaskContext shared_known.goal must be a non-empty string")
    return copy.deepcopy(value)
