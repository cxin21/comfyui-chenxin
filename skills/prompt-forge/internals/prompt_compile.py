"""Compile explicit prompt drafts into validated PromptPackage envelopes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
try:
    from .dialect_lookup import lookup_dialect
    from .prompt_package import _reject, validate_draft
except ImportError:  # direct script execution
    from dialect_lookup import lookup_dialect
    from prompt_package import _reject, validate_draft

def compile_prompt(evidence: dict, draft: dict | None = None, dialect_id: str | None = None) -> dict:
    """Validate a caller-authored draft; prompt prose is never synthesized here."""
    if not isinstance(evidence, dict): raise ValueError("evidence must be an object")
    if not isinstance(draft, dict): raise ValueError("caller-authored draft is required")
    if not isinstance(dialect_id, str) or not dialect_id.strip(): raise ValueError("dialect_id is required")
    return validate_draft(draft, evidence, lookup_dialect(dialect_id))

def compile_payload(payload: dict) -> dict:
    if not isinstance(payload, dict): raise ValueError("payload must be an object")
    _reject(payload, "payload")
    allowed = {"evidence", "draft", "dialect_id"}
    unexpected = sorted(set(payload) - allowed)
    if unexpected: raise ValueError(f"compile payload has unexpected fields: {', '.join(unexpected)}")
    missing=[key for key in ("evidence","draft","dialect_id") if key not in payload]
    if missing: raise ValueError(f"compile payload missing required fields: {', '.join(missing)}")
    return compile_prompt(payload["evidence"],payload["draft"],payload["dialect_id"])

def _parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input",type=Path,help="JSON compile-envelope path")
    source.add_argument("--stdin",action="store_true",help="read JSON compile envelope from stdin")
    return parser

def main(argv: list[str] | None = None) -> int:
    args=_parser().parse_args(argv)
    try:
        raw=args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
        package=compile_payload(json.loads(raw))
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        print(json.dumps({"error":str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2
    print(json.dumps(package,ensure_ascii=False,indent=2))
    return 0 if package["quality"]["ready_for_review"] else 1

if __name__=="__main__": raise SystemExit(main())