from copy import deepcopy

from runtime.prompt_quality import validate_anima_prompt_build


def valid_anima_build():
    return {
        "target": "image",
        "dialect": "tags",
        "prompt": "score_9, 1girl, red_hair",
        "negative_prompt": "worst_quality, watermark",
        "validated_tags": ["1girl", "red_hair"],
        "rejected_tags": [],
        "recipe_control_tokens": ["score_9"],
        "locked_facts": ["red hair"],
        "ready_to_execute": True,
    }


def test_anima_rejects_unverified_tags_and_positive_negative_conflict():
    build = valid_anima_build()
    build["negative_prompt"] = "red hair, watermark"
    build["validated_tags"] = ["1girl"]
    build["rejected_tags"] = ["red_hair"]

    errors = validate_anima_prompt_build(build, {"locked_facts": ["red hair"]})

    assert any("unverified" in item for item in errors)
    assert any("contradicts" in item for item in errors)


def test_anima_rejects_positive_tokens_not_verified_by_build_metadata():
    build = valid_anima_build()
    build["prompt"] = "score_9, 1girl, red_hair, unknown_tag"

    errors = validate_anima_prompt_build(build, {"locked_facts": ["red hair"]})

    assert any("unverified" in item for item in errors)


def test_anima_rejects_missing_required_quality_signals_fail_closed():
    build = valid_anima_build()
    build.update(
        {
            "dialect": "natural-language",
            "prompt": "",
            "recipe_control_tokens": [],
            "ready_to_execute": False,
            "locked_facts": [],
        }
    )

    errors = validate_anima_prompt_build(build, {"locked_facts": ["red hair"]})

    assert any("tag dialect" in item for item in errors)
    assert any("not ready" in item for item in errors)
    assert any("recipe control" in item for item in errors)
    assert any("empty" in item for item in errors)
    assert any("locked facts" in item for item in errors)


def test_anima_rejects_placeholders_and_duplicate_tokens():
    build = valid_anima_build()
    build["prompt"] = "score_9, 1girl, 1girl, [unset]"
    build["negative_prompt"] = "watermark, watermark"

    errors = validate_anima_prompt_build(build, {"locked_facts": ["red hair"]})

    assert any("placeholder" in item for item in errors)
    assert any("duplicate" in item for item in errors)


def test_anima_accepts_a_valid_build_without_mutating_inputs():
    build = valid_anima_build()
    intent = {"locked_facts": ["red hair"]}
    original_build = deepcopy(build)
    original_intent = deepcopy(intent)

    assert validate_anima_prompt_build(build, intent) == []
    assert build == original_build
    assert intent == original_intent


def test_anima_rejects_non_object_inputs_fail_closed():
    assert validate_anima_prompt_build(None, {})
    assert validate_anima_prompt_build({}, None)
