"""Fail-closed contracts for story evidence and visual assets.

Asset-card schema ``1.0`` uses ``feature-value-v1`` structured facts for
visual fingerprints, face locks, and environment anchors. Their values use an
open vocabulary guarded by a generic denylist; evidence, not a closed cue list,
is authoritative. Legacy string facts are intentionally rejected: producers
must migrate them to ``{"feature": ..., "value": ...}`` rather than receiving
ambiguous best-effort interpretation.
"""

import copy

from .contracts import (
    ContractError,
    SHA256_HEX_RE,
    content_hash,
    validate_json_compatible,
)


_ASSET_TYPES = {"environment", "character", "prop"}
_EVIDENCE_TIER_KEYS = {
    "explicit_evidence",
    "reasonable_inference",
    "prohibited_expansion",
}
ASSET_CARD_SCHEMA_VERSION = "1.0"
STRUCTURED_FACT_SCHEMA_VERSION = "feature-value-v1"
STRUCTURED_FACT_MIGRATION = "legacy-string-facts-rejected"

STRUCTURED_FACT_VOCABULARY = "open-with-generic-denylist-v1"
_GENERIC_AESTHETIC_VALUES = {
    "beautiful",
    "pretty",
    "very pretty",
    "really pretty",
    "handsome",
    "attractive",
    "good-looking",
    "\u597d\u770b",
    "\u6f02\u4eae",
    "\u5f88\u6f02\u4eae",
    "\u975e\u5e38\u597d",
    "\u7f8e\u4e3d",
    "\u5e05",
    "\u5e05\u6c14",
}
_GENERIC_ENVIRONMENT_FEATURES = {
    "a", "thing", "object", "item", "place", "some place", "stuff", "something",
    "\u4e1c\u897f", "\u7269\u4ef6", "\u5730\u65b9", "\u67d0\u5904",
}
_GENERIC_ENVIRONMENT_VALUES = {
    "a", "thing", "thing-1", "object", "item", "place", "some place", "nice roof", "stuff", "something",
    "\u4e1c\u897f", "\u7269\u4ef6", "\u5730\u65b9", "\u67d0\u7269",
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


def _require_feature_value(value: object, label: str) -> tuple[str, str]:
    if not isinstance(value, dict) or set(value) != {"feature", "value"}:
        raise ContractError(
            f"{label} entries must be {{'feature', 'value'}} objects; "
            "legacy string facts are not supported"
        )
    return (
        _require_non_empty_string(value["feature"], f"{label}.feature"),
        _require_non_empty_string(value["value"], f"{label}.value"),
    )


def _normalized(value: str) -> str:
    return value.strip().casefold()


def _require_specific_face_value(feature: str, value: str) -> None:
    normalized_value = _normalized(value)
    if normalized_value in _GENERIC_AESTHETIC_VALUES:
        raise ContractError("character face_lock must contain specific visual information")


def _is_non_generic_environment_feature(value: str) -> bool:
    normalized = _normalized(value)
    if normalized in _GENERIC_ENVIRONMENT_FEATURES:
        return False
    if any("\u4e00" <= char <= "\u9fff" for char in normalized):
        return True
    return len(normalized) >= 2


def _require_stable_environment_anchor(feature: str, value: str) -> None:
    normalized_feature = _normalized(feature)
    normalized_value = _normalized(value)
    if (
        not _is_non_generic_environment_feature(normalized_feature)
        or normalized_value in _GENERIC_ENVIRONMENT_VALUES
    ):
        raise ContractError("environment_anchors must contain specific stable facts")


def _require_visual_fingerprint(value: object) -> None:
    if not isinstance(value, list) or len(value) != 6:
        raise ContractError("visual_fingerprint must contain exactly six parts")
    features: set[str] = set()
    for part in value:
        feature, _ = _require_feature_value(part, "visual_fingerprint")
        if feature in features:
            raise ContractError("visual_fingerprint features must be unique")
        features.add(feature)


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
    facts = [part["value"] for part in card["visual_fingerprint"]]
    if card["asset_type"] == "character":
        facts.extend(card["identity_lock"])
        facts.extend(fact["value"] for fact in card["face_lock"])
    elif card["asset_type"] == "environment":
        facts.extend(anchor["value"] for anchor in card["environment_anchors"])
    else:
        facts.extend((card["scale"], card["function"]))
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
    validate_json_compatible(value, "story breakdown")
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
    validate_json_compatible(value, "art bible")
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
    face_lock = _require_non_empty_list(value.get("face_lock"), "character face_lock")
    for fact in face_lock:
        feature, face_value = _require_feature_value(fact, "character face_lock")
        _require_specific_face_value(feature, face_value)


def _validate_environment_fields(value: dict) -> None:
    anchors = value.get("environment_anchors")
    if not isinstance(anchors, list) or not 3 <= len(anchors) <= 5:
        raise ContractError("environment_anchors must be a list of 3-5 stable facts")
    features: set[str] = set()
    values: set[str] = set()
    for anchor in anchors:
        feature, fact = _require_feature_value(anchor, "environment_anchors")
        if feature in features or fact in values:
            raise ContractError("environment_anchors must contain unique stable facts")
        _require_stable_environment_anchor(feature, fact)
        features.add(feature)
        values.add(fact)


def _validate_prop_fields(value: dict) -> None:
    _require_non_empty_string(value.get("scale"), "prop scale")
    _require_non_empty_string(value.get("function"), "prop function")


def validate_asset_card(value: dict, expected_type: str | None = None) -> dict:
    """Validate and deep-copy an environment, character, or prop asset card."""
    value = _require_object(value, "asset card")
    validate_json_compatible(value, "asset card")
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
