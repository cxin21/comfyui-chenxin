"""Fail-closed quality gates for Anima image PromptBuild dictionaries."""

from __future__ import annotations

import re


_PLACEHOLDER_RE = re.compile(r"\[[^\]]*\]|\{\{[^}]*\}\}|<[^>]*>")


def _normalized(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\s_-]+", "_", value.strip().casefold())


def _tokens(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    return [token for part in value.split(",") if (token := _normalized(part))]


def _duplicates(tokens: list[str]) -> set[str]:
    return {token for token in tokens if tokens.count(token) > 1}


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return value


def validate_anima_prompt_build(build: object, intent: object) -> list[str]:
    """Return all quality errors for an Anima image build without mutating inputs."""
    if not isinstance(build, dict):
        return ["PromptBuild must be an object"]
    if not isinstance(intent, dict):
        return ["PromptIntent must be an object"]

    errors: list[str] = []
    prompt = build.get("prompt")
    negative_prompt = build.get("negative_prompt")
    positive_tokens = _tokens(prompt)
    negative_tokens = _tokens(negative_prompt)

    if _normalized(build.get("dialect")) not in {"tag", "tags", "danbooru", "comma_separated_tags"}:
        errors.append("Anima PromptBuild requires a tag dialect")
    if build.get("ready_to_execute") is not True:
        errors.append("Anima PromptBuild is not ready to execute")
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append("positive prompt is empty")
    if not isinstance(negative_prompt, str) or not negative_prompt.strip():
        errors.append("negative prompt is empty")

    controls = _string_list(build.get("recipe_control_tokens"))
    if not controls or not any(token.strip() for token in controls):
        errors.append("recipe control tokens are required")

    rejected_tags = _string_list(build.get("rejected_tags"))
    if rejected_tags is None:
        errors.append("rejected tags must be a string list")
    elif rejected_tags:
        errors.append("unverified tag candidates are present")

    validated_tags = _string_list(build.get("validated_tags"))
    if validated_tags is None:
        errors.append("validated tags must be a string list")

    if controls is not None and validated_tags is not None:
        verified_tokens = {
            _normalized(token)
            for token in controls + validated_tags
            if _normalized(token)
        }
        unverified_tokens = sorted(set(positive_tokens).difference(verified_tokens))
        if unverified_tokens:
            errors.append(
                "unverified positive prompt tokens: " + ", ".join(unverified_tokens)
            )

    if isinstance(prompt, str) and _PLACEHOLDER_RE.search(prompt):
        errors.append("positive prompt contains a placeholder")
    if isinstance(negative_prompt, str) and _PLACEHOLDER_RE.search(negative_prompt):
        errors.append("negative prompt contains a placeholder")

    if _duplicates(positive_tokens):
        errors.append("positive prompt contains duplicate tokens")
    if _duplicates(negative_tokens):
        errors.append("negative prompt contains duplicate tokens")

    build_facts = _string_list(build.get("locked_facts"))
    intent_facts = _string_list(intent.get("locked_facts"))
    if build_facts is None or intent_facts is None:
        errors.append("locked facts must be string lists")
    else:
        expected_facts = {_normalized(fact) for fact in intent_facts if _normalized(fact)}
        declared_facts = {_normalized(fact) for fact in build_facts if _normalized(fact)}
        if not expected_facts:
            errors.append("locked facts are required")
        elif not expected_facts.issubset(declared_facts):
            errors.append("locked facts are not preserved from PromptIntent")

        missing_facts = expected_facts.difference(set(positive_tokens))
        if missing_facts:
            errors.append("locked facts are not represented in the positive prompt")
        if expected_facts.intersection(set(positive_tokens), set(negative_tokens)):
            errors.append("negative prompt contradicts locked facts")

    return errors
