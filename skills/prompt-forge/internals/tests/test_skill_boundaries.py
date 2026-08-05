import json
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[2]
INTERNALS = SKILL_DIR / "internals"


def _keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).casefold()
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def _evidence():
    return {
        "shared_known": [{"value": "a red-robed swordsman", "origin": "explicit"}],
        "locked_facts": ["a red-robed swordsman"],
        "continuity_locks": {"identity": ["red robe"]},
    }


def test_prompt_forge_source_has_no_runtime_imports():
    forbidden = re.compile(
        r"(?:comfyui|mcp|workflow_profile|workflow_discovery|character_video_pipeline|runtime\.mcp)",
        re.IGNORECASE,
    )
    for path in INTERNALS.rglob("*.py"):
        if "tests" in path.parts or "__pycache__" in path.parts:
            continue
        assert forbidden.search(path.read_text(encoding="utf-8")) is None, path


def test_compile_requires_a_caller_authored_draft_and_has_no_execution_fields():
    from internals.prompt_compile import compile_prompt

    with pytest.raises(ValueError):
        compile_prompt(_evidence(), draft=None, dialect_id="flux")

    package = compile_prompt(
        _evidence(),
        draft={"positive": "A red-robed swordsman in a moonlit alley."},
        dialect_id="flux",
    )
    forbidden = {"ready_to_execute", "execution", "workflow", "node", "gpu", "hash"}
    assert forbidden.isdisjoint(set(_keys(package)))


def test_public_boundary_documents_name_the_llm_author_and_external_pipeline():
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    spec = (SKILL_DIR / "SPEC.md").read_text(encoding="utf-8")
    combined = skill + "\n" + spec
    assert "Claude or Codex" in combined
    assert "PromptPackage" in combined
    assert "character-video-pipeline" in combined
    assert "never generates fallback prose" in combined


def test_registry_files_are_json_data_not_runtime_configuration():
    for path in (
        SKILL_DIR / "dialects/index.json",
        SKILL_DIR / "dialects/image.json",
        SKILL_DIR / "dialects/video.json",
        SKILL_DIR / "styles/index.json",
        SKILL_DIR / "styles/visual-language.json",
    ):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert {"workflow", "node", "hash", "gpu", "execution"}.isdisjoint(set(_keys(document)))
