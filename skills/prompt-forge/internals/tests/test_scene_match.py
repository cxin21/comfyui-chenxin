# skills/prompt-forge/internals/tests/test_scene_match.py
import json
from pathlib import Path
import tempfile
from internals.scene_match import load_index, match


# Path adaptation (Task 3 deviation): the brief's test references the main
# checkout D:/Projects/comfyui-chenxin/... but the dictionary + scene files
# were copied into the worktree in Task 1. Tests run from the worktree.
WORKSPACE = Path(__file__).resolve().parents[4]
INDEX = WORKSPACE / "skills/prompt-forge/aesthetics/INDEX.md"
PRESETS = WORKSPACE / "skills/prompt-forge/aesthetics/style-presets.md"
SCENE_MATCH_SCRIPT = WORKSPACE / "skills/prompt-forge/internals/scene_match.py"


def test_load_index():
    idx = load_index(INDEX)
    assert len(idx) >= 10
    assert all("scene" in e and "keywords" in e and "lighting" in e for e in idx)


def test_match_clear_hit():
    idx = load_index(INDEX)
    results = match(idx, "夜景 霓虹", top=3)
    assert len(results) >= 1
    assert results[0]["scene"] == "night_street"
    assert "夜景" in results[0]["keywords_matched"]


def test_match_english_scene_terms():
    idx = load_index(INDEX)
    results = match(idx, "neon urban street", top=3)
    assert results[0]["scene"] == "night_street"
    assert "neon" in results[0]["keywords_matched"]


def test_match_no_keywords_miss_returns_presets():
    idx = load_index(INDEX)
    results = match(idx, "完全无关的查询 xyz123", top=3, presets_path=PRESETS)
    assert results[0]["scene"] == "_no_scene_match"
    assert results[0]["requires_selection"] is True
    assert all(choice["scene"].startswith("_preset:") for choice in results[0]["choices"])


def test_generic_soft_word_is_not_enough_to_choose_overcast():
    idx = load_index(INDEX)
    results = match(idx, "soft portrait", top=3, presets_path=PRESETS)
    assert results[0]["scene"] == "_no_scene_match"


def test_match_top_n():
    idx = load_index(INDEX)
    results = match(idx, "光 摄影", top=2)
    assert len(results) <= 2


def test_match_score_threshold():
    idx = load_index(INDEX)
    results = match(idx, "夜景", top=10)
    for r in results:
        if r.get("keywords_matched"):
            assert r["score"] >= 0.2


def test_load_index_ignores_frontmatter_by_behavior():
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write("---\nokm: dated\nkind: knowledge\n---\n\n")
        handle.write("| scene | keywords | lighting | composition | color |\n")
        handle.write("|---|---|---|---|---|\n")
        handle.write("| my_scene | foo,bar | light | composition | color |\n")
        path = Path(handle.name)
    try:
        entries = load_index(path)
        assert len(entries) == 1
        assert entries[0]["scene"] == "my_scene"
    finally:
        path.unlink()


def test_cli_query_night():
    import subprocess
    r = subprocess.run(
        ["python", str(SCENE_MATCH_SCRIPT), "--query", "夜景", "--top", "1"],
        capture_output=True, text=True,
        cwd=str(WORKSPACE),
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data[0]["scene"] == "night_street"
