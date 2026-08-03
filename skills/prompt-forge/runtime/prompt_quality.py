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


def _video_dimension_values(intent: dict, name: str) -> list[str]:
    dimensions = intent.get("dimensions")
    if not isinstance(dimensions, dict):
        return []
    raw_values = dimensions.get(name)
    if not isinstance(raw_values, list):
        return []
    values: list[str] = []
    for item in raw_values:
        value = item.get("value") if isinstance(item, dict) else item
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    return values


def _word_variants(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    variants: set[str] = set()
    for word in words:
        if len(word) <= 2:
            continue
        variants.add(word)
        if len(word) >= 4:
            variants.add(word[:4])
        for suffix in ("ing", "ies", "es", "ly", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                variants.add(word[: -len(suffix)])
    return variants


def _video_phrase_present(prompt: str, phrase: str) -> bool:
    prompt_words = re.findall(r"[a-z0-9]+", prompt.casefold())
    phrase_words = [word for word in re.findall(r"[a-z0-9]+", phrase.casefold()) if len(word) > 2]
    for phrase_word in phrase_words:
        if not any(
            prompt_word == phrase_word
            or prompt_word.startswith(phrase_word)
            or phrase_word.startswith(prompt_word)
            or (len(prompt_word) >= 4 and len(phrase_word) >= 4 and prompt_word[:4] == phrase_word[:4])
            for prompt_word in prompt_words
        ):
            return False
    return bool(phrase_words)


def validate_ltx_prompt_build(build: object, intent: object) -> list[str]:
    """Return deterministic quality errors for a Yusu LTX video build."""
    if not isinstance(build, dict):
        return ["Video PromptBuild must be an object"]
    if not isinstance(intent, dict):
        return ["Video PromptIntent must be an object"]
    errors: list[str] = []
    if build.get("target") != "video":
        errors.append("LTX PromptBuild target must be video")
    if _normalized(build.get("dialect")) != "video_timeline":
        errors.append("LTX PromptBuild requires the video-timeline dialect")
    if build.get("ready_to_execute") is not True:
        errors.append("LTX PromptBuild is not ready to execute")
    prompt = build.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append("video prompt is empty")
        prompt = ""
    negative = build.get("negative_prompt")
    if negative != "":
        errors.append("LTX uses the workflow-owned negative conditioning; negative_prompt must be empty")

    for dimension in ("subject", "action", "motion", "camera"):
        values = _video_dimension_values(intent, dimension)
        if not values:
            errors.append(f"video {dimension} dimension is required")
            continue
        for value in values:
            if not _video_phrase_present(prompt, value):
                errors.append(f"video {dimension} is not represented in the prompt: {value}")

    locked_facts = intent.get("locked_facts")
    if not isinstance(locked_facts, list) or not all(isinstance(item, str) for item in locked_facts):
        errors.append("video locked facts must be a string list")
    else:
        for fact in locked_facts:
            if fact.strip() and not _video_phrase_present(prompt, fact):
                errors.append(f"video locked fact is not represented in the prompt: {fact}")
    return errors
