"""Contract tests for the prompt-language dialect registry."""

import json
import sys

import pytest
from pathlib import Path


PROMPT_FORGE = Path(__file__).resolve().parents[2]
DIALECTS_DIR = PROMPT_FORGE / "dialects"
sys.path.insert(0, str(PROMPT_FORGE))

from internals.dialect_lookup import lookup_dialect  # noqa: E402
REQUIRED_FIELDS = {
    "id",
    "modality",
    "prompt_form",
    "ordering",
    "negative_policy",
    "reference_rules",
    "required_dimensions",
    "forbidden_patterns",
    "source_notes",
}
FORBIDDEN_EXECUTION_FIELDS = {"workflow", "node", "hash", "gpu", "execution"}


def _load_json(name: str):
    return json.loads((DIALECTS_DIR / name).read_text(encoding="utf-8"))


def _dialects_by_id():
    return {
        entry["id"]: entry
        for filename in ("image.json", "video.json")
        for entry in _load_json(filename)["dialects"]
    }


def _keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key.lower()
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def test_supported_dialects_resolve_to_expected_modality_and_prompt_form():
    expected = {
        "anima": ("image", "tag_then_natural_language"),
        "flux": ("image", "natural_language_paragraph"),
        "ltx_2_3": ("video", "shot_opening_motion_sequence"),
        "wan_2_7": ("video", "cinematic_shot_description"),
        "kling_kuaishou": ("video", "natural_language_motion_description"),
        "sora_2_sora_2_pro": ("video", "storyboard_sketch"),
    }

    dialects = _dialects_by_id()

    for dialect_id, (modality, prompt_form) in expected.items():
        assert dialects[dialect_id]["modality"] == modality
        assert dialects[dialect_id]["prompt_form"] == prompt_form


def test_index_exposes_canonical_ids_and_aliases():
    index = _load_json("index.json")
    canonical_ids = {entry["id"] for entry in index["dialects"]}
    aliases = {
        alias
        for entry in index["dialects"]
        for alias in entry["aliases"]
    }

    assert {"anima", "flux", "ltx_2_3", "wan_2_7", "kling_kuaishou", "sora_2_sora_2_pro"} <= canonical_ids
    assert {"ltx", "wan", "kling", "sora"} <= aliases


def test_index_aliases_are_deterministic_lists():
    for entry in _load_json("index.json")["dialects"]:
        assert isinstance(entry["aliases"], list)
        assert entry["aliases"] == sorted(set(entry["aliases"]))


def test_index_canonical_ids_match_registry_once():
    index_ids = [entry["id"] for entry in _load_json("index.json")["dialects"]]
    registry_ids = set(_dialects_by_id())

    assert len(index_ids) == len(set(index_ids))
    assert set(index_ids) == registry_ids


def test_aliases_do_not_collide_with_canonical_ids_or_each_other():
    entries = _load_json("index.json")["dialects"]
    canonical_ids = {entry["id"] for entry in entries}
    aliases = [alias for entry in entries for alias in entry["aliases"]]

    assert canonical_ids.isdisjoint(aliases)
    assert len(aliases) == len(set(aliases))


def test_registry_preserves_broad_image_and_video_recipe_coverage():
    expected_ids = {
        "z_image_turbo", "stable_diffusion_3_5_large", "hidream_i1", "bria_3_x",
        "omnigen_unified_gen_edit", "chroma", "krea_2", "ernie_image", "recraft",
        "nano_banana", "grok_image", "reve", "kandinsky", "svd",
    }
    assert expected_ids <= _dialects_by_id().keys()


def test_video_registry_excludes_audio_prompt_knowledge():
    assert "audio" not in json.dumps(_load_json("video.json"), ensure_ascii=False).lower()


def test_dialect_entries_are_complete_and_unique():
    entries = [
        entry
        for filename in ("image.json", "video.json")
        for entry in _load_json(filename)["dialects"]
    ]

    assert len({entry["id"] for entry in entries}) == len(entries)
    for entry in entries:
        assert REQUIRED_FIELDS <= entry.keys()


def test_registries_exclude_execution_metadata():
    registry_documents = [_load_json(name) for name in ("index.json", "image.json", "video.json")]

    for document in registry_documents:
        assert FORBIDDEN_EXECUTION_FIELDS.isdisjoint(_keys(document))


def test_lookup_dialect_resolves_exact_id_and_alias():
    assert lookup_dialect("flux")["id"] == "flux"
    assert lookup_dialect("ltx")["id"] == "ltx_2_3"


def test_lookup_dialect_rejects_substrings_and_modality_mismatch():
    with pytest.raises(ValueError):
        lookup_dialect("wan_2_")
    with pytest.raises(ValueError):
        lookup_dialect("anima", modality="video")