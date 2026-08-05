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

from runtime.adapters.camera import (
    activate_g1,
    normalize_camera_api_graph,
    patch_character_base,
    verify_img2img_path,
)
from runtime.adapters.flux_multiview import FluxAdapterError
from runtime.adapters.yusu_timeline import patch_yusu_timeline
from runtime.artifacts import accept_stage3_reference, verify_video_artifact
from runtime.asset_plans import (
    AssetPlanError,
    build_art_bible,
    build_character_board_plan,
    build_environment_board_plan,
    build_prop_board_plan,
)
from runtime.capabilities import build_capability_report
from runtime.comfy_api import CapabilityError, ComfyApi
from runtime.contracts import ContractError, canonical_json, content_hash
from runtime.execution import (
    ExecutionError,
    _canonical_consumption_root,
    approve_execution_draft,
    build_approval_consumption,
    build_execution_draft,
    build_multiview_draft,
    build_multiview_run_record,
    build_run_record,
)
from runtime.pipeline_state import advance_state, stage_is_reusable
from runtime.reference_select import select_reference
from runtime.stages import StageError, build_shot_plan, build_video_plan
from runtime.stages import build_character_base_plan
from runtime.story_assets import (
    art_bible_hash,
    asset_card_hash,
    story_breakdown_hash,
    validate_story_breakdown,
)
from runtime.stage_execution import (
    StageExecutionError,
    approve_stage_execution_draft,
    build_stage_consumption,
    build_stage_execution_draft,
    build_stage_run_record,
    build_stage_submission,
    write_stage_consumption,
)
from runtime.local_orchestrator import (
    submit_character_base_via_local_rest,
    submit_stage_via_local_rest,
    validate_trusted_stage_profile,
    validate_trusted_video_evidence,
    wait_for_stage_history,
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

    plan_multiview = commands.add_parser(
        "plan-multiview",
        help="fail closed: Stage 2 production planning requires local MCP callables",
    )
    _add_json_source(plan_multiview)

    ingest_story = commands.add_parser("ingest-story", help="validate story evidence and emit its canonical hash")
    _add_json_source(ingest_story)

    compile_assets = commands.add_parser("compile-assets", help="compile an art bible and typed asset-board plans")
    _add_json_source(compile_assets)

    plan_character_base = commands.add_parser("plan-character-base", help="build a clean identity-master plan")
    _add_json_source(plan_character_base)

    approve = commands.add_parser("approve-plan", help="approve one displayed ExecutionDraft")
    _add_json_source(approve)
    approve.add_argument("--run-dir", type=Path, required=True)

    consume = commands.add_parser("consume-approval", help="consume one approved enqueue scope")
    _add_json_source(consume)
    consume.add_argument("--run-dir", type=Path, required=True)

    patch = commands.add_parser("patch-camera", help="patch the camera API graph")
    _add_json_source(patch)

    patch_flux = commands.add_parser("patch-flux", help="patch both Flux base-image inputs")
    _add_json_source(patch_flux)

    select = commands.add_parser("select-reference", help="select one accepted shot reference")
    _add_json_source(select)

    accept_reference = commands.add_parser(
        "accept-reference", help="record explicit human acceptance for one verified angle artifact"
    )
    _add_json_source(accept_reference)

    activate = commands.add_parser("activate-g1", help="activate the complete camera G1 group")
    _add_json_source(activate)

    normalize_camera = commands.add_parser(
        "normalize-camera", help="repair the pinned camera UI-to-API conversion bridge"
    )
    _add_json_source(normalize_camera)

    verify_path = commands.add_parser("verify-img2img-path", help="prove the G1 latent path")
    _add_json_source(verify_path)

    plan_shot = commands.add_parser("plan-shot", help="build a Stage 3 shot-image draft")
    _add_json_source(plan_shot)

    patch_yusu = commands.add_parser("patch-yusu", help="patch one Yusu Director timeline segment")
    _add_json_source(patch_yusu)

    plan_video = commands.add_parser("plan-video", help="build a Stage 4 video draft")
    _add_json_source(plan_video)

    stage_draft = commands.add_parser(
        "plan-stage-execution", help="bind a Stage 3/4 plan to fresh local graph evidence"
    )
    _add_json_source(stage_draft)

    stage_approve = commands.add_parser(
        "approve-stage", help="approve one displayed Stage 3/4 execution draft"
    )
    _add_json_source(stage_approve)
    stage_approve.add_argument("--run-dir", type=Path, required=True)

    stage_consume = commands.add_parser(
        "consume-stage", help="consume one approved Stage 3/4 enqueue scope"
    )
    _add_json_source(stage_consume)
    stage_consume.add_argument("--run-dir", type=Path, required=True)

    stage_submit = commands.add_parser(
        "build-stage-submission", help="build the exact Stage 3/4 graph/request without enqueueing"
    )
    _add_json_source(stage_submit)

    stage_execute = commands.add_parser(
        "submit-stage",
        help="after approval/consumption, submit one Stage 3/4 request to local ComfyUI",
    )
    _add_json_source(stage_execute)
    stage_execute.add_argument("--base-url", default="http://127.0.0.1:8188")
    stage_execute.add_argument("--timeout", type=float, default=30.0)

    base_execute = commands.add_parser(
        "submit-character-base",
        help="after approval/consumption, submit the Stage 1 graph to local ComfyUI",
    )
    _add_json_source(base_execute)
    base_execute.add_argument("--base-url", default="http://127.0.0.1:8188")
    base_execute.add_argument("--timeout", type=float, default=30.0)

    wait_stage = commands.add_parser(
        "wait-stage",
        help="poll local ComfyUI history until one prompt reaches a terminal state",
    )
    _add_json_source(wait_stage)
    wait_stage.add_argument("--base-url", default="http://127.0.0.1:8188")
    wait_stage.add_argument("--timeout", type=float, default=3600.0)
    wait_stage.add_argument("--poll-interval", type=float, default=2.0)

    stage_record = commands.add_parser(
        "record-stage", help="build and retain a verified Stage 3/4 RunRecord"
    )
    _add_json_source(stage_record)
    stage_record.add_argument("--run-dir", type=Path, required=True)

    verify_video = commands.add_parser("verify-video", help="verify video technical metadata")
    _add_json_source(verify_video)

    state = commands.add_parser("pipeline-state", help="advance or check pipeline state")
    _add_json_source(state)

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


def _planning_result(value: dict, *, stage: str) -> dict:
    """Annotate pure stage output; this flag never grants execution approval."""
    result = dict(value)
    result.setdefault("stage", stage)
    result["planning_only"] = True
    return result


def _story_payload(payload: dict) -> dict:
    if "story" in payload:
        if set(payload) != {"story"}:
            raise CliUsageError("ingest-story accepts only story; hashes are derived canonically")
        story = payload["story"]
    else:
        story = payload
    try:
        return validate_story_breakdown(story)
    except ContractError as exc:
        raise CliUsageError(f"invalid story breakdown: {exc}") from exc


def _strict_hash(value: object, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise CliUsageError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _reject_caller_hash_override(payload: dict, canonical: dict[str, str]) -> None:
    for field, expected in canonical.items():
        if field in payload and payload[field] != expected:
            raise CliUsageError(f"caller-supplied {field} does not match canonical evidence")


def _dispatch(command: str, payload: dict, args) -> dict | tuple[dict, int]:
    if command == "discover":
        return _discover(payload)
    if command == "fingerprint":
        return {"structure_fingerprint": structure_fingerprint(payload)}
    if command == "ingest-story":
        story = _story_payload(payload)
        return _planning_result(
            {
                "schema_version": "1.0",
                "story": story,
                "story_breakdown_hash": story_breakdown_hash(story),
            },
            stage="ingest-story",
        )
    if command == "compile-assets":
        if not isinstance(payload.get("story"), dict):
            raise CliUsageError("compile-assets requires story")
        story = _story_payload({"story": payload["story"]})
        style_override = payload.get("style_override", {})
        if not isinstance(style_override, dict):
            raise CliUsageError("style_override must be an object")
        try:
            bible = build_art_bible(story, style_override=style_override)
        except AssetPlanError as exc:
            raise CliUsageError(str(exc)) from exc
        _reject_caller_hash_override(payload, {"story_breakdown_hash": story_breakdown_hash(story)})
        assets = payload.get("assets", {})
        if not isinstance(assets, dict):
            raise CliUsageError("assets must be an object keyed by asset type")
        builders = {
            "environment": build_environment_board_plan,
            "character": build_character_board_plan,
            "prop": build_prop_board_plan,
        }
        boards = {}
        asset_hashes = {}
        board_plan_hashes = {}
        for asset_type, asset in assets.items():
            if asset_type not in builders:
                raise CliUsageError(f"unsupported asset type: {asset_type}")
            try:
                boards[asset_type] = builders[asset_type](bible, asset)
                asset_hashes[asset.get("asset_id", asset_type)] = asset_card_hash(asset)
                board_plan_hashes[asset.get("asset_id", asset_type)] = content_hash(boards[asset_type])
            except (AssetPlanError, ContractError, AttributeError) as exc:
                raise CliUsageError(f"invalid {asset_type} asset: {exc}") from exc
        return _planning_result(
            {
                "schema_version": "1.0",
                "story_breakdown_hash": story_breakdown_hash(story),
                "art_bible": bible,
                "art_bible_hash": art_bible_hash(bible),
                "boards": boards,
                "asset_hashes": asset_hashes,
                "board_plan_hashes": board_plan_hashes,
            },
            stage="compile-assets",
        )
    if command == "plan-character-base":
        character = payload.get("character", payload.get("character_asset"))
        profile = payload.get("profile")
        if not isinstance(character, dict) or not isinstance(profile, dict):
            raise CliUsageError("plan-character-base requires character and profile")
        ui_workflow = payload.get("ui_workflow")
        workflow_fingerprint = (
            structure_fingerprint(ui_workflow)
            if isinstance(ui_workflow, dict)
            else profile.get("workflow_fingerprint")
        )
        profile_digest = content_hash(profile)
        _reject_caller_hash_override(
            payload,
            {"workflow_fingerprint": workflow_fingerprint, "profile_hash": profile_digest},
        )
        if not isinstance(workflow_fingerprint, str):
            raise CliUsageError("plan-character-base requires a trusted workflow fingerprint")
        try:
            plan = build_character_base_plan(
                character,
                workflow_fingerprint=workflow_fingerprint,
                profile_hash=profile_digest,
                profile=profile,
                distance=payload.get("distance", "full_body"),
            )
        except StageError as exc:
            return {"accepted": False, "error": str(exc), "planning_only": True}, 1
        return _planning_result(plan, stage="character-base")
    if command == "patch-camera":
        return patch_character_base(
            payload["api_graph"], payload["prompt_build"], payload["slots"]
        )
    if command == "patch-flux":
        raise ExecutionError(
            "patch-flux is unavailable at the JSON CLI boundary: a trusted local "
            "MCP enqueue callable is required; no graph was submitted"
        )
    if command == "select-reference":
        if set(payload) != {"desired_view", "artifacts"}:
            raise CliUsageError("select-reference accepts desired_view and artifacts")
        return select_reference(payload["desired_view"], payload["artifacts"])
    if command == "accept-reference":
        if set(payload) != {"artifact", "actor", "accepted_at"}:
            raise CliUsageError("accept-reference accepts artifact, actor and accepted_at")
        return accept_stage3_reference(payload["artifact"], payload["actor"], payload["accepted_at"])
    if command == "activate-g1":
        if set(payload) != {"workflow", "image_name", "profile"}:
            raise CliUsageError("activate-g1 accepts workflow, image_name and profile")
        return activate_g1(payload["workflow"], payload["image_name"], payload["profile"])
    if command == "normalize-camera":
        if set(payload) != {"api_graph", "ui_workflow", "profile"}:
            raise CliUsageError("normalize-camera accepts api_graph, ui_workflow and profile")
        return normalize_camera_api_graph(
            payload["api_graph"], payload["ui_workflow"], payload["profile"]
        )
    if command == "verify-img2img-path":
        if set(payload) != {"api_graph", "profile"}:
            raise CliUsageError("verify-img2img-path accepts api_graph and profile")
        return verify_img2img_path(payload["api_graph"], payload["profile"])
    if command == "plan-shot":
        try:
            return _planning_result(build_shot_plan(**payload), stage="shot-image")
        except StageError as exc:
            return {"accepted": False, "error": str(exc), "planning_only": True}, 1
    if command == "patch-yusu":
        required = {"graph", "image_ref", "prompt", "frames", "fps", "profile"}
        if set(payload) != required:
            raise CliUsageError("patch-yusu accepts graph, image_ref, prompt, frames, fps and profile")
        return patch_yusu_timeline(
            payload["graph"],
            payload["image_ref"],
            payload["prompt"],
            payload["frames"],
            payload["fps"],
            payload["profile"],
        )
    if command == "plan-video":
        try:
            request = dict(payload)
            shot = request.pop("shot")
            prompt_build = request.pop("prompt_build")
            workflow_hash = request.pop("workflow_hash")
            profile_hash = request.pop("profile_hash")
            execution_approved = request.pop("execution_approved")
            production = isinstance(shot, dict) and any(
                key in shot for key in ("task_context_hash", "source_story_hash", "art_bible_hash", "lineage_id")
            ) or any(
                key in request for key in ("motion_delta", "split_decision", "timeline_segments", "intent", "duration_profile_id")
            )
            if production:
                duration_id = request.get("duration_profile_id")
                if duration_id not in {"ltx-yusu-short-v1", "ltx-yusu-long-v1"}:
                    raise StageError("trusted duration profile is required for production video")
                _strict_hash(workflow_hash, "workflow_hash")
                _strict_hash(profile_hash, "profile_hash")
                trusted_profile = request.pop("workflow_profile", request.pop("profile", None))
                trusted_graph = request.pop("workflow_graph", request.pop("source_api_graph", None))
                if not isinstance(trusted_profile, dict) or not isinstance(trusted_graph, dict):
                    raise StageError(
                        "production video requires trusted workflow_graph and workflow_profile evidence"
                    )
                if content_hash(trusted_profile) != profile_hash:
                    raise StageError("profile_hash is not derived from the trusted workflow profile")
                if content_hash(trusted_graph) != workflow_hash:
                    raise StageError("workflow_hash is not derived from the trusted workflow graph")
                try:
                    validate_trusted_video_evidence(
                        trusted_profile, trusted_graph, duration_id
                    )
                except StageExecutionError as exc:
                    raise StageError(str(exc)) from exc
                if execution_approved is not True:
                    raise StageError("production planning requires explicit approval boundary")
            return _planning_result(
                build_video_plan(shot, prompt_build, workflow_hash, profile_hash, execution_approved, **request),
                stage="video",
            )
        except StageError as exc:
            return {"accepted": False, "error": str(exc), "planning_only": True}, 1
    if command == "plan-stage-execution":
        try:
            optional = {
                key: payload[key]
                for key in ("ui_workflow", "image_name", "reference_artifact", "image_ref")
                if key in payload
            }
            return build_stage_execution_draft(
                payload["stage_plan"],
                payload["source_api_graph"],
                payload["profile"],
                payload["capability_report"],
                **optional,
            )
        except StageExecutionError as exc:
            return {"accepted": False, "error": str(exc)}, 1
    if command == "approve-stage":
        draft = _require_object(payload.get("draft"), "draft")
        event = _require_object(payload.get("approval_event"), "approval_event")
        if set(payload) != {"draft", "approval_event", "profile"}:
            raise StageExecutionError("approve-stage requires draft, approval_event and trusted profile")
        validate_trusted_stage_profile(draft, _require_object(payload.get("profile"), "profile"))
        approved = approve_stage_execution_draft(draft, event, args.run_dir)
        event_path = _write_execution_evidence(
            args.run_dir, event, digest=approved["approval_id"], suffix="stage-approval"
        )
        plan_path = _write_execution_evidence(
            args.run_dir, approved,
            digest=approved["execution_plan_hash"], suffix="stage-approved-plan",
        )
        return {"plan": approved, "approval_event_path": str(event_path), "plan_path": str(plan_path)}
    if command == "consume-stage":
        if set(payload) != {"approved_plan", "enqueue_request_id"}:
            raise StageExecutionError("consume-stage accepts only approved_plan and enqueue_request_id")
        consumption = build_stage_consumption(payload["approved_plan"], payload["enqueue_request_id"])
        path = write_stage_consumption(args.run_dir, consumption)
        return {"consumption": consumption, "consumption_path": str(path)}
    if command == "build-stage-submission":
        required = {
            "approved_plan", "source_api_graph", "consumption", "consumption_path",
            "profile", "capability_report",
        }
        if not required.issubset(payload):
            raise CliUsageError("build-stage-submission is missing required evidence")
        validate_trusted_stage_profile(payload["approved_plan"], payload["profile"])
        optional = {
            key: payload[key]
            for key in ("ui_workflow", "reference_image_name", "reference_artifact", "image_ref")
            if key in payload
        }
        return build_stage_submission(
            payload["approved_plan"], payload["source_api_graph"], payload["consumption"],
            Path(payload["consumption_path"]), profile=payload["profile"],
            capability_report=payload["capability_report"], **optional,
        )
    if command == "submit-stage":
        required = {
            "approved_plan", "source_api_graph", "consumption", "consumption_path",
            "profile", "capability_report",
        }
        if not required.issubset(payload):
            raise CliUsageError("submit-stage is missing required approval/submission evidence")
        optional = {
            key: payload[key]
            for key in ("ui_workflow", "reference_image_name", "reference_artifact", "image_ref")
            if key in payload
        }
        return submit_stage_via_local_rest(
            payload["approved_plan"],
            payload["source_api_graph"],
            payload["consumption"],
            payload["consumption_path"],
            profile=payload["profile"],
            capability_report=payload["capability_report"],
            base_url=args.base_url,
            timeout=args.timeout,
            **optional,
        )
    if command == "submit-character-base":
        required = {
            "approved_plan", "prompt_build", "source_api_graph", "consumption", "consumption_path", "profile",
        }
        if not required.issubset(payload):
            raise CliUsageError("submit-character-base is missing required approval/submission evidence")
        return submit_character_base_via_local_rest(
            payload["approved_plan"],
            payload["prompt_build"],
            payload["source_api_graph"],
            payload["consumption"],
            payload["consumption_path"],
            base_url=args.base_url,
            timeout=args.timeout,
            ui_workflow=payload.get("ui_workflow"),
            profile=payload.get("profile"),
        )
    if command == "wait-stage":
        if set(payload) != {"prompt_id"}:
            raise CliUsageError("wait-stage accepts only prompt_id")
        api = ComfyApi(base_url=args.base_url, timeout=args.timeout)
        return wait_for_stage_history(
            api,
            payload["prompt_id"],
            timeout=args.timeout,
            poll_interval=args.poll_interval,
        )
    if command == "verify-video":
        metadata = payload.get("metadata")
        expected_fps = payload.get("expected_fps")
        expected_frames = payload.get("expected_frames")
        artifact_path = payload.get("artifact_path")
        if artifact_path is not None:
            artifact_path = Path(artifact_path)
        return verify_video_artifact(
            metadata,
            expected_fps,
            expected_frames,
            expected_width=payload.get("expected_width"),
            expected_height=payload.get("expected_height"),
            lineage_id=payload.get("lineage_id"),
            source_shot_hash=payload.get("source_shot_hash"),
            artifact_path=artifact_path,
        )
    if command == "pipeline-state":
        if set(payload) == {"state", "transition"}:
            return advance_state(payload["state"], payload["transition"])
        if set(payload) == {"saved", "input_hash", "prompt_build_hash", "workflow_hash", "profile_version"}:
            return {"reusable": stage_is_reusable(payload["saved"], payload["input_hash"], payload["prompt_build_hash"], payload["workflow_hash"], payload["profile_version"])}
        raise CliUsageError("pipeline-state accepts a transition or a reuse check")
    if command == "plan":
        try:
            return build_execution_draft(**payload)
        except ExecutionError as exc:
            return {"accepted": False, "error": str(exc)}, 1
    if command == "plan-multiview":
        try:
            return build_multiview_draft(**payload)
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
        plan = payload.get("execution_plan")
        if isinstance(plan, dict) and plan.get("stage") == "character-multiview":
            record = build_multiview_run_record(**payload)
        else:
            record = build_run_record(**payload)
        path = _write_run_record(args.run_dir, record)
        return {"record": record, "record_path": str(path)}
    if command == "record-stage":
        if not isinstance(payload.get("history"), dict):
            raise StageExecutionError("record-stage requires raw history evidence")
        record = build_stage_run_record(
            payload["approved_plan"], payload["submission"], payload["enqueue_receipt"],
            payload["artifact"], history=payload["history"], artifact_root=payload.get("artifact_root"),
        )
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
        StageExecutionError,
        FluxAdapterError,
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
