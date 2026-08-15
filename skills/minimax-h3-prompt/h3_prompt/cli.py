"""MiniMax-H3 prompt skill standalone CLI.

Exposes the canonical H3 authoring, audit, tokenizer, and budget workflows as
``minimax-h3-prompt ...`` console script commands. The CLI obeys the shared
P1 protocol (``h3_prompt.cli_protocol``): it reads each request from a UTF-8
JSON file or stdin, never both; writes one final JSON envelope to stdout
under ``--json``; routes diagnostics to stderr; and selects its exit code
from ``EXIT_CODES`` based on the failure category.

The dispatcher never substitutes prompts for the Skill LLM. Raw natural
language cannot impersonate a structured ``H3T2VAAuthoringRequest`` or
``H3Ref2VAAuthoringRequest``; the request shape is asserted before any
author/audit call runs.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from .audit import audit_ref2va, audit_t2va
from .cli_protocol import (
    EXIT_CODES,
    RequestInputError,
    emit_failure,
    emit_success,
    load_json_request,
    write_json,
)
from .common import (
    H3_CONTEXT_LIMIT,
    H3AuditError,
    plan_h3_context,
)
from .contracts import (
    AuthoredSegment,
    Fact,
    H3Ref2VAAuthoringRequest,
    H3ReferenceImage,
    H3T2VAAuthoringRequest,
)
from .ref2va import author_h3_ref2va_prompt
from .t2va import author_h3_t2va_prompt
from .token_counting import (
    TokenCounter,
    TokenizerIntegrityError,
    count_h3_text_context,
)


H3_EXPECTED_SNAPSHOT = "h3-qwen3-vl"
H3_DEFAULT_REFERENCE_WIDTH = 512
H3_DEFAULT_REFERENCE_HEIGHT = 512
H3_DEFAULT_SPECIAL_TOKENS = 0
H3_DEFAULT_RUNTIME_SAFETY_MARGIN = 256
H3_DEFAULT_TEXT_QUALITY_LIMIT = 2400


def main(
    argv: Sequence[str] | None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Entry point. ``argv`` mirrors :mod:`argparse`; defaults to ``sys.argv``."""

    parser = _build_parser()
    parsed = parser.parse_args(list(argv) if argv is not None else None)
    out_stream = stdout if stdout is not None else sys.stdout
    err_stream = stderr if stderr is not None else sys.stderr
    in_stream = stdin if stdin is not None else sys.stdin

    try:
        envelope, exit_code = _dispatch(parsed, in_stream)
    except RequestInputError as error:
        envelope, exit_code = _failure(
            command=getattr(parsed, "command", None),
            stage=getattr(parsed, "stage", None),
            code="invalid_request",
            message=str(error),
            details={},
            category="request",
        )
    except H3AuditError as error:
        envelope, exit_code = _failure(
            command=getattr(parsed, "command", None),
            stage=getattr(parsed, "stage", None),
            code="h3_audit_failed",
            message=str(error),
            details={"findings": [str(error)]},
            category="validation",
        )
    except TokenizerIntegrityError as error:
        envelope, exit_code = _failure(
            command=getattr(parsed, "command", None),
            stage=getattr(parsed, "stage", None),
            code="tokenizer_integrity_failed",
            message=str(error),
            details={"reason": str(error)},
            category="integrity",
        )
    except ValueError as error:
        envelope, exit_code = _failure(
            command=getattr(parsed, "command", None),
            stage=getattr(parsed, "stage", None),
            code="validation_failed",
            message=str(error),
            details={},
            category="validation",
        )
    except Exception as error:  # noqa: BLE001 - last-resort unexpected handler
        err_stream.write(f"unexpected error: {error}\n")
        envelope, exit_code = _failure(
            command=getattr(parsed, "command", None),
            stage=getattr(parsed, "stage", None),
            code="unexpected_error",
            message="internal CLI failure",
            details={"type": type(error).__name__},
            category="unexpected",
        )

    write_json(envelope, stream=out_stream)
    return exit_code


