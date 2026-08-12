"""Read-only retrieval from the bundled Anima tag dictionary."""

from __future__ import annotations

import sqlite3
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


_DEFAULT_DATABASE = (
    Path(__file__).resolve().parents[2] / "knowledge" / "anima" / "tags.sqlite"
)
_RESOLUTION_CACHE: OrderedDict[tuple[str, int, int, str], TagCandidate | None] = OrderedDict()
_RESOLUTION_CACHE_LIMIT = 4096


class DictionaryQueryError(ValueError):
    """A dictionary query violates its bounded read-only contract."""


@dataclass(frozen=True)
class TagCandidate:
    canonical: str
    anima_form: str
    category: str
    usage_count: int
    source: str
    verification_status: str
    match_kind: Literal["canonical", "alias", "concept"]
    confidence: float


class AnimaTagDictionary:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = (database_path or _DEFAULT_DATABASE).resolve()
        if not self.database_path.is_file():
            raise DictionaryQueryError(
                f"bundled Anima dictionary is missing: {self.database_path}"
            )

    def connect(self) -> sqlite3.Connection:
        uri = f"{self.database_path.as_uri()}?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection

    def lookup(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 20,
    ) -> tuple[TagCandidate, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise DictionaryQueryError("limit must be an integer between 1 and 100")
        if not isinstance(query, str) or not query.strip():
            raise DictionaryQueryError("query must be a non-empty string")
        if category is not None and (not isinstance(category, str) or not category):
            raise DictionaryQueryError("category must be a non-empty string when provided")

        display = " ".join(query.strip().lower().lstrip("@").split())
        canonical = display.replace(" ", "_")
        category_sql = "" if category is None else " AND t.category = ?"
        exact_sql = f"""
            SELECT t.canonical, t.anima_form, t.category, t.usage_count,
                   t.source, t.verification_status,
                   CASE
                     WHEN t.canonical = ? OR t.anima_form = ? THEN 'canonical'
                     ELSE 'alias'
                   END AS match_kind,
                   CASE
                     WHEN t.canonical = ? THEN 1.0
                     ELSE COALESCE(a.confidence, 1.0)
                   END AS confidence,
                   CASE
                     WHEN t.canonical = ? OR t.anima_form = ? THEN 0
                     ELSE 1
                   END AS match_rank
              FROM tags t
             LEFT JOIN aliases a ON a.tag_id = t.tag_id AND a.alias = ?
             WHERE (t.canonical = ? OR t.anima_form = ? OR a.alias = ?)
             {category_sql}
             ORDER BY match_rank, confidence DESC, t.usage_count DESC, t.canonical
             LIMIT ?
        """
        # The repeated predicates make the ranking explicit and keep parameters bounded.
        exact_parameters = [canonical, display, canonical, canonical, display, canonical,
                            canonical, display, canonical]
        if category is not None:
            exact_parameters.append(category)
        exact_parameters.append(limit)

        with self.connect() as connection:
            rows = connection.execute(exact_sql, exact_parameters).fetchall()
            if len(rows) < limit:
                remaining = limit - len(rows)
                excluded = [str(row["canonical"]) for row in rows]
                terms = [term for term in display.split() if term]
                pattern = "%" + "%".join(terms) + "%"
                clauses = ["t.anima_form LIKE ?"]
                parameters: list[object] = [pattern]
                if category is not None:
                    clauses.append("t.category = ?")
                    parameters.append(category)
                if excluded:
                    placeholders = ",".join("?" for _ in excluded)
                    clauses.append(f"t.canonical NOT IN ({placeholders})")
                    parameters.extend(excluded)
                parameters.append(remaining)
                concept_rows = connection.execute(
                    f"""
                    SELECT t.canonical, t.anima_form, t.category, t.usage_count,
                           t.source, t.verification_status,
                           'concept' AS match_kind, 0.60 AS confidence
                      FROM tags t
                     WHERE {' AND '.join(clauses)}
                     ORDER BY t.usage_count DESC, t.canonical
                     LIMIT ?
                    """,
                    parameters,
                ).fetchall()
                rows.extend(concept_rows)
        return tuple(_candidate(row) for row in rows)

    def resolve(
        self,
        tag: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> TagCandidate | None:
        """Resolve only an exact canonical/form/alias without concept scanning."""
        if not isinstance(tag, str) or not tag.strip():
            return None
        if connection is None:
            return self.resolve_many((tag,))[0]
        display = " ".join(tag.strip().lower().lstrip("@").split())
        canonical = display.replace(" ", "_")
        row = connection.execute(
                """
                SELECT t.canonical, t.anima_form, t.category, t.usage_count,
                       t.source, t.verification_status,
                       CASE WHEN t.canonical = ? OR t.anima_form = ?
                            THEN 'canonical' ELSE 'alias' END AS match_kind,
                       CASE WHEN t.canonical = ? THEN 1.0
                            ELSE COALESCE(a.confidence, 1.0) END AS confidence,
                       CASE WHEN t.canonical = ? OR t.anima_form = ?
                            THEN 0 ELSE 1 END AS match_rank
                  FROM tags t
                  LEFT JOIN aliases a ON a.tag_id = t.tag_id AND a.alias = ?
                 WHERE t.canonical = ? OR t.anima_form = ? OR a.alias = ?
                 ORDER BY match_rank, confidence DESC, t.usage_count DESC, t.canonical
                 LIMIT 1
                """,
                (
                    canonical,
                    display,
                    canonical,
                    canonical,
                    display,
                    canonical,
                    canonical,
                    display,
                    canonical,
                ),
            ).fetchone()
        return _candidate(row) if row is not None else None

    def resolve_many(self, tags: tuple[str, ...]) -> tuple[TagCandidate | None, ...]:
        if not isinstance(tags, tuple) or not all(isinstance(tag, str) for tag in tags):
            raise TypeError("tags must be a tuple of strings")
        stat = self.database_path.stat()
        prefix = (str(self.database_path), stat.st_size, stat.st_mtime_ns)
        keys = [(*prefix, " ".join(tag.strip().lower().split())) for tag in tags]
        missing = [index for index, key in enumerate(keys) if key not in _RESOLUTION_CACHE]
        if missing:
            with self.connect() as connection:
                for index in missing:
                    _cache_resolution(keys[index], self.resolve(tags[index], connection=connection))
        result: list[TagCandidate | None] = []
        for key in keys:
            value = _RESOLUTION_CACHE[key]
            _RESOLUTION_CACHE.move_to_end(key)
            result.append(value)
        return tuple(result)


def _candidate(row: sqlite3.Row) -> TagCandidate:
    return TagCandidate(
        canonical=str(row["canonical"]),
        anima_form=str(row["anima_form"]),
        category=str(row["category"]),
        usage_count=int(row["usage_count"]),
        source=str(row["source"]),
        verification_status=str(row["verification_status"]),
        match_kind=row["match_kind"],
        confidence=float(row["confidence"]),
    )


def _cache_resolution(
    key: tuple[str, int, int, str],
    value: TagCandidate | None,
) -> None:
    _RESOLUTION_CACHE[key] = value
    _RESOLUTION_CACHE.move_to_end(key)
    while len(_RESOLUTION_CACHE) > _RESOLUTION_CACHE_LIMIT:
        _RESOLUTION_CACHE.popitem(last=False)
