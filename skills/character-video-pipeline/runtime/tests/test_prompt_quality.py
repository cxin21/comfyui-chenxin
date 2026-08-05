from copy import deepcopy

import pytest

from runtime import prompt_quality
from runtime.prompt_quality import validate_anima_prompt_build, validate_ltx_prompt_build


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


def test_evidence_bound_anima_build_rejects_malformed_locks_and_source_hashes():
    build = valid_anima_build()
    build.update(
        {
            "reference_roles": [],
            "identity_lock": "red hair",
            "style_lock": [],
            "scene_lock": [],
            "prop_lock": [],
            "source_contract_hashes": {"story_breakdown": "not-a-hash"},
        }
    )

    errors = validate_anima_prompt_build(build, {"locked_facts": ["red hair"]})

    assert any("reference roles" in error for error in errors)
    assert any("identity_lock" in error for error in errors)
    assert any("source contract hashes" in error for error in errors)


def valid_video_intent():
    dimensions = {
        name: []
        for name in (
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
    }
    dimensions["subject"] = [{"value": "the swordswoman", "origin": "explicit"}]
    dimensions["action"] = [{"value": "raises her sword", "origin": "explicit"}]
    dimensions["motion"] = [{"value": "cloth and hair trail continuously", "origin": "explicit"}]
    dimensions["camera"] = [{"value": "slow dolly in", "origin": "explicit"}]
    return {
        "target": "video",
        "dimensions": dimensions,
        "locked_facts": ["the swordswoman"],
        "input_type": "reference",
        "global_prompts": {
            "reference": "Preserve reference identity and scene continuity.",
            "script": "Follow the script's event order.",
        },
        "continuity_locks": {
            "identity": ["the swordswoman"],
            "scene": ["the same courtyard"],
        },
    }


def valid_evidence_bound_video_build():
    positive_zh = (
        "参考图1（人物）：保持同一位女剑士与同一庭院。"
        "女剑士抬剑，布料和头发持续飘动，镜头缓慢推进。"
        "〖0-1.7 s〗女剑士抬头。〖1.7-4.2 s〗女剑士说：“快走。”并向前迈步。"
    )
    positive_en = (
        "Reference image 1 (character): preserve the same swordswoman and courtyard. "
        "The swordswoman raises her sword as cloth and hair trail continuously; the camera slowly dollies in. "
        "〖0-1.7 s〗The swordswoman looks up. "
        "〖1.7-4.2 s〗The swordswoman says “快走。” and steps forward."
    )
    return {
        "target": "video",
        "dialect": "video-timeline",
        "prompt": positive_en,
        "negative_prompt": "",
        "positive_zh": positive_zh,
        "positive_en": positive_en,
        "global_prompt": "Preserve reference identity and scene continuity.",
        "timeline_segments": [
            {"start": 0.0, "end": 1.7, "text_zh": "女剑士抬头。", "text_en": "The swordswoman looks up."},
            {
                "start": 1.7,
                "end": 4.2,
                "text_zh": "女剑士说：“快走。”并向前迈步。",
                "text_en": "The swordswoman says “快走。” and steps forward.",
            },
        ],
        "dialogue_attribution": [
            {
                "speaker": "女剑士",
                "speaker_en": "The swordswoman",
                "text": "快走。",
                "start": 1.7,
                "end": 4.2,
            }
        ],
        "continuity_requirements": ["the swordswoman", "the same courtyard"],
        "split_recommendation": {"required": False, "reason": ""},
        "source_shot_plan_hash": "a" * 64,
        "ready_to_execute": True,
    }


def test_complete_ltx_build_passes():
    build = {
        "target": "video",
        "dialect": "video-timeline",
        "prompt": "The swordswoman raises her sword as cloth and hair trail continuously. The camera slowly dollies in.",
        "negative_prompt": "",
        "ready_to_execute": True,
    }
    assert validate_ltx_prompt_build(build, valid_video_intent()) == []


def test_static_quality_only_prompt_fails():
    build = {
        "target": "video",
        "dialect": "video-timeline",
        "prompt": "masterpiece, best quality, cinematic",
        "negative_prompt": "",
        "ready_to_execute": True,
    }
    errors = validate_ltx_prompt_build(build, valid_video_intent())
    assert "motion" in " ".join(errors)


def test_second_negative_system_fails():
    build = {
        "target": "video",
        "dialect": "video-timeline",
        "prompt": "The swordswoman moves while the camera dollies in.",
        "negative_prompt": "watermark",
        "ready_to_execute": True,
    }
    assert any("workflow-owned negative" in item for item in validate_ltx_prompt_build(build, valid_video_intent()))


def test_parse_ltx_timeline_accepts_dynamic_monotonic_seconds():
    parser = getattr(prompt_quality, "parse_ltx_timeline", None)
    assert parser is not None, "parse_ltx_timeline must be implemented"

    assert parser("〖0-1.7 s〗looks up; 〖1.7-4.2 s〗steps forward") == [
        {"start": 0.0, "end": 1.7, "duration": 1.7, "text": "looks up;"},
        {"start": 1.7, "end": 4.2, "duration": 2.5, "text": "steps forward"},
    ]


def test_parse_ltx_timeline_accepts_float_tolerance_at_adjacent_boundary():
    parser = getattr(prompt_quality, "parse_ltx_timeline", None)
    assert parser is not None, "parse_ltx_timeline must be implemented"

    assert len(parser("〖0-0.3 s〗first 〖0.3000000001-0.6 s〗second")) == 2


@pytest.mark.parametrize(
    "timeline",
    [
        "〖0-0 s〗still",
        "〖0-2 s〗first 〖1.5-3 s〗overlap",
        "〖2-3 s〗later 〖0-1 s〗earlier",
        "〖1-2 s〗first 〖5-6 s〗gap and non-zero start",
        "〖0.5-1 s〗non-zero start",
        "〖0-1 s〗first 〖2-3 s〗gap",
        "〖start-end s〗placeholder",
        "0-2s hidden timeline; 2-4s hidden timeline",
        "〖0-2 s〗valid plus 2-4s hidden timeline",
    ],
)
def test_parse_ltx_timeline_rejects_invalid_or_hidden_ranges(timeline):
    parser = getattr(prompt_quality, "parse_ltx_timeline", None)
    assert parser is not None, "parse_ltx_timeline must be implemented"
    with pytest.raises(ValueError, match="timeline"):
        parser(timeline)


def test_evidence_bound_ltx_build_requires_complete_bilingual_contract():
    build = valid_evidence_bound_video_build()
    del build["positive_en"]

    errors = validate_ltx_prompt_build(build, valid_video_intent())

    assert any("positive_en" in error for error in errors)


def test_evidence_bound_ltx_build_preserves_chinese_dialogue_and_speaker():
    build = valid_evidence_bound_video_build()
    build["dialogue_attribution"][0]["speaker"] = ""
    build["positive_en"] = build["positive_en"].replace("快走。", "Move!")
    build["prompt"] = build["positive_en"]

    errors = validate_ltx_prompt_build(build, valid_video_intent())

    assert any("dialogue" in error for error in errors)
    assert any("Chinese dialogue" in error for error in errors)


def test_evidence_bound_ltx_build_requires_attributed_speaker_in_both_prompts():
    build = valid_evidence_bound_video_build()
    build["dialogue_attribution"][0]["speaker"] = "旁白"
    build["dialogue_attribution"][0]["speaker_en"] = "Narrator"

    errors = validate_ltx_prompt_build(build, valid_video_intent())

    assert any("speaker" in error for error in errors)


def test_quoted_signage_is_not_inferred_as_unattributed_dialogue():
    build = valid_evidence_bound_video_build()
    positive_zh = (
        "参考图1（人物）：保持同一位女剑士与同一庭院。"
        "女剑士抬剑，布料和头发持续飘动，镜头缓慢推进。"
        "〖0-1.7 s〗女剑士抬头。〖1.7-4.2 s〗女剑士走过写有“青云客栈”的招牌。"
    )
    positive_en = (
        "Reference image 1 (character): preserve the same swordswoman and courtyard. "
        "The swordswoman raises her sword as cloth and hair trail continuously; the camera slowly dollies in. "
        "〖0-1.7 s〗The swordswoman looks up. "
        "〖1.7-4.2 s〗The swordswoman passes a sign titled “青云客栈”."
    )
    build.update(
        {
            "prompt": positive_en,
            "positive_zh": positive_zh,
            "positive_en": positive_en,
            "timeline_segments": [
                {
                    "start": 0.0,
                    "end": 1.7,
                    "text_zh": "女剑士抬头。",
                    "text_en": "The swordswoman looks up.",
                },
                {
                    "start": 1.7,
                    "end": 4.2,
                    "text_zh": "女剑士走过写有“青云客栈”的招牌。",
                    "text_en": "The swordswoman passes a sign titled “青云客栈”.",
                },
            ],
            "dialogue_attribution": [],
        }
    )

    assert validate_ltx_prompt_build(build, valid_video_intent()) == []


def test_explicit_dialogue_marker_requires_attribution_without_quotation_marks():
    errors = prompt_quality._validate_dialogue(
        [],
        "对白：快走。",
        "Dialogue: Go now.",
    )

    assert any("speaker attribution" in error for error in errors)


def test_evidence_bound_ltx_build_rejects_a_second_negative_channel():
    build = valid_evidence_bound_video_build()
    build["negative_prompt_en"] = "watermark"

    errors = validate_ltx_prompt_build(build, valid_video_intent())

    assert any("second negative" in error for error in errors)


def test_evidence_bound_ltx_build_selects_exactly_one_global_prompt():
    build = valid_evidence_bound_video_build()
    build["global_prompt"] = "Follow the script's event order."

    errors = validate_ltx_prompt_build(build, valid_video_intent())

    assert any("global prompt" in error for error in errors)


def test_evidence_bound_ltx_build_requires_split_for_complex_intent():
    intent = valid_video_intent()
    intent["core_characters"] = ["a", "b", "c", "d"]
    build = valid_evidence_bound_video_build()

    errors = validate_ltx_prompt_build(build, intent)

    assert any("split recommendation" in error for error in errors)


def test_evidence_bound_ltx_build_rejects_missing_continuity_and_extreme_wide_default():
    build = valid_evidence_bound_video_build()
    build["continuity_requirements"] = []
    build["positive_en"] = build["positive_en"].replace(
        "camera slowly dollies in", "camera uses an extreme-wide shot"
    )
    build["prompt"] = build["positive_en"]

    errors = validate_ltx_prompt_build(build, valid_video_intent())

    assert any("continuity" in error for error in errors)
    assert any("extreme-wide" in error for error in errors)


def test_evidence_bound_ltx_build_rejects_a_second_narrative_layer():
    build = valid_evidence_bound_video_build()
    build["narrative_layers"] = ["shot premise", "the same shot retold"]

    errors = validate_ltx_prompt_build(build, valid_video_intent())

    assert any("narrative layers" in error for error in errors)


def test_complete_evidence_bound_ltx_build_passes_without_mutation():
    build = valid_evidence_bound_video_build()
    intent = valid_video_intent()
    original_build = deepcopy(build)
    original_intent = deepcopy(intent)

    assert validate_ltx_prompt_build(build, intent) == []
    assert build == original_build
    assert intent == original_intent