def _dispatch(args: argparse.Namespace, stdin: TextIO) -> tuple[dict[str, Any], int]:
    command = getattr(args, "command", None)
    if command == "author":
        return _cmd_author(args, stdin)
    if command == "audit":
        return _cmd_audit(args, stdin)
    if command == "tokenizer":
        return _cmd_tokenizer(args)
    if command == "count":
        return _cmd_count(args)
    if command == "context-plan":
        return _cmd_context_plan(args, stdin)
    raise RequestInputError(f"unknown command: {command!r}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minimax-h3-prompt",
        description="Standalone MiniMax-H3 prompt authoring and budget CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    author = subparsers.add_parser("author", help="Author H3 text from a structured request.")
    _add_request_source(author)
    author.add_argument("--stage", required=True, choices=["t2va", "ref2va"], dest="stage")
    author.add_argument(
        "--tokenizer-dir",
        type=Path,
        default=None,
        help="Required for --stage ref2va. Pre-verified tokenizer snapshot directory.",
    )
    author.add_argument("--json", action="store_true", dest="json")

    audit = subparsers.add_parser("audit", help="Run H3 audit gates without authoring.")
    _add_request_source(audit)
    audit.add_argument("--stage", required=True, choices=["t2va", "ref2va"], dest="stage")
    audit.add_argument("--json", action="store_true", dest="json")

    tokenizer = subparsers.add_parser("tokenizer", help="Tokenizer snapshot integrity commands.")
    tokenizer_sub = tokenizer.add_subparsers(dest="tokenizer_command", required=True)
    verify = tokenizer_sub.add_parser(
        "verify", help="Verify a tokenizer snapshot against its manifest."
    )
    verify.add_argument("--tokenizer-dir", required=True, type=Path, dest="tokenizer_dir")
    verify.add_argument("--json", action="store_true", dest="json")

    count = subparsers.add_parser(
        "count", help="Count exact H3 user-message tokens for a prompt body."
    )
    count.add_argument("--text", required=True, type=Path, help="Path to the UTF-8 prompt body.")
    count.add_argument(
        "--references", type=int, default=0, help="Number of ordered reference images."
    )
    count.add_argument("--tokenizer-dir", required=True, type=Path, dest="tokenizer_dir")
    count.add_argument("--json", action="store_true", dest="json")

    plan = subparsers.add_parser(
        "context-plan", help="Compute the exact H3 multimodal context plan."
    )
    _add_request_source(plan)
    plan.add_argument("--tokenizer-dir", required=True, type=Path, dest="tokenizer_dir")
    plan.add_argument("--json", action="store_true", dest="json")

    return parser


def _add_request_source(parser: argparse.ArgumentParser) -> None:
    source = parser.add_argument_group("request source (exactly one required)")
    source.add_argument(
        "--request", type=Path, default=None, help="Path to a UTF-8 JSON request file."
    )
    source.add_argument(
        "--stdin", action="store_true", dest="stdin", help="Read the JSON request from stdin."
    )


def _resolve_request_path(args: argparse.Namespace) -> tuple[Path | None, bool]:
    request_path = getattr(args, "request", None)
    use_stdin = bool(getattr(args, "stdin", False))
    if (request_path is None) == (not use_stdin):
        raise RequestInputError("provide exactly one of --request FILE or --stdin")
    return request_path, use_stdin


def _load_request(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    request_path, use_stdin = _resolve_request_path(args)
    if use_stdin:
        return load_json_request(stdin=stdin)
    assert request_path is not None  # guaranteed by _resolve_request_path
    return load_json_request(request_path=request_path)


def _cmd_author(args: argparse.Namespace, stdin: TextIO) -> tuple[dict[str, Any], int]:
    payload = _load_request(args, stdin)
    stage = args.stage
    if stage == "t2va":
        request = _coerce_t2va_request(payload)
        result = author_h3_t2va_prompt(request)
        budget = _build_t2va_budget(result)
    else:
        request = _coerce_ref2va_request(payload)
        result = author_h3_ref2va_prompt(request)
        tokenizer_dir = _require_tokenizer_dir(args)
        budget = _build_ref2va_budget(request, tokenizer_dir, result)

    payload_dict = {
        "text": result.text,
        "findings": list(result.findings),
        "budget": budget,
    }
    return emit_success("author", stage, payload_dict), 0


def _cmd_audit(args: argparse.Namespace, stdin: TextIO) -> tuple[dict[str, Any], int]:
    payload = _load_request(args, stdin)
    stage = args.stage
    if stage == "t2va":
        request = _coerce_t2va_request(payload)
        findings = audit_t2va(request)
    else:
        request = _coerce_ref2va_request(payload)
        findings = audit_ref2va(request)

    findings_list = list(findings)
    if findings_list:
        envelope = emit_failure(
            "audit",
            stage,
            [
                {
                    "code": "h3_audit_failed",
                    "message": "H3 audit produced blocking findings",
                    "details": {"findings": findings_list},
                }
            ],
        )
        return envelope, EXIT_CODES["validation"]
    return emit_success("audit", stage, {"findings": []}), 0


def _cmd_tokenizer(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.tokenizer_command != "verify":
        raise RequestInputError("tokenizer subcommand must be 'verify'")
    counter = TokenCounter.load(args.tokenizer_dir, H3_EXPECTED_SNAPSHOT)
    manifest = counter.manifest
    payload = {
        "verified": True,
        "snapshot_id": manifest.snapshot_id,
        "model_id": manifest.model_id,
        "model_hard_limit": manifest.model_hard_limit,
        "files": [name for name, _ in manifest.file_hashes],
    }
    return emit_success("tokenizer verify", None, payload), 0


def _cmd_count(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.references < 0:
        raise RequestInputError("--references must be a non-negative integer")
    text_path: Path = args.text
    if not text_path.is_file():
        raise RequestInputError(f"--text file is missing: {text_path}")
    body = text_path.read_text(encoding="utf-8")
    counter = TokenCounter.load(args.tokenizer_dir, H3_EXPECTED_SNAPSHOT)
    tokens = count_h3_text_context(counter, body, reference_count=args.references)
    payload = {
        "verified": True,
        "tokens": tokens,
        "reference_count": args.references,
        "snapshot_id": counter.snapshot_id,
        "model_id": counter.manifest.model_id,
    }
    return emit_success("count", None, payload), 0


def _cmd_context_plan(args: argparse.Namespace, stdin: TextIO) -> tuple[dict[str, Any], int]:
    payload = _load_request(args, stdin)
    references = _coerce_references(payload.get("references", ()))
    text_quality_limit = int(payload.get("text_quality_limit", H3_DEFAULT_TEXT_QUALITY_LIMIT))
    special_tokens = int(payload.get("special_tokens", H3_DEFAULT_SPECIAL_TOKENS))
    runtime_safety_margin = int(
        payload.get("runtime_safety_margin", H3_DEFAULT_RUNTIME_SAFETY_MARGIN)
    )
    counter = TokenCounter.load(args.tokenizer_dir, H3_EXPECTED_SNAPSHOT)
    try:
        plan = plan_h3_context(
            counter,
            tuple(references),
            text_quality_limit=text_quality_limit,
            special_tokens=special_tokens,
            runtime_safety_margin=runtime_safety_margin,
        )
    except H3AuditError as error:
        envelope = emit_failure(
            "context-plan",
            None,
            [
                {
                    "code": "context_overflow",
                    "message": str(error),
                    "details": {
                        "text_quality_limit": text_quality_limit,
                        "special_tokens": special_tokens,
                        "runtime_safety_margin": runtime_safety_margin,
                    },
                }
            ],
        )
        return envelope, EXIT_CODES["validation"]
    payload_dict = {
        "verified": True,
        "snapshot_id": counter.snapshot_id,
        "model_id": counter.manifest.model_id,
        "context_plan": {
            "visual_tokens": plan.visual_tokens,
            "chat_template_tokens": plan.chat_template_tokens,
            "special_tokens": plan.special_tokens,
            "runtime_safety_margin": plan.runtime_safety_margin,
            "available_tokens": plan.available_tokens,
            "text_quality_limit": plan.text_quality_limit,
            "effective_quality_limit": plan.effective_quality_limit,
        },
    }
    return emit_success("context-plan", None, payload_dict), 0


def _build_t2va_budget(result: Any) -> dict[str, Any]:
    # t2va preserves the no-reference path: the design explicitly avoids loading
    # a TokenCounter when there are no reference images. We expose text_tokens
    # as a deterministic best-effort approximation (whitespace-split count)
    # so consumers can still reason about prompt length without forcing a
    # tokenizer snapshot for the no-reference authoring workflow.
    body = result.text or ""
    text_tokens = len([token for token in body.split() if token])
    return {
        "verified": True,
        "visual_budget_applicable": False,
        "reference_count": 0,
        "text_tokens": text_tokens,
        "model_hard_limit": H3_CONTEXT_LIMIT,
    }


def _build_ref2va_budget(
    request: H3Ref2VAAuthoringRequest,
    tokenizer_dir: Path,
    result: Any,
) -> dict[str, Any]:
    counter = TokenCounter.load(tokenizer_dir, H3_EXPECTED_SNAPSHOT)
    text_tokens = count_h3_text_context(
        counter, result.text or "", reference_count=len(request.references)
    )
    plan = plan_h3_context(
        counter,
        tuple(request.references),
        text_quality_limit=H3_DEFAULT_TEXT_QUALITY_LIMIT,
        special_tokens=H3_DEFAULT_SPECIAL_TOKENS,
        runtime_safety_margin=H3_DEFAULT_RUNTIME_SAFETY_MARGIN,
    )
    return {
        "verified": True,
        "visual_budget_applicable": True,
        "reference_count": len(request.references),
        "text_tokens": text_tokens,
        "model_hard_limit": counter.manifest.model_hard_limit,
        "context_plan": {
            "visual_tokens": plan.visual_tokens,
            "chat_template_tokens": plan.chat_template_tokens,
            "special_tokens": plan.special_tokens,
            "runtime_safety_margin": plan.runtime_safety_margin,
            "available_tokens": plan.available_tokens,
            "text_quality_limit": plan.text_quality_limit,
            "effective_quality_limit": plan.effective_quality_limit,
        },
    }


def _coerce_facts(raw: Any) -> tuple[Fact, ...]:
    items = _expect_list(raw, "facts")
    facts: list[Fact] = []
    for item in items:
        if not isinstance(item, dict):
            raise RequestInputError("every fact must be a JSON object")
        facts.append(
            Fact(
                fact_id=str(item["fact_id"]),
                value=str(item["value"]),
                origin=str(item["origin"]),
                locked=bool(item["locked"]),
                owner=str(item["owner"]),
                dimension=str(item["dimension"]),
            )
        )
    return tuple(facts)


def _coerce_segments(raw: Any, field: str) -> tuple[AuthoredSegment, ...]:
    items = _expect_list(raw, field)
    segments: list[AuthoredSegment] = []
    for item in items:
        if not isinstance(item, dict):
            raise RequestInputError(f"every {field} entry must be a JSON object")
        segments.append(
            AuthoredSegment(
                segment_id=str(item["segment_id"]),
                field=str(item.get("field", field)),
                text=str(item["text"]),
                fact_ids=tuple(str(value) for value in item.get("fact_ids", ())),
                priority=float(item.get("priority", 1.0)),
                adherence_risk=float(item.get("adherence_risk", 0.5)),
                source_confidence=float(item.get("source_confidence", 1.0)),
            )
        )
    return tuple(segments)


def _coerce_references(raw: Any) -> tuple[H3ReferenceImage, ...]:
    items = _expect_list(raw, "references")
    refs: list[H3ReferenceImage] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise RequestInputError("every reference must be a JSON object")
        width = int(item.get("resized_width", H3_DEFAULT_REFERENCE_WIDTH))
        height = int(item.get("resized_height", H3_DEFAULT_REFERENCE_HEIGHT))
        refs.append(
            H3ReferenceImage(
                reference_id=str(item.get("reference_id", f"Picture {index + 1}")),
                owner=str(item["owner"]) if "owner" in item else "",
                resized_width=width,
                resized_height=height,
            )
        )
    return tuple(refs)


def _coerce_t2va_request(payload: dict[str, Any]) -> H3T2VAAuthoringRequest:
    duration = _expect_number(payload, "duration_seconds")
    shot_count = _expect_int(payload, "shot_count")
    return H3T2VAAuthoringRequest(
        facts=_coerce_facts(payload.get("facts", ())),
        duration_seconds=float(duration),
        shot_count=shot_count,
        integrated_multimodal_description=_coerce_segments(
            payload.get("integrated_multimodal_description", ()),
            "integrated_multimodal_description",
        ),
        overall_soundscape=_coerce_segments(
            payload.get("overall_soundscape", ()), "overall_soundscape"
        ),
        non_diegetic_music=_coerce_segments(
            payload.get("non_diegetic_music", ()), "non_diegetic_music"
        ),
    )


def _coerce_ref2va_request(payload: dict[str, Any]) -> H3Ref2VAAuthoringRequest:
    duration = _expect_number(payload, "duration_seconds")
    shot_count = _expect_int(payload, "shot_count")
    return H3Ref2VAAuthoringRequest(
        facts=_coerce_facts(payload.get("facts", ())),
        duration_seconds=float(duration),
        shot_count=shot_count,
        references=_coerce_references(payload.get("references", ())),
        subject_definitions=_coerce_segments(
            payload.get("subject_definitions", ()), "subject_definitions"
        ),
        summary=_coerce_segments(payload.get("summary", ()), "summary"),
        retention_analysis=_coerce_segments(
            payload.get("retention_analysis", ()), "retention_analysis"
        ),
        detailed_description=_coerce_segments(
            payload.get("detailed_description", ()), "detailed_description"
        ),
        overall_soundscape=_coerce_segments(
            payload.get("overall_soundscape", ()), "overall_soundscape"
        ),
        non_diegetic_music=_coerce_segments(
            payload.get("non_diegetic_music", ()), "non_diegetic_music"
        ),
    )


def _require_tokenizer_dir(args: argparse.Namespace) -> Path:
    tokenizer_dir = getattr(args, "tokenizer_dir", None)
    if tokenizer_dir is None:
        raise RequestInputError("--tokenizer-dir is required for --stage ref2va")
    if not tokenizer_dir.is_dir():
        raise RequestInputError(f"--tokenizer-dir is not a directory: {tokenizer_dir}")
    return tokenizer_dir


def _expect_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise RequestInputError(f"field '{field}' must be a list")
    return value


def _expect_number(payload: dict[str, Any], field: str) -> float:
    if field not in payload:
        raise RequestInputError(f"missing required field '{field}'")
    value = payload[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequestInputError(f"field '{field}' must be a number")
    return float(value)


def _expect_int(payload: dict[str, Any], field: str) -> int:
    value = _expect_number(payload, field)
    if not value.is_integer():
        raise RequestInputError(f"field '{field}' must be an integer")
    return int(value)


def _failure(
    *,
    command: str | None,
    stage: str | None,
    code: str,
    message: str,
    details: dict[str, Any],
    category: str,
) -> tuple[dict[str, Any], int]:
    envelope = emit_failure(
        command or "unknown",
        stage,
        [{"code": code, "message": message, "details": details}],
    )
    return envelope, EXIT_CODES[category]
