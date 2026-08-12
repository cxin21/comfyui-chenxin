from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.verify_release import (
    ReleaseVerificationError,
    compare_source_cache,
    verify_dictionary_release,
    verify_greenfield_shape,
    verify_plugin_manifest,
    verify_python_packages,
    verify_public_surface,
    source_cache_key_files,
    verify_tokenizer_snapshot,
)
from scripts.stage_release import ReleaseStagingError, stage_release


REPO = Path(__file__).resolve().parents[3]
PROMPT_FORGE = REPO / "skills" / "prompt-forge"


def test_plugin_manifest_is_valid_and_contains_no_old_package_language() -> None:
    report = verify_plugin_manifest(REPO)
    assert report["name"] == "comfyui-chenxin"
    assert report["version"].startswith("0.2.0+")


def test_python_package_versions_and_tokenizer_runtime_are_release_locked() -> None:
    report = verify_python_packages(REPO)
    assert report == {"packages": 5, "tokenizers": "0.22.2"}


def test_tokenizer_verifier_fails_for_missing_and_modified_assets(tmp_path: Path) -> None:
    source = PROMPT_FORGE / "knowledge" / "tokenizers" / "anima-qwen3-0.6b"
    snapshot = tmp_path / "snapshot"
    shutil.copytree(source, snapshot)
    (snapshot / "tokenizer.json").unlink()
    with pytest.raises(ReleaseVerificationError, match="missing"):
        verify_tokenizer_snapshot(snapshot)

    shutil.rmtree(snapshot)
    shutil.copytree(source, snapshot)
    config = snapshot / "tokenizer_config.json"
    config.write_bytes(config.read_bytes() + b"\n")
    with pytest.raises(ReleaseVerificationError, match="SHA-256"):
        verify_tokenizer_snapshot(snapshot)


def test_dictionary_release_requires_sources_licenses_and_exact_hash(tmp_path: Path) -> None:
    source = PROMPT_FORGE / "knowledge" / "anima"
    fixture = tmp_path / "anima"
    fixture.mkdir()
    for name in ("manifest.json", "sources.lock.json", "protocol.json"):
        shutil.copy2(source / name, fixture / name)
    (fixture / "tags.sqlite").write_bytes(b"not-the-database")
    with pytest.raises(ReleaseVerificationError, match="database SHA-256"):
        verify_dictionary_release(fixture)

    manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
    manifest["sqlite_sha256"] = hashlib.sha256(b"not-the-database").hexdigest()
    (fixture / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    sources = json.loads((fixture / "sources.lock.json").read_text(encoding="utf-8"))
    sources["sources"][0]["license_url"] = ""
    (fixture / "sources.lock.json").write_text(json.dumps(sources), encoding="utf-8")
    with pytest.raises(ReleaseVerificationError, match="license"):
        verify_dictionary_release(fixture)


@pytest.mark.parametrize(
    "relative",
    [
        "skills/prompt-forge/profiles/old.json",
        "skills/prompt-forge/knowledge/lora/entry.json",
        "skills/prompt-forge/prompt_forge/dialects.py",
        "skills/prompt-forge/scripts/lint_prompt.py",
        "skills/prompt-forge/scripts/verify_profile.py",
    ],
)
def test_greenfield_shape_rejects_legacy_or_model_overlay_paths(
    tmp_path: Path,
    relative: str,
) -> None:
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")
    with pytest.raises(ReleaseVerificationError):
        verify_greenfield_shape(tmp_path)


def test_greenfield_shape_rejects_legacy_symbols(tmp_path: Path) -> None:
    target = tmp_path / "skills" / "prompt-forge" / "prompt_forge" / "bad.py"
    target.parent.mkdir(parents=True)
    target.write_text("class PromptPackage: pass", encoding="utf-8")
    with pytest.raises(ReleaseVerificationError, match="legacy symbol"):
        verify_greenfield_shape(tmp_path)


def test_public_surface_rejects_a_fourth_author_or_generic_extension_file(
    tmp_path: Path,
) -> None:
    package = tmp_path / "skills" / "prompt-forge" / "prompt_forge"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "\n".join(f"def {name}(request): pass" for name in (
            "author_anima_prompt",
            "author_h3_t2va_prompt",
            "author_h3_ref2va_prompt",
            "author_future_model_prompt",
        )),
        encoding="utf-8",
    )
    with pytest.raises(ReleaseVerificationError, match="unexpected public author"):
        verify_public_surface(tmp_path)

    (package / "__init__.py").write_text(
        "\n".join(f"def {name}(request): pass" for name in (
            "author_anima_prompt",
            "author_h3_t2va_prompt",
            "author_h3_ref2va_prompt",
        )),
        encoding="utf-8",
    )
    (package / "registry.py").write_text("{}", encoding="utf-8")
    with pytest.raises(ReleaseVerificationError, match="extension surface"):
        verify_public_surface(tmp_path)


