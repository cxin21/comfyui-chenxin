import json
import subprocess
import sys
from pathlib import Path

# Allow tests to import internals.* siblings without a package install.
INTERNALS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERNALS_DIR.parent))

from internals.recipe_lookup import _match_recipe, _parse_recipes, RECIPES_PATH  # noqa: E402

# CLI subprocess tests target the worktree copy of the script (same convention
# as test_scene_match / test_tag_lookup). Brief's verbatim hard-coded
# `D:/Projects/comfyui-chenxin/...` main-checkout path doesn't exist because
# Task 1 placed files in the worktree.
WORKSPACE = Path(__file__).resolve().parents[4]
RECIPE_LOOKUP = WORKSPACE / "skills" / "prompt-forge" / "internals" / "recipe_lookup.py"


def test_exact_match_returns_score_one():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "anima")
    assert result is not None
    assert score == 1.0
    assert path == "exact"


def test_alias_match_resolves_to_canonical():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "anima_baseV10")
    assert result is not None
    assert score == 0.95
    assert path == "alias"
    assert result["frontmatter"]["id"] == "anima"


def test_weighted_fuzzy_match():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "stable_diffusion_xl")
    assert result is not None
    assert path in ("alias", "weighted_fuzzy")
    assert result["frontmatter"]["id"] == "sdxl"


def test_no_match_returns_none():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "totally_made_up_xyz")
    assert result is None


def test_no_short_query_fuzzy_match():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "__nonexistent")
    assert result is None
    assert score == 0.0
    assert path == "none"


def test_backwards_compat_v4_signature():
    text = RECIPES_PATH.read_text(encoding="utf-8")
    recipes = _parse_recipes(text)
    result, score, path = _match_recipe(recipes, "anima")
    assert "matched" in result
    assert "matched_id" in result
    assert "heading" in result
    assert "frontmatter" in result
    assert "dialect_block" in result
    assert "score" in result
    assert "match_path" in result


def test_cli_alias_resolution():
    r = subprocess.run(
        ["python", str(RECIPE_LOOKUP), "--check-alias", "anima_baseV10"],
        capture_output=True, text=True,
        cwd=str(WORKSPACE),
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["canonical"] == "anima"


def test_cli_anima_backwards_compat():
    r = subprocess.run(
        ["python", str(RECIPE_LOOKUP), "--model", "anima"],
        capture_output=True, text=True,
        cwd=str(WORKSPACE),
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["matched"] is True
    assert data["matched_id"] == "anima"
    assert "frontmatter" in data
    assert "dialect_block" in data
    assert data["score"] == 1.0
    assert data["match_path"] == "exact"


def test_cli_list_aliases():
    r = subprocess.run(
        ["python", str(RECIPE_LOOKUP), "--list-aliases"],
        capture_output=True, text=True,
        cwd=str(WORKSPACE),
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "anima_basev10" in data
    assert "stable_diffusion_xl" in data
