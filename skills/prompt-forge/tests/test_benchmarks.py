from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.run_benchmarks import (
    compile_case,
    load_cases,
    prepare_generation_pairs,
    run_benchmarks,
    verify_baseline,
)


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks" / "cases"


@pytest.fixture(scope="module")
def benchmark_report() -> dict:
    return run_benchmarks(CASES)


def test_each_path_has_30_balanced_hand_reviewed_cases() -> None:
    all_ids: set[str] = set()
    for path in ("anima", "h3_t2va", "h3_ref2va"):
        cases = load_cases(CASES / f"{path}.jsonl")
        assert len(cases) == 30
        assert Counter(case["stratum"] for case in cases) == {
            "simple": 10,
            "boundary": 10,
            "adversarial": 10,
        }
        assert all(case["path"] == path for case in cases)
        assert all(case["reviewed"] is True for case in cases)
        assert all(case["facts"] and case["request"] for case in cases)
        case_ids = {case["case_id"] for case in cases}
        assert len(case_ids) == 30
        assert not all_ids.intersection(case_ids)
        all_ids.update(case_ids)


def test_every_case_is_deterministic_and_matches_expected_status(
    benchmark_report: dict,
) -> None:
    assert len(benchmark_report["cases"]) == 90
    assert all(case["status_expected"] for case in benchmark_report["cases"])
    assert all(case["sacrificed_facts"] == [] for case in benchmark_report["cases"])


def test_benchmark_reports_non_compensating_metrics_and_matches_baseline(
    benchmark_report: dict,
) -> None:
    assert benchmark_report["schema_version"] == 1
    assert "composite_score" not in benchmark_report
    assert len(benchmark_report["cases"]) == 90
    for metric in (
        "protected_fact_recall",
        "duplicate_semantic_count",
        "binding_violations",
        "token_count",
        "compression_savings",
        "deterministic_hash",
    ):
        assert all(metric in result for result in benchmark_report["cases"])
    verify_baseline(
        benchmark_report,
        ROOT / "benchmarks" / "baselines" / "prompt_metrics.json",
    )


def test_prepare_generation_pairs_is_reproducible_and_never_runs_comfyui(tmp_path: Path) -> None:
    output = tmp_path / "pairs.jsonl"
    first = prepare_generation_pairs(CASES, output)
    raw_first = output.read_bytes()
    assert output.read_bytes() == raw_first
    assert first
    assert len(first) == 8
    assert {record["case_id"] for record in first} == {
        "anima-simple-01",
        "anima-boundary-01",
        "h3-t2va-simple-01",
        "h3-t2va-simple-04",
        "h3-t2va-simple-08",
        "h3-t2va-simple-10",
        "h3-ref2va-boundary-01",
        "h3-ref2va-boundary-02",
    }
    for record in first:
        assert record["execution_requested"] is False
        assert record["seed"] >= 0
        assert record["workflow_sha256"] is None
        assert set(record["variants"]) == {
            "authored_uncompressed",
            "compiled",
            "expert_authored",
        }
        assert record["variants"]["expert_authored"] is None


def test_calibration_schema_requires_blind_human_decisions() -> None:
    schema = json.loads(
        (ROOT / "benchmarks" / "calibration.schema.json").read_text(encoding="utf-8")
    )
    required = set(schema["required"])
    assert {
        "artifact_sha256",
        "workflow_sha256",
        "seed",
        "path",
        "blind_pair_id",
        "human_decision",
        "criteria",
    }.issubset(required)
    assert schema["properties"]["human_decision"]["enum"] == ["A", "B", "tie"]
