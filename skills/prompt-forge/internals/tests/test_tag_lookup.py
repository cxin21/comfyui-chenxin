# skills/prompt-forge/internals/tests/test_tag_lookup.py
import json
from pathlib import Path
from internals.tag_lookup import load_index, lookup, lookup_many


WORKSPACE = Path(__file__).resolve().parents[4]
INDEX = WORKSPACE / "skills/prompt-forge/dictionary/tag-index.json"


def test_load_index():
    idx = load_index(INDEX)
    assert "by_canonical" in idx
    assert "by_alias" in idx
    assert "long_hair" in idx["by_canonical"]


def test_lookup_exact_canonical():
    idx = load_index(INDEX)
    results = lookup(idx, "long_hair")
    assert len(results) >= 1
    assert results[0]["canonical"] == "long_hair"
    assert results[0]["count"] > 1000000


def test_lookup_via_alias():
    idx = load_index(INDEX)
    results = lookup(idx, "/lh")
    assert len(results) >= 1
    assert any(r["canonical"] == "long_hair" for r in results)


def test_lookup_substring_match():
    idx = load_index(INDEX)
    results = lookup(idx, "hair", limit=10)
    assert len(results) >= 1
    assert all("hair" in r["canonical"].lower() for r in results)


def test_lookup_cjk_substring():
    idx = load_index(INDEX)
    results = lookup(idx, "金发")
    assert isinstance(results, list)


def test_lookup_no_match():
    idx = load_index(INDEX)
    results = lookup(idx, "definitely_nonexistent_xyz_12345")
    assert results == []


def test_lookup_category_filter():
    idx = load_index(INDEX)
    results = lookup(idx, "1girl", category=0)
    assert all(r.get("category") == 0 for r in results)


def test_lookup_respects_limit():
    idx = load_index(INDEX)
    results = lookup(idx, "hair", limit=3)
    assert len(results) <= 3


def test_lookup_many_keeps_candidates_independent():
    idx = load_index(INDEX)
    results = lookup_many(idx, ["blonde_hair", "elf"], exact=True)
    assert [item["query"] for item in results] == ["blonde_hair", "elf"]
    assert results[0]["results"][0]["canonical"] == "blonde_hair"
    assert results[1]["results"][0]["canonical"] == "elf"


def test_cli_query_long_hair():
    import subprocess

    script = WORKSPACE / "skills/prompt-forge/internals/tag_lookup.py"
    r = subprocess.run(
        ["python", str(script), "--query", "long_hair"],
        capture_output=True,
        text=True,
        cwd=str(WORKSPACE),
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert any(t["canonical"] == "long_hair" for t in data)


def test_cli_queries_returns_per_candidate_results():
    import subprocess

    script = WORKSPACE / "skills/prompt-forge/internals/tag_lookup.py"
    r = subprocess.run(
        ["python", str(script), "--queries", "blonde_hair", "elf", "--exact"],
        capture_output=True,
        text=True,
        cwd=str(WORKSPACE),
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert [item["query"] for item in data] == ["blonde_hair", "elf"]
    assert all(item["results"] for item in data)
