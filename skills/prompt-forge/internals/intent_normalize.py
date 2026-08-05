"""Normalize caller-supplied creative evidence without execution concerns."""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = "1.0"
JOINT_UNKNOWN_FIELDS = ("hypothesis", "single_variable", "success_signal", "failure_signal", "next_data")
FORBIDDEN_METADATA = {"workflow", "node", "hash", "gpu", "execution", "mode", "runtime"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _normal(value: object) -> str:
    return " ".join(str(value).casefold().split())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = _normal(value)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _forbidden_key(key: str) -> bool:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key.casefold())
    parts = {part for part in re.split(r"[^a-z0-9]+", separated) if part}
    return bool(parts & FORBIDDEN_METADATA)


def _sanitize(value: object, *, allow_sha256: bool = False) -> object:
    if isinstance(value, dict):
        clean: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("evidence object keys must be strings")
            if key.casefold() == "sha256":
                if allow_sha256:
                    clean[key] = copy.deepcopy(child)
                continue
            if _forbidden_key(key):
                continue
            clean[key] = _sanitize(child)
        return clean
    if isinstance(value, list):
        return [_sanitize(child) for child in value]
    return copy.deepcopy(value)


def _records(raw: object, name: str, default_origin: str) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"evidence '{name}' must be a list")
    result: list[dict] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            record = {"value": item.strip(), "origin": default_origin}
        elif isinstance(item, dict):
            record = _sanitize(item)
            if not isinstance(record.get("value"), str) or not record["value"].strip():
                raise ValueError(f"evidence '{name}' records require a value")
            record["value"] = record["value"].strip()
            record.setdefault("origin", default_origin)
            if "source_text" in record and (not isinstance(record["source_text"], str) or not record["source_text"].strip()):
                raise ValueError(f"evidence '{name}' source_text must be non-empty")
        else:
            raise ValueError(f"evidence '{name}' must contain strings or objects")
        result.append(record)
    return result


def _dedupe_records(records: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for record in records:
        key = (str(record.get("dimension", "")).casefold(), _normal(record["value"]))
        if key not in seen:
            seen.add(key)
            result.append(record)
    return result


def _string_list(payload: dict, name: str) -> list[str]:
    raw = payload.get(name, [])
    if not isinstance(raw, list) or not all(isinstance(item, str) and item.strip() for item in raw):
        raise ValueError(f"evidence '{name}' must be a string list")
    return _dedupe([item.strip() for item in raw])


def _continuity_locks(payload: dict) -> dict[str, list[str]]:
    raw = payload.get("continuity_locks", {})
    if not isinstance(raw, dict):
        raise ValueError("evidence 'continuity_locks' must be an object")
    result: dict[str, list[str]] = {}
    for role, values in raw.items():
        if not isinstance(role, str) or not role.strip() or not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError(f"continuity lock '{role}' must be a string list")
        result[role.strip()] = _dedupe([value.strip() for value in values])
    return result


def _joint_unknowns(payload: dict) -> list[dict[str, str]]:
    raw = payload.get("joint_unknown", [])
    if not isinstance(raw, list):
        raise ValueError("evidence 'joint_unknown' must be a list")
    result: list[dict[str, str]] = []
    for experiment in raw:
        if not isinstance(experiment, dict):
            raise ValueError("joint unknowns must be experiment objects")
        clean: dict[str, str] = {}
        for field in JOINT_UNKNOWN_FIELDS:
            value = experiment.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"joint unknown experiment requires string '{field}'")
            clean[field] = value.strip()
        result.append(clean)
    return result


def _source_provenance(payload: dict) -> list[dict]:
    raw = payload.get("source_provenance", [])
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ValueError("evidence 'source_provenance' must be a list of objects")
    result: list[dict] = []
    for item in raw:
        source = _sanitize(item, allow_sha256=True)
        digest = source.get("sha256")
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise ValueError("source provenance requires a lowercase SHA-256 hash")
        result.append(source)
    return result


