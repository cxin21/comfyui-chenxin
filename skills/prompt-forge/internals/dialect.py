"""Dialect registry: lookup with approved-alias, modality, ambiguity, fail-closed.

Design (v3 redesign, virgin-principle rewrite):

v2 had two pieces:
  - `dialect_lookup.py` — case-insensitive exact match against an
    approved-alias list, with modality check, ambiguity detection, and
    fail-closed semantics. Loaded from `dialects/index.json` (alias
    table) + `dialects/image.json` / `dialects/video.json` (per-
    modality dialect data).
  - The dialect data files were separate from the alias table.

v3 collapses the alias table and dialect data into ONE registry file
(`registry/dialects.json`) with `id`, `aliases`, and all per-dialect
fields on the same row. v3 inherits v2's lookup semantics verbatim:

  - case-insensitive exact match (no substring, no fuzzy)
  - approved aliases only (caller-supplied aliases via the
    `aliases` kwarg are also allowed, like v2's `_approved_aliases`)
  - modality check (when requested)
  - ambiguity detection (multiple canonicals matching the same query
    is a hard error)
  - fail-closed (unknown / ambiguous / wrong-modality / malformed
    queries all raise ValueError)

v3 adds:
  - Single registry source of truth (no split between index and data)
  - Frozen `Dialect` dataclass with typed fields (no runtime dict
    reads on hot path)
  - `load_dialects()` returns all canonical dialects
  - `list_by_modality(modality)` filter
  - `reload()` clears the lru_cache

Conventions:
  - Functions never invent facts: an unknown query raises.
  - Functions never fall back to substring matching.
  - Functions are pure modulo a process-lifetime lru_cache.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional, Sequence


SKILL_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = SKILL_DIR / "registry" / "dialects.json"

_MODALITIES = frozenset({"image", "video"})

_FORBIDDEN_DIALECT_KEYS = frozenset({
    "workflow", "node", "hash", "gpu", "execution", "mode", "runtime",
    "ready_to_execute", "profile", "slot", "transport", "settings",
})

# Aliases with no whitespace, dashes, or underscores map to the same
# canonical as the dash/space/underscore variants (v2 had this
# normalisation in `lookup_dialect` indirectly via casefold).
_NORMALISE_RE = re.compile(r"[\s\-_]+")


def _normalise(name: str) -> str:
    """Casefold + collapse all whitespace / dash / underscore separators.

    `flux_kontext` and `flux-kontext` and `flux kontext` and `FluxKontext`
    all map to the same key. v2 only casefolded; v3 also collapses
    separators because registered dialect ids sometimes drift.
    """
    return _NORMALISE_RE.sub("", name.casefold())


def _is_forbidden_dialect_key(key: str) -> bool:
    """Reject runtime metadata that should not appear in dialect data."""
    if key.casefold() in _FORBIDDEN_DIALECT_KEYS:
        return True
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    parts = {p for p in re.split(r"[^a-zA-Z0-9]+", separated.casefold()) if p}
    return bool(parts & _FORBIDDEN_DIALECT_KEYS)


@dataclass(frozen=True)
class Dialect:
    """A single dialect definition. Mirrors the registry JSON 1:1.

    `projection` is the short name of a function in `project.py`. The
    registry never inlines projection logic.
    """

    id: str
    aliases: tuple[str, ...]
    modality: Literal["image", "video"]
    form: str
    projection: str
    ordering: tuple[str, ...]
    required: tuple[str, ...]
    supports_negative: bool
    supports_style: bool
    notes: str


@lru_cache(maxsize=1)
def _load() -> dict[str, Dialect]:
    """Load and cache the registry. Cache is process-lifetime."""
    # utf-8-sig strips a leading BOM if present (PowerShell Set-Content
    # often adds one). Pure utf-8 would preserve the BOM and break json.loads.
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict) or "dialects" not in raw:
        raise ValueError("registry must contain a 'dialects' array")
    out: dict[str, Dialect] = {}
    for entry in raw["dialects"]:
        if not isinstance(entry, dict):
            raise ValueError("each dialect entry must be an object")
        for k in entry:
            if _is_forbidden_dialect_key(str(k)):
                raise ValueError(
                    f"runtime metadata field is not allowed in dialect registry: {k!r}"
                )
        canonical_id = entry.get("id")
        if not isinstance(canonical_id, str) or not canonical_id.strip():
            raise ValueError("dialect entry must have a non-empty 'id'")
        if canonical_id in out:
            raise ValueError(f"duplicate dialect id {canonical_id!r} in registry")
        modality = entry.get("modality")
        if modality not in _MODALITIES:
            raise ValueError(
                f"dialect {canonical_id!r} has invalid modality {modality!r}; "
                f"must be 'image' or 'video'"
            )
        out[canonical_id] = Dialect(
            id=canonical_id,
            aliases=tuple(entry.get("aliases", []) or ()),
            modality=modality,
            form=str(entry.get("form", "")),
            projection=str(entry.get("projection", "")),
            ordering=tuple(entry.get("ordering", []) or ()),
            required=tuple(entry.get("required", []) or ()),
            supports_negative=bool(entry.get("supports_negative", False)),
            supports_style=bool(entry.get("supports_style", True)),
            notes=str(entry.get("notes", "")),
        )
    return out


def load_dialects() -> tuple[Dialect, ...]:
    """Return all canonical dialects. Order is registry order."""
    return tuple(_load().values())


def list_by_modality(modality: Literal["image", "video"]) -> tuple[Dialect, ...]:
    """Return all dialects of a given modality, in registry order."""
    if modality not in _MODALITIES:
        raise ValueError(f"unsupported modality: {modality!r}")
    return tuple(d for d in _load().values() if d.modality == modality)


def _resolve_canonical_id(
    query: str,
    extra_aliases: Optional[dict[str, str | Sequence[str]]] = None,
) -> set[str]:
    """Return the set of canonical ids that match `query` exactly.

    Matching is:
      - case-insensitive
      - separator-agnostic (whitespace, dash, underscore collapse)
      - exact substring only (no prefix / substring / fuzzy match)
      - canonical id first, then `aliases` array on each entry, then
        caller-supplied `extra_aliases`.

    The returned set may contain zero or multiple canonical ids; callers
    must reject ambiguous matches (multiple canonicals) themselves.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("dialect query must be a non-empty string")
    target = _normalise(query)

    candidates: set[str] = set()
    registry = _load()

    for canonical, dialect in registry.items():
        names = [canonical, *dialect.aliases]
        for name in names:
            if isinstance(name, str) and _normalise(name) == target:
                candidates.add(canonical)
                break

    if extra_aliases:
        for alias, target_canonicals in extra_aliases.items():
            if not isinstance(alias, str):
                raise ValueError(
                    f"extra_aliases key {alias!r} must be a string"
                )
            if _normalise(alias) != target:
                continue
            if isinstance(target_canonicals, str):
                iter_targets = [target_canonicals]
            elif isinstance(target_canonicals, Sequence):
                iter_targets = list(target_canonicals)
            else:
                raise ValueError(
                    f"extra_aliases[{alias!r}] must be a string or list of strings"
                )
            for tc in iter_targets:
                if not isinstance(tc, str) or not tc.strip():
                    raise ValueError(
                        f"extra_aliases[{alias!r}] entries must be non-empty strings"
                    )
                if tc not in registry:
                    raise ValueError(
                        f"extra_aliases[{alias!r}] references unknown canonical {tc!r}"
                    )
                candidates.add(tc)

    return candidates


def lookup_dialect(
    query: str,
    modality: Optional[Literal["image", "video"]] = None,
    extra_aliases: Optional[dict[str, str | Sequence[str]]] = None,
) -> Dialect:
    """Resolve a dialect by exact id or alias. Case- and separator-insensitive.

    Args:
        query: The dialect id or alias to look up.
        modality: If given, must match the dialect's modality. Used to
            catch image/video confusion at the call site.
        extra_aliases: Optional caller-supplied alias table mapping alias
            string to one or more canonical ids. Used to register
            additional aliases without editing the registry.

    Raises:
        ValueError: empty query, unknown dialect, ambiguous dialect
            (multiple canonicals match), or modality mismatch.
    """
    if modality is not None and modality not in _MODALITIES:
        raise ValueError(f"unsupported modality: {modality!r}")

    candidates = _resolve_canonical_id(query, extra_aliases)

    if not candidates:
        raise ValueError(f"unknown dialect: {query!r}")
    if len(candidates) > 1:
        joined = ", ".join(sorted(candidates))
        raise ValueError(f"ambiguous dialect {query!r}: {joined}")

    canonical_id = next(iter(candidates))
    dialect = _load()[canonical_id]

    if modality is not None and dialect.modality != modality:
        raise ValueError(
            f"dialect {canonical_id!r} has modality {dialect.modality!r}, "
            f"not {modality!r}"
        )

    return dialect


def reload() -> None:
    """Clear the registry cache. Useful after editing dialects.json in tests."""
    _load.cache_clear()