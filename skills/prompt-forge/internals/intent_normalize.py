#!/usr/bin/env python3
"""Normalize a structured prompt intent and derive deterministic lookup terms.

The agent owns open-vocabulary Chinese understanding and controlled enrichment.
This module owns schema validation, curated concept matching, provenance-preserving
flattening, and canonical tag candidate extraction. It is not a general translator.

Output is JSON on stdout; errors are written to stderr. Stdlib only.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path


_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
CONCEPT_MAP_PATH = SKILL_DIR / "dictionary" / "zh-en.json"
TAG_INDEX_PATH = SKILL_DIR / "dictionary" / "tag-index.json"

SCHEMA_VERSION = "6.1"

DIMENSIONS = (
    "subject",
    "action",
    "scene",
    "lighting",
    "composition",
    "camera",
    "motion",
    "timeline",
    "audio",
    "color",
    "style",
    "mood",
    "medium",
    "quality",
)
ORIGINS = {"explicit", "recipe", "inferred"}
ORIGIN_PRIORITY = {"explicit": 3, "recipe": 2, "inferred": 1}
TARGETS = {"image", "video"}
MODES = {"compile", "execute"}
GENERATION_MODES = {
    "text-to-image": "image",
    "image-to-image": "image",
    "image-edit": "image",
    "text-to-video": "video",
    "image-to-video": "video",
    "video-to-video": "video",
    "first-last-frame-to-video": "video",
    "reference-to-video": "video",
}
REFERENCE_KINDS = {"image", "video", "audio"}
SCENE_DIMENSIONS = {"scene", "lighting", "composition", "color", "style", "mood"}
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_RE = re.compile(r"[a-zA-Z0-9_'-]+")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_IGNORED_CJK_FRAGMENTS = {
    "用", "出", "在", "的", "图", "画", "给", "请", "帮我", "生成",
    "一张", "一个", "一幅", "一位", "让", "把", "和", "与", "要", "做", "来",
}


def load_concept_map(path: Path = CONCEPT_MAP_PATH) -> dict[str, dict]:
    """Load and validate the curated zh-CN concept entries."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("entries")
    if not isinstance(entries, dict) or not entries:
        raise ValueError("concept map requires a non-empty 'entries' object")
    for surface, entry in entries.items():
        if not isinstance(surface, str) or not surface:
            raise ValueError("concept surfaces must be non-empty strings")
        if not isinstance(entry, dict):
            raise ValueError(f"concept '{surface}' must be an object")
        if not isinstance(entry.get("english"), str) or not entry["english"].strip():
            raise ValueError(f"concept '{surface}' requires non-empty english")
        tags = entry.get("canonical_tags")
        if not isinstance(tags, list) or not all(isinstance(t, str) and t for t in tags):
            raise ValueError(f"concept '{surface}' canonical_tags must be a string list")
        if entry.get("dimension") not in DIMENSIONS:
            raise ValueError(f"concept '{surface}' has invalid dimension")
    return entries


def validate_canonical_tags(
    entries: dict[str, dict], tag_index_path: Path = TAG_INDEX_PATH
) -> list[str]:
    """Return sorted canonical tags referenced by the map but absent from the index."""
    index = json.loads(tag_index_path.read_text(encoding="utf-8"))
    canonical = set(index.get("by_canonical", {}))
    referenced = {tag for entry in entries.values() for tag in entry["canonical_tags"]}
    return sorted(referenced - canonical)


def match_concepts(text: str, entries: dict[str, dict]) -> list[dict]:
    """Match non-overlapping surface phrases, preferring the longest phrase."""
    occupied = [False] * len(text)
    matches: list[dict] = []
    for surface in sorted(entries, key=lambda value: (-len(value), value)):
        # Single CJK characters are too ambiguous inside ordinary sentences
        # (for example 夜 in 夜空 or 雨 in 雨伞). Accept them only when the
        # complete query is that concept; longer curated phrases still match.
        if len(surface) == 1 and text.strip() != surface:
            continue
        start = 0
        while True:
            start = text.find(surface, start)
            if start < 0:
                break
            end = start + len(surface)
            if not any(occupied[start:end]):
                entry = entries[surface]
                matches.append(
                    {
                        "source_text": surface,
                        "english": entry["english"],
                        "canonical_tags": list(entry["canonical_tags"]),
                        "dimension": entry["dimension"],
                        "span": [start, end],
                    }
                )
                for index in range(start, end):
                    occupied[index] = True
            start = end
    matches.sort(key=lambda item: (item["span"][0], item["span"][1]))
    return matches


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _string_list_field(intent: dict, name: str) -> list[str]:
    value = intent.get(name, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"intent '{name}' must be a string list")
    return _dedupe([item.strip() for item in value])


