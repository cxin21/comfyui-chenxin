from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anima_prompt_v1.authoring.relation_submission import submit_relation_payload
from anima_prompt_v1.catalog import Catalog


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and persist the current LLM's post-authoring relation submission."
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--model", default="current-llm")
    parser.add_argument("--source", default="llm")
    args = parser.parse_args()

    try:
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
        result = submit_relation_payload(
            payload,
            catalog=Catalog(args.database),
            overlay=args.overlay,
            model=args.model,
            source=args.source,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps({
        "record_ids": list(result.record_ids),
        "proposals": [proposal.__dict__ for proposal in result.proposals],
        "issues": list(result.issues),
    }, ensure_ascii=False, default=list))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
