"""JSON command-line boundary for the Prompt Forge v7 runtime."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.adapters.camera import patch_character_base
from runtime.capabilities import build_capability_report
from runtime.comfy_api import CapabilityError, ComfyApi
from runtime.contracts import ContractError, canonical_json
from runtime.execution import (
    ExecutionError,
    _canonical_consumption_root,
    approve_execution_draft,
    build_approval_consumption,
    build_execution_draft,
    build_run_record,
)
from runtime.workflow_profile import ProfileError, structure_fingerprint


_PREFIX = "[prompt-forge-runtime]"


class CliUsageError(ValueError):
    """Raised instead of argparse's multi-line process exit."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise CliUsageError(message)


def _add_json_source(parser: argparse.ArgumentParser, *, workflow: bool = False) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--workflow" if workflow else "--input",
        "--input" if workflow else "--payload",
        dest="source_path",
        type=Path,
        help="UTF-8 JSON file",
    )
    source.add_argument("--from-stdin", action="store_true", help="read JSON from stdin")


def _parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="prompt-forge-runtime")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)

    discover = commands.add_parser("discover", help="build a live CapabilityReport")
    _add_json_source(discover)

    fingerprint = commands.add_parser("fingerprint", help="fingerprint a UI workflow")
    _add_json_source(fingerprint, workflow=True)

    plan = commands.add_parser("plan", help="build a Stage 1 unapproved ExecutionDraft")
    _add_json_source(plan)

    approve = commands.add_parser("approve-plan", help="approve one displayed ExecutionDraft")
    _add_json_source(approve)
    approve.add_argument("--run-dir", type=Path, required=True)

    consume = commands.add_parser("consume-approval", help="consume one approved enqueue scope")
    _add_json_source(consume)
    consume.add_argument("--run-dir", type=Path, required=True)

    patch = commands.add_parser("patch-camera", help="patch the camera API graph")
    _add_json_source(patch)

    record = commands.add_parser("record", help="build and retain a RunRecord")
    _add_json_source(record)
    record.add_argument("--run-dir", type=Path, required=True)
    return parser


def _read_payload(args) -> object:
    text = sys.stdin.read() if args.from_stdin else args.source_path.read_text(encoding="utf-8")
    return json.loads(text)


def _require_object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _discover(payload: dict) -> dict:
    adapter = _require_object(payload.get("adapter"), "adapter")
    base_url = payload.get("base_url", "http://127.0.0.1:8188")
    timeout = payload.get("timeout", 30.0)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout must be a positive number")
    api = ComfyApi(base_url=base_url, timeout=float(timeout))
    return build_capability_report(api, adapter, datetime.now(timezone.utc))


def _write_run_record(run_dir: Path, record: dict) -> Path:
    record_hash = record.get("record_hash")
    if not isinstance(record_hash, str) or len(record_hash) != 64:
        raise ExecutionError("RunRecord requires a lowercase SHA-256 record_hash")
    run_dir.mkdir(parents=True, exist_ok=True)
    if not run_dir.is_dir():
        raise OSError(f"run directory is not a directory: {run_dir}")
    path = run_dir / f"{record_hash}.json"
    canonical = canonical_json(record)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical)
            handle.write("\n")
    except FileExistsError:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            identical = canonical_json(existing) == canonical
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            identical = False
        if not identical:
            raise ExecutionError(f"refusing to overwrite different RunRecord: {path}")
    return path.resolve()


def _write_execution_evidence(
    run_dir: Path,
    value: dict,
    *,
    digest: str,
    suffix: str,
) -> Path:
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ExecutionError("execution evidence requires a lowercase SHA-256 digest")
    run_dir.mkdir(parents=True, exist_ok=True)
    if not run_dir.is_dir():
        raise OSError(f"run directory is not a directory: {run_dir}")
    path = run_dir / f"{digest}.{suffix}.json"
    canonical = canonical_json(value)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical)
            handle.write("\n")
    except FileExistsError:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            identical = canonical_json(existing) == canonical
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            identical = False
        if not identical:
            raise ExecutionError(f"refusing to overwrite different execution evidence: {path}")
    return path.resolve()


def _write_approval_consumption(run_dir: Path, consumption: dict) -> Path:
    approval_id = consumption.get("approval_id")
    if not isinstance(approval_id, str) or re.fullmatch(r"[0-9a-f]{64}", approval_id) is None:
        raise ExecutionError("approval consumption requires a lowercase SHA-256 approval_id")
    canonical_run_dir = _canonical_consumption_root(run_dir, "CLI run-dir")
    if consumption.get("consumption_root") != canonical_run_dir:
        raise ExecutionError(
            "approval consumption root does not match the CLI run-dir consumption root"
        )
    path = Path(canonical_run_dir) / f"{approval_id}.consumed.json"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(consumption))
            handle.write("\n")
    except FileExistsError as exc:
        raise ExecutionError(f"approval already consumed: {path}") from exc
    return path.resolve()


def _dispatch(command: str, payload: dict, args) -> dict | tuple[dict, int]:
    if command == "discover":
        return _discover(payload)
    if command == "fingerprint":
        return {"structure_fingerprint": structure_fingerprint(payload)}
    if command == "patch-camera":
        return patch_character_base(
            payload["api_graph"], payload["prompt_build"], payload["slots"]
        )
    if command == "plan":
        try:
            return build_execution_draft(**payload)
        except ExecutionError as exc:
            return {"accepted": False, "error": str(exc)}, 1
    if command == "approve-plan":
        draft = _require_object(payload.get("draft"), "draft")
        event = _require_object(payload.get("approval_event"), "approval_event")
        if set(payload) != {"draft", "approval_event"}:
            raise ExecutionError("approve-plan accepts only draft and approval_event")
        approved = approve_execution_draft(
            draft,
            event,
            consumption_root=args.run_dir,
        )
        event_path = _write_execution_evidence(
            args.run_dir,
            event,
            digest=approved["approval_id"],
            suffix="approval",
        )
        plan_path = _write_execution_evidence(
            args.run_dir,
            approved,
            digest=approved["plan_hash"],
            suffix="approved-plan",
        )
        return {
            "plan": approved,
            "approval_event_path": str(event_path),
            "plan_path": str(plan_path),
        }
    if command == "consume-approval":
        if set(payload) != {"approved_plan", "enqueue_request_id"}:
            raise ExecutionError(
                "consume-approval accepts only approved_plan and enqueue_request_id"
            )
        approved_plan = _require_object(payload.get("approved_plan"), "approved_plan")
        consumption = build_approval_consumption(
            approved_plan,
            payload.get("enqueue_request_id"),
        )
        path = _write_approval_consumption(args.run_dir, consumption)
        return {"consumption": consumption, "consumption_path": str(path)}
    if command == "record":
        record = build_run_record(**payload)
        path = _write_run_record(args.run_dir, record)
        return {"record": record, "record_path": str(path)}
    raise CliUsageError(f"unsupported command: {command}")


def _diagnostic(exc: BaseException) -> str:
    return " ".join(str(exc).splitlines()) or exc.__class__.__name__


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        payload = _require_object(_read_payload(args), args.command)
        dispatched = _dispatch(args.command, payload, args)
        if isinstance(dispatched, tuple):
            result, exit_code = dispatched
        else:
            result, exit_code = dispatched, 0
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return exit_code
    except (
        CapabilityError,
        CliUsageError,
        ContractError,
        ExecutionError,
        ProfileError,
        KeyError,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"{_PREFIX} {_diagnostic(exc)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
