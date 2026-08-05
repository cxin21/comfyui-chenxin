"""Fail-closed quality gates for Anima image PromptBuild dictionaries."""

from __future__ import annotations

import math
import re


_PLACEHOLDER_RE = re.compile(r"\[[^\]]*\]|\{\{[^}]*\}\}|<[^>]*>")
_LTX_TIMELINE_RE = re.compile(
    r"〖\s*(?P<start>\d+(?:\.\d+)?)\s*-\s*"
    r"(?P<end>\d+(?:\.\d+)?)\s*s\s*〗"
)
_BARE_TIMELINE_RE = re.compile(
    r"(?<![\w.])(?:\d+(?:\.\d+)?|start|begin)\s*-\s*"
    r"(?:\d+(?:\.\d+)?|end|finish)\s*s\b",
    re.IGNORECASE,
)
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_QUOTED_RE = re.compile(r"[“‘\"']([^”’\"']+)[”’\"']")
_EXPLICIT_DIALOGUE_RE = re.compile(
    r"(?:对白|台词|dialogue|spoken\s+line)\s*[:：]\s*"
    r"[“‘\"']([^”’\"']+)[”’\"']",
    re.IGNORECASE,
)
_EXPLICIT_DIALOGUE_MARKER_RE = re.compile(
    r"(?:对白|台词|dialogue|spoken\s+line)\s*[:：]",
    re.IGNORECASE,
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_EXTREME_WIDE_RE = re.compile(
    r"\b(?:extreme|ultra)[\s-]+wide(?:\s+shot)?\b|\bextreme\s+long\s+shot\b|超远景",
    re.IGNORECASE,
)
_LTX_V2_FIELDS = frozenset(
    {
        "positive_zh",
        "positive_en",
        "global_prompt",
        "timeline_segments",
        "dialogue_attribution",
        "continuity_requirements",
        "split_recommendation",
        "source_shot_plan_hash",
    }
)
_IMAGE_V2_FIELDS = frozenset(
    {
        "reference_roles",
        "identity_lock",
        "style_lock",
        "scene_lock",
        "prop_lock",
        "source_contract_hashes",
    }
)


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


def _validate_anima_v2(build: dict, intent: dict) -> list[str]:
    errors: list[str] = []
    reference_roles = build.get("reference_roles")
    if not isinstance(reference_roles, list) or not reference_roles:
        errors.append("reference roles must be a non-empty list")
    else:
        for item in reference_roles:
            if not isinstance(item, dict):
                errors.append("reference roles must contain objects")
                continue
            role = item.get("role")
            source = item.get("asset_id", item.get("reference_id", item.get("source")))
            if not isinstance(role, str) or not role.strip():
                errors.append("reference roles require a non-empty role")
            if not isinstance(source, str) or not source.strip():
                errors.append("reference roles require an asset or reference source")

    locks: dict[str, list[str]] = {}
    for name in ("identity_lock", "style_lock", "scene_lock", "prop_lock"):
        values = build.get(name)
        if not isinstance(values, list) or not all(
            isinstance(item, str) and item.strip() for item in values
        ):
            errors.append(f"{name} must be a string list")
        else:
            locks[name.removesuffix("_lock")] = [item.strip() for item in values]

    source_hashes = build.get("source_contract_hashes")
    if not isinstance(source_hashes, dict) or not source_hashes:
        errors.append("source contract hashes must be a non-empty object")
    elif not all(
        isinstance(name, str)
        and name.strip()
        and isinstance(value, str)
        and _SHA256_RE.fullmatch(value)
        for name, value in source_hashes.items()
    ):
        errors.append("source contract hashes must contain lowercase SHA-256 values")

    continuity_locks = intent.get("continuity_locks")
    if continuity_locks is not None:
        if not isinstance(continuity_locks, dict):
            errors.append("PromptIntent continuity_locks must be an object")
        else:
            for role in ("identity", "style", "scene", "prop"):
                expected = continuity_locks.get(role, [])
                if not isinstance(expected, list) or not all(
                    isinstance(item, str) and item.strip() for item in expected
                ):
                    errors.append(f"PromptIntent continuity lock '{role}' is malformed")
                    continue
                declared = {_normalized(item) for item in locks.get(role, [])}
                if any(_normalized(item) not in declared for item in expected):
                    errors.append(f"{role}_lock does not preserve PromptIntent continuity")

    prohibited = intent.get("prohibited_expansion", [])
    if isinstance(prohibited, list):
        prohibited_values = {_normalized(item) for item in prohibited if isinstance(item, str)}
        locked_values = {
            _normalized(item)
            for values in locks.values()
            for item in values
        }
        if prohibited_values.intersection(locked_values):
            errors.append("image locks contain a prohibited expansion")
    return errors


def parse_ltx_timeline(prompt: str) -> list[dict]:
    """Parse strict ``〖start-end s〗`` intervals from one positive prompt."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("LTX timeline prompt must be a non-empty string")
    if _PLACEHOLDER_RE.search(prompt):
        raise ValueError("LTX timeline contains a placeholder")

    matches = list(_LTX_TIMELINE_RE.finditer(prompt))
    if not matches:
        raise ValueError("LTX timeline requires 〖start-end s〗 intervals")
    without_valid_markers = _LTX_TIMELINE_RE.sub("", prompt)
    if (
        "〖" in without_valid_markers
        or "〗" in without_valid_markers
        or _BARE_TIMELINE_RE.search(without_valid_markers)
    ):
        raise ValueError("LTX timeline contains a malformed or hidden interval")

    segments: list[dict] = []
    previous_end = -1.0
    for index, match in enumerate(matches):
        start = float(match.group("start"))
        end = float(match.group("end"))
        if start < 0 or end <= start:
            raise ValueError("LTX timeline intervals must have positive duration")
        if index == 0 and not math.isclose(start, 0.0, abs_tol=1e-9):
            raise ValueError("LTX timeline must start at 0 seconds")
        if index > 0 and not math.isclose(
            start, previous_end, rel_tol=1e-9, abs_tol=1e-9
        ):
            raise ValueError(
                "LTX timeline intervals must be contiguous without gaps or overlaps"
            )
        text_start = match.end()
        text_end = matches[index + 1].start() if index + 1 < len(matches) else len(prompt)
        text = prompt[text_start:text_end].strip()
        if not text:
            raise ValueError("LTX timeline interval text must be non-empty")
        segments.append(
            {
                "start": start,
                "end": end,
                "duration": round(end - start, 9),
                "text": text,
            }
        )
        previous_end = end
    return segments


def select_ltx_global_prompt(input_type: str, candidates: object) -> str:
    """Select one director prompt without concatenating competing candidates."""
    if input_type not in {"reference", "script", "storyboard", "character_sheet"}:
        raise ValueError("LTX input_type has no global prompt policy")
    if not isinstance(candidates, dict):
        raise ValueError("LTX global prompt candidates must be an object")
    selected = candidates.get(input_type)
    if not isinstance(selected, str) or not selected.strip():
        raise ValueError(f"LTX global prompt is missing for input_type '{input_type}'")
    return selected.strip()


def _change_requested(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value > 0
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return False


def recommend_ltx_split(intent: object) -> dict:
    """Return the deterministic complexity split decision for a shot intent."""
    if not isinstance(intent, dict):
        raise ValueError("Video PromptIntent must be an object")
    raw_complexity = intent.get("complexity", {})
    if raw_complexity is None:
        raw_complexity = {}
    if not isinstance(raw_complexity, dict):
        raise ValueError("video complexity must be an object")
    complexity = dict(intent)
    complexity.update(raw_complexity)

    reasons: list[str] = []
    if any(
        _change_requested(complexity.get(name))
        for name in ("scene_change", "scene_changes", "time_change", "time_changes")
    ):
        reasons.append("scene/time change")
    core_characters = complexity.get("core_characters", [])
    if isinstance(core_characters, int) and not isinstance(core_characters, bool):
        core_character_count = core_characters
    elif isinstance(core_characters, list):
        core_character_count = len(core_characters)
    else:
        core_character_count = 0
    if core_character_count > 3:
        reasons.append("more than three core characters")
    complex_beats = complexity.get("complex_beats", [])
    if isinstance(complex_beats, int) and not isinstance(complex_beats, bool):
        complex_beat_count = complex_beats
    elif isinstance(complex_beats, list):
        complex_beat_count = len(complex_beats)
    else:
        complex_beat_count = 0
    if complex_beat_count > 4:
        reasons.append("more than four complex beats")
    if _change_requested(complexity.get("mixed_complex_events")) or (
        _change_requested(complexity.get("complex_action"))
        and _change_requested(complexity.get("long_dialogue"))
    ):
        reasons.append("mixed complex events")
    if isinstance(complexity.get("major_events"), list) and len(complexity["major_events"]) > 1:
        reasons.append("multiple major events")
    return {"required": bool(reasons), "reason": "; ".join(reasons)}


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

    if _IMAGE_V2_FIELDS.intersection(build):
        errors.extend(_validate_anima_v2(build, intent))

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


def _has_value(value: object) -> bool:
    return value not in (None, "", [], {})


def _flatten_continuity(value: object) -> list[str] | None:
    if isinstance(value, list) and all(
        isinstance(item, str) and item.strip() for item in value
    ):
        return [item.strip() for item in value]
    if isinstance(value, dict):
        flattened: list[str] = []
        for role in sorted(value):
            items = value[role]
            if not isinstance(items, list) or not all(
                isinstance(item, str) and item.strip() for item in items
            ):
                return None
            flattened.extend(item.strip() for item in items)
        return flattened
    return None


def _validate_declared_timeline(
    declared: object,
    parsed_zh: list[dict],
    parsed_en: list[dict],
) -> list[str]:
    if not isinstance(declared, list) or not declared:
        return ["timeline_segments must be a non-empty list"]
    if len(declared) != len(parsed_zh) or len(declared) != len(parsed_en):
        return ["timeline_segments do not match the bilingual timeline"]
    errors: list[str] = []
    for index, item in enumerate(declared):
        if not isinstance(item, dict):
            errors.append("timeline_segments must contain objects")
            continue
        start = item.get("start")
        end = item.get("end")
        if (
            not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not isinstance(end, (int, float))
            or isinstance(end, bool)
            or float(start) != parsed_zh[index]["start"]
            or float(end) != parsed_zh[index]["end"]
            or float(start) != parsed_en[index]["start"]
            or float(end) != parsed_en[index]["end"]
        ):
            errors.append("timeline_segments ranges do not match the bilingual timeline")
        for language, parsed in (("zh", parsed_zh), ("en", parsed_en)):
            text = item.get(f"text_{language}")
            if not isinstance(text, str) or text.strip() != parsed[index]["text"]:
                errors.append(
                    f"timeline_segments text_{language} does not match the positive prompt"
                )
    return errors


def _validate_dialogue(
    attribution: object,
    positive_zh: str,
    positive_en: str,
) -> list[str]:
    if not isinstance(attribution, list):
        return ["dialogue_attribution must be a list"]
    errors: list[str] = []
    declared_text: list[str] = []
    declared_speakers: list[str] = []
    for item in attribution:
        if not isinstance(item, dict):
            errors.append("dialogue_attribution must contain objects")
            continue
        speaker = item.get("speaker")
        speaker_en = item.get("speaker_en", speaker)
        text = item.get("text")
        if not isinstance(speaker, str) or not speaker.strip():
            errors.append("dialogue attribution requires a speaker")
        else:
            speaker = speaker.strip()
            declared_speakers.append(speaker)
            if speaker not in positive_zh:
                errors.append("dialogue speaker is missing from positive_zh")
        if not isinstance(speaker_en, str) or not speaker_en.strip():
            errors.append("dialogue attribution requires speaker_en or a shared speaker")
        else:
            speaker_en = speaker_en.strip()
            declared_speakers.append(speaker_en)
            if speaker_en not in positive_en:
                errors.append("dialogue speaker is missing from positive_en")
        if not isinstance(text, str) or not text.strip():
            errors.append("dialogue attribution requires exact dialogue text")
            continue
        text = text.strip()
        declared_text.append(text)
        if text not in positive_zh:
            errors.append("dialogue text is missing from positive_zh")
        if text not in positive_en:
            if _CJK_RE.search(text):
                errors.append("Chinese dialogue must be copied exactly into positive_en")
            else:
                errors.append("dialogue text is missing from positive_en")

    explicitly_marked_dialogue = {
        match.group(1).strip()
        for prompt in (positive_zh, positive_en)
        for match in _EXPLICIT_DIALOGUE_RE.finditer(prompt)
    }
    has_explicit_marker = any(
        _EXPLICIT_DIALOGUE_MARKER_RE.search(prompt)
        for prompt in (positive_zh, positive_en)
    )
    if has_explicit_marker and not declared_text:
        errors.append("explicit dialogue marker requires speaker attribution")
    elif not explicitly_marked_dialogue.issubset(set(declared_text)):
        errors.append("explicit dialogue in the positive prompt lacks speaker attribution")

    translated_surroundings = positive_en
    for preserved_text in declared_text + declared_speakers:
        translated_surroundings = translated_surroundings.replace(preserved_text, "")
    translated_surroundings = _QUOTED_RE.sub(
        lambda match: "" if _CJK_RE.search(match.group(1)) else match.group(0),
        translated_surroundings,
    )
    if _CJK_RE.search(translated_surroundings):
        errors.append("positive_en contains untranslated Chinese outside dialogue")
    return errors


def _validate_ltx_v2(build: dict, intent: dict) -> list[str]:
    errors: list[str] = []
    narrative_layers = build.get("narrative_layers")
    if isinstance(narrative_layers, list) and len(narrative_layers) > 1:
        errors.append("duplicated narrative layers are forbidden")
    positive_zh = build.get("positive_zh")
    positive_en = build.get("positive_en")
    if not isinstance(positive_zh, str) or not positive_zh.strip():
        errors.append("positive_zh is required")
        positive_zh = ""
    if not isinstance(positive_en, str) or not positive_en.strip():
        errors.append("positive_en is required")
        positive_en = ""

    prompt = build.get("prompt")
    execution_language = build.get("execution_language")
    if execution_language in {"zh", "en"}:
        selected = positive_zh if execution_language == "zh" else positive_en
        if prompt != selected:
            errors.append("prompt must equal the selected execution-language positive prompt")
    elif prompt not in {positive_zh, positive_en}:
        errors.append("prompt must equal one bilingual positive prompt")

    parsed_zh: list[dict] = []
    parsed_en: list[dict] = []
    for language, value in (("zh", positive_zh), ("en", positive_en)):
        try:
            parsed = parse_ltx_timeline(value)
        except ValueError as exc:
            errors.append(f"positive_{language} timeline is invalid: {exc}")
        else:
            if language == "zh":
                parsed_zh = parsed
            else:
                parsed_en = parsed
    if parsed_zh and parsed_en:
        if [item["start"] for item in parsed_zh] != [item["start"] for item in parsed_en] or [
            item["end"] for item in parsed_zh
        ] != [item["end"] for item in parsed_en]:
            errors.append("bilingual timeline ranges must be identical")
        errors.extend(
            _validate_declared_timeline(
                build.get("timeline_segments"), parsed_zh, parsed_en
            )
        )

    errors.extend(
        _validate_dialogue(build.get("dialogue_attribution"), positive_zh, positive_en)
    )

    for key, value in build.items():
        if key != "negative_prompt" and "negative" in _normalized(key) and _has_value(value):
            errors.append(f"second negative system is forbidden: {key}")

    global_prompt = build.get("global_prompt")
    if not isinstance(global_prompt, str) or not global_prompt.strip():
        errors.append("one global prompt is required")
    elif "global_prompts" in intent or "input_type" in intent:
        try:
            expected_global = select_ltx_global_prompt(
                intent.get("input_type"), intent.get("global_prompts")
            )
        except ValueError as exc:
            errors.append(f"global prompt selection failed: {exc}")
        else:
            if global_prompt.strip() != expected_global:
                errors.append("global prompt does not match the selected input type")

    continuity = _flatten_continuity(build.get("continuity_requirements"))
    if not continuity:
        errors.append("continuity requirements are required")
    else:
        intent_locks = _flatten_continuity(intent.get("continuity_locks", {}))
        if intent_locks is None:
            errors.append("PromptIntent continuity_locks are malformed")
        else:
            declared = {_normalized(item) for item in continuity}
            missing = [item for item in intent_locks if _normalized(item) not in declared]
            if missing:
                errors.append("continuity requirements do not preserve PromptIntent locks")

    requested_split = recommend_ltx_split(intent)
    declared_split = build.get("split_recommendation")
    if not isinstance(declared_split, dict) or not isinstance(
        declared_split.get("required"), bool
    ):
        errors.append("split recommendation must declare required as a boolean")
    elif declared_split["required"] != requested_split["required"]:
        errors.append("split recommendation does not match shot complexity")
    elif declared_split["required"] and not isinstance(declared_split.get("reason"), str):
        errors.append("split recommendation requires a reason")

    source_hash = build.get("source_shot_plan_hash")
    if not isinstance(source_hash, str) or _SHA256_RE.fullmatch(source_hash) is None:
        errors.append("source_shot_plan_hash must be a lowercase SHA-256 hash")

    combined_positive = f"{positive_zh}\n{positive_en}"
    explicit_composition = " ".join(_video_dimension_values(intent, "composition"))
    if _EXTREME_WIDE_RE.search(combined_positive) and not _EXTREME_WIDE_RE.search(
        explicit_composition
    ):
        errors.append("extreme-wide framing cannot be introduced as a default")

    if isinstance(global_prompt, str) and global_prompt.strip():
        if global_prompt.strip() in positive_zh or global_prompt.strip() in positive_en:
            errors.append("duplicated narrative layers include the global prompt")
    if parsed_zh and parsed_en:
        declared = build.get("timeline_segments")
        if isinstance(declared, list):
            for item in declared:
                if not isinstance(item, dict):
                    continue
                for language, positive in (("zh", positive_zh), ("en", positive_en)):
                    text = item.get(f"text_{language}")
                    if isinstance(text, str) and text.strip() and positive.count(text.strip()) > 1:
                        errors.append(f"positive_{language} contains duplicated narrative layers")
    return errors


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
    if _LTX_V2_FIELDS.intersection(build):
        errors.extend(_validate_ltx_v2(build, intent))
    return errors
