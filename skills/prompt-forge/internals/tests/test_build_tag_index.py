# skills/prompt-forge/internals/tests/test_build_tag_index.py
import json
from pathlib import Path
import tempfile
from internals.build_tag_index import parse_danbooru_csv, build_index, write_index


# Workspace is the worktree; brief paths assume the main checkout.
WORKSPACE = Path("D:/Projects/comfyui-chenxin/.worktrees/prompt-forge-v5")
DANBOORU_CSV = WORKSPACE / "skills/prompt-forge/dictionary/danbooru.csv"
BUILD_SCRIPT = WORKSPACE / "skills/prompt-forge/internals/build_tag_index.py"
INDEX_JSON = WORKSPACE / "skills/prompt-forge/dictionary/tag-index.json"


def test_parse_danbooru_csv_first_row():
    rows = parse_danbooru_csv(DANBOORU_CSV)
    assert len(rows) > 100000
    first = rows[0]
    assert "name" in first and "category" in first and "count" in first and "aliases" in first


def test_parse_danbooru_csv_long_hair_row():
    rows = parse_danbooru_csv(DANBOORU_CSV)
    long_hair = next((r for r in rows if r["name"] == "long_hair"), None)
    assert long_hair is not None
    assert long_hair["count"] > 1000000
    assert "/lh" in long_hair["aliases"]


def test_build_index_has_by_canonical_and_by_alias():
    rows = parse_danbooru_csv(DANBOORU_CSV)
    idx = build_index(rows, version="test")
    assert "by_canonical" in idx
    assert "by_alias" in idx
    assert "long_hair" in idx["by_canonical"]
    assert idx["by_canonical"]["long_hair"]["count"] > 1000000


def test_build_index_meta():
    rows = parse_danbooru_csv(DANBOORU_CSV)
    idx = build_index(rows, version="test-version")
    assert idx["_meta"]["version"] == "test-version"
    assert idx["_meta"]["row_count"] == len(rows)


def test_write_index_atomic():
    rows = parse_danbooru_csv(DANBOORU_CSV)
    idx = build_index(rows, version="test")
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "tag-index.json"
        write_index(idx, out)
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["_meta"]["version"] == "test"


def test_cli_build_runs():
    import subprocess
    r = subprocess.run(
        ["python", str(BUILD_SCRIPT)],
        capture_output=True, text=True,
        cwd=str(WORKSPACE),
    )
    assert r.returncode == 0
    assert INDEX_JSON.exists()