def _contract_hash(intent: dict, name: str) -> str | None:
    value = intent.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"intent '{name}' must be a lowercase SHA-256 hash")
    return value


def _continuity_locks(intent: dict) -> dict[str, list[str]]:
    raw = intent.get("continuity_locks", {})
    if not isinstance(raw, dict):
        raise ValueError("intent 'continuity_locks' must be an object")
    locks: dict[str, list[str]] = {}
    for role in sorted(raw):
        if not isinstance(role, str) or not role.strip():
            raise ValueError("intent continuity lock roles must be non-empty strings")
        values = raw[role]
        if not isinstance(values, list) or not all(
            isinstance(item, str) and item.strip() for item in values
        ):
            raise ValueError(f"intent continuity lock '{role}' must be a string list")
        locks[role] = _dedupe([item.strip() for item in values])
    return locks


def _asset_refs(intent: dict) -> list[dict]:
    raw = intent.get("asset_refs", [])
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ValueError("intent 'asset_refs' must be a list of objects")
    try:
        json.dumps(raw, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("intent 'asset_refs' must be canonical JSON") from exc
    return copy.deepcopy(raw)


def _evidence_extension(intent: dict) -> dict:
    explicit = _string_list_field(intent, "explicit_evidence")
    reasonable = _string_list_field(intent, "reasonable_inference")
    prohibited = _string_list_field(intent, "prohibited_expansion")
    uncertainty = _string_list_field(intent, "uncertainty")
    locks = _continuity_locks(intent)
    lock_values = _dedupe([fact for role in locks for fact in locks[role]])

    explicit_keys = {_normalized_fact(item) for item in explicit}
    reasonable = [
        item for item in reasonable if _normalized_fact(item) not in explicit_keys
    ]
    allowed = intent.get("locked_facts", []) + explicit + reasonable + lock_values
    allowed_keys = {_normalized_fact(item) for item in allowed}
    prohibited_keys = {_normalized_fact(item) for item in prohibited}
    if allowed_keys.intersection(prohibited_keys):
        raise ValueError("prohibited expansion cannot be evidence or a continuity lock")

    return {
        "story_breakdown_hash": _contract_hash(intent, "story_breakdown_hash"),
        "art_bible_hash": _contract_hash(intent, "art_bible_hash"),
        "asset_refs": _asset_refs(intent),
        "explicit_evidence": explicit,
        "reasonable_inference": reasonable,
        "prohibited_expansion": prohibited,
        "continuity_locks": locks,
        "uncertainty": uncertainty,
        "continuity_lock_values": lock_values,
    }


def _normalized_fact(value: str) -> str:
    return " ".join(value.casefold().split())


def _unresolved_cjk(text: str, matches: list[dict]) -> list[str]:
    covered = [False] * len(text)
    for match in matches:
        start, end = match["span"]
        for index in range(start, end):
            covered[index] = True

    unresolved: list[str] = []
    for cjk_match in _CJK_RE.finditer(text):
        fragment_start: int | None = None
        for index in range(cjk_match.start(), cjk_match.end() + 1):
            is_boundary = index == cjk_match.end() or covered[index]
            if fragment_start is not None and is_boundary:
                fragment = text[fragment_start:index]
                if fragment not in _IGNORED_CJK_FRAGMENTS:
                    unresolved.append(fragment)
                fragment_start = None
            if index < cjk_match.end() and not covered[index] and fragment_start is None:
                fragment_start = index
    return _dedupe(unresolved)


def normalize_query(text: str, entries: dict[str, dict]) -> dict:
    """Extract known concepts without claiming to translate open vocabulary."""
    matches = match_concepts(text, entries)
    events: list[tuple[int, str]] = [
        (match["span"][0], match["english"]) for match in matches
    ]
    for latin in _LATIN_RE.finditer(text):
        events.append((latin.start(), latin.group(0).lower()))
    events.sort(key=lambda item: item[0])

    tag_candidates = _dedupe(
        [tag for match in matches for tag in match["canonical_tags"]]
    )
    scene_terms = _dedupe(
        [match["english"] for match in matches if match["dimension"] in SCENE_DIMENSIONS]
    )
    unresolved = _unresolved_cjk(text, matches)
    return {
        "original_query": text,
        "concepts": matches,
        "english_terms": _dedupe([value for _, value in events]),
        "scene_terms": scene_terms,
        "tag_candidates": tag_candidates,
        "lexicon_unresolved": unresolved,
        "has_unresolved": bool(unresolved),
    }


def validate_intent(intent: dict) -> None:
    """Validate the PromptIntent boundary consumed by deterministic tools."""
    if not isinstance(intent, dict):
        raise ValueError("intent must be a JSON object")
    if intent.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"intent schema_version must be '{SCHEMA_VERSION}'")
    for key in ("original_query", "model_id", "dialect"):
        if not isinstance(intent.get(key), str) or not intent[key].strip():
            raise ValueError(f"intent requires non-empty '{key}'")
    if intent.get("target") not in TARGETS:
        raise ValueError("intent target must be 'image' or 'video'")
    if intent.get("mode") not in MODES:
        raise ValueError("intent mode must be 'compile' or 'execute'")
    generation_mode = intent.get("generation_mode")
    if generation_mode not in GENERATION_MODES:
        raise ValueError("intent has invalid generation_mode")
    if GENERATION_MODES[generation_mode] != intent["target"]:
        raise ValueError("intent generation_mode does not match target")
    for key in ("negative_constraints", "locked_facts"):
        values = intent.get(key)
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            raise ValueError(f"intent '{key}' must be a string list")
    if not isinstance(intent.get("output_constraints"), dict):
        raise ValueError("intent output_constraints must be an object")
    references = intent.get("references")
    if not isinstance(references, list):
        raise ValueError("intent references must be a list")
    for reference in references:
        if not isinstance(reference, dict):
            raise ValueError("intent references must contain objects")
        if reference.get("kind") not in REFERENCE_KINDS:
            raise ValueError("intent reference has invalid kind")
        if not isinstance(reference.get("source"), str) or not reference["source"].strip():
            raise ValueError("intent reference requires non-empty source")
    dimensions = intent.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("intent requires a dimensions object")
    missing = [dimension for dimension in DIMENSIONS if dimension not in dimensions]
    if missing:
        raise ValueError(f"intent missing dimensions: {', '.join(missing)}")
    unknown = sorted(set(dimensions) - set(DIMENSIONS))
    if unknown:
        raise ValueError(f"intent has unknown dimensions: {', '.join(unknown)}")
    for dimension in DIMENSIONS:
        items = dimensions[dimension]
        if not isinstance(items, list):
            raise ValueError(f"dimension '{dimension}' must be a list")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"dimension '{dimension}' items must be objects")
            if not isinstance(item.get("value"), str) or not item["value"].strip():
                raise ValueError(f"dimension '{dimension}' item requires value")
            if item.get("origin") not in ORIGINS:
                raise ValueError(f"dimension '{dimension}' item has invalid origin")
            if "locked" in item and not isinstance(item["locked"], bool):
                raise ValueError(f"dimension '{dimension}' item locked must be boolean")
            if item.get("origin") == "explicit" and item.get("locked") is False:
                raise ValueError(f"dimension '{dimension}' explicit item cannot be unlocked")
            if "source_text" in item and (
                not isinstance(item["source_text"], str) or not item["source_text"].strip()
            ):
                raise ValueError(f"dimension '{dimension}' source_text must be non-empty")
            tags = item.get("tag_candidates", [])
            if not isinstance(tags, list) or not all(isinstance(tag, str) and tag for tag in tags):
                raise ValueError(f"dimension '{dimension}' tag_candidates must be a string list")
    _evidence_extension(intent)


