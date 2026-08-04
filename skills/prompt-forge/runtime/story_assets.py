"""Fail-closed contracts for story evidence and visual assets."""

import copy

from .contracts import ContractError, SHA256_HEX_RE, content_hash


_ASSET_TYPES = {"environment", "character", "prop"}
_EVIDENCE_TIER_KEYS = {
    "explicit_evidence",
    "reasonable_inference",
    "prohibited_expansion",
}


def _require_object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    return value


def _require_non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty string")
    return value


def _require_sha256(value: object, label: str) -> str:
    value = _require_non_empty_string(value, label)
    if not SHA256_HEX_RE.fullmatch(value):
        raise ContractError(f"{label} must be a lowercase SHA-256 hash")
    return value


def _require_schema_version(value: dict, label: str) -> None:
    if value.get("schema_version") != "1.0":
        raise ContractError(f"{label} schema_version must be '1.0'")


def _require_non_empty_list(value: object, label: str) -> list:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{label} must be a non-empty list")
    return value


def _require_string_list(value: object, label: str) -> list[str]:
    values = _require_non_empty_list(value, label)
    for item in values:
        _require_non_empty_string(item, label)
    return values


def _require_visual_fingerprint(value: object) -> None:
    if not isinstance(value, (list, dict)) or len(value) != 6:
        raise ContractError("visual_fingerprint must contain exactly six parts")
    parts = value.values() if isinstance(value, dict) else value
    for part in parts:
        _require_non_empty_string(part, "visual_fingerprint part")


def _tier_references(entries: list, label: str) -> set[str]:
    references: set[str] = set()
    for entry in entries:
        if isinstance(entry, str):
            references.add(_require_non_empty_string(entry, label))
            continue
        if not isinstance(entry, dict) or set(entry) != {"field", "value"}:
            raise ContractError(
                f"{label} entries must be strings or {{'field', 'value'}} objects"
            )
        field = _require_non_empty_string(entry["field"], f"{label}.field")
        fact = _require_non_empty_string(entry["value"], f"{label}.value")
        references.update({field, fact, f"{field}:{fact}"})
    return references


def _provenance_and_facts(value: object) -> tuple[dict, list[str]]:
    value = _require_object(value, "provenance")
    if "provenance" in value:
        provenance = _require_object(value["provenance"], "provenance")
        return provenance, _downstream_facts(value)
    downstream_facts = value.get("downstream_facts", [])
    if not isinstance(downstream_facts, list):
        raise ContractError("provenance downstream_facts must be a list")
    return value, [_require_non_empty_string(fact, "downstream fact") for fact in downstream_facts]


def _downstream_facts(card: dict) -> list[str]:
    fields = {
        "character": ("identity_lock", "face_lock"),
        "environment": ("environment_anchors",),
        "prop": ("scale", "function"),
    }
    facts: list[str] = []
    for field in fields.get(card.get("asset_type"), ()):
        value = card.get(field)
        if isinstance(value, list):
            facts.extend(value)
        elif isinstance(value, str):
            facts.append(value)
    return facts


def validate_provenance_tiers(value: dict) -> None:
    """Ensure claimed facts are evidence-backed and never prohibited."""
    provenance, facts = _provenance_and_facts(value)
    if not _EVIDENCE_TIER_KEYS.issubset(provenance):
        raise ContractError("provenance requires all evidence tiers")
    tier_references = {
        key: _tier_references(provenance[key], f"provenance.{key}")
        for key in _EVIDENCE_TIER_KEYS
        if isinstance(provenance[key], list)
    }
    if len(tier_references) != len(_EVIDENCE_TIER_KEYS):
        raise ContractError("provenance evidence tiers must be lists")

    prohibited = tier_references["prohibited_expansion"]
    explicit = tier_references["explicit_evidence"]
    if explicit & prohibited:
        raise ContractError("prohibited expansion cannot also be explicit evidence")

    allowed = explicit | tier_references["reasonable_inference"]
    for fact in facts:
        if fact in prohibited:
            raise ContractError("prohibited expansion cannot become a downstream fact")
        if fact not in allowed:
            raise ContractError("downstream facts must be referenced by evidence or inference")


def validate_story_breakdown(value: dict) -> dict:
    """Validate and deep-copy the story evidence boundary."""
    value = _require_object(value, "story breakdown")
    _require_schema_version(value, "story breakdown")
    for field in (
        "visual_system",
        "characters",
        "scenes",
        "story_logic",
        "uncertainty",
        "source_hash",
    ):
        if field not in value:
            raise ContractError(f"story breakdown requires '{field}'")
    _require_sha256(value["source_hash"], "story breakdown source_hash")
    return copy.deepcopy(value)


def validate_art_bible(value: dict) -> dict:
    """Validate and deep-copy the global visual-language contract."""
    value = _require_object(value, "art bible")
    for field in (
        "style",
        "medium",
        "visual_grammar",
        "palette",
        "materials",
        "lighting",
        "motifs",
        "world_taboos",
        "continuity_strategy",
        "style_prompt",
    ):
        if field not in value:
            raise ContractError(f"art bible requires '{field}'")
        field_value = value[field]
        if isinstance(field_value, str):
            _require_non_empty_string(field_value, f"art bible {field}")
        elif not isinstance(field_value, (list, dict)) or not field_value:
            raise ContractError(f"art bible {field} must be a non-empty string, list, or object")
    return copy.deepcopy(value)


def _validate_character_fields(value: dict) -> None:
    _require_string_list(value.get("identity_lock"), "character identity_lock")
    face_lock = _require_string_list(value.get("face_lock"), "character face_lock")
    for fact in face_lock:
        if len(fact.split()) < 2:
            raise ContractError("character face_lock must contain specific visual information")


def _validate_environment_fields(value: dict) -> None:
    anchors = value.get("environment_anchors")
    if not isinstance(anchors, list) or not 3 <= len(anchors) <= 5:
        raise ContractError("environment_anchors must be a list of 3-5 stable facts")
    for anchor in anchors:
        _require_non_empty_string(anchor, "environment anchor")


def _validate_prop_fields(value: dict) -> None:
    _require_non_empty_string(value.get("scale"), "prop scale")
    _require_non_empty_string(value.get("function"), "prop function")


def validate_asset_card(value: dict, expected_type: str | None = None) -> dict:
    """Validate and deep-copy an environment, character, or prop asset card."""
    value = _require_object(value, "asset card")
    _require_schema_version(value, "asset card")
    asset_type = value.get("asset_type")
    if asset_type not in _ASSET_TYPES:
        raise ContractError("asset_type must be environment, character, or prop")
    if expected_type is not None:
        if expected_type not in _ASSET_TYPES:
            raise ContractError("expected_type must be environment, character, or prop")
        if asset_type != expected_type:
            raise ContractError("asset_type does not match expected_type")
    _require_visual_fingerprint(value.get("visual_fingerprint"))
    _require_non_empty_string(value.get("asset_id"), "asset_id")
    _require_sha256(value.get("source_story_hash"), "source_story_hash")
    if asset_type == "character":
        _validate_character_fields(value)
    elif asset_type == "environment":
        _validate_environment_fields(value)
    else:
        _validate_prop_fields(value)
    validate_provenance_tiers(value)
    return copy.deepcopy(value)


def story_breakdown_hash(value: dict) -> str:
    return content_hash(validate_story_breakdown(value))


def art_bible_hash(value: dict) -> str:
    return content_hash(validate_art_bible(value))


def asset_card_hash(value: dict) -> str:
    return content_hash(validate_asset_card(value))
