import json
from pathlib import Path

from internals.evaluate import evaluate_cases


SKILL_DIR = Path(__file__).resolve().parents[2]


def test_prompt_build_corpus_meets_production_gate():
    result = evaluate_cases(SKILL_DIR / "evals/prompt-build-cases.json")
    assert result["case_count"] >= 12
    assert result["pass_rate"] >= 0.90, result["rows"]


def test_trigger_corpus_has_balanced_positive_and_negative_cases():
    rows = [
        json.loads(line)
        for line in (SKILL_DIR / "evals/trigger-cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    labels = [row["label"] for row in rows]
    assert len(rows) >= 20
    assert labels.count("should_trigger") >= 10
    assert labels.count("should_not_trigger") >= 10
    assert all(row["expected_skill"] == "prompt-forge" for row in rows)
