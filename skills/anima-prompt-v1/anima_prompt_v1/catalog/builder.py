from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .facets import classify_category, derived_facets, normalize
from .models import CatalogStats
from .storage import CatalogStore

_TABLES = ("sources", "records", "names", "relations", "concepts", "facets", "record_facets")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("content_filters") is not False:
            return False
        for entry_name in ("source", "output"):
            entry = payload[entry_name]
            artifact = path.parent / entry["path"]
            checksum = entry["checksum"]
            if not isinstance(checksum, str) or len(checksum) != 64 or not artifact.is_file():
                return False
            int(checksum, 16)
            if sha256_file(artifact) != checksum:
                return False
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return False
    return True


class CatalogBuilder:
    def __init__(self, source: Path, output: Path) -> None:
        self.source = source
        self.output = output

    def build(self, *, manifest_path: Path | None = None) -> CatalogStats:
        if not self.source.is_file():
            raise FileNotFoundError(self.source)
        if self.source.resolve() == self.output.resolve():
            raise ValueError("output must not overwrite source")
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.output.with_suffix(self.output.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
        source = sqlite3.connect(f"file:{self.source.resolve().as_posix()}?mode=ro", uri=True)
        output = sqlite3.connect(temporary)
        try:
            output.execute("PRAGMA foreign_keys = ON")
            CatalogStore.create_schema(output)
            source_tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if {"tags", "aliases"} <= source_tables:
                self._build_from_raw_tags(source, output)
            else:
                self._copy_normalized(source, output)
            names = output.execute("SELECT name_id, record_id, value, normalized_value FROM names ORDER BY normalized_value, name_id").fetchall()
            output.executemany("INSERT INTO catalog_fts VALUES (?, ?, ?, ?)", names)
            output.commit()
            output.execute("VACUUM")
        finally:
            source.close()
            output.close()
        os.replace(temporary, self.output)
        stats = self._stats()
        if manifest_path is not None:
            self._write_manifest(manifest_path)
        return stats

    @staticmethod
    def _copy_normalized(source: sqlite3.Connection, output: sqlite3.Connection) -> None:
        for table in _TABLES:
            columns = tuple(row[1] for row in source.execute(f"PRAGMA table_info({table})"))
            if not columns:
                raise ValueError(f"source catalog missing required table: {table}")
            expected = tuple(row[1] for row in output.execute(f"PRAGMA table_info({table})"))
            if columns != expected:
                raise ValueError(f"source table {table} does not use the current schema")
            rows = source.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY {', '.join(columns)}").fetchall()
            placeholders = ", ".join("?" for _ in columns)
            output.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", rows)

    def _build_from_raw_tags(self, source: sqlite3.Connection, output: sqlite3.Connection) -> None:
        source_checksum = sha256_file(self.source)
        aliases = source.execute("SELECT alias, tag_id, source FROM aliases ORDER BY tag_id, alias, source").fetchall()
        source_rows = set(source.execute("SELECT DISTINCT source, source_version FROM tags").fetchall())
        source_rows.update((alias_source, "unknown") for _alias, _tag_id, alias_source in aliases)
        source_rows = sorted(source_rows)
        output.executemany(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (f"{name}:{version}", name, "", "unknown", version, "", source_checksum, "tags.sqlite + aliases")
                for name, version in source_rows
            ],
        )
        source_ids = {(name, version): f"{name}:{version}" for name, version in source_rows}
        tags = source.execute("SELECT tag_id, canonical, anima_form, category, usage_count, source, source_version FROM tags ORDER BY tag_id").fetchall()
        records = []
        for tag_id, canonical, prompt_form, source_category, usage_count, source_name, source_version in tags:
            source_id = source_ids[(source_name, source_version)]
            category = classify_category(canonical, source_category)
            provenance = {
                "source_id": source_id,
                "source_version": source_version,
                "raw_record_id": str(tag_id),
            }
            records.append((
                str(tag_id), canonical, prompt_form, category, "", "[]", None,
                json.dumps([source_id], ensure_ascii=False),
                json.dumps(provenance, ensure_ascii=False, sort_keys=True),
                usage_count, 0,
            ))
        output.executemany(
            "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            records,
        )
        names = []
        for tag_id, canonical, _prompt_form, _source_category, _usage_count, source_name, source_version in tags:
            source_id = source_ids[(source_name, source_version)]
            names.append((f"canonical:{tag_id}", str(tag_id), canonical, normalize(canonical), "canonical", "", source_id))
        for index, (alias, tag_id, alias_source) in enumerate(aliases):
            source_id = source_ids[(alias_source, "unknown")]
            names.append((f"alias:{tag_id}:{index}", str(tag_id), alias, normalize(alias), "alias", "", source_id))
        output.executemany("INSERT INTO names VALUES (?, ?, ?, ?, ?, ?, ?)", names)

        # The raw snapshot contains no semantic relation evidence. Keep the
        # semantic relation table empty instead of turning aliases into facts.
        facets = {}
        record_facets = []
        for tag_id, canonical, _prompt_form, source_category, _usage_count, _source, _version in tags:
            category = classify_category(canonical, source_category)
            for value in derived_facets(canonical, source_category, category):
                facet_id = f"facet:{value}"
                facets[facet_id] = (facet_id, "category" if value.startswith("category:") else "derived", value)
                record_facets.append((str(tag_id), facet_id))
        output.executemany("INSERT INTO facets VALUES (?, ?, ?)", sorted(facets.values()))
        output.executemany("INSERT INTO record_facets VALUES (?, ?)", sorted(set(record_facets)))

        concepts = []
        for tag_id, canonical, _prompt_form, _source_category, _usage_count, source_name, source_version in tags:
            source_id = source_ids[(source_name, source_version)]
            provenance = {"source_id": source_id, "source_version": source_version, "raw_record_id": str(tag_id)}
            concepts.append((
                f"concept:{tag_id}", str(tag_id), canonical, "", "", None,
                json.dumps([source_id], ensure_ascii=False),
                json.dumps(provenance, ensure_ascii=False, sort_keys=True),
            ))
        output.executemany("INSERT INTO concepts VALUES (?, ?, ?, ?, ?, ?, ?, ?)", concepts)

    def _stats(self) -> CatalogStats:
        with closing(CatalogStore.connect_readonly(self.output)) as connection:
            counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (*_TABLES[1:], "catalog_fts")}
        return CatalogStats(counts["records"], counts["names"], counts["relations"], counts["concepts"], counts["facets"], counts["catalog_fts"])

    def _write_manifest(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        directory = path.parent.resolve()
        payload = {
            "content_filters": False,
            "source": {"path": _manifest_artifact_path(self.source, directory), "checksum": sha256_file(self.source)},
            "output": {"path": _manifest_artifact_path(self.output, directory), "checksum": sha256_file(self.output)},
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _manifest_artifact_path(artifact: Path, directory: Path) -> str:
    try:
        return os.path.relpath(artifact.resolve(), directory)
    except ValueError:
        return str(artifact.resolve())
