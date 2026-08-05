import json
from pathlib import Path

from internals.evaluate import evaluate_cases

SKILL_DIR = Path(__file__).resolve().parents[2]


def _all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_keys(child)


def test_prompt_package_corpus_covers_image_video_and_invalid_review_gate():
    result = evaluate_cases(SKILL_DIR / "evals/prompt-package-cases.json")
    assert result["case_count"] == 3
    assert result["passed"] == 3
    assert result["failed"] == 0
    assert result["pass_rate"] == 1.0, result["rows"]
    case_ids = {row["case_id"] for row in result["rows"]}
    assert case_ids == {
        "image-flux-reviewable",
        "video-ltx-reviewable",
        "image-placeholder-and-fact-gap",
    }
    assert any(row["package"]["target"] == "image" for row in result["rows"])
    video = next(row["package"] for row in result["rows"] if row["package"]["target"] == "video")
    assert any("\u4e00" <= char <= "\u9fff" for char in video["positive_zh"])
    for segment in video["timeline_segments"]:
        assert segment["zh"] != segment["en"]
        assert any("\u4e00" <= char <= "\u9fff" for char in segment["zh"])
    assert any(row["package"]["quality"]["ready_for_review"] is False for row in result["rows"])
    for row in result["rows"]:
        assert {"execution", "ready_to_execute"}.isdisjoint(_all_keys(row["package"]))


def test_trigger_corpus_has_balanced_positive_and_negative_cases():
    rows = [
        json.loads(line)
        for line in (SKILL_DIR / "evals/trigger-cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    labels = [row["label"] for row in rows]
    assert len(rows) >= 20
    assert labels.count("should_trigger") >= 10
    assert labels.count("should_not_trigger") >= 10
    assert all(row["expected_skill"] == "prompt-forge" for row in rows)

def test_virgin_cleanup_removes_obsolete_surfaces_and_keeps_runtime_indexes():
    obsolete = [
        "recipes/MODELS.md",
        "models/INDEX.md",
        "references/concept-map.md",
        "internals/recipe_lookup.py",
        "internals/recipe_yaml.py",
        "internals/scene_match.py",
        "internals/build_tag_index.py",
        "aesthetics/concept-archetypes.md",
        "aesthetics/video-archetypes.md",
        "negative/negative-prompts.md",
        "hardware/8gb.json",
        "dictionary/danbooru.csv",
        "dictionary/wd14-tags.csv",
        "internals/tests/test_recipe_lookup.py",
        "internals/tests/test_recipe_yaml.py",
        "internals/tests/test_scene_match.py",
        "internals/tests/test_build_tag_index.py",
        "internals/tests/test_aliases.py",
    ]
    assert not [relative for relative in obsolete if (SKILL_DIR / relative).exists()]
    assert (SKILL_DIR / "dictionary/tag-index.json").is_file()
    assert (SKILL_DIR / "dictionary/zh-en.json").is_file()
    python_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (SKILL_DIR / "internals").rglob("*.py")
    )
    for retired_import in ("recipe_lookup", "recipe_yaml", "scene_match", "build_tag_index"):
        assert f"import {retired_import}" not in python_sources
        assert f"from internals.{retired_import}" not in python_sources
