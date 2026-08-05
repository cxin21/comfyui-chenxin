#!/usr/bin/env python3
"""Evaluate explicit PromptPackage envelopes."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
try:
    from .prompt_compile import compile_payload
except ImportError:
    from prompt_compile import compile_payload

_THIS = Path(__file__).resolve()
SKILL_DIR = _THIS.parent.parent
DEFAULT_CASES = SKILL_DIR / "evals" / "prompt-package-cases.json"
_REQUIRED_CASE_FIELDS = ("dialect_id", "evidence", "draft")


def _prompt_text(package: dict) -> str:
    values = []
    for key in ("positive", "negative", "positive_zh", "positive_en", "global_prompt"):
        value = package.get(key)
        if isinstance(value, str):
            values.append(value)
    for segment in package.get("timeline_segments", []):
        if isinstance(segment, dict):
            values.extend(value for key in ("zh", "en") if isinstance((value := segment.get(key)), str))
    return "\n".join(values)


def evaluate_case(case: dict) -> dict:
    if not isinstance(case, dict):
        raise ValueError("evaluation case must be an object")
    missing = [key for key in _REQUIRED_CASE_FIELDS if key not in case]
    if missing:
        raise ValueError(f"evaluation case requires a PromptPackage envelope (missing: {', '.join(missing)})")
    package = compile_payload({key: case[key] for key in _REQUIRED_CASE_FIELDS})
    expected = case.get("expect", {})
    if not isinstance(expected, dict):
        raise ValueError("case expect must be an object")
    checks = {}
    if "ready_for_review" in expected:
        checks["ready_for_review"] = package["quality"]["ready_for_review"] is expected["ready_for_review"]
    if "dialect" in expected:
        checks["dialect"] = package["dialect"] == expected["dialect"]
    prompt_text = _prompt_text(package).casefold()
    if "contains" in expected:
        checks["contains"] = all(str(value).casefold() in prompt_text for value in expected["contains"])
    if "absent" in expected:
        checks["absent"] = all(str(value).casefold() not in prompt_text for value in expected["absent"])
    if "error_contains" in expected:
        checks["error_contains"] = all(any(str(value).casefold() in error.casefold() for error in package["errors"]) for value in expected["error_contains"])
    return {"case_id": case.get("case_id", "unnamed"), "passed": bool(checks) and all(checks.values()), "checks": checks, "package": package, "errors": package["errors"], "warnings": package["warnings"]}


def evaluate_cases(path: Path = DEFAULT_CASES) -> dict:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("evaluation corpus must be a list")
    rows = [evaluate_case(case) for case in cases]
    passed = sum(row["passed"] for row in rows)
    return {"case_count": len(rows), "passed": passed, "failed": len(rows) - passed, "pass_rate": round(passed / len(rows), 3) if rows else 0.0, "rows": rows}


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
