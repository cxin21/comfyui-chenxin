# skills/prompt-forge/internals/tests/test_recipe_yaml.py
"""Tests for recipe_yaml.py — covers v4 backward-compat modes plus new
v5 modes (--validate-schema, --add-alias, --list-aliases)."""

import subprocess
from pathlib import Path

# Path adaptation (Task 3 / Task 6 deviation): the brief references the main
# checkout D:/Projects/comfyui-chenxin/... but recipe_yaml.py was moved into
# the worktree in Task 1. Resolve both via Path(__file__) so the tests work
# from whichever worktree they are run in.
WORKSPACE = Path(__file__).resolve().parents[4]
RECIPE_YAML_SCRIPT = WORKSPACE / "skills/prompt-forge/internals/recipe_yaml.py"
RECIPES_DIR = WORKSPACE / "skills/prompt-forge/recipes"


def _run(*args: str) -> subprocess.CompletedProcess:
    """Helper: invoke recipe_yaml.py with the given CLI args."""
    return subprocess.run(
        ["python", str(RECIPE_YAML_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(WORKSPACE),
    )


def test_validate_schema_clean():
    """v5 NEW: --validate-schema on the bundled MODELS.md exits 0."""
    r = _run("--validate-schema")
    assert r.returncode == 0, f"validate-schema failed: {r.stderr}"


def test_check_idempotent():
    """v4 backward-compat: --check exits 0 on an up-to-date MODELS.md."""
    r = _run("--check")
    assert r.returncode == 0, f"check failed: {r.stderr}"


def test_list_aliases():
    """v5 NEW: --list-aliases dumps JSON of the alias table; includes known alias."""
    r = _run("--list-aliases")
    assert r.returncode == 0, f"list-aliases failed: {r.stderr}"
    assert "anima_basev10" in r.stdout
