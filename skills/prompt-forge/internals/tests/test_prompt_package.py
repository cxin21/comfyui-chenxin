import re
import sys
from pathlib import Path
import pytest

PROMPT_FORGE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROMPT_FORGE))
from internals.dialect_lookup import lookup_dialect  # noqa: E402
from internals.prompt_package import lint_prompt_text, validate_draft  # noqa: E402


def _evidence():
    return {
        "shared_known": [{"value": "a swordsman in a red robe", "origin": "explicit"}],
        "locked_facts": ["a swordsman in a red robe"],
        "continuity_locks": {"identity": ["red robe"]},
        "assistant_known_user_unknown": [],
        "uncertainty": [],
    }


def _video_draft():
    return {
        "positive_zh": "红衣剑客在雨夜巷道拔剑。",
        "positive_en": "A swordsman in a red robe draws his sword in a rainy night alley.",
        "global_prompt": "A swordsman in a red robe, restrained cinematic motion.",
        "timeline_segments": [
            {"start": 0.0, "end": 2.0, "zh": "剑客转身。", "en": "The swordsman turns."},
            {"start": 2.0, "end": 4.0, "zh": "剑客拔剑。", "en": "The swordsman draws his sword."},
        ],
        "dialogue_attribution": [
            {"speaker": "swordsman", "text": "Stop", "start": 2.5, "end": 3.0}
        ],
        "continuity_locks": ["red robe", "same sword", "rain continues"],
    }


def test_lint_prompt_text_is_deterministic_for_placeholders_and_patterns():
    text = "A hero with [TODO] and a watermark."
    expected = ["placeholder: [TODO]", "forbidden pattern: watermark", "forbidden pattern: hero"]
    assert lint_prompt_text(text, ["watermark", "hero"]) == expected
    assert lint_prompt_text(text, ["watermark", "hero"]) == expected


def test_image_negative_policy_rejects_flux_but_accepts_anima_and_sdxl():
    evidence = _evidence()
    for dialect_id in ("anima", "sdxl"):
        package = validate_draft(
            {"positive": "a swordsman in a red robe", "negative": "watermark"},
            evidence,
            lookup_dialect(dialect_id),
        )
        assert package["negative"] == "watermark"
        assert package["quality"]["ready_for_review"] is True
        assert "timeline_segments" not in package

    flux = validate_draft(
        {"positive": "a swordsman in a red robe", "negative": "watermark"},
        evidence,
        lookup_dialect("flux"),
    )
    assert "negative" not in flux
    assert any("negative" in error for error in flux["errors"])
    assert flux["quality"]["ready_for_review"] is False


def test_missing_explicit_fact_and_placeholder_are_reported():
    package = validate_draft(
        {"positive": "A lone traveler in [TODO]."}, _evidence(), lookup_dialect("flux")
    )
    assert any("missing explicit fact" in warning for warning in package["warnings"])
    assert any("placeholder" in error for error in package["errors"])
    assert package["quality"]["facts_preserved"] is False


def test_video_package_validates_bilingual_contiguous_timeline_dialogue_and_continuity():
    package = validate_draft(_video_draft(), _evidence(), lookup_dialect("ltx_2_3"))
    assert package["target"] == "video"
    assert re.search(r"[\u4e00-\u9fff]", package["positive_zh"])
    for segment in package["timeline_segments"]:
        assert segment["zh"] != segment["en"]
        assert re.search(r"[\u4e00-\u9fff]", segment["zh"])
    assert package["positive_en"].startswith("A swordsman")
    assert package["global_prompt"].startswith("A swordsman")
    assert package["timeline_segments"][0]["start"] == 0.0
    assert package["timeline_segments"][0]["end"] == package["timeline_segments"][1]["start"]
    assert package["dialogue_attribution"][0]["speaker"] == "swordsman"
    assert package["continuity_locks"] == ["red robe", "same sword", "rain continues"]
    assert "positive" not in package and "negative" not in package
    assert package["quality"]["temporal_logic_valid"] is True
    assert package["quality"]["ready_for_review"] is True


def test_video_timeline_gaps_dialogue_ranges_and_missing_continuity_fail_review():
    draft = _video_draft()
    draft["timeline_segments"][1]["start"] = 2.5
    draft["dialogue_attribution"][0]["end"] = 5.0
    draft["continuity_locks"] = []
    package = validate_draft(draft, _evidence(), lookup_dialect("ltx_2_3"))
    assert package["quality"]["temporal_logic_valid"] is False
    assert package["quality"]["ready_for_review"] is False
    assert any("timeline" in error for error in package["errors"])
    assert any("dialogue" in error for error in package["errors"])
    assert any("continuity" in error for error in package["errors"])


def test_validate_draft_rejects_snake_case_and_camel_case_execution_fields():
    forbidden_keys = (
        "workflow_hash", "workflowHash", "WorkflowHash", "nodeId",
        "executionState", "gpuMemory", "runtimeOptions",
    )
    for key in forbidden_keys:
        draft = _video_draft()
        draft["metadata"] = {"nested": {key: "forbidden"}}
        with pytest.raises(ValueError):
            validate_draft(draft, _evidence(), lookup_dialect("ltx_2_3"))

def test_validate_draft_rejects_execution_metadata_inside_public_dialect_argument():
    for key in ("workflowHash", "NodeId", "executionState"):
        dialect = lookup_dialect("flux")
        dialect["reference_rules"] = {"nested": {key: "forbidden"}}
        with pytest.raises(ValueError):
            validate_draft(
                {"positive": "a swordsman in a red robe"}, _evidence(), dialect
            )


def test_validate_draft_allows_model_id_in_evidence():
    evidence = _evidence()
    evidence["model_id"] = "flux-dev"
    package = validate_draft(
        {"positive": "a swordsman in a red robe"}, evidence, lookup_dialect("flux")
    )
    assert package["quality"]["ready_for_review"] is True
