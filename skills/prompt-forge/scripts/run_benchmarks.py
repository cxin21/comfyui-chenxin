"""Offline deterministic Prompt Forge benchmark and calibration manifest tool."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterable

_SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from prompt_forge import author_anima_prompt, author_h3_ref2va_prompt, author_h3_t2va_prompt
from prompt_forge.artifacts import PromptArtifact
from prompt_forge.contracts import (
    AnimaAuthoringRequest,
    AuthoredSegment,
    Complexity,
    Fact,
    H3Ref2VAAuthoringRequest,
    H3ReferenceImage,
    H3T2VAAuthoringRequest,
)


ROOT = _SKILL_ROOT
DEFAULT_CASES = ROOT / "benchmarks" / "cases"
DEFAULT_BASELINE = ROOT / "benchmarks" / "baselines" / "prompt_metrics.json"
_CALIBRATION_CASE_IDS = frozenset({
    "anima-simple-01",
    "anima-boundary-01",
    "h3-t2va-simple-01",
    "h3-t2va-simple-04",
    "h3-t2va-simple-08",
    "h3-t2va-simple-10",
    "h3-ref2va-boundary-01",
    "h3-ref2va-boundary-02",
})


class BenchmarkError(ValueError):
    """The corpus, baseline, or calibration request is invalid."""


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise BenchmarkError(f"{path}:{line_number} must contain an object")
        _validate_case(value, path, line_number)
        cases.append(value)
    return cases


def compile_case(case: dict[str, Any]) -> PromptArtifact:
    facts = tuple(_fact(value) for value in case["facts"])
    request = case["request"]
    path = case["path"]
    if path == "anima":
        return author_anima_prompt(
            AnimaAuthoringRequest(
                facts=facts,
                positive_segments=_segments(request["positive_segments"]),
                complexity=Complexity(**request["complexity"]),
                negative_segments=_segments(request.get("negative_segments", [])),
                exclusion_groups=request.get("exclusion_groups", 0),
            )
        )
    if path == "h3_t2va":
        return author_h3_t2va_prompt(
            H3T2VAAuthoringRequest(
                facts=facts,
                duration_seconds=request["duration_seconds"],
                shot_count=request["shot_count"],
                integrated_multimodal_description=_segments(
                    request["integrated_multimodal_description"]
                ),
                overall_soundscape=_segments(request.get("overall_soundscape", [])),
                non_diegetic_music=_segments(request.get("non_diegetic_music", [])),
            )
        )
    if path == "h3_ref2va":
        references = tuple(H3ReferenceImage(**value) for value in request["references"])
        return author_h3_ref2va_prompt(
            H3Ref2VAAuthoringRequest(
                facts=facts,
                duration_seconds=request["duration_seconds"],
                shot_count=request["shot_count"],
                references=references,
                subject_definitions=_segments(request["subject_definitions"]),
                summary=_segments(request["summary"]),
                retention_analysis=_segments(request["retention_analysis"]),
                detailed_description=_segments(request["detailed_description"]),
                overall_soundscape=_segments(request.get("overall_soundscape", [])),
                non_diegetic_music=_segments(request.get("non_diegetic_music", [])),
            )
        )
    raise BenchmarkError(f"unsupported benchmark path: {path!r}")


def run_benchmarks(cases_dir: Path = DEFAULT_CASES) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for path in ("anima", "h3_t2va", "h3_ref2va"):
        for stratum in ("simple", "boundary", "adversarial"):
            results.extend(_run_isolated_chunk(cases_dir, path, stratum))
    status_counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema_version": 1,
        "case_count": len(results),
        "hard_failures": {
            "status_mismatches": 0,
            "non_deterministic_artifacts": 0,
            "sacrificed_fact_cases": sum(bool(item["sacrificed_facts"]) for item in results),
            "binding_violation_cases": sum(item["binding_violations"] > 0 for item in results),
        },
        "status_counts": dict(sorted(status_counts.items())),
        "cases": results,
    }


def _run_isolated_chunk(
    cases_dir: Path,
    path: str,
    stratum: str,
) -> list[dict[str, Any]]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--cases-dir",
        str(cases_dir.resolve()),
        "--run-chunk",
        path,
        stratum,
    ]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise BenchmarkError(
            f"benchmark chunk {path}/{stratum} failed with exit {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    payload = json.loads(result.stdout)
    if not isinstance(payload, list) or len(payload) != 10:
        raise BenchmarkError(f"benchmark chunk {path}/{stratum} returned invalid metrics")
    return payload


def _run_chunk(cases_dir: Path, path: str, stratum: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cases = load_cases(cases_dir / f"{path}.jsonl")
    selected = [case for case in cases if case["stratum"] == stratum]
    if len(selected) != 10:
        raise BenchmarkError(f"chunk {path}/{stratum} must contain exactly 10 cases")
    for case in selected:
        first = compile_case(case)
        second = compile_case(case)
        if first.to_json() != second.to_json():
            raise BenchmarkError(f"non-deterministic artifact: {case['case_id']}")
        if first.status != case["expected_status"]:
            raise BenchmarkError(
                f"{case['case_id']} expected {case['expected_status']}, got {first.status}"
            )
        results.append(_metrics(case, first))
    return results


def verify_baseline(report: dict[str, Any], path: Path = DEFAULT_BASELINE) -> None:
    baseline = json.loads(path.read_text(encoding="utf-8"))
    if baseline != report:
        expected = {item["case_id"]: item for item in baseline.get("cases", [])}
        actual = {item["case_id"]: item for item in report.get("cases", [])}
        changed = sorted(
            case_id for case_id in set(expected) | set(actual)
            if expected.get(case_id) != actual.get(case_id)
        )
        raise BenchmarkError(f"benchmark baseline mismatch in cases: {changed}")


def prepare_generation_pairs(
    cases_dir: Path,
    output: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in ("anima", "h3_t2va", "h3_ref2va"):
        for case in load_cases(cases_dir / f"{path}.jsonl"):
            if case["case_id"] not in _CALIBRATION_CASE_IDS:
                continue
            artifact = compile_case(case)
            if artifact.status != "production_ready":
                raise BenchmarkError(
                    f"calibration anchor is not production_ready: {case['case_id']}"
                )
            records.append(_pair_record(case, artifact))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(_canonical(record) + "\n" for record in records),
        encoding="utf-8",
        newline="\n",
    )
    return records


def _pair_record(case: dict[str, Any], artifact: PromptArtifact) -> dict[str, Any]:
    return {
        "pair_id": f"{case['case_id']}-pair",
        "case_id": case["case_id"],
        "path": case["path"],
        "stratum": case["stratum"],
        "seed": int.from_bytes(
            hashlib.sha256(case["case_id"].encode()).digest()[:8], "big"
        ),
        "artifact_sha256": artifact.artifact_sha256,
        "workflow_sha256": None,
        "execution_requested": False,
        "variants": {
            "authored_uncompressed": _authored_fields(case),
            "compiled": dict(artifact.prompt or {}),
            "expert_authored": None,
        },
    }


def _validate_case(value: dict[str, Any], path: Path, line_number: int) -> None:
    required = {
        "case_id", "path", "stratum", "reviewed", "expected_status", "facts", "request"
    }
    if set(value) != required:
        raise BenchmarkError(f"{path}:{line_number} has invalid fields")
    if value["path"] not in {"anima", "h3_t2va", "h3_ref2va"}:
        raise BenchmarkError(f"{path}:{line_number} has invalid path")
    if value["stratum"] not in {"simple", "boundary", "adversarial"}:
        raise BenchmarkError(f"{path}:{line_number} has invalid stratum")
    if value["reviewed"] is not True:
        raise BenchmarkError(f"{path}:{line_number} is not hand-reviewed")
    if value["expected_status"] not in {
        "production_ready", "quality_rejected", "budget_conflict"
    }:
        raise BenchmarkError(f"{path}:{line_number} has invalid expected status")
    if not isinstance(value["facts"], list) or not value["facts"]:
        raise BenchmarkError(f"{path}:{line_number} requires facts")
    if not isinstance(value["request"], dict) or not value["request"]:
        raise BenchmarkError(f"{path}:{line_number} requires a request")


def _fact(value: dict[str, Any]) -> Fact:
    payload = dict(value)
    raw = payload.pop("value_spec", payload.pop("value", ""))
    payload["value"] = _text(raw)
    return Fact(**payload)


def _segments(values: Iterable[dict[str, Any]]) -> tuple[AuthoredSegment, ...]:
    result: list[AuthoredSegment] = []
    for value in values:
        payload = dict(value)
        raw = payload.pop("text_spec", payload.pop("text", ""))
        payload["text"] = _text(raw)
        payload["fact_ids"] = tuple(payload["fact_ids"])
        result.append(AuthoredSegment(**payload))
    return tuple(result)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict) or set(value) != {"prefix", "count", "joiner"}:
        raise BenchmarkError("text must be a string or an exact synthetic series")
    prefix = value["prefix"]
    count = value["count"]
    joiner = value["joiner"]
    if not isinstance(prefix, str) or not isinstance(joiner, str):
        raise BenchmarkError("synthetic series prefix and joiner must be strings")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise BenchmarkError("synthetic series count must be positive")
    return joiner.join(f"{prefix}{index}" for index in range(count))


def _metrics(case: dict[str, Any], artifact: PromptArtifact) -> dict[str, Any]:
    protected = [fact.fact_id for fact in artifact.facts if fact.origin != "agent_embellishment"]
    rendered = sum(bool(artifact.trace.get(fact_id)) for fact_id in protected)
    findings = _findings(artifact.audit)
    hard_codes = set(artifact.audit.get("hard_gate_codes", ()))
    binding_codes = {
        "reference_binding", "reference_ownership", "stable_appearance_scope",
        "possible_binding_conflict",
    }
    return {
        "case_id": case["case_id"],
        "path": case["path"],
        "stratum": case["stratum"],
        "status": artifact.status,
        "protected_fact_recall": rendered / len(protected) if protected else 1.0,
        "duplicate_semantic_count": sum(
            finding.get("code") == "duplicate_semantics" for finding in findings
        ),
        "binding_violations": len(hard_codes.intersection(binding_codes)) + sum(
            finding.get("code") == "possible_binding_conflict" for finding in findings
        ),
        "token_count": _actual_tokens(artifact.token_report),
        "compression_savings": sum(
            int(getattr(operation, "token_saving", 0)) for operation in artifact.compression
        ),
        "status_expected": artifact.status == case["expected_status"],
        "sacrificed_facts": list(artifact.sacrificed_facts),
        "deterministic_hash": artifact.artifact_sha256,
    }


def _findings(value: Any) -> list[Mapping[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        if isinstance(value.get("findings"), (list, tuple)):
            found.extend(item for item in value["findings"] if isinstance(item, Mapping))
        for child in value.values():
            found.extend(_findings(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.extend(_findings(child))
    return found


def _actual_tokens(value: Any) -> int:
    if not isinstance(value, Mapping):
        return 0
    own = value.get("actual")
    if isinstance(own, int) and not isinstance(own, bool):
        return own
    return sum(_actual_tokens(child) for child in value.values())


def _authored_fields(case: dict[str, Any]) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for value in case["request"].values():
        if not isinstance(value, list):
            continue
        for segment in value:
            if isinstance(segment, dict) and "field" in segment:
                fields.setdefault(segment["field"], []).append(
                    _text(segment.get("text_spec", segment.get("text", "")))
                )
    return fields


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-dir", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--verify-baseline", action="store_true")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--prepare-generation-pairs", type=Path)
    parser.add_argument("--run-chunk", nargs=2, metavar=("PATH", "STRATUM"))
    args = parser.parse_args()
    if args.run_chunk is not None:
        print(_canonical(_run_chunk(args.cases_dir, *args.run_chunk)))
        return 0
    if args.prepare_generation_pairs is not None:
        prepare_generation_pairs(args.cases_dir, args.prepare_generation_pairs)
        return 0
    report = run_benchmarks(args.cases_dir)
    if args.write_baseline:
        DEFAULT_BASELINE.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_BASELINE.write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if args.verify_baseline:
        verify_baseline(report)
    print(_canonical(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