def test_source_cache_comparison_detects_missing_or_changed_key_file(tmp_path: Path) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    key = Path("skills/prompt-forge/SKILL.md")
    (source / key).parent.mkdir(parents=True)
    (cache / key).parent.mkdir(parents=True)
    (source / key).write_text("source", encoding="utf-8")
    (cache / key).write_text("source", encoding="utf-8")
    compare_source_cache(source, cache, (key,))
    (cache / key).write_text("changed", encoding="utf-8")
    with pytest.raises(ReleaseVerificationError, match="mismatch"):
        compare_source_cache(source, cache, (key,))
    (cache / key).unlink()
    with pytest.raises(ReleaseVerificationError, match="missing"):
        compare_source_cache(source, cache, (key,))


def test_release_staging_uses_an_explicit_clean_file_set(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    destination.mkdir()
    for relative, content in {
        ".codex-plugin/plugin.json": "{}",
        ".mcp.json": "{}",
        "LICENSE": "license",
        "README.md": "readme",
        "skills/prompt-forge/SKILL.md": "skill",
        "skills/prompt-forge/prompt_forge/author.py": "runtime",
        "skills/prompt-forge/benchmarks/cases.jsonl": "fixture",
        "mcp_server/src/server.py": "runtime",
    }.items():
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    for relative in (
        "skills/prompt-forge/.pytest_cache/state",
        "skills/prompt-forge/tests/test_author.py",
        "skills/prompt-forge/prompt_forge/__pycache__/author.pyc",
        "mcp_server/package.egg-info/PKG-INFO",
    ):
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("development residue", encoding="utf-8")

    report = stage_release(source, destination)

    assert report["files"] == 8
    assert (destination / "skills/prompt-forge/benchmarks/cases.jsonl").is_file()
    assert not (destination / "skills/prompt-forge/.pytest_cache").exists()
    assert not (destination / "skills/prompt-forge/tests").exists()
    assert not (destination / "skills/prompt-forge/prompt_forge/__pycache__").exists()
    assert not (destination / "mcp_server/package.egg-info").exists()


def test_release_staging_refuses_nonempty_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("readme", encoding="utf-8")
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "stale.txt").write_text("stale", encoding="utf-8")

    with pytest.raises(ReleaseStagingError, match="empty"):
        stage_release(source, destination)


def test_source_cache_key_set_includes_every_prompt_forge_python_file() -> None:
    keys = set(source_cache_key_files(REPO))
    expected = {
        path.relative_to(REPO)
        for root in (
            PROMPT_FORGE / "prompt_forge",
            PROMPT_FORGE / "scripts",
        )
        for path in root.rglob("*.py")
    }
    assert expected <= keys
    assert {
        Path("mcp_server/pyproject.toml"),
        Path("skills/prompt-forge/pyproject.toml"),
        Path("skills/camera-image/pyproject.toml"),
        Path("skills/camera-multiview/pyproject.toml"),
        Path("skills/camera-video/pyproject.toml"),
    } <= keys
