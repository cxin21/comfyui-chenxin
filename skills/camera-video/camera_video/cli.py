"""camera-video standalone CLI dispatcher."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from comfyui_http import ComfyUIClient, ComfyUIHTTPError

from .cli_protocol import (
    EXIT_CODES,
    RequestInputError,
    emit_failure,
    emit_success,
    load_json_request,
    write_json,
)
from .runtime.assets import load_fixed_workflow, scene_spec
from .runtime.runner import VIDEO_STAGES, RunResult, run as run_pipeline


def _descriptor(stage: str) -> dict[str, Any]:
    spec = scene_spec(stage)
    return {
        "workflow_name": spec.get("workflow_name", stage),
        "workflow_fingerprint": spec.get("workflow_fingerprint", ""),
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
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
    except ComfyUIHTTPError as error:
        envelope, exit_code = _failure(
            command=getattr(parsed, "command", None),
            stage=getattr(parsed, "stage", None),
            code="comfyui_runtime_error",
            message=str(error),
            details={"type": type(error).__name__},
            category="runtime",
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
    except Exception as error:  # noqa: BLE001
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="camera-video",
        description="camera-video skill standalone CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    describe = subparsers.add_parser("describe", help="Describe stage-specific field map.")
    describe.add_argument("--stage", required=True, choices=VIDEO_STAGES)
    describe.add_argument("--json", action="store_true", dest="json")

    validate = subparsers.add_parser("validate", help="Validate envelope + config without network.")
    validate.add_argument("--stage", required=True, choices=VIDEO_STAGES)
    validate.add_argument("--envelope", required=True, type=Path)
    validate.add_argument("--config", required=True, type=Path)
    validate.add_argument("--comfyui-url", default="http://127.0.0.1:8188")
    validate.add_argument("--json", action="store_true", dest="json")

    runner = subparsers.add_parser("run", help="Execute the fixed asset against ComfyUI.")
    runner.add_argument("--stage", required=True, choices=VIDEO_STAGES)
    runner.add_argument("--envelope", required=True, type=Path)
    runner.add_argument("--config", required=True, type=Path)
    runner.add_argument("--output-dir", required=True, type=Path, dest="output_dir")
    runner.add_argument("--comfyui-url", default="http://127.0.0.1:8188")
    runner.add_argument("--timeout", type=float, default=1800.0)
    runner.add_argument("--poll-interval", type=float, default=2.0, dest="poll_interval")
    runner.add_argument("--json", action="store_true", dest="json")

    assets = subparsers.add_parser("assets", help="Operate on the bundled fixed workflow asset.")
    assets_sub = assets.add_subparsers(dest="assets_command", required=True)
    verify = assets_sub.add_parser("verify", help="Verify the bundled asset digest + fingerprint.")
    verify.add_argument("--stage", required=True, choices=VIDEO_STAGES)
    verify.add_argument("--json", action="store_true", dest="json")

    return parser


def _dispatch(args: argparse.Namespace, stdin: TextIO) -> tuple[dict[str, Any], int]:
    command = getattr(args, "command", None)
    if command == "describe":
        return _cmd_describe(args)
    if command == "validate":
        return _cmd_validate(args)
    if command == "run":
        return _cmd_run(args)
    if command == "assets":
        return _cmd_assets(args)
    raise RequestInputError(f"unknown command: {command!r}")


def _cmd_describe(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    descriptor = _descriptor(args.stage)
    payload = {
        "stage": args.stage,
        "asset_workflow_name": descriptor["workflow_name"],
        "asset_fingerprint": descriptor["workflow_fingerprint"],
    }
    return emit_success("describe", args.stage, payload), 0


def _cmd_validate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    envelope = load_json_request(request_path=args.envelope)
    config = load_json_request(request_path=args.config)
    if not isinstance(envelope, dict) or "prompt" not in envelope:
        raise ValueError("envelope must include 'prompt'")
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    descriptor = _descriptor(args.stage)
    payload = {
        "stage": args.stage,
        "duration": config.get("duration"),
        "asset_fingerprint": descriptor["workflow_fingerprint"],
        "comfyui_url": args.comfyui_url,
    }
    return emit_success("validate", args.stage, payload), 0


def _cmd_assets(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.assets_command != "verify":
        raise RequestInputError("assets subcommand must be 'verify'")
    descriptor = _descriptor(args.stage)
    workflow = load_fixed_workflow(args.stage)
    node_count = len(workflow.get("nodes", [])) if isinstance(workflow, dict) else 0
    return emit_success(
        "assets verify",
        args.stage,
        {
            "verified": True,
            "asset": args.stage,
            "workflow_name": descriptor["workflow_name"],
            "fingerprint": descriptor["workflow_fingerprint"],
            "node_count": node_count,
        },
    ), 0


def _cmd_run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    envelope = load_json_request(request_path=args.envelope)
    config = load_json_request(request_path=args.config)
    if not isinstance(envelope, dict) or not isinstance(config, dict):
        raise ValueError("envelope and config must both be JSON objects")
    prompt_text = str(envelope.get("prompt", {}).get("text", ""))
    duration = float(config.get("duration", 4.0))
    reference_paths = tuple(Path(p) for p in config.get("reference_images", []) if p)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    client = ComfyUIClient(args.comfyui_url)
    result: RunResult = run_pipeline(
        client,
        stage=args.stage,
        prompt_text=prompt_text,
        duration=duration,
        reference_paths=reference_paths,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )
    for artifact in result.artifacts:
        target = args.output_dir / artifact.filename
        target.write_bytes(artifact.bytes)
    summary = {
        "prompt_id": result.prompt_id,
        "api_graph_sha256": result.api_graph_sha256,
        "uploads": [{"name": u.name, "type": u.file_type} for u in result.upload_summary],
        "artifacts": [{"filename": a.filename, "sha256": a.sha256} for a in result.artifacts],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return emit_success("run", args.stage, summary), 0


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
