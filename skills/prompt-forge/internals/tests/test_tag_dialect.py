from pathlib import Path

from internals.tag_lookup import load_index, validate_tags


WORKSPACE = Path(__file__).resolve().parents[4]
INDEX = WORKSPACE / "skills/prompt-forge/dictionary/tag-index.json"


def _index():
    return {
        "by_canonical": {
            "long_hair": {"cat": 0, "count": 10, "aliases": ["/lh"]},
            "elf": {"cat": 0, "count": 8, "aliases": ["pointy_ears"]},
            "1girl": {"cat": 0, "count": 20, "aliases": []},
        },
        "by_alias": {"/lh": ["long_hair"], "pointy_ears": ["elf"]},
    }


def test_validate_tags_accepts_only_exact_canonical_and_approved_aliases():
    result = validate_tags(
        ["long_hair", "/lh", "hair", "Long_Hair", "pointy_ears"], _index()
    )
    assert result["validated"] == ["long_hair", "elf"]
    assert result["rejected"] == ["hair", "Long_Hair"]
    assert result["duplicates"] == ["long_hair"]
    assert result["recipe_control_tokens"] == []


def test_explicit_alias_table_restricts_which_aliases_are_approved():
    result = validate_tags(
        ["/lh", "approved_elf"], _index(), aliases={"approved_elf": "elf"}
    )
    assert result["validated"] == ["elf"]
    assert result["rejected"] == ["/lh"]


def test_unknown_and_ambiguous_aliases_never_become_canonical():
    result = validate_tags(
        ["long hair", "mystery", "ambiguous", "mystery"],
        _index(),
        aliases={"mystery": "not_in_index", "ambiguous": ["elf", "long_hair"]},
    )
    assert result["validated"] == []
    assert result["rejected"] == ["long hair", "mystery", "ambiguous"]
    assert result["duplicates"] == ["mystery"]


def test_recipe_control_tokens_are_separate_and_duplicates_are_stable():
    result = validate_tags(
        ["score_9", "1girl", "BREAK", "score_9", "1girl", "score_8_up"], _index()
    )
    assert result["validated"] == ["1girl"]
    assert result["rejected"] == []
    assert result["recipe_control_tokens"] == ["score_9", "BREAK", "score_8_up"]
    assert result["duplicates"] == ["score_9", "1girl"]


def test_runtime_index_validates_without_raw_dictionary_imports():
    index = load_index(INDEX)
    result = validate_tags(["long_hair", "/lh", "definitely_unknown"], index)
    assert result["validated"] == ["long_hair"]
    assert result["duplicates"] == ["long_hair"]
    assert result["rejected"] == ["definitely_unknown"]