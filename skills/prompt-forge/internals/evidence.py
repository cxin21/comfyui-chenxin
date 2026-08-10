"""Evidence normalization: external input -> canonical CreativeEvidence.

Design (v3 redesign, virgin-principle rewrite):

v2 (`intent_normalize.py`) had a JSON-payload-based normalizer that:
  - Accepted caller-supplied dicts with `shared_known`,
    `user_known_agent_unknown`, `assistant_known_user_unknown`,
    `joint_unknown`, `locked_facts`, `continuity_locks`,
    `prohibited_expansion`, `source_provenance`, `dimensions`,
    `style_evidence` / `style_suggestions`, `dialect_suggestions`.
  - Normalised the four quadrants.
  - Routed `dimensions` into the right quadrants by origin.
  - Validated `joint_unknown` experiments (hypothesis /
    single_variable / success_signal / failure_signal / next_data all
    required, all non-empty strings).
  - Detected `locked_facts ∩ prohibited_expansion` overlap.
  - Sanitised forbidden metadata (workflow / node / hash / gpu /
    execution / mode / runtime) at any depth, except for sha256
    identifiers.
  - Returned a plain dict, not a typed object.

v3 inherits the v2 normalisation rules verbatim but changes the
output type from `dict` to a frozen `CreativeEvidence` dataclass with
typed `EvidenceFact` and `JointUnknown` records. v3 also adds a CLI
entry (`python -m internals.evidence --stdin`) so the v2 invocation
pattern still works, plus a `normalize_evidence_dict()` function that
returns the plain-dict form for downstream serialisation.

Conventions:
  - Functions never invent facts: empty/missing fields are kept empty.
  - Forbidden metadata is silently stripped at any depth.
  - Validation errors raise ValueError with the path to the bad field.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional


SCHEMA_VERSION = "3.0"

JOINT_UNKNOWN_FIELDS = (
    "hypothesis",
    "single_variable",
    "success_signal",
    "failure_signal",
    "next_data",
)

FORBIDDEN_METADATA = frozenset({
    "workflow", "node", "hash", "gpu", "execution", "mode", "runtime",
})

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

Origin = Literal["explicit", "inferred", "advisory", "user_known_agent_unknown"]


# ===========================================================================
# Typed records
# ===========================================================================

@dataclass(frozen=True)
class EvidenceFact:
    """A single fact in one of the four quadrants.

    `dimension` is optional (empty when the caller did not tag the
    fact). `confidence` is "known" by default; callers may override.
    """

    value: str
    origin: Origin
    source_id: str = ""
    source_section: str = ""
    source_text: str = ""
    dimension: str = ""
    confidence: str = "known"
    locked: bool = False


@dataclass(frozen=True)
class JointUnknown:
    """An open question expressed as a single-variable experiment.

    All five fields (hypothesis / single_variable / success_signal /
    failure_signal / next_data) are required non-empty strings.
    """

    hypothesis: str
    single_variable: str
    success_signal: str
    failure_signal: str
    next_data: str = ""


@dataclass(frozen=True)
class CreativeEvidence:
    """The canonical four-quadrant evidence ledger."""

    schema_version: str
    shared_known: tuple[EvidenceFact, ...]
    user_known_agent_unknown: tuple[EvidenceFact, ...]
    assistant_known_user_unknown: tuple[EvidenceFact, ...]
    joint_unknown: tuple[JointUnknown, ...]
    locked_facts: tuple[str, ...]
    continuity_locks: tuple[tuple[str, str], ...]  # (kind, description)
    style_evidence: tuple[tuple[str, str], ...]    # (kind, suggestion)
    asset_refs: tuple[tuple[str, str], ...]        # (asset_id, role)
    uncertainty: tuple[str, ...]
    prohibited_expansion: tuple[str, ...]
    source_provenance: tuple[dict, ...]


# ===========================================================================
# Helpers
# ===========================================================================

def _normal(value: Any) -> str:
    """Casefold + collapse whitespace for set-membership tests."""
    return " ".join(str(value).casefold().split())


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = _normal(v)
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _is_forbidden_key(key: str) -> bool:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key.casefold())
    parts = {p for p in re.split(r"[^a-z0-9]+", separated) if p}
    return bool(parts & FORBIDDEN_METADATA)


def _sanitize(value: Any, *, allow_sha256: bool = False) -> Any:
    """Strip forbidden metadata at any depth. Allow sha256 identifiers only."""
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("evidence object keys must be strings")
            if key.casefold() == "sha256":
                if allow_sha256 and isinstance(child, str) and SHA256_RE.match(child):
                    clean[key] = copy.deepcopy(child)
                continue
            if _is_forbidden_key(key):
                continue
            clean[key] = _sanitize(child, allow_sha256=allow_sha256)
        return clean
    if isinstance(value, list):
        return [_sanitize(child, allow_sha256=allow_sha256) for child in value]
    return copy.deepcopy(value)


def _as_list(value: Any, name: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"evidence {name!r} must be a list")
    return value


def _records(
    raw: Any,
    name: str,
    default_origin: str,
) -> list[EvidenceFact]:
    """Parse a list of fact records (str or dict) into EvidenceFact."""
    out: list[EvidenceFact] = []
    for item in _as_list(raw, name):
        if isinstance(item, str):
            value = item.strip()
            if not value:
                continue
            out.append(EvidenceFact(
                value=value,
                origin=_normalise_origin(default_origin),
            ))
            continue
        if isinstance(item, dict):
            clean = _sanitize(item)
            value = clean.get("value")
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"evidence {name!r} records require a non-empty value")
            if "source_text" in clean and (
                not isinstance(clean["source_text"], str)
                or not clean["source_text"].strip()
            ):
                raise ValueError(f"evidence {name!r} source_text must be non-empty")
            out.append(EvidenceFact(
                value=value.strip(),
                origin=_normalise_origin(clean.get("origin", default_origin)),
                source_id=str(clean.get("source_id", "")).strip(),
                source_section=str(clean.get("source_section", "")).strip(),
                source_text=str(clean.get("source_text", "")).strip(),
                dimension=str(clean.get("dimension", "")).strip(),
                confidence=str(clean.get("confidence", "known")).strip() or "known",
                locked=bool(clean.get("locked", False)),
            ))
            continue
        raise ValueError(f"evidence {name!r} records must be strings or objects")
    return out


def _normalise_origin(raw: Any) -> Origin:
    s = str(raw or "").casefold()
    if s in ("explicit", "inferred", "advisory", "user_known_agent_unknown"):
        return s  # type: ignore[return-value]
    return "inferred"


def _dedupe_records(records: list[EvidenceFact]) -> list[EvidenceFact]:
    seen: set[tuple[str, str]] = set()
    out: list[EvidenceFact] = []
    for r in records:
        key = (r.dimension.casefold(), _normal(r.value))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _string_list(payload: dict, name: str) -> list[str]:
    raw = payload.get(name, [])
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(
        isinstance(item, str) and item.strip() for item in raw
    ):
        raise ValueError(f"evidence {name!r} must be a string list")
    return _dedupe_strings([item.strip() for item in raw])


def _continuity_locks(payload: dict) -> dict[str, list[str]]:
    raw = payload.get("continuity_locks", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("evidence 'continuity_locks' must be an object")
    out: dict[str, list[str]] = {}
    for role, values in raw.items():
        if not isinstance(role, str) or not role.strip():
            raise ValueError("continuity_locks keys must be non-empty strings")
        if not isinstance(values, list) or not all(
            isinstance(v, str) and v.strip() for v in values
        ):
            raise ValueError(f"continuity_locks[{role!r}] must be a string list")
        out[role.strip()] = _dedupe_strings([v.strip() for v in values])
    return out


def _joint_unknowns(payload: dict) -> list[JointUnknown]:
    raw = payload.get("joint_unknown", [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("evidence 'joint_unknown' must be a list")
    out: list[JointUnknown] = []
    for exp in raw:
        if not isinstance(exp, dict):
            raise ValueError("joint unknowns must be experiment objects")
        clean = _sanitize(exp)
        record: dict[str, str] = {}
        required = [f for f in JOINT_UNKNOWN_FIELDS if f != "next_data"]
        for field in required:
            value = clean.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"joint unknown experiment requires non-empty string {field!r}"
                )
            record[field] = value.strip()
        next_data = clean.get("next_data")
        if isinstance(next_data, str) and next_data.strip():
            record["next_data"] = next_data.strip()
        out.append(JointUnknown(
            hypothesis=record["hypothesis"],
            single_variable=record["single_variable"],
            success_signal=record["success_signal"],
            failure_signal=record["failure_signal"],
            next_data=record.get("next_data", ""),
        ))
    return out


def _source_provenance(payload: dict) -> list[dict]:
    raw = payload.get("source_provenance", [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("evidence 'source_provenance' must be a list")
    return [_sanitize(item, allow_sha256=True) for item in raw]


def _style_evidence(payload: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    raw = payload.get("style_evidence", [])
    if raw is not None:
        if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
            raise ValueError("evidence 'style_evidence' must be a list of objects")
        for item in raw:
            clean = _sanitize(item)
            kind = clean.get("kind")
            suggestion = clean.get("suggestion")
            if not isinstance(kind, str) or not isinstance(suggestion, str):
                raise ValueError(
                    "evidence 'style_evidence' entries require string 'kind' and 'suggestion'"
                )
            out.append((kind, suggestion))
    for field, kind in (("style_suggestions", "style_suggestion"),
                        ("dialect_suggestions", "dialect_suggestion")):
        items = payload.get(field, [])
        if items is None:
            continue
        if not isinstance(items, list) or not all(isinstance(it, dict) for it in items):
            raise ValueError(f"evidence {field!r} must be a list of objects")
        for item in items:
            clean = _sanitize(item)
            out.append((kind, _summarise_dict(clean)))
    return out


def _summarise_dict(entry: dict) -> str:
    parts: list[str] = []
    for key in ("id", "name", "score", "reason"):
        if key in entry:
            parts.append(f"{key}={entry[key]}")
    return "; ".join(parts) or "{}"


def _asset_refs(payload: dict) -> list[tuple[str, str]]:
    raw = payload.get("asset_refs", [])
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ValueError("evidence 'asset_refs' must be a list of objects")
    out: list[tuple[str, str]] = []
    for item in raw:
        clean = _sanitize(item)
        asset_id = str(clean.get("asset_id", clean.get("id", ""))).strip()
        role = str(clean.get("role", "")).strip()
        if asset_id and role:
            out.append((asset_id, role))
    return out


# ===========================================================================
# Public entry: normalize_evidence
# ===========================================================================

def normalize_evidence(payload: dict) -> CreativeEvidence:
    """Return a canonical four-quadrant CreativeEvidence ledger.

    Raises ValueError on any structural problem (forbidden metadata
    leakage, joint_unknown missing fields, locked_facts ∩
    prohibited_expansion overlap, asset_refs wrong shape, etc.).
    """
    if not isinstance(payload, dict):
        raise ValueError("evidence payload must be a JSON object")

    shared: list[EvidenceFact] = []
    user: list[EvidenceFact] = []
    assistant: list[EvidenceFact] = []

    for name in ("shared_known", "explicit_evidence"):
        for record in _records(payload.get(name, []), name, "explicit"):
            origin = record.origin
            if origin == "explicit":
                shared.append(record)
            elif origin == "user_known_agent_unknown":
                user.append(record)
            else:
                assistant.append(record)

    user.extend(_records(payload.get("user_known_agent_unknown", []),
                         "user_known_agent_unknown", "user_known_agent_unknown"))
    assistant.extend(_records(payload.get("assistant_known_user_unknown", []),
                               "assistant_known_user_unknown", "inferred"))
    assistant.extend(_records(payload.get("reasonable_inference", []),
                               "reasonable_inference", "inferred"))

    dimensions = payload.get("dimensions", {})
    if dimensions is None:
        dimensions = {}
    if not isinstance(dimensions, dict):
        raise ValueError("evidence 'dimensions' must be an object")
    for dimension, raw in sorted(dimensions.items()):
        for record in _records(raw, f"dimensions.{dimension}", "inferred"):
            record = EvidenceFact(
                value=record.value,
                origin=record.origin,
                source_id=record.source_id,
                source_section=record.source_section,
                source_text=record.source_text,
                dimension=dimension,
                confidence=record.confidence,
                locked=record.locked,
            )
            (shared if record.origin == "explicit" else assistant).append(record)

    shared = _dedupe_records(shared)
    shared_values = {_normal(r.value) for r in shared}
    assistant = _dedupe_records([
        r for r in assistant if _normal(r.value) not in shared_values
    ])
    user = _dedupe_records(user)

    locks = _continuity_locks(payload)
    locked_facts = _string_list(payload, "locked_facts")
    locked_facts.extend(r.value for r in shared if r.locked)
    for values in locks.values():
        locked_facts.extend(values)
    locked_facts = _dedupe_strings(locked_facts)

    prohibited = _string_list(payload, "prohibited_expansion")
    locked_set = {_normal(v) for v in locked_facts}
    prohibited_set = {_normal(v) for v in prohibited}
    if locked_set & prohibited_set:
        overlap = sorted(locked_set & prohibited_set)
        raise ValueError(
            "prohibited_expansion cannot overlap locked facts or continuity locks: "
            + ", ".join(overlap)
        )

    return CreativeEvidence(
        schema_version=SCHEMA_VERSION,
        shared_known=tuple(shared),
        user_known_agent_unknown=tuple(user),
        assistant_known_user_unknown=tuple(assistant),
        joint_unknown=tuple(_joint_unknowns(payload)),
        locked_facts=tuple(locked_facts),
        continuity_locks=tuple((k, v) for k, vs in locks.items() for v in vs),
        style_evidence=tuple(_style_evidence(payload)),
        asset_refs=tuple(_asset_refs(payload)),
        uncertainty=tuple(_string_list(payload, "uncertainty")),
        prohibited_expansion=tuple(prohibited),
        source_provenance=tuple(_source_provenance(payload)),
    )


def normalize_evidence_dict(payload: dict) -> dict:
    """Serialise the normalised evidence to a plain dict.

    This is the form v2 returned from `normalize_evidence()`. v3 returns
    a typed CreativeEvidence by default; this helper gives callers who
    want JSON-friendly output a one-call path.
    """
    ev = normalize_evidence(payload)
    return {
        "schema_version": ev.schema_version,
        "shared_known": [
            {
                "value": r.value, "origin": r.origin,
                "source_id": r.source_id, "source_section": r.source_section,
                "source_text": r.source_text, "dimension": r.dimension,
                "confidence": r.confidence, "locked": r.locked,
            }
            for r in ev.shared_known
        ],
        "user_known_agent_unknown": [
            {"value": r.value, "origin": r.origin, "dimension": r.dimension}
            for r in ev.user_known_agent_unknown
        ],
        "assistant_known_user_unknown": [
            {"value": r.value, "origin": r.origin, "dimension": r.dimension}
            for r in ev.assistant_known_user_unknown
        ],
        "joint_unknown": [
            {
                "hypothesis": j.hypothesis,
                "single_variable": j.single_variable,
                "success_signal": j.success_signal,
                "failure_signal": j.failure_signal,
                "next_data": j.next_data,
            }
            for j in ev.joint_unknown
        ],
        "locked_facts": list(ev.locked_facts),
        "continuity_locks": [{"kind": k, "description": d} for k, d in ev.continuity_locks],
        "style_evidence": [{"kind": k, "suggestion": s} for k, s in ev.style_evidence],
        "asset_refs": [{"asset_id": a, "role": r} for a, r in ev.asset_refs],
        "uncertainty": list(ev.uncertainty),
        "prohibited_expansion": list(ev.prohibited_expansion),
        "source_provenance": list(ev.source_provenance),
    }


# ===========================================================================
# CLI entry (v2 parity: `python -m internals.evidence --stdin`)
# ===========================================================================

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="prompt_forge_evidence")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="CreativeEvidence JSON path")
    source.add_argument("--stdin", action="store_true",
                        help="read CreativeEvidence JSON from stdin")
    parser.add_argument("--output-format", choices=("typed", "dict"),
                        default="dict",
                        help="typed = return CreativeEvidence dict-of-dicts; "
                             "dict = return serialised plain dict (default)")
    args = parser.parse_args(argv)
    if bool(args.input) == bool(args.stdin):
        parser.error("choose exactly one of --input or --stdin")
    try:
        raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
        payload = json.loads(raw)
        result = normalize_evidence_dict(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[evidence] {exc}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())