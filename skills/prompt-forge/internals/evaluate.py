#!/usr/bin/env python3
"""Run the deterministic PromptBuild evaluation corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .intent_normalize import DIMENSIONS
    from .prompt_compile import compile_prompt
except ImportError:
    from intent_normalize import DIMENSIONS
    from prompt_compile import compile_prompt


_THIS = Path(__file__).resolve()
SKILL_DIR = _THIS.parent.parent
DEFAULT_CASES = SKILL_DIR / "evals" / "prompt-build-cases.json"


def _expand_case(case: dict) -> tuple[dict, dict]:
    dimensions = {dimension: [] for dimension in DIMENSIONS}
    for dimension, items in case.get("dimensions", {}).items():
        if dimension not in dimensions:
            raise ValueError(f"{case['case_id']}: unknown dimension {dimension}")
        for raw in items:
            item = {"value": raw, "origin": "explicit", "locked": True} if isinstance(raw, str) else dict(raw)
            dimensions[dimension].append(item)
    intent = {
        "schema_version": "6.1",
        "original_query": case["query"],
        "target": case["target"],
        "mode": "compile",
        "generation_mode": case["generation_mode"],
        "model_id": case["model_id"],
        "dialect": case["dialect"],
        "negative_constraints": case.get("negative_constraints", []),
        "output_constraints": case.get("output_constraints", {}),
        "references": case.get("references", []),
        "locked_facts": case.get("locked_facts", []),
        "dimensions": dimensions,
    }
    return intent, case.get("draft", {})


def evaluate_case(case: dict) -> dict:
    intent, draft = _expand_case(case)
    build = compile_prompt(intent, draft)
    expected = case["expect"]
    checks = {
        "ready": build["ready_to_execute"] is expected["ready"],
        "dialect": build["dialect"] == expected["dialect"],
        "contains": all(value.lower() in build["prompt"].lower() for value in expected.get("contains", [])),
        "absent": all(value.lower() not in build["prompt"].lower() for value in expected.get("absent", [])),
        "negative_empty": (
            "negative_empty" not in expected
            or (not build["negative_prompt"]) is expected["negative_empty"]
        ),
        "error_contains": all(
            any(value.lower() in error.lower() for error in build["errors"])
            for value in expected.get("error_contains", [])
        ),
    }
    return {
        "case_id": case["case_id"],
        "passed": all(checks.values()),
        "checks": checks,
        "errors": build["errors"],
        "warnings": build["warnings"],
    }


def evaluate_cases(path: Path = DEFAULT_CASES) -> dict:
    cases = json.loads(path.read_text(encoding="utf-8"))
    rows = [evaluate_case(case) for case in cases]
    passed = sum(row["passed"] for row in rows)
    return {
        "case_count": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prompt_forge_evaluate")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args(argv)
    try:
        result = evaluate_cases(args.cases)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"[evaluate] {exc}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
