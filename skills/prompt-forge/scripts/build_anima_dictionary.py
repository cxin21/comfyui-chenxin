#!/usr/bin/env python3
"""Build the bundled Anima tag dictionary from license-gated snapshots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Mapping


CATEGORY_NAMES = {
    0: "general",
    1: "artist",
    3: "copyright",
    4: "character",
    5: "meta",
}
SOURCE_PRECEDENCE = {
    "danbooru_compatibility_alias": 1,
    "gelbooru_canonical": 2,
    "official_anima_rule": 3,
}
SCHEMA = """
CREATE TABLE tags (
  tag_id INTEGER PRIMARY KEY,
  canonical TEXT NOT NULL UNIQUE,
  anima_form TEXT NOT NULL,
  category TEXT NOT NULL,
  usage_count INTEGER NOT NULL,
  source TEXT NOT NULL,
  source_version TEXT NOT NULL,
  verification_status TEXT NOT NULL
);
CREATE TABLE aliases (
  alias TEXT NOT NULL,
  tag_id INTEGER NOT NULL REFERENCES tags(tag_id),
  source TEXT NOT NULL,
  confidence REAL NOT NULL,
  PRIMARY KEY(alias, tag_id)
);
"""


class DictionaryBuildError(ValueError):
    """A source or build result failed a release-blocking invariant."""


def build_dictionary(
    *,
    lock_path: Path,
    source_root: Path,
    protocol_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    lock = _load_object(lock_path, "sources lock")
    version = _required_string(lock, "dictionary_version", "sources lock")
    precedence = _string_list(lock, "precedence", "sources lock")
    expected_precedence = [
        "official_anima_rule",
        "gelbooru_canonical",
        "danbooru_compatibility_alias",
    ]
    if precedence != expected_precedence:
        raise DictionaryBuildError(
            f"precedence must be exactly {expected_precedence!r}"
        )
    raw_sources = lock.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise DictionaryBuildError("sources lock sources must be a non-empty array")

    sources: dict[str, tuple[Mapping[str, Any], Path]] = {}
    manifest_sources: list[dict[str, object]] = []
    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise DictionaryBuildError("every source lock entry must be an object")
        source_id = _required_string(raw, "source_id", "source")
        kind = _required_string(raw, "kind", source_id)
        if kind in sources:
            raise DictionaryBuildError(f"duplicate source kind: {kind}")
        source_path = (
            protocol_path
            if kind == "anima_protocol"
            else source_root / _required_string(raw, "filename", source_id)
        )
        _validate_release_source(raw, source_path)
        sources[kind] = (raw, source_path)
        manifest_sources.append(
            {
                key: raw[key]
                for key in (
                    "source_id",
                    "kind",
                    "revision",
                    "sha256",
                    "acquired_at",
                    "source_url",
                    "license_spdx",
                    "license_url",
                    "redistribution_allowed",
                )
            }
        )

    required_kinds = {"gelbooru_jsonl", "danbooru_csv", "anima_protocol"}
    if set(sources) != required_kinds:
        raise DictionaryBuildError(
            f"source kinds must be exactly {sorted(required_kinds)!r}"
        )

    records: dict[str, dict[str, object]] = {}
    aliases: dict[tuple[str, str], tuple[str, float]] = {}
    gel_lock, gel_path = sources["gelbooru_jsonl"]
    _ingest_gelbooru(records, gel_path, _required_string(gel_lock, "revision", "gelbooru"))

    dan_lock, dan_path = sources["danbooru_csv"]
    _ingest_danbooru(
        records,
        aliases,
        dan_path,
        _required_string(dan_lock, "revision", "danbooru"),
    )

    protocol_lock, verified_protocol_path = sources["anima_protocol"]
    protocol = _load_object(verified_protocol_path, "Anima protocol")
    _validate_protocol(protocol)
    _apply_official_protocol(
        records,
        protocol,
        _required_string(protocol_lock, "revision", "Anima protocol"),
    )
    _drop_self_aliases(records, aliases)

    output_dir.mkdir(parents=True, exist_ok=True)
    database_path = output_dir / "tags.sqlite"
    _write_database(database_path, records, aliases)
    database_hash = _sha256(database_path)
    manifest: dict[str, object] = {
        "dictionary_version": version,
        "source_ids": [source["source_id"] for source in manifest_sources],
        "sources": manifest_sources,
        "precedence": precedence,
        "row_counts": {"tags": len(records), "aliases": len(aliases)},
        "sqlite_sha256": database_hash,
        "builder_sha256": _sha256(Path(__file__)),
        "schema_version": 1,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def _validate_release_source(source: Mapping[str, Any], path: Path) -> None:
    source_id = _required_string(source, "source_id", "source")
    for field in (
        "revision",
        "sha256",
        "acquired_at",
        "source_url",
        "license_spdx",
        "license_url",
    ):
        _required_string(source, field, source_id)
    if source.get("redistribution_allowed") is not True:
        raise DictionaryBuildError(
            f"source {source_id} redistribution_allowed must be true"
        )
    if not path.is_file():
        raise DictionaryBuildError(f"source {source_id} file is missing: {path}")
    expected = str(source["sha256"]).lower()
    actual = _sha256(path)
    if expected != actual:
        raise DictionaryBuildError(
            f"source {source_id} sha256 mismatch: expected {expected}, got {actual}"
        )


def _ingest_gelbooru(
    records: dict[str, dict[str, object]],
    path: Path,
    revision: str,
) -> None:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DictionaryBuildError(
                    f"invalid Gelbooru JSONL at line {line_number}"
                ) from exc
            if not isinstance(raw, dict):
                raise DictionaryBuildError(
                    f"Gelbooru row {line_number} must be an object"
                )
            category_id = raw.get("type", raw.get("category_id"))
            if category_id not in CATEGORY_NAMES:
                continue
            canonical = _canonical(raw.get("name", raw.get("tag_name")))
            if not canonical:
                continue
            usage_count = _non_negative_count(
                raw.get("count", raw.get("post_count")),
                f"Gelbooru row {line_number}",
            )
            candidate = {
                "canonical": canonical,
                "category": CATEGORY_NAMES[int(category_id)],
                "usage_count": usage_count,
                "source": "gelbooru_canonical",
                "source_version": revision,
                "verification_status": "gelbooru_canonical",
            }
            _merge_record(records, candidate)


def _ingest_danbooru(
    records: dict[str, dict[str, object]],
    aliases: dict[tuple[str, str], tuple[str, float]],
    path: Path,
    revision: str,
) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, row in enumerate(csv.reader(handle), start=1):
            if len(row) < 3 or len(row) > 4:
                raise DictionaryBuildError(
                    f"Danbooru CSV row {line_number} must have 3 or 4 columns"
                )
            canonical = _canonical(row[0])
            if not canonical:
                continue
            try:
                category_id = int(row[1])
            except ValueError as exc:
                raise DictionaryBuildError(
                    f"Danbooru row {line_number} has invalid category"
                ) from exc
            if category_id not in CATEGORY_NAMES:
                continue
            usage_count = _non_negative_count(row[2], f"Danbooru row {line_number}")
            row_aliases = tuple(
                alias
                for alias in (_canonical(value) for value in (row[3] if len(row) == 4 else "").split(","))
                if alias
            )
            existing_targets = sorted(
                {value for value in row_aliases if value in records}
            )
            if canonical in records:
                target = canonical
            elif existing_targets:
                target = existing_targets[0]
                aliases[(canonical, target)] = ("danbooru", 0.85)
            else:
                target = canonical
                _merge_record(
                    records,
                    {
                        "canonical": canonical,
                        "category": CATEGORY_NAMES[category_id],
                        "usage_count": usage_count,
                        "source": "danbooru_compatibility_alias",
                        "source_version": revision,
                        "verification_status": "danbooru_compatibility",
                    },
                )
            for alias in row_aliases:
                if alias != target:
                    aliases[(alias, target)] = ("danbooru", 0.85)


def _apply_official_protocol(
    records: dict[str, dict[str, object]],
    protocol: Mapping[str, Any],
    revision: str,
) -> None:
    official_tags = protocol.get("official_tags")
    assert isinstance(official_tags, list)
    for item in official_tags:
        assert isinstance(item, dict)
        canonical = _canonical(item["canonical"])
        assert canonical
        usage_count = int(records.get(canonical, {}).get("usage_count", 0))
        _merge_record(
            records,
            {
                "canonical": canonical,
                "category": item["category"],
                "usage_count": usage_count,
                "source": "official_anima_rule",
                "source_version": revision,
                "verification_status": "official",
            },
        )


def _merge_record(
    records: dict[str, dict[str, object]],
    candidate: dict[str, object],
) -> None:
    canonical = str(candidate["canonical"])
    current = records.get(canonical)
    if current is None:
        records[canonical] = candidate
        return
    candidate_count = int(candidate["usage_count"])
    current_count = int(current["usage_count"])
    if SOURCE_PRECEDENCE[str(candidate["source"])] >= SOURCE_PRECEDENCE[str(current["source"])]:
        candidate["usage_count"] = max(candidate_count, current_count)
        records[canonical] = candidate
    elif candidate_count > current_count:
        current["usage_count"] = candidate_count


def _drop_self_aliases(
    records: Mapping[str, Mapping[str, object]],
    aliases: dict[tuple[str, str], tuple[str, float]],
) -> None:
    for key in tuple(aliases):
        alias, target = key
        if alias == target or target not in records:
            del aliases[key]


def _write_database(
    destination: Path,
    records: Mapping[str, Mapping[str, object]],
    aliases: Mapping[tuple[str, str], tuple[str, float]],
) -> None:
    with tempfile.NamedTemporaryFile(
        dir=destination.parent,
        prefix="tags-",
        suffix=".sqlite",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute("PRAGMA page_size=4096")
            connection.execute("PRAGMA auto_vacuum=NONE")
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA encoding='UTF-8'")
            connection.execute("PRAGMA application_id=1095649613")
            connection.execute("PRAGMA user_version=1")
            connection.executescript(SCHEMA)
            ids: dict[str, int] = {}
            for tag_id, canonical in enumerate(sorted(records), start=1):
                record = records[canonical]
                ids[canonical] = tag_id
                connection.execute(
                    "INSERT INTO tags VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        tag_id,
                        canonical,
                        _anima_form(canonical, str(record["category"])),
                        record["category"],
                        record["usage_count"],
                        record["source"],
                        record["source_version"],
                        record["verification_status"],
                    ),
                )
            for (alias, target), (source, confidence) in sorted(aliases.items()):
                connection.execute(
                    "INSERT INTO aliases VALUES (?, ?, ?, ?)",
                    (alias, ids[target], source, confidence),
                )
            connection.commit()
            connection.execute("VACUUM")
        finally:
            connection.close()
        os.replace(temporary_path, destination)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _validate_protocol(protocol: Mapping[str, Any]) -> None:
    exact = {
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
    }
    for key, expected in exact.items():
        if protocol.get(key) != expected:
            raise DictionaryBuildError(
                f"Anima protocol {key} must be exactly {expected!r}"
            )
    official_tags = protocol.get("official_tags")
    if not isinstance(official_tags, list) or not official_tags:
        raise DictionaryBuildError("Anima protocol official_tags must be non-empty")
    seen: set[str] = set()
    for item in official_tags:
        if not isinstance(item, dict):
            raise DictionaryBuildError("official_tags entries must be objects")
        canonical = _canonical(item.get("canonical"))
        category = item.get("category")
        if not canonical or not isinstance(category, str) or not category:
            raise DictionaryBuildError(
                "official_tags require canonical and category strings"
            )
        if canonical in seen:
            raise DictionaryBuildError(f"duplicate official tag: {canonical}")
        seen.add(canonical)


def _anima_form(canonical: str, category: str) -> str:
    if canonical.startswith("score_"):
        return canonical
    ordinary = canonical.replace("_", " ")
    return f"@{ordinary}" if category == "artist" else ordinary


def _canonical(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return "_".join(html.unescape(value).strip().lower().split())


def _non_negative_count(value: object, context: str) -> int:
    if isinstance(value, bool):
        raise DictionaryBuildError(f"{context} usage count must be an integer")
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise DictionaryBuildError(f"{context} usage count must be an integer") from exc
    if result < 0:
        raise DictionaryBuildError(f"{context} usage count must be non-negative")
    return result


def _load_object(path: Path, context: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DictionaryBuildError(f"cannot load {context}: {path}") from exc
    if not isinstance(value, dict):
        raise DictionaryBuildError(f"{context} must be a JSON object")
    return value


def _required_string(payload: Mapping[str, Any], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DictionaryBuildError(f"{context} {key} must be a non-empty string")
    return value


def _string_list(payload: Mapping[str, Any], key: str, context: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise DictionaryBuildError(f"{context} {key} must be a string array")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = build_dictionary(
        lock_path=args.lock,
        source_root=args.source_root,
        protocol_path=args.protocol,
        output_dir=args.output,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
