"""Contract tests for reusable visual-language style entries."""

import copy
import json
import sys
from pathlib import Path


PROMPT_FORGE = Path(__file__).resolve().parents[2]
STYLES_DIR = PROMPT_FORGE / "styles"
sys.path.insert(0, str(PROMPT_FORGE))

from internals.style_lookup import render_style, suggest_styles  # noqa: E402
REQUIRED_FIELDS = {"id", "axes", "visual_fingerprint", "renderings", "incompatible_styles"}
FORBIDDEN_EXECUTION_FIELDS = {"workflow", "node", "hash", "gpu", "execution"}


def _load_json(name: str):
    return json.loads((STYLES_DIR / name).read_text(encoding="utf-8"))


def _keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key.lower()
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def test_xianxia_cinematic_exposes_the_required_visual_language_axes():
    styles = {entry["id"]: entry for entry in _load_json("visual-language.json")["styles"]}
    style = styles["xianxia_cinematic"]

    assert {"lighting", "color", "composition", "material", "rendering"} <= style["axes"].keys()
    assert all(style["axes"][axis] for axis in ("lighting", "color", "composition", "material", "rendering"))


def test_style_entries_are_complete_and_indexed_once():
    document = _load_json("visual-language.json")
    entries = document["styles"]
    index = _load_json("index.json")

    assert len({entry["id"] for entry in entries}) == len(entries)
    assert {entry["id"] for entry in entries} == {entry["id"] for entry in index["styles"]}
    for entry in entries:
        assert REQUIRED_FIELDS <= entry.keys()


def test_style_registries_exclude_execution_metadata():
    for document in [_load_json("index.json"), _load_json("visual-language.json")]:
        assert FORBIDDEN_EXECUTION_FIELDS.isdisjoint(_keys(document))

def test_suggest_styles_returns_explicit_advice_without_random_fallback():
    exact = suggest_styles("cinematic_xianxia")
    assert exact[0]["id"] == "xianxia_cinematic"
    assert exact[0]["score"] == 0.95
    assert exact[0]["evidence"] == ["alias:cinematic_xianxia"]
    assert suggest_styles("totally unrelated geometry") == []


def test_style_suggestions_and_rendering_do_not_mutate_inputs():
    style = _load_json("visual-language.json")["styles"][0]
    dialect = json.loads((PROMPT_FORGE / "dialects" / "image.json").read_text(encoding="utf-8"))["dialects"][0]
    before_style = copy.deepcopy(style)
    before_dialect = copy.deepcopy(dialect)

    suggestions = suggest_styles("jade mist cinematic", limit=1)
    rendered = render_style(style, dialect)

    assert suggestions[0]["id"] == "xianxia_cinematic"
    assert suggestions[0]["score"] > 0
    assert suggestions[0]["evidence"]
    assert rendered["style_id"] == "xianxia_cinematic"
    assert rendered["dialect_id"] == dialect["id"]
    assert rendered["visual_language"]["mode"] == "tags"
    assert style == before_style
    assert dialect == before_dialect