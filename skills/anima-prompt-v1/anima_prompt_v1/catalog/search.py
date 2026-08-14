from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from .models import RelationHit, TagHit, TagRecord
from .relation_overlay import RelationOverlay

Mode = Literal["auto", "exact", "prefix", "alias", "fuzzy", "related"]


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def _fts_query(value: str) -> str:
    return " AND ".join(f'"{part.replace(chr(34), "")}"*' for part in normalize(value).split() if part)


class Catalog:
    def __init__(self, database: str | Path | None = None, relation_overlay: str | Path | RelationOverlay | None = None) -> None:
        self.database = Path(database) if database else Path(__file__).parents[2] / "knowledge" / "tag-catalog.sqlite"
        if isinstance(relation_overlay, RelationOverlay):
            self.relation_overlay = relation_overlay
        else:
            self.relation_overlay = RelationOverlay(relation_overlay or self.database.parent / "relation-overlay.sqlite")

    def _open(self) -> sqlite3.Connection:
        uri = self.database.resolve().as_uri() + "?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def has_record(self, record_id: str) -> bool:
        with closing(self._open()) as connection:
            return connection.execute("SELECT 1 FROM records WHERE record_id=?", (record_id,)).fetchone() is not None

    def get_record(self, record_id: str) -> TagRecord:
        with closing(self._open()) as connection:
            row = connection.execute("SELECT record_id, canonical_name, prompt_form, category, description, language_names, confidence, source_ids, provenance, usage_count, deprecated FROM records WHERE record_id=?", (record_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown Catalog record: {record_id}")
        return TagRecord(
            row["record_id"], row["canonical_name"], row["prompt_form"], row["category"], row["description"],
            tuple(_json_list(row["language_names"])), row["confidence"], tuple(_json_list(row["source_ids"])),
            _json_provenance(row["provenance"]), row["usage_count"], bool(row["deprecated"]),
        )

    def search(
        self,
        query: str,
        *,
        mode: Mode = "auto",
        categories: tuple[str, ...] = (),
        facets: tuple[str, ...] = (),
        sources: tuple[str, ...] = (),
        include_aliases: bool = True,
        include_deprecated: bool = True,
        limit: int = 20,
    ) -> list[TagHit]:
        normalized = normalize(query)
        if not normalized or limit < 1:
            return []
        if mode not in {"auto", "exact", "prefix", "alias", "fuzzy", "related"}:
            raise ValueError(f"unsupported search mode: {mode}")
        modes = ("exact", "alias", "prefix", "related", "fuzzy") if mode == "auto" else (mode,)
        if not include_aliases:
            modes = tuple(value for value in modes if value != "alias")
        with closing(self._open()) as connection:
            for current in modes:
                rows = self._query(connection, normalized, current, categories, facets, sources, include_aliases, include_deprecated, limit)
                if rows:
                    hits = self._hydrate(connection, rows)
                    if current == "related":
                        hits.extend(self._overlay_search(connection, normalized, categories, facets, sources, include_deprecated, limit, {hit.record_id for hit in hits}))
                    return hits[:limit]
                if current == "related":
                    overlay_hits = self._overlay_search(connection, normalized, categories, facets, sources, include_deprecated, limit, set())
                    if overlay_hits:
                        return overlay_hits
        return []

    @classmethod
    def _query(cls, connection, query, mode, categories, facets, sources, include_aliases, include_deprecated, limit):
        scope, params = cls._scope(connection, categories, facets, sources, include_deprecated)
        if mode == "alias" and not include_aliases:
            return []
        if mode == "related":
            record = cls._lookup_record(connection, query)
            if record is None:
                return []
            sql = """
                SELECT rel.relation_id, r.*, 'related' AS match_type,
                       n.value AS matched_name, n.name_type, 300.0 AS score
                FROM relations rel
                JOIN records r ON r.record_id = CASE
                    WHEN rel.from_record_id=? THEN rel.to_record_id ELSE rel.from_record_id END
                JOIN names n ON n.record_id=r.record_id AND n.name_type='canonical'
                WHERE (rel.from_record_id=? OR rel.to_record_id=?)
                  AND rel.status='accepted'""" + scope + " ORDER BY rel.confidence DESC, r.usage_count DESC LIMIT ?"
            return connection.execute(sql, (record[0], record[0], record[0], *params, limit)).fetchall()
        if mode in {"exact", "alias", "prefix"}:
            name_clause = "n.normalized_value=?" if mode in {"exact", "alias"} else "n.normalized_value LIKE ?"
            name_param = query if mode in {"exact", "alias"} else query + "%"
            name_type = "canonical" if mode == "exact" else "alias" if mode == "alias" else None
            if name_type is not None:
                type_clause = " AND n.name_type=?"
                type_params = [name_type]
            else:
                type_clause = " AND (n.name_type='canonical' OR n.name_type='alias')" if include_aliases else " AND n.name_type='canonical'"
                type_params = []
            matched = "'canonical'" if mode == "exact" else "'alias'" if mode == "alias" else "CASE WHEN n.name_type='alias' THEN 'alias-prefix' ELSE 'prefix' END"
            score = "1000.0" if mode == "exact" else "850.0" if mode == "alias" else "700.0"
            sql = f"SELECT NULL AS relation_id, r.*, {matched} AS match_type, n.value AS matched_name, n.name_type, {score} AS score FROM names n JOIN records r ON r.record_id=n.record_id WHERE {name_clause}{type_clause}{scope} ORDER BY r.usage_count DESC, r.record_id LIMIT ?"
            return connection.execute(sql, [name_param, *type_params, *params, limit]).fetchall()
        fts = _fts_query(query)
        if not fts:
            return []
        name_type_clause = " AND n.name_type='canonical'" if not include_aliases else ""
        sql = "SELECT NULL AS relation_id, r.*, 'fuzzy' AS match_type, n.value AS matched_name, n.name_type, (500.0 - bm25(catalog_fts)) AS score FROM catalog_fts f JOIN names n ON n.name_id=f.name_id JOIN records r ON r.record_id=f.record_id WHERE catalog_fts MATCH ?" + name_type_clause + scope + " ORDER BY bm25(catalog_fts), r.usage_count DESC LIMIT ?"
        return connection.execute(sql, [fts, *params, limit]).fetchall()

    @staticmethod
    def _lookup_record(connection, query: str):
        return connection.execute(
            "SELECT n.record_id FROM names n JOIN records r ON r.record_id=n.record_id "
            "WHERE n.normalized_value=? ORDER BY CASE WHEN n.name_type='canonical' THEN 0 ELSE 1 END, r.usage_count DESC LIMIT 1",
            (query,),
        ).fetchone()

    @staticmethod
    def _scope(connection, categories, facets, sources, include_deprecated):
        clauses: list[str] = []
        params: list[object] = []
        if categories:
            placeholders = ",".join("?" for _ in categories)
            clauses.append(f"(r.category IN ({placeholders}) OR EXISTS (SELECT 1 FROM record_facets rfc JOIN facets fc ON fc.facet_id=rfc.facet_id WHERE rfc.record_id=r.record_id AND fc.name='category' AND fc.value IN ({placeholders})))")
            params.extend(categories)
            params.extend(categories)
        if sources:
            clauses.append("EXISTS (SELECT 1 FROM json_each(r.source_ids) WHERE value IN (" + ",".join("?" for _ in sources) + "))")
            params.extend(sources)
        if facets:
            placeholders = ",".join("?" for _ in facets)
            clauses.append(f"EXISTS (SELECT 1 FROM record_facets rf JOIN facets f ON f.facet_id=rf.facet_id WHERE rf.record_id=r.record_id AND (f.value IN ({placeholders}) OR f.name IN ({placeholders})))")
            params.extend(facets)
            params.extend(facets)
        if not include_deprecated:
            clauses.append("r.deprecated=0")
        return ((" AND " + " AND ".join(clauses)) if clauses else ""), params

    def _hydrate(self, connection, rows, extra_provenance: tuple[str, ...] = ()) -> list[TagHit]:
        hits = []
        for row in rows:
            facets = connection.execute("SELECT f.value FROM record_facets rf JOIN facets f ON f.facet_id=rf.facet_id WHERE rf.record_id=? ORDER BY f.value", (row["record_id"],)).fetchall()
            aliases = connection.execute("SELECT value FROM names WHERE record_id=? AND name_type='alias' ORDER BY normalized_value, name_id", (row["record_id"],)).fetchall()
            source_ids = tuple(json_value for json_value in _json_list(row["source_ids"]))
            source = connection.execute("SELECT name, snapshot_version, checksum FROM sources WHERE source_id=?", (source_ids[0] if source_ids else "",)).fetchone()
            provenance = list(_json_provenance(row["provenance"]))
            if source:
                provenance.extend((f"source_name:{source[0]}", f"version:{source[1]}", f"checksum:{source[2]}"))
            provenance.extend(extra_provenance)
            hits.append(TagHit(
                row["record_id"], row["canonical_name"], row["prompt_form"], row["category"], row["usage_count"],
                source_ids[0] if source_ids else "", source[1] if source else "", bool(row["deprecated"]),
                tuple(item[0] for item in facets), row["match_type"], row["matched_name"], row["name_type"],
                float(row["score"]), tuple(item[0] for item in aliases), tuple(provenance),
            ))
        return hits

    def related(self, record_id: str, *, relation_type: str | None = None, limit: int = 50) -> list[RelationHit]:
        if limit < 1:
            return []
        relation_clause = " AND relation_type=?" if relation_type else ""
        params: list[object] = [record_id]
        if relation_type:
            params.append(relation_type)
        params.append(record_id)
        if relation_type:
            params.append(relation_type)
        params.append(limit)
        with closing(self._open()) as connection:
            rows = connection.execute(
                "SELECT relation_id, from_record_id, to_record_id, relation_type, status, source, confidence, model, rationale, evidence, updated_at "
                "FROM relations WHERE (from_record_id=?" + relation_clause + ") OR (to_record_id=?" + relation_clause + ") "
                "ORDER BY confidence DESC LIMIT ?", params,
            ).fetchall()
        result = [_base_relation_hit(row) for row in rows]
        if self.relation_overlay.path.is_file():
            result.extend(
                _overlay_relation_hit(item)
                for item in self.relation_overlay.list(status="accepted", record_id=record_id, limit=limit)
                if relation_type is None or item.relation_type == relation_type
            )
        return result[:limit]

    def _overlay_search(self, connection, query, categories, facets, sources, include_deprecated, limit, existing_ids):
        if not self.relation_overlay.path.is_file():
            return []
        record = self._lookup_record(connection, query)
        if record is None:
            return []
        proposals = self.relation_overlay.list(status="accepted", record_id=str(record[0]), limit=limit * 2)
        target_ids = {item.to_record_id if item.from_record_id == str(record[0]) else item.from_record_id for item in proposals} - set(existing_ids)
        if not target_ids:
            return []
        placeholders = ",".join("?" for _ in target_ids)
        scope, params = self._scope(connection, categories, facets, sources, include_deprecated)
        rows = connection.execute(
            "SELECT NULL AS relation_id, r.*, 'related' AS match_type, n.value AS matched_name, n.name_type, 300.0 AS score "
            "FROM names n JOIN records r ON r.record_id=n.record_id WHERE n.name_type='canonical' AND r.record_id IN (" + placeholders + ")" + scope + " ORDER BY r.usage_count DESC LIMIT ?",
            (*target_ids, *params, limit),
        ).fetchall()
        relation_provenance = tuple(f"accepted_relation:{item.proposal_id}" for item in proposals)
        return self._hydrate(connection, rows, relation_provenance)

    def browse(self, *, categories=(), facets=(), sources=(), include_aliases=True, include_deprecated=True, limit=20) -> list[TagHit]:
        if limit < 1:
            return []
        with closing(self._open()) as connection:
            scope, params = self._scope(connection, categories, facets, sources, include_deprecated)
            rows = connection.execute(
                "SELECT NULL AS relation_id, r.*, CASE WHEN n.name_type='alias' THEN 'alias' ELSE 'canonical' END AS match_type, n.value AS matched_name, n.name_type, 0.0 AS score "
                "FROM names n JOIN records r ON r.record_id=n.record_id WHERE 1=1" + (" AND n.name_type IN ('canonical','alias')" if include_aliases else " AND n.name_type='canonical'") + scope + " ORDER BY r.record_id, n.name_type, n.name_id LIMIT ?",
                (*params, limit),
            ).fetchall()
            return self._hydrate(connection, rows)

    def stats(self) -> dict[str, int]:
        with closing(self._open()) as connection:
            return {key: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for key, table in (("records", "records"), ("names", "names"), ("relations", "relations"), ("concepts", "concepts"), ("facets", "facets"), ("fts_rows", "catalog_fts"))}


def _json_list(value: str) -> list[str]:
    import json
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _json_provenance(value: str) -> tuple[str, ...]:
    import json
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return ()
    if isinstance(parsed, dict):
        return tuple(f"{key}:{parsed[key]}" for key in sorted(parsed))
    return tuple(str(item) for item in parsed) if isinstance(parsed, list) else ()


def _base_relation_hit(row) -> RelationHit:
    import json
    evidence = tuple(json.loads(row[9]))
    return RelationHit(
        str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]),
        float(row[6]) if row[6] is not None else None, str(row[7]) if row[7] is not None else None,
        str(row[8]), evidence, (f"relation_id:{row[0]}", f"source:{row[5]}", f"updated_at:{row[10]}"),
    )


def _overlay_relation_hit(item) -> RelationHit:
    return RelationHit(
        item.proposal_id, item.from_record_id, item.to_record_id, item.relation_type, "accepted",
        item.source, item.confidence, item.model, item.rationale, item.evidence,
        (f"proposal_id:{item.proposal_id}", f"source:{item.source}", f"model:{item.model or 'unknown'}"),
    )