def _merge_items(items: list[dict]) -> list[dict]:
    """Deduplicate exact semantic values using explicit > recipe > inferred."""
    positions: dict[str, int] = {}
    merged: list[dict] = []
    for raw in items:
        item = dict(raw)
        key = " ".join(item["value"].lower().split())
        if key not in positions:
            positions[key] = len(merged)
            merged.append(item)
            continue
        index = positions[key]
        current = merged[index]
        if ORIGIN_PRIORITY[item["origin"]] > ORIGIN_PRIORITY[current["origin"]]:
            merged[index] = item
        elif ORIGIN_PRIORITY[item["origin"]] == ORIGIN_PRIORITY[current["origin"]]:
            tags = _dedupe(current.get("tag_candidates", []) + item.get("tag_candidates", []))
            if tags:
                current["tag_candidates"] = tags
    return merged


def normalize_intent(intent: dict, entries: dict[str, dict]) -> dict:
    """Normalize PromptIntent while preserving explicit and inferred provenance."""
    validate_intent(intent)
    extension = _evidence_extension(intent)
    lexical = normalize_query(intent["original_query"], entries)
    dimensions = {
        dimension: _merge_items(intent["dimensions"][dimension])
        for dimension in DIMENSIONS
    }

    english_terms: list[str] = []
    scene_terms: list[str] = []
    proposed_tags: list[str] = []
    for dimension in DIMENSIONS:
        for item in dimensions[dimension]:
            english_terms.append(item["value"])
            proposed_tags.extend(item.get("tag_candidates", []))
            if dimension in SCENE_DIMENSIONS:
                scene_terms.append(item["value"])

    explicit_values = [
        item["value"]
        for dimension in DIMENSIONS
        for item in dimensions[dimension]
        if item["origin"] == "explicit"
    ]
    locked_facts = _dedupe(
        intent["locked_facts"]
        + explicit_values
        + extension["explicit_evidence"]
        + extension["continuity_lock_values"]
    )
    normalized_intent = copy.deepcopy(intent)
    normalized_intent["dimensions"] = dimensions
    has_evidence_extension = any(
        name in intent
        for name in (
            "story_breakdown_hash",
            "art_bible_hash",
            "asset_refs",
            "explicit_evidence",
            "reasonable_inference",
            "prohibited_expansion",
            "continuity_locks",
            "uncertainty",
        )
    )
    if has_evidence_extension:
        normalized_intent["locked_facts"] = locked_facts
        normalized_intent["negative_constraints"] = _dedupe(
            intent["negative_constraints"] + extension["prohibited_expansion"]
        )

    uncertainty = _dedupe(extension["uncertainty"] + lexical["lexicon_unresolved"])
    evidence_provenance = {
        name: copy.deepcopy(extension[name])
        for name in (
            "explicit_evidence",
            "reasonable_inference",
            "prohibited_expansion",
        )
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "intent": normalized_intent,
        "story_breakdown_hash": extension["story_breakdown_hash"],
        "art_bible_hash": extension["art_bible_hash"],
        "asset_refs": extension["asset_refs"],
        **evidence_provenance,
        "continuity_locks": copy.deepcopy(extension["continuity_locks"]),
        "uncertainty": uncertainty,
        "english_terms": _dedupe(english_terms),
        "scene_terms": _dedupe(scene_terms),
        "tag_candidates": _dedupe(lexical["tag_candidates"] + proposed_tags),
        "lexicon_matches": lexical["concepts"],
        "lexicon_unresolved": lexical["lexicon_unresolved"],
        "locked_facts": locked_facts,
        "provenance": {
            origin: sum(
                item["origin"] == origin
                for dimension in DIMENSIONS
                for item in dimensions[dimension]
            )
            for origin in sorted(ORIGINS)
        }
        | evidence_provenance,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="intent_normalize")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--query", help="Direct source query for deterministic concept extraction")
    source.add_argument("--intent", type=Path, help="PromptIntent JSON file")
    source.add_argument("--from-stdin", action="store_true", help="Read PromptIntent or {'query': ...} JSON")
    parser.add_argument("--stats", action="store_true", help="Report concept-map integrity")
    parser.add_argument("--concept-map", type=Path, default=CONCEPT_MAP_PATH)
    args = parser.parse_args(argv)

    try:
        entries = load_concept_map(args.concept_map)
        if args.stats:
            missing = validate_canonical_tags(entries)
            result = {
                "entries": len(entries),
                "canonical_tags": len({tag for entry in entries.values() for tag in entry["canonical_tags"]}),
                "missing_canonical_tags": missing,
                "path": str(args.concept_map),
            }
        elif args.query is not None:
            result = normalize_query(args.query, entries)
        elif args.intent is not None:
            payload = json.loads(args.intent.read_text(encoding="utf-8"))
            result = normalize_intent(payload, entries)
        elif args.from_stdin:
            payload = json.loads(sys.stdin.read())
            result = (
                normalize_query(payload["query"], entries)
                if set(payload) == {"query"}
                else normalize_intent(payload, entries)
            )
        else:
            parser.error("provide --query, --intent, --from-stdin, or --stats")
            return 2
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"[intent_normalize] {exc}", file=sys.stderr)
        return 2

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
