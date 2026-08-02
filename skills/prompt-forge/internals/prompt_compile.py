#!/usr/bin/env python3
"""Compile PromptIntent into an auditable PromptBuild artifact.

This module never invokes ComfyUI or any remote generator. It resolves the
model recipe, renders or validates the target dialect, checks locked facts and
canonical tags, applies negative-prompt policy, and returns a deterministic
execution-ready contract. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # package imports in tests
    from .intent_normalize import DIMENSIONS, load_concept_map, normalize_intent
    from .recipe_lookup import lookup_recipe
    from .tag_lookup import load_index as load_tag_index, lookup
except ImportError:  # direct script execution
    from intent_normalize import DIMENSIONS, load_concept_map, normalize_intent
    from recipe_lookup import lookup_recipe
    from tag_lookup import load_index as load_tag_index, lookup


BUILD_SCHEMA_VERSION = "1.0"
TAG_DIALECTS = {"danbooru", "tags", "tag", "comma-separated-tags"}
NATURAL_DIALECTS = {"natural-language", "natural language", "prose"}
TAG_ORDER = (
    "quality", "subject", "action", "scene", "composition", "camera",
    "lighting", "color", "style", "medium", "mood",
)
IMAGE_ORDER = (
    "subject", "action", "scene", "composition", "camera", "lighting",
    "color", "style", "medium", "mood", "quality",
)
VIDEO_ORDER = (
    "composition", "subject", "action", "motion", "camera", "timeline",
    "scene", "lighting", "color", "style", "mood", "audio", "quality",
)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _values(intent: dict, dimension: str) -> list[str]:
    return [item["value"].strip() for item in intent["dimensions"][dimension]]


def _recipe_supports_negative(policy: str) -> bool | None:
    normalized = policy.lower()
    if any(marker in normalized for marker in ("not supported", "no negatives", "positive-only")):
        return False
    if "supported" in normalized:
        return True
    return None


def _derived_dialect(intent: dict, recipe: dict) -> str:
    if intent["target"] == "video":
        return "video-timeline"
    text = str(recipe["frontmatter"].get("dialect", "")).lower()
    if "danbooru" in text or "comma-separated tag" in text:
        return "tags"
    return "natural-language"


def _split_control_tokens(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _compile_tags(normalized: dict, tag_index: dict) -> tuple[str, list[str], list[str], list[str]]:
    intent = normalized["intent"]
    valid: list[str] = []
    rejected: list[str] = []
    controls: list[str] = []

    for dimension in TAG_ORDER:
        for item in intent["dimensions"][dimension]:
            candidates = item.get("tag_candidates", [])
            if dimension == "quality" and item["origin"] == "recipe" and not candidates:
                controls.extend(_split_control_tokens(item["value"]))
            for candidate in candidates:
                results = lookup(tag_index, candidate, exact=True)
                if results:
                    valid.append(results[0]["canonical"])
                else:
                    rejected.append(candidate)

    controls = _dedupe(controls)
    valid = _dedupe(valid)
    rejected = _dedupe(rejected)
    return ", ".join(controls + valid), valid, rejected, controls


def _compile_prose(intent: dict, dialect: str) -> str:
    order = VIDEO_ORDER if dialect == "video-timeline" else IMAGE_ORDER
    segments = [", ".join(_values(intent, dimension)) for dimension in order]
    segments = [segment for segment in segments if segment]
    return ". ".join(segments).strip() + ("." if segments else "")


def _locked_fact_gaps(normalized: dict, prompt: str, dialect: str, valid_tags: list[str]) -> list[str]:
    intent = normalized["intent"]
    if dialect == "tags":
        gaps: list[str] = []
        for dimension in DIMENSIONS:
            for item in intent["dimensions"][dimension]:
                if item["origin"] != "explicit":
                    continue
                candidates = item.get("tag_candidates", [])
                if not candidates or not any(candidate in valid_tags for candidate in candidates):
                    gaps.append(item["value"])
        return _dedupe(gaps)

    normalized_prompt = " ".join(prompt.lower().split())
    return [
        fact for fact in normalized["locked_facts"]
        if " ".join(fact.lower().split()) not in normalized_prompt
    ]


def _validate_video_contract(intent: dict, prompt: str) -> list[str]:
    if intent["target"] != "video":
        return []
    missing: list[str] = []
    for dimension in ("action", "motion", "camera"):
        if not intent["dimensions"][dimension]:
            missing.append(dimension)
    if intent["generation_mode"] == "text-to-video" and not intent["dimensions"]["subject"]:
        missing.append("subject")
    if not prompt.strip():
        missing.append("prompt")
    return missing


def compile_prompt(intent: dict, draft: dict | None = None) -> dict:
    """Compile one validated PromptIntent into a PromptBuild dictionary."""
    draft = draft or {}
    if not isinstance(draft, dict):
        raise ValueError("draft must be an object")
    for key in ("prompt", "negative_prompt"):
        if key in draft and not isinstance(draft[key], str):
            raise ValueError(f"draft {key} must be a string")

    normalized = normalize_intent(intent, load_concept_map())
    canonical_intent = normalized["intent"]
    recipe = lookup_recipe(canonical_intent["model_id"])
    if recipe is None:
        raise ValueError(f"no model recipe matched '{canonical_intent['model_id']}'")

    frontmatter = recipe["frontmatter"]
    recipe_modality = str(frontmatter.get("modality", "")).lower()
    errors: list[str] = []
    warnings: list[str] = []
    if recipe_modality and recipe_modality != canonical_intent["target"]:
        errors.append(
            f"recipe modality '{recipe_modality}' does not match target '{canonical_intent['target']}'"
        )

    dialect = _derived_dialect(canonical_intent, recipe)
    declared = canonical_intent["dialect"].lower().strip()
    if dialect == "tags" and declared not in TAG_DIALECTS:
        errors.append(f"declared dialect '{declared}' conflicts with recipe tag dialect")
    if dialect == "natural-language" and declared not in NATURAL_DIALECTS:
        errors.append(f"declared dialect '{declared}' conflicts with recipe natural-language dialect")

    valid_tags: list[str] = []
    rejected_tags: list[str] = []
    control_tokens: list[str] = []
    if dialect == "tags":
        generated_prompt, valid_tags, rejected_tags, control_tokens = _compile_tags(
            normalized, load_tag_index()
        )
    else:
        generated_prompt = _compile_prose(canonical_intent, dialect)
    prompt = draft.get("prompt", "").strip() or generated_prompt

    negative_policy = str(frontmatter.get("negative_policy", "see body"))
    negative_supported = _recipe_supports_negative(negative_policy)
    proposed_negative = draft.get("negative_prompt", "").strip() or ", ".join(
        canonical_intent["negative_constraints"]
    )
    if negative_supported is False:
        negative_prompt = ""
        if proposed_negative:
            warnings.append(
                "negative prompt withheld; renderer must express constraints as positive exclusions"
            )
    elif negative_supported is True:
        negative_prompt = proposed_negative
    else:
        negative_prompt = ""
        if proposed_negative:
            warnings.append("recipe negative policy is ambiguous; negative prompt withheld")

    locked_gaps = _locked_fact_gaps(normalized, prompt, dialect, valid_tags)
    if locked_gaps:
        errors.append("locked facts are not represented: " + "; ".join(locked_gaps))
    if rejected_tags:
        errors.append("unverified tag candidates: " + ", ".join(rejected_tags))
    video_missing = _validate_video_contract(canonical_intent, prompt)
    if video_missing:
        errors.append("video contract missing: " + ", ".join(video_missing))
    if normalized["lexicon_unresolved"] and normalized["provenance"]["explicit"] == 0:
        errors.append(
            "source spans are unresolved and have no explicit representation: "
            + ", ".join(normalized["lexicon_unresolved"])
        )
    if not prompt:
        errors.append("compiled prompt is empty")
    if re.search(r"\[(?:unset)?\]", prompt, flags=re.I):
        errors.append("compiled prompt contains an internal placeholder")

    requested_capability = (
        "video-generation"
        if canonical_intent["target"] == "video"
        else "image-generation"
    )
    return {
        "schema_version": BUILD_SCHEMA_VERSION,
        "target": canonical_intent["target"],
        "generation_mode": canonical_intent["generation_mode"],
        "model_id": recipe["matched_id"],
        "dialect": dialect,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "parameters": canonical_intent["output_constraints"],
        "references": canonical_intent["references"],
        "validated_tags": valid_tags,
        "rejected_tags": rejected_tags,
        "recipe_control_tokens": control_tokens,
        "locked_facts": normalized["locked_facts"],
        "lexicon_unresolved": normalized["lexicon_unresolved"],
        "provenance": normalized["provenance"],
        "warnings": warnings,
        "errors": errors,
        "ready_to_execute": not errors,
        "execution": {
            "mode": canonical_intent["mode"],
            "requested": canonical_intent["mode"] == "execute",
            "performed": False,
            "tool": None,
            "capability": requested_capability,
        },
        "recipe": {
            "match_path": recipe["match_path"],
            "score": recipe["score"],
            "negative_policy": negative_policy,
        },
    }


def compile_payload(payload: dict) -> dict:
    """Accept either a raw PromptIntent or {'intent': ..., 'draft': ...}."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if "intent" in payload:
        return compile_prompt(payload["intent"], payload.get("draft"))
    return compile_prompt(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prompt_compile")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="PromptIntent or compile-envelope JSON")
    source.add_argument("--from-stdin", action="store_true", help="Read JSON payload from stdin")
    args = parser.parse_args(argv)

    try:
        payload = (
            json.loads(args.input.read_text(encoding="utf-8"))
            if args.input is not None
            else json.loads(sys.stdin.read())
        )
        result = compile_payload(payload)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"[prompt_compile] {exc}", file=sys.stderr)
        return 2

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if result["ready_to_execute"] else 1


if __name__ == "__main__":
    sys.exit(main())
