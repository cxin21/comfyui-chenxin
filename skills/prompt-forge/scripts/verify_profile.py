"""Verify one production profile using only objective checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {"profile_id", "status", "grammar", "operations", "workflow_bindings", "sources"}


def verify(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = [f"missing field: {key}" for key in sorted(REQUIRED - data.keys())]
    if data.get("status") != "production_verified":
        errors.append("status must be production_verified")
    if not data.get("operations"):
        errors.append("operations must be non-empty")
    if not data.get("workflow_bindings"):
        errors.append("workflow_bindings must be non-empty")
    if not data.get("sources"):
        errors.append("sources must be non-empty")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    errors = verify(args.profile)
    print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