def _style_evidence(payload: dict) -> list[dict]:
    result: list[dict] = []
    raw = payload.get("style_evidence", [])
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ValueError("evidence 'style_evidence' must be a list of objects")
    result.extend(_sanitize(item) for item in raw)
    for field, kind in (("style_suggestions", "style_suggestion"), ("dialect_suggestions", "dialect_suggestion")):
        suggestions = payload.get(field, [])
        if not isinstance(suggestions, list) or not all(isinstance(item, dict) for item in suggestions):
            raise ValueError(f"evidence '{field}' must be a list of objects")
        result.extend({"kind": kind, "suggestion": _sanitize(item)} for item in suggestions)
    return result


def normalize_evidence(payload: dict) -> dict:
    """Return a canonical four-quadrant CreativeEvidence ledger."""
    if not isinstance(payload, dict):
        raise ValueError("evidence payload must be a JSON object")
    payload_user: list[dict] = []
    payload_assistant: list[dict] = []
    shared: list[dict] = []
    for name in ("shared_known", "explicit_evidence"):
        for record in _records(payload.get(name, []), name, "explicit"):
            origin = str(record.get("origin", "")).casefold()
            if origin == "explicit":
                shared.append(record)
            elif origin == "user_known_agent_unknown":
                payload_user.append(record)
            else:
                payload_assistant.append(record)
    payload_user.extend(_records(payload.get("user_known_agent_unknown", []), "user_known_agent_unknown", "user_known_agent_unknown"))
    payload_assistant.extend(_records(payload.get("assistant_known_user_unknown", []), "assistant_known_user_unknown", "inferred"))
    payload_assistant.extend(_records(payload.get("reasonable_inference", []), "reasonable_inference", "inferred"))
    dimensions = payload.get("dimensions", {})
    if not isinstance(dimensions, dict):
        raise ValueError("evidence 'dimensions' must be an object")
    for dimension, raw in sorted(dimensions.items()):
        for record in _records(raw, f"dimensions.{dimension}", "inferred"):
            record["dimension"] = dimension
            (shared if record.get("origin") == "explicit" else payload_assistant).append(record)
    shared = _dedupe_records(shared)
    shared_values = {_normal(record["value"]) for record in shared}
    assistant = _dedupe_records([record for record in payload_assistant if _normal(record["value"]) not in shared_values])
    user = _dedupe_records(payload_user)
    locks = _continuity_locks(payload)
    locked_facts = _string_list(payload, "locked_facts")
    locked_facts.extend(record["value"] for record in shared if record.get("locked") is True)
    locked_facts.extend(value for values in locks.values() for value in values)
    locked_facts = _dedupe(locked_facts)
    prohibited = _string_list(payload, "prohibited_expansion")
    if {_normal(value) for value in locked_facts} & {_normal(value) for value in prohibited}:
        raise ValueError("prohibited expansion cannot overlap locked facts or continuity locks")
    assets = payload.get("asset_refs", [])
    if not isinstance(assets, list) or not all(isinstance(item, dict) for item in assets):
        raise ValueError("evidence 'asset_refs' must be a list of objects")
    return {
        "schema_version": SCHEMA_VERSION,
        "shared_known": copy.deepcopy(shared),
        "user_known_agent_unknown": copy.deepcopy(user),
        "assistant_known_user_unknown": copy.deepcopy(assistant),
        "joint_unknown": _joint_unknowns(payload),
        "locked_facts": locked_facts,
        "continuity_locks": locks,
        "style_evidence": _style_evidence(payload),
        "asset_refs": _sanitize(assets),
        "uncertainty": _string_list(payload, "uncertainty"),
        "prohibited_expansion": prohibited,
        "source_provenance": _source_provenance(payload),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="intent_normalize")
    parser.add_argument("--input", type=Path, help="CreativeEvidence JSON path")
    parser.add_argument("--stdin", action="store_true", help="read CreativeEvidence JSON from stdin")
    args = parser.parse_args(argv)
    if bool(args.input) == bool(args.stdin):
        parser.error("choose exactly one of --input or --stdin")
    try:
        raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
        result = normalize_evidence(json.loads(raw))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[intent_normalize] {exc}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
