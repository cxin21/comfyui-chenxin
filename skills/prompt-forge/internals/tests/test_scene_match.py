# skills/prompt-forge/internals/tests/test_scene_match.py
import json
from pathlib import Path
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


def test_match_no_keywords_miss_returns_presets():
    idx = load_index(INDEX)
    results = match(idx, "完全无关的查询 xyz123", top=3, presets_path=PRESETS)
    assert len(results) >= 1


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
