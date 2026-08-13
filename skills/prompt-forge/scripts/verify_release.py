"""Strict offline release verification for the greenfield Prompt Forge build."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable


class ReleaseVerificationError(ValueError):
    """A release asset, source shape, plugin manifest, or cache copy is invalid."""


_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LEGACY_SYMBOLS = (
    "ForgeRequest",
    "forge_prompt",
    "PromptPackage",
    "profile_id",
    "dialect_id",
    "adapter_manifest",
)
_PUBLIC_AUTHORS = (
    "author_anima_prompt",
    "author_h3_t2va_prompt",
    "author_h3_ref2va_prompt",
)
_FORBIDDEN_PROMPT_FORGE_PATH_PARTS = frozenset(
    {"profiles", "dialects", "internals", "checkpoint", "checkpoints", "lora", "loras"}
)
_FORBIDDEN_PROMPT_FORGE_FILES = frozenset(
    {Path("scripts/lint_prompt.py"), Path("scripts/verify_profile.py")}
)


def verify_plugin_manifest(source_root: Path) -> dict[str, str]:
    path = source_root / ".codex-plugin" / "plugin.json"
    manifest = _json(path, "plugin manifest")
    if not isinstance(manifest, dict):
        raise ReleaseVerificationError("plugin manifest must be an object")
    required = {"name", "version", "description", "author", "skills", "mcpServers", "interface"}
    if not required.issubset(manifest):
        raise ReleaseVerificationError("plugin manifest is missing required fields")
    if manifest["name"] != "comfyui-chenxin":
        raise ReleaseVerificationError("plugin name must be comfyui-chenxin")
    version = manifest["version"]
    if not isinstance(version, str) or _SEMVER.fullmatch(version) is None:
        raise ReleaseVerificationError("plugin version must be strict semver")
    if not version.startswith("0.2.0+"):
        raise ReleaseVerificationError("redesigned plugin release must use the 0.2.0 line")
    if manifest["skills"] != "./skills/":
        raise ReleaseVerificationError("plugin skills path must be ./skills/")
    interface_text = json.dumps(manifest.get("interface"), ensure_ascii=False)
    if any(symbol in interface_text for symbol in _LEGACY_SYMBOLS):
        raise ReleaseVerificationError("plugin interface contains old prompt package language")
    return {"name": manifest["name"], "version": version}


def verify_python_packages(source_root: Path) -> dict[str, Any]:
    projects = (
        Path("mcp_server/pyproject.toml"),
        Path("skills/prompt-forge/pyproject.toml"),
        Path("skills/camera-image/pyproject.toml"),
        Path("skills/camera-multiview/pyproject.toml"),
        Path("skills/camera-video/pyproject.toml"),
    )
    prompt_dependencies: list[str] | None = None
    for relative in projects:
        path = source_root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ReleaseVerificationError(f"invalid Python package metadata: {relative}") from exc
        project_match = re.search(
            r"(?ms)^\[project\]\s*$(.*?)(?=^\[|\Z)",
            text,
        )
        if project_match is None:
            raise ReleaseVerificationError(f"missing [project] metadata: {relative}")
        project = project_match.group(1)
        version_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', project)
        if version_match is None or version_match.group(1) != "0.2.0":
            raise ReleaseVerificationError(f"Python package version must be 0.2.0: {relative}")
        if relative == Path("skills/prompt-forge/pyproject.toml"):
            dependencies_match = re.search(
                r"(?ms)^dependencies\s*=\s*\[(.*?)^\]\s*$",
                project,
            )
            if dependencies_match is None:
                raise ReleaseVerificationError("Prompt Forge dependencies are missing")
            prompt_dependencies = re.findall(r'"([^"]+)"', dependencies_match.group(1))
    if prompt_dependencies != ["tokenizers==0.22.2"]:
        raise ReleaseVerificationError(
            "Prompt Forge must lock its verified native tokenizer runtime to 0.22.2"
        )
    return {"packages": len(projects), "tokenizers": "0.22.2"}


def verify_tokenizer_snapshot(snapshot: Path) -> dict[str, Any]:
    manifest = _json(snapshot / "manifest.json", "tokenizer manifest")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ReleaseVerificationError("tokenizer manifest schema is invalid")
    files = manifest.get("files")
    if not isinstance(files, dict) or "tokenizer.json" not in files:
        raise ReleaseVerificationError("tokenizer manifest has no tokenizer.json")
    license_record = manifest.get("license")
    if not isinstance(license_record, dict) or license_record.get("redistribution_allowed") is not True:
        raise ReleaseVerificationError("tokenizer redistribution license is missing")
    if not _https(license_record.get("url")):
        raise ReleaseVerificationError("tokenizer license URL must be HTTPS")
    revision = manifest.get("upstream_revision")
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ReleaseVerificationError("tokenizer revision must be immutable")
    for name, expected in sorted(files.items()):
        if not isinstance(name, str) or Path(name).name != name:
            raise ReleaseVerificationError("tokenizer manifest filename is invalid")
        path = snapshot / name
        if not path.is_file():
            raise ReleaseVerificationError(f"tokenizer asset is missing: {name}")
        if not isinstance(expected, str) or _SHA256.fullmatch(expected) is None:
            raise ReleaseVerificationError(f"tokenizer SHA-256 is invalid: {name}")
        if _sha256(path) != expected:
            raise ReleaseVerificationError(f"tokenizer SHA-256 mismatch: {name}")
    actual = {path.name for path in snapshot.iterdir() if path.is_file()}
    expected_names = set(files) | {"manifest.json"}
    if actual != expected_names:
        raise ReleaseVerificationError("tokenizer snapshot file set is invalid")
    return {"snapshot_id": manifest.get("snapshot_id"), "files": len(files)}


def verify_dictionary_release(root: Path) -> dict[str, Any]:
    manifest = _json(root / "manifest.json", "dictionary manifest")
    sources = _json(root / "sources.lock.json", "dictionary source lock")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ReleaseVerificationError("dictionary manifest schema is invalid")
    database = root / "tags.sqlite"
    if not database.is_file():
        raise ReleaseVerificationError("dictionary database is missing")
    expected_hash = manifest.get("sqlite_sha256")
    if not isinstance(expected_hash, str) or _sha256(database) != expected_hash:
        raise ReleaseVerificationError("dictionary database SHA-256 mismatch")
    if not isinstance(sources, dict) or not isinstance(sources.get("sources"), list):
        raise ReleaseVerificationError("dictionary source evidence is missing")
    locked = sources["sources"]
    manifest_sources = manifest.get("sources")
    if not isinstance(manifest_sources, list) or len(manifest_sources) != len(locked):
        raise ReleaseVerificationError("dictionary source manifests do not agree")
    for source in locked:
        if not isinstance(source, dict):
            raise ReleaseVerificationError("dictionary source evidence is invalid")
        for key in (
            "source_id", "revision", "sha256", "source_url", "license_spdx",
            "license_url", "redistribution_basis",
        ):
            if not isinstance(source.get(key), str) or not source[key].strip():
                raise ReleaseVerificationError(f"dictionary source {key} or license evidence is missing")
        if source.get("redistribution_allowed") is not True or not _https(source.get("license_url")):
            raise ReleaseVerificationError("dictionary source license does not permit redistribution")
    try:
        connection = sqlite3.connect(f"{database.as_uri()}?mode=ro&immutable=1", uri=True)
        try:
            tags = int(connection.execute("SELECT COUNT(*) FROM tags").fetchone()[0])
            aliases = int(connection.execute("SELECT COUNT(*) FROM aliases").fetchone()[0])
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise ReleaseVerificationError("dictionary database cannot be opened read-only") from exc
    counts = manifest.get("row_counts")
    if not isinstance(counts, dict) or counts != {"aliases": aliases, "tags": tags}:
        raise ReleaseVerificationError("dictionary row counts do not match the manifest")
    return {"sqlite_sha256": expected_hash, "tags": tags, "aliases": aliases}


def verify_greenfield_shape(source_root: Path) -> dict[str, Any]:
    prompt_root = source_root / "skills" / "prompt-forge"
    violations: list[str] = []
    if prompt_root.exists():
        for path in prompt_root.rglob("*"):
            relative = path.relative_to(prompt_root)
            names = {
                name
                for part in relative.parts
                for name in (part.casefold(), Path(part).stem.casefold())
            }
            if _FORBIDDEN_PROMPT_FORGE_PATH_PARTS.intersection(names):
                violations.append(str(relative))
            if relative in _FORBIDDEN_PROMPT_FORGE_FILES:
                violations.append(str(relative))
        source_dir = prompt_root / "prompt_forge"
        if source_dir.exists():
            for path in source_dir.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                for symbol in _LEGACY_SYMBOLS:
                    if symbol in text:
                        raise ReleaseVerificationError(
                            f"legacy symbol {symbol} in {path.relative_to(source_root)}"
                        )
    if violations:
        raise ReleaseVerificationError(f"forbidden Prompt Forge path(s): {sorted(violations)}")
    return {"forbidden_paths": 0, "legacy_symbols": 0}


def verify_public_surface(source_root: Path) -> dict[str, Any]:
    package = source_root / "skills" / "prompt-forge" / "prompt_forge"
    init = (package / "__init__.py").read_text(encoding="utf-8")
    for name in _PUBLIC_AUTHORS:
        if name not in init:
            raise ReleaseVerificationError(f"missing public author: {name}")
    unexpected_authors = sorted(
        set(re.findall(r"^def (author_[A-Za-z0-9_]+)\(", init, flags=re.MULTILINE))
        - set(_PUBLIC_AUTHORS)
    )
    if unexpected_authors:
        raise ReleaseVerificationError(
            f"unexpected public author function(s): {unexpected_authors}"
        )
    for forbidden in ("registry.py", "profiles.py", "dialects.py", "adapters.py"):
        if (package / forbidden).exists():
            raise ReleaseVerificationError(f"forbidden extension surface: {forbidden}")
    return {"authors": list(_PUBLIC_AUTHORS), "extension_surfaces": 0}


def compare_source_cache(
    source_root: Path,
    cache_root: Path,
    key_files: Iterable[Path],
) -> dict[str, int]:
    compared = 0
    for relative in key_files:
        source = source_root / relative
        cached = cache_root / relative
        if not source.is_file() or not cached.is_file():
            raise ReleaseVerificationError(f"source/cache key file is missing: {relative}")
        if _sha256(source) != _sha256(cached):
            raise ReleaseVerificationError(f"source/cache SHA-256 mismatch: {relative}")
        compared += 1
    return {"compared_files": compared}


def source_cache_key_files(source_root: Path) -> tuple[Path, ...]:
    prompt = source_root / "skills" / "prompt-forge"
    files = [
        Path(".codex-plugin/plugin.json"),
        Path("mcp_server/pyproject.toml"),
        Path("skills/camera-image/pyproject.toml"),
        Path("skills/camera-multiview/pyproject.toml"),
        Path("skills/camera-video/pyproject.toml"),
        Path("skills/prompt-forge/pyproject.toml"),
        Path("skills/prompt-forge/SKILL.md"),
        Path("skills/prompt-forge/knowledge/anima/manifest.json"),
        Path("skills/prompt-forge/knowledge/anima/sources.lock.json"),
        Path("skills/prompt-forge/knowledge/anima/tags.sqlite"),
        Path("skills/prompt-forge/knowledge/anima/budget-policy.json"),
        Path("skills/prompt-forge/references/dialects/minimax-h3/budget-policy.json"),
    ]
    for snapshot in ("anima-qwen3-0.6b", "h3-qwen3-vl"):
        root = prompt / "knowledge" / "tokenizers" / snapshot
        files.extend(path.relative_to(source_root) for path in sorted(root.iterdir()) if path.is_file())
    source_dir = prompt / "prompt_forge"
    files.extend(path.relative_to(source_root) for path in sorted(source_dir.rglob("*.py")))
    script_dir = prompt / "scripts"
    files.extend(path.relative_to(source_root) for path in sorted(script_dir.glob("*.py")))
    return tuple(files)


def verify_source(source_root: Path) -> dict[str, Any]:
    prompt = source_root / "skills" / "prompt-forge"
    return {
        "plugin": verify_plugin_manifest(source_root),
        "python_packages": verify_python_packages(source_root),
        "shape": verify_greenfield_shape(source_root),
        "public_surface": verify_public_surface(source_root),
        "anima_tokenizer": verify_tokenizer_snapshot(
            prompt / "knowledge" / "tokenizers" / "anima-qwen3-0.6b"
        ),
        "h3_tokenizer": verify_tokenizer_snapshot(
            prompt / "knowledge" / "tokenizers" / "h3-qwen3-vl"
        ),
        "dictionary": verify_dictionary_release(prompt / "knowledge" / "anima"),
    }


def _json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseVerificationError(f"{label} is missing or invalid: {path}") from exc


def _https(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("https://")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    args = parser.parse_args()
    source = args.source_root.resolve()
    report = verify_source(source)
    if args.cache_root is not None:
        cache = args.cache_root.resolve()
        cache_manifest = verify_plugin_manifest(cache)
        if cache_manifest["version"] != report["plugin"]["version"]:
            raise ReleaseVerificationError("source/cache plugin version mismatch")
        verify_python_packages(cache)
        verify_public_surface(cache)
        report["cache"] = compare_source_cache(
            source, cache, source_cache_key_files(source)
        )
        verify_greenfield_shape(cache)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseVerificationError as exc:
        raise SystemExit(f"release verification failed: {exc}")
