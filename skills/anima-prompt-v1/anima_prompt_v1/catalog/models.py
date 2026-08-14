from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CatalogRelationType = Literal["parent", "child", "related", "cooccurrence"]
RelationStatus = Literal["accepted"]
NameType = Literal["canonical", "alias", "translation", "historical"]


@dataclass(frozen=True)
class SourceInfo:
    source_id: str
    name: str
    uri: str
    license: str
    snapshot_version: str
    fetched_at: str
    checksum: str
    raw_schema: str


@dataclass(frozen=True)
class TagRecord:
    record_id: str
    canonical_name: str
    prompt_form: str
    category: str
    description: str
    language_names: tuple[str, ...]
    confidence: float | None
    source_ids: tuple[str, ...]
    provenance: tuple[str, ...]
    usage_count: int
    deprecated: bool


@dataclass(frozen=True)
class TagName:
    name_id: str
    record_id: str
    value: str
    name_type: NameType
    language: str
    source_id: str


@dataclass(frozen=True)
class TagRelation:
    from_record_id: str
    to_record_id: str
    relation_type: CatalogRelationType
    status: RelationStatus
    confidence: float | None
    source: str
    model: str | None
    rationale: str
    evidence: tuple[str, ...]
    updated_at: str


@dataclass(frozen=True)
class CatalogStats:
    records: int
    names: int
    relations: int
    concepts: int
    facets: int
    fts_rows: int


@dataclass(frozen=True)
class TagHit:
    record_id: str
    canonical_name: str
    prompt_form: str
    category: str
    usage_count: int
    source: str
    source_version: str
    deprecated: bool
    facets: tuple[str, ...]
    match_type: str
    matched_name: str
    name_type: NameType
    score: float
    aliases: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationHit:
    relation_id: str
    record_id: str
    related_record_id: str
    relation_type: CatalogRelationType
    status: RelationStatus
    source: str
    confidence: float | None
    model: str | None
    rationale: str
    evidence: tuple[str, ...]
    provenance: tuple[str, ...] = ()
