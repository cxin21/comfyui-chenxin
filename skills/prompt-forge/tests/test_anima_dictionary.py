from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path
from types import ModuleType

import pytest

from prompt_forge.anima.audit import audit_anima_prompt
from prompt_forge.anima.dictionary import AnimaTagDictionary, DictionaryQueryError
from prompt_forge.contracts import Fact
from prompt_forge.facts import FactLedger


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_anima_dictionary.py"
BUNDLED_ROOT = Path(__file__).parents[1] / "knowledge" / "anima"


def load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_anima_dictionary", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def builder() -> ModuleType:
    return load_builder()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(root: Path) -> tuple[Path, Path]:
    sources = root / "sources"
    sources.mkdir(parents=True)
    gelbooru = sources / "gelbooru.jsonl"
    gelbooru.write_text(
        "\n".join(
            json.dumps(row, sort_keys=True)
            for row in (
                {"id": 3, "name": "blue_hair", "count": 900, "type": 0},
                {"id": 1, "name": "artist_name", "count": 300, "type": 1},
                {"id": 2, "name": "series_name", "count": 500, "type": 3},
                {"id": 4, "name": "deprecated", "count": 1, "type": 6},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    danbooru = sources / "danbooru.csv"
    with danbooru.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("blue_hair", 0, 800, "azure_hair,bluehead"))
        writer.writerow(("green_eyes", 0, 700, "emerald_eyes"))
        writer.writerow(("old_blue_hair", 0, 100, "blue_hair"))

    protocol = root / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "ordinary_tag_form": "lowercase_spaces",
                "score_tag_form": "retain_underscore",
                "artist_prefix": "@",
                "tag_order": [
                    "quality_meta_year_safety",
                    "count",
                    "character",
                    "copyright",
                    "artist",
                    "general",
                ],
                "official_tags": [
                    {"canonical": "blue_hair", "category": "general"},
                    {"canonical": "score_7", "category": "quality"},
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    lock = root / "sources.lock.json"
    lock.write_text(
        json.dumps(
            {
                "dictionary_version": "test-v1",
                "precedence": [
                    "official_anima_rule",
                    "gelbooru_canonical",
                    "danbooru_compatibility_alias",
                ],
                "sources": [
                    source_lock("gelbooru", "gelbooru_jsonl", gelbooru),
                    source_lock("danbooru", "danbooru_csv", danbooru),
                    source_lock("anima_protocol", "anima_protocol", protocol),
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return lock, protocol


def source_lock(source_id: str, kind: str, path: Path) -> dict[str, object]:
    return {
        "source_id": source_id,
        "kind": kind,
        "filename": path.name,
        "revision": f"immutable-{source_id}-revision",
        "sha256": sha256(path),
        "acquired_at": "2026-08-12T00:00:00Z",
        "source_url": f"https://example.test/{source_id}",
        "license_spdx": "CC0-1.0",
        "license_url": f"https://example.test/{source_id}/license",
        "redistribution_allowed": True,
    }


def build(builder: ModuleType, root: Path) -> tuple[Path, dict[str, object]]:
    lock, protocol = write_fixture(root)
    output = root / "output"
    manifest = builder.build_dictionary(
        lock_path=lock,
        source_root=root / "sources",
        protocol_path=protocol,
        output_dir=output,
    )
    return output / "tags.sqlite", manifest


def test_builder_schema_precedence_aliases_and_protocol_forms(
    builder: ModuleType,
    tmp_path: Path,
) -> None:
    database, manifest = build(builder, tmp_path)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall() == [("aliases",), ("tags",)]
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        tags = connection.execute(
            "SELECT tag_id, canonical, anima_form, category, usage_count, source, "
            "source_version, verification_status FROM tags ORDER BY tag_id"
        ).fetchall()
        aliases = connection.execute(
            "SELECT alias, tag_id, source, confidence FROM aliases "
            "ORDER BY alias, tag_id"
        ).fetchall()

    assert [row[1] for row in tags] == sorted(row[1] for row in tags)
    by_name = {row[1]: row for row in tags}
    assert by_name["blue_hair"][2:] == (
        "blue hair",
        "general",
        900,
        "official_anima_rule",
        "immutable-anima_protocol-revision",
        "official",
    )
    assert by_name["artist_name"][2] == "@artist name"
    assert by_name["score_7"][2] == "score_7"
    assert "deprecated" not in by_name
    assert "green_eyes" in by_name

    blue_id = by_name["blue_hair"][0]
    green_id = by_name["green_eyes"][0]
    assert ("azure_hair", blue_id, "danbooru", 0.85) in aliases
    assert ("bluehead", blue_id, "danbooru", 0.85) in aliases
    assert ("old_blue_hair", blue_id, "danbooru", 0.85) in aliases
    assert ("emerald_eyes", green_id, "danbooru", 0.85) in aliases
    assert manifest["precedence"] == [
        "official_anima_rule",
        "gelbooru_canonical",
        "danbooru_compatibility_alias",
    ]
    assert manifest["row_counts"] == {"tags": 5, "aliases": 4}


def test_identical_inputs_produce_byte_identical_database_and_manifest(
    builder: ModuleType,
    tmp_path: Path,
) -> None:
    first_db, first_manifest = build(builder, tmp_path / "first")
    second_db, second_manifest = build(builder, tmp_path / "second")
    assert first_db.read_bytes() == second_db.read_bytes()
    assert first_manifest == second_manifest
    assert first_manifest["sqlite_sha256"] == sha256(first_db)
    assert first_manifest["builder_sha256"] == sha256(SCRIPT)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("license_url", None, "license_url"),
        ("revision", None, "revision"),
        ("redistribution_allowed", False, "redistribution_allowed"),
        ("sha256", "0" * 64, "sha256 mismatch"),
    ],
)
def test_release_gate_rejects_unlicensed_or_unverified_sources(
    builder: ModuleType,
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    lock, protocol = write_fixture(tmp_path)
    payload = json.loads(lock.read_text(encoding="utf-8"))
    if value is None:
        payload["sources"][0].pop(field)
    else:
        payload["sources"][0][field] = value
    lock.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(builder.DictionaryBuildError, match=message):
        builder.build_dictionary(
            lock_path=lock,
            source_root=tmp_path / "sources",
            protocol_path=protocol,
            output_dir=tmp_path / "output",
        )


def test_canonical_collisions_and_alias_targets_are_deterministic(
    builder: ModuleType,
    tmp_path: Path,
) -> None:
    database, _ = build(builder, tmp_path)
    with sqlite3.connect(database) as connection:
        canonical_count = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT canonical) FROM tags"
        ).fetchone()
        dangling = connection.execute(
            "SELECT COUNT(*) FROM aliases a LEFT JOIN tags t ON t.tag_id=a.tag_id "
            "WHERE t.tag_id IS NULL"
        ).fetchone()
    assert canonical_count == (5, 5)
    assert dangling == (0,)


def test_bundled_dictionary_is_full_verified_and_manifest_bound() -> None:
    database = BUNDLED_ROOT / "tags.sqlite"
    manifest = json.loads((BUNDLED_ROOT / "manifest.json").read_text(encoding="utf-8"))
    lock = json.loads((BUNDLED_ROOT / "sources.lock.json").read_text(encoding="utf-8"))
    assert database.stat().st_size > 200_000_000
    assert manifest["sqlite_sha256"] == sha256(database)
    assert manifest["builder_sha256"] == sha256(SCRIPT)
    assert manifest["row_counts"] == {"tags": 1_376_178, "aliases": 36_725}
    assert manifest["precedence"] == lock["precedence"]
    assert all(source["redistribution_allowed"] is True for source in lock["sources"])
    assert all(source["revision"] and source["license_url"] for source in lock["sources"])

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall() == [("aliases",), ("tags",)]
        assert connection.execute(
            "SELECT canonical, anima_form, category FROM tags WHERE canonical='blue_hair'"
        ).fetchone() == ("blue_hair", "blue hair", "general")
        assert connection.execute(
            "SELECT canonical, anima_form, category FROM tags WHERE canonical='score_7'"
        ).fetchone() == ("score_7", "score_7", "quality")
        artist = connection.execute(
            "SELECT anima_form FROM tags WHERE category='artist' ORDER BY usage_count DESC LIMIT 1"
        ).fetchone()
        assert artist is not None and artist[0].startswith("@")


def test_anima_knowledge_has_no_translation_checkpoint_or_lora_overlay() -> None:
    names = {path.name.lower() for path in BUNDLED_ROOT.iterdir()}
    forbidden_fragments = ("translation", "checkpoint", "lora", "profile", "registry")
    assert not any(fragment in name for name in names for fragment in forbidden_fragments)


def test_dictionary_lookup_distinguishes_canonical_alias_and_concept_matches() -> None:
    dictionary = AnimaTagDictionary(BUNDLED_ROOT / "tags.sqlite")
    canonical = dictionary.lookup("blue_hair", limit=3)
    assert canonical[0].canonical == "blue_hair"
    assert canonical[0].match_kind == "canonical"
    assert canonical[0].source
    assert canonical[0].verification_status

    alias = dictionary.lookup("1girls", limit=3)
    assert alias[0].canonical == "1girl"
    assert alias[0].match_kind == "alias"
    assert alias[0].confidence == 0.85

    concept = dictionary.lookup("blue hair", category="general", limit=5)
    assert concept[0].canonical == "blue_hair"
    assert all(item.category == "general" for item in concept)
    assert [item.usage_count for item in concept] == sorted(
        (item.usage_count for item in concept),
        reverse=True,
    )


def test_dictionary_lookup_has_a_strict_limit_and_read_only_connection() -> None:
    dictionary = AnimaTagDictionary(BUNDLED_ROOT / "tags.sqlite")
    assert len(dictionary.lookup("hair", limit=2)) == 2
    with pytest.raises(DictionaryQueryError, match="limit"):
        dictionary.lookup("hair", limit=0)
    with pytest.raises(DictionaryQueryError, match="limit"):
        dictionary.lookup("hair", limit=101)
    with pytest.raises(sqlite3.OperationalError):
        with dictionary.connect() as connection:
            connection.execute("DELETE FROM tags")


def audit_ledger() -> FactLedger:
    return FactLedger(
        (
            Fact("s1.hair", "blue hair", "user_explicit", False, "subject_1", "hair"),
            Fact("s2.hair", "blue hair", "user_explicit", False, "subject_2", "hair"),
            Fact("style", "masterpiece", "agent_embellishment", False, "scene", "quality"),
        )
    )


def test_protocol_audit_classifies_without_rewriting() -> None:
    tags = ("masterpiece", "blue hair", "1girls", "invented visual idea")
    natural_language = "Subject 1 has blue hair."
    report = audit_anima_prompt(tags, natural_language, audit_ledger())
    assert report.tags == tags
    assert report.natural_language == natural_language
    assert [entry.status for entry in report.entries] == [
        "canonical",
        "canonical",
        "known_alias",
        "unverified",
    ]
    assert report.entries[1].fact_ids == ("s1.hair", "s2.hair")
    assert any(finding.code == "duplicate_semantics" for finding in report.findings)
    assert any(finding.code == "possible_binding_conflict" for finding in report.findings)


@pytest.mark.parametrize(
    ("tag", "code"),
    [
        ("blue_hair", "wrong_underscore_form"),
        ("score 7", "wrong_underscore_form"),
        ("score_10", "invalid_protocol_tag"),
        ("kantoku", "artist_prefix_missing"),
        ("@definitely unknown artist namespace", "invalid_protocol_tag"),
        ("year twenty twenty", "invalid_protocol_tag"),
    ],
)
def test_malformed_or_reserved_protocol_syntax_is_release_blocking(
    tag: str,
    code: str,
) -> None:
    report = audit_anima_prompt((tag,), "", FactLedger(()))
    assert report.release_blocking
    assert any(finding.code == code and finding.severity == "error" for finding in report.findings)


def test_unknown_ordinary_semantics_are_advisory_only() -> None:
    report = audit_anima_prompt(("an entirely new visible concept",), "", FactLedger(()))
    assert report.entries[0].status == "unverified"
    assert not report.release_blocking
    assert report.findings[0].severity == "warning"
