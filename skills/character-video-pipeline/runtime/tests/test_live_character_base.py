"""Opt-in Experiments A/B against the local ComfyUI camera workflow."""

import copy
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image

PROMPT_FORGE_ROOT = Path(__file__).resolve().parents[4] / "skills" / "prompt-forge"
sys.path.insert(0, str(PROMPT_FORGE_ROOT))
from internals.prompt_compile import compile_prompt
import runtime.execution as execution_module
from runtime.adapters.camera import patch_character_base
from runtime.capabilities import build_capability_report, report_is_fresh
from runtime.comfy_api import ComfyApi
from runtime.asset_plans import (
    build_art_bible,
    build_character_board_plan,
    build_scene_variant_plan,
)
from runtime.contracts import canonical_json, content_hash
from runtime.execution import (
    approve_execution_draft,
    build_approval_consumption,
    build_execution_draft,
    build_run_record,
)
from runtime.runtime_cli import _write_approval_consumption, _write_run_record
from runtime.workflow_profile import resolve_slots, structure_fingerprint


LIVE_MARK = pytest.mark.skipif(
    os.environ.get("PROMPT_FORGE_LIVE") != "1",
    reason="set PROMPT_FORGE_LIVE=1 to enqueue real ComfyUI jobs",
)


BASE_URL = "http://127.0.0.1:8188"
WORKFLOW_NAME = "文生图相机视角.json"
WORKSPACE = Path(__file__).resolve().parents[4]
SKILL_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = SKILL_ROOT / "runtime/profiles/camera-anima.json"
ANIMA_INTENT = SKILL_ROOT / "internals/tests/fixtures/anima-intent.json"
DEFAULT_RUN_DIR = (
    WORKSPACE
    / ".superpowers/sdd/current-character-video-pipeline/live-runs"
)
_PENDING_BUNDLE_KEYS = frozenset(
    {
        "schema_version",
        "bundle_type",
        "created_at",
        "consumption_root",
        "draft",
        "task_context",
        "prompt_build",
        "profile",
        "history_ui_workflow",
        "source_api_graph",
        "seed_node",
        "seed",
        "patches",
        "capability_report",
        "experiment_a",
        "bundle_hash",
    }
)
_PENDING_INPUT_KEYS = _PENDING_BUNDLE_KEYS.difference(
    {"schema_version", "bundle_type", "created_at", "consumption_root", "bundle_hash"}
)


def _request_json(path, *, method="GET", payload=None, timeout=30.0):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _queue_is_empty():
    queue = _request_json("/queue")
    return not queue.get("queue_running") and not queue.get("queue_pending")


def _saved_workflow():
    names = _request_json("/userdata?dir=workflows&recurse=true")
    assert isinstance(names, list), "saved workflow listing is not a string list"
    assert WORKFLOW_NAME in names, f"required saved workflow is unavailable: {WORKFLOW_NAME}"
    encoded = urllib.parse.quote(f"workflows/{WORKFLOW_NAME}", safe="")
    workflow = _request_json(f"/userdata/{encoded}")
    assert isinstance(workflow, dict) and isinstance(workflow.get("nodes"), list)
    return names, workflow


def _successful(entry):
    status = entry.get("status", {})
    return status.get("status_str") == "success" and status.get("completed") is True


def _history_ui_workflow(entry):
    try:
        prompt = entry["prompt"]
        workflow = prompt[3]["extra_pnginfo"]["workflow"]
    except (IndexError, KeyError, TypeError):
        return None
    return workflow if isinstance(workflow, dict) else None


def _latest_matching_history(history, saved_workflow, profile):
    workflow_id = saved_workflow.get("id")
    assert isinstance(workflow_id, str) and workflow_id, "saved workflow has no stable UI id"
    candidates = []
    for prompt_id, entry in history.items():
        if not isinstance(entry, dict) or not _successful(entry):
            continue
        ui_workflow = _history_ui_workflow(entry)
        prompt = entry.get("prompt")
        if not isinstance(prompt, list) or len(prompt) < 3 or not isinstance(prompt[2], dict):
            continue
        try:
            matches = (
                ui_workflow is not None
                and ui_workflow.get("id") == workflow_id
                and resolve_slots(ui_workflow, profile)["positive_prompt"] == 24
                and resolve_slots(ui_workflow, profile)["negative_prompt"] == 25
            )
        except (KeyError, TypeError, ValueError):
            matches = False
        graph = prompt[2]
        if not matches:
            continue
        if graph.get("24", {}).get("class_type") != "ImpactWildcardProcessor":
            continue
        if graph.get("25", {}).get("class_type") != "ImpactWildcardProcessor":
            continue
        sequence = prompt[0]
        if not isinstance(sequence, (int, float)) or isinstance(sequence, bool):
            continue
        candidates.append((sequence, prompt_id, entry, ui_workflow, graph))
    assert candidates, (
        "no successful history entry matches the selected saved workflow id, "
        "camera-anima-v1 slots, and API graph node classes for "
        f"{WORKFLOW_NAME}"
    )
    return max(candidates, key=lambda item: item[0])


def _verify_graph_resources(graph, object_info):
    class_types = {
        node.get("class_type")
        for node in graph.values()
        if isinstance(node, dict) and isinstance(node.get("class_type"), str)
    }
    missing_classes = sorted(class_types.difference(object_info))
    assert not missing_classes, f"history graph node types are unavailable: {missing_classes}"

    resource_inputs = {"ckpt_name", "unet_name", "clip_name", "vae_name", "lora_name", "model_name"}
    verified = []
    for node_id, node in graph.items():
        class_type = node.get("class_type")
        inputs = node.get("inputs", {})
        schema = object_info[class_type].get("input", {})
        declared = {}
        for section in ("required", "optional"):
            values = schema.get(section, {})
            if isinstance(values, dict):
                declared.update(values)
        for input_name, value in inputs.items():
            if input_name not in resource_inputs or not isinstance(value, str):
                continue
            descriptor = declared.get(input_name)
            choices = descriptor[0] if isinstance(descriptor, list) and descriptor else None
            assert isinstance(choices, list), (
                f"cannot verify resource schema {class_type}.{input_name} for node {node_id}"
            )
            assert value in choices, f"history graph resource is unavailable: {value}"
            verified.append(
                {"node_id": node_id, "class_type": class_type, "input": input_name, "value": value}
            )
    assert verified, "history graph exposes no verifiable model resources"
    return verified


def _prompt_inputs(graph):
    result = {}
    for node_id, label in (("24", "positive"), ("25", "negative")):
        inputs = graph[node_id].get("inputs", {})
        wildcard = inputs.get("wildcard_text")
        populated = inputs.get("populated_text")
        assert isinstance(wildcard, str) and wildcard.strip(), f"{label} prompt is empty"
        assert wildcard == populated, f"{label} prompt inputs are not synchronized"
        result[label] = wildcard
    return result


def _seed_location(graph):
    locations = []
    for node_id, node in graph.items():
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if not isinstance(inputs, dict):
            continue
        seed = inputs.get("seed")
        if isinstance(seed, int) and not isinstance(seed, bool):
            locations.append((node_id, seed))
    assert len(locations) == 1, f"expected exactly one integer seed input, found {locations}"
    return locations[0]


def _diff_paths(left, right, prefix=""):
    if isinstance(left, dict) and isinstance(right, dict) and set(left) == set(right):
        paths = []
        for key in sorted(left):
            child = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_diff_paths(left[key], right[key], child))
        return paths
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        paths = []
        for index, (a, b) in enumerate(zip(left, right)):
            paths.extend(_diff_paths(a, b, f"{prefix}[{index}]"))
        return paths
    return [] if left == right else [prefix]


def _task_context(experiment):
    return {
        "schema_version": "1.0",
        "shared_known": {
            "goal": f"Prompt Forge live Experiment {experiment}",
            "background": [WORKFLOW_NAME],
            "acceptance": ["terminal success", "new decodable PNG", "retained RunRecord"],
            "boundaries": ["local only", "one job at a time", "do not save workflow"],
        },
        "user_known_agent_unknown": {
            "references": [],
            "aesthetic_preferences": [],
            "real_world_constraints": ["8 GB device"],
        },
        "agent_known_user_unknown": {
            "capabilities": ["history replay", "artifact verification"],
            "risks": ["workflow or history provenance drift"],
            "alternatives": ["fail closed without enqueue"],
        },
        "shared_unknown": {
            "hypotheses": [f"Experiment {experiment} completes without graph drift"],
            "experiments": [experiment],
        },
    }


def _capability_report():
    adapter = {
        "name": "comfyui-rest-history-replay",
        "version": "1",
        "runtime_classification": "local",
        "tools": ["history-read", "enqueue", "job-monitor", "artifact-read"],
    }
    report = build_capability_report(ComfyApi(BASE_URL), adapter, datetime.now(timezone.utc))
    report["workflow_candidates"] = [
        {
            "profile_id": "camera-anima-v1",
            "production": True,
            "status": "needs-normalization",
            "production_ready": False,
        }
    ]
    return report


def _draft(build, profile, ui_workflow, graph, report):
    patches = [
        {"slot": "positive_prompt", "input": "wildcard_text", "value": build["prompt"]},
        {"slot": "positive_prompt", "input": "populated_text", "value": build["prompt"]},
        {"slot": "negative_prompt", "input": "wildcard_text", "value": build["negative_prompt"]},
        {"slot": "negative_prompt", "input": "populated_text", "value": build["negative_prompt"]},
    ]
    return build_execution_draft(
        "character-base",
        build,
        "camera-anima-v1",
        structure_fingerprint(ui_workflow),
        patches,
        capability_report=report,
        profile=profile,
        actual_ui_workflow=ui_workflow,
        api_graph=graph,
    )


def _enqueue(graph, ui_workflow, experiment, enqueue_request_id):
    assert _queue_is_empty(), "ComfyUI queue must be empty before enqueue"
    response = _request_json(
        "/prompt",
        method="POST",
        payload={
            "prompt": graph,
            "client_id": enqueue_request_id,
            "extra_data": {
                "extra_pnginfo": {"workflow": ui_workflow},
                "prompt_forge_experiment": experiment,
                "prompt_forge_enqueue_request_id": enqueue_request_id,
            },
        },
    )
    assert not response.get("node_errors"), response.get("node_errors")
    prompt_id = response.get("prompt_id")
    assert isinstance(prompt_id, str) and prompt_id
    return prompt_id


def _enqueue_or_recover(graph, ui_workflow, experiment, enqueue_request_id):
    try:
        return _enqueue(graph, ui_workflow, experiment, enqueue_request_id)
    except Exception as enqueue_error:
        try:
            history = _request_json("/history")
        except Exception as history_error:
            raise AssertionError(
                "enqueue outcome is uncertain; consumption is retained and history "
                "could not be queried by the stable enqueue request id"
            ) from history_error
        if not isinstance(history, dict):
            raise AssertionError(
                "enqueue outcome is uncertain; consumption is retained and history "
                "was not a mapping"
            ) from enqueue_error
        matches = []
        for prompt_id, entry in history.items():
            prompt = entry.get("prompt") if isinstance(entry, dict) else None
            extra_data = prompt[3] if isinstance(prompt, list) and len(prompt) >= 4 else None
            if (
                isinstance(prompt_id, str)
                and isinstance(extra_data, dict)
                and extra_data.get("prompt_forge_enqueue_request_id") == enqueue_request_id
            ):
                matches.append(prompt_id)
        if len(matches) == 1:
            return matches[0]
        raise AssertionError(
            "enqueue outcome is uncertain; consumption is retained and history did not "
            "contain exactly one prompt for the stable enqueue request id"
        ) from enqueue_error


def _wait_terminal(prompt_id, timeout_seconds=1800):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        history = _request_json(f"/history/{urllib.parse.quote(prompt_id, safe='')}")
        entry = history.get(prompt_id)
        if isinstance(entry, dict):
            status = entry.get("status", {})
            if status.get("completed") is True:
                assert status.get("status_str") == "success", status
                return history, entry
            if status.get("status_str") == "error":
                pytest.fail(f"ComfyUI job failed: {status}")
        time.sleep(2)
    pytest.fail(f"ComfyUI job did not reach a terminal state within {timeout_seconds}s")


def test_enqueue_timeout_recovers_prompt_id_from_stable_request_id(monkeypatch):
    request_id = "prompt-forge-stable-request"
    history = {
        "accepted-prompt": {
            "prompt": [
                7,
                "accepted-prompt",
                {},
                {"prompt_forge_enqueue_request_id": request_id},
            ]
        }
    }
    monkeypatch.setattr(
        __name__ + "._enqueue",
        lambda *_args: (_ for _ in ()).throw(TimeoutError("POST timed out")),
    )
    monkeypatch.setattr(
        __name__ + "._request_json",
        lambda path, **_kwargs: history if path == "/history" else None,
    )

    assert _enqueue_or_recover({}, {}, "B", request_id) == "accepted-prompt"


def test_enqueue_timeout_without_history_match_reports_uncertain(monkeypatch):
    monkeypatch.setattr(
        __name__ + "._enqueue",
        lambda *_args: (_ for _ in ()).throw(TimeoutError("POST timed out")),
    )
    monkeypatch.setattr(__name__ + "._request_json", lambda *_args, **_kwargs: {})

    with pytest.raises(AssertionError, match="outcome is uncertain"):
        _enqueue_or_recover({}, {}, "B", "prompt-forge-stable-request")


def _output_descriptors(entry):
    descriptors = []
    for node_outputs in entry.get("outputs", {}).values():
        if isinstance(node_outputs, dict):
            descriptors.extend(node_outputs.get("images", []))
    assert descriptors, "successful history has no image outputs"
    filenames = [item.get("filename") for item in descriptors]
    assert len(filenames) == len(set(filenames)), "history output filenames are ambiguous"
    return descriptors


def _history_filenames(history):
    filenames = set()
    for entry in history.values():
        if not isinstance(entry, dict):
            continue
        outputs = entry.get("outputs")
        if not isinstance(outputs, dict):
            continue
        for node_outputs in outputs.values():
            if not isinstance(node_outputs, dict):
                continue
            for image in node_outputs.get("images", []):
                if isinstance(image, dict) and isinstance(image.get("filename"), str):
                    filenames.add(image["filename"])
    return filenames


def _verify_outputs(entry, output_dir, before_filenames):
    hashes = {}
    absolute_paths = {}
    new_retained_outputs = []
    roots = {"output": output_dir, "temp": output_dir.parent / "temp"}
    for descriptor in _output_descriptors(entry):
        output_type = descriptor.get("type")
        assert output_type in roots, f"unexpected ComfyUI image type: {output_type}"
        filename = descriptor["filename"]
        subfolder = descriptor.get("subfolder", "")
        root = roots[output_type].resolve(strict=True)
        path = (root / subfolder / filename).resolve(strict=True)
        assert path.is_relative_to(root), "artifact path escaped its configured ComfyUI root"
        data = path.read_bytes()
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
            assert image.format == "PNG"
        hashes[filename] = hashlib.sha256(data).hexdigest()
        absolute_paths[filename] = str(path)
        if output_type == "output" and filename not in before_filenames:
            new_retained_outputs.append(filename)
    assert new_retained_outputs, "job did not create a new retained output PNG filename"
    return hashes, absolute_paths


def _write_json_evidence(path, value):
    canonical = canonical_json(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical)
            handle.write("\n")
    except FileExistsError:
        existing = json.loads(path.read_text(encoding="utf-8"))
        assert canonical_json(existing) == canonical, f"refusing to overwrite evidence: {path}"
    return path.resolve()


def _utc_timestamp(value, label):
    assert isinstance(value, str) and value, f"{label} must be a UTC timestamp"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssertionError(f"{label} must be a UTC timestamp") from exc
    assert parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), (
        f"{label} must be UTC"
    )
    return parsed


def _validate_pending_bundle(bundle):
    assert isinstance(bundle, dict) and set(bundle) == _PENDING_BUNDLE_KEYS, (
        "pending bundle schema is incomplete or contains unexpected fields"
    )
    assert bundle["schema_version"] == "1.0"
    assert bundle["bundle_type"] == "character-base-b-pending"
    root_text = bundle["consumption_root"]
    assert isinstance(root_text, str) and Path(root_text).is_absolute(), (
        "pending bundle consumption root must be absolute"
    )
    root_path = Path(root_text).resolve(strict=True)
    assert root_path.is_dir() and str(root_path) == root_text, (
        "pending bundle consumption root must be an existing canonical directory"
    )
    unsigned = dict(bundle)
    claimed_hash = unsigned.pop("bundle_hash")
    assert claimed_hash == content_hash(unsigned), "pending bundle_hash is not self-consistent"

    trusted_now = execution_module._utc_now()
    created_at = _utc_timestamp(bundle["created_at"], "pending bundle created_at")
    age = (trusted_now - created_at).total_seconds()
    assert 0 <= age <= 600, "pending bundle must be resumed within 600 seconds"
    report = bundle["capability_report"]
    assert isinstance(report, dict) and report.get("generated_at") == bundle["created_at"], (
        "pending bundle CapabilityReport timestamp does not match bundle creation"
    )
    assert report_is_fresh(report, trusted_now), "pending bundle CapabilityReport is expired"

    draft = build_execution_draft(
        "character-base",
        bundle["prompt_build"],
        "camera-anima-v1",
        structure_fingerprint(bundle["history_ui_workflow"]),
        bundle["patches"],
        capability_report=report,
        profile=bundle["profile"],
        actual_ui_workflow=bundle["history_ui_workflow"],
        api_graph=bundle["source_api_graph"],
    )
    assert draft == bundle["draft"], "pending bundle does not rebuild the exact draft"
    assert draft["draft_hash"] == bundle["draft"]["draft_hash"]

    seed_node = bundle["seed_node"]
    assert isinstance(seed_node, str) and seed_node in bundle["source_api_graph"]
    assert bundle["source_api_graph"][seed_node]["inputs"].get("seed") == bundle["seed"], (
        "pending bundle source graph seed lineage is invalid"
    )
    experiment_a = bundle["experiment_a"]
    assert isinstance(experiment_a, dict) and set(experiment_a) == {
        "prompt_id",
        "history",
        "artifact_hashes",
        "artifact_paths",
        "record_hash",
    }
    prompt_id = experiment_a["prompt_id"]
    history = experiment_a["history"]
    assert isinstance(prompt_id, str) and isinstance(history.get(prompt_id), dict)
    prompt = history[prompt_id].get("prompt")
    assert isinstance(prompt, list) and len(prompt) >= 3 and prompt[1] == prompt_id
    assert canonical_json(prompt[2]) == canonical_json(bundle["source_api_graph"]), (
        "pending bundle Experiment A graph lineage is invalid"
    )
    hashes = experiment_a["artifact_hashes"]
    paths = experiment_a["artifact_paths"]
    assert isinstance(hashes, dict) and hashes and set(hashes) == set(paths)
    assert all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes.values())
    assert isinstance(experiment_a["record_hash"], str) and re.fullmatch(
        r"[0-9a-f]{64}", experiment_a["record_hash"]
    )
    return bundle, draft


def _write_pending_bundle(run_dir, frozen_inputs):
    assert isinstance(frozen_inputs, dict) and set(frozen_inputs) == _PENDING_INPUT_KEYS
    raw_root = Path(run_dir)
    raw_root.mkdir(parents=True, exist_ok=True)
    run_root = raw_root.resolve(strict=True)
    assert str(raw_root) == str(run_root), "pending bundle consumption root must be canonical"
    report = frozen_inputs["capability_report"]
    bundle = {
        "schema_version": "1.0",
        "bundle_type": "character-base-b-pending",
        "created_at": report["generated_at"],
        "consumption_root": str(run_root),
        **copy.deepcopy(frozen_inputs),
    }
    bundle["bundle_hash"] = content_hash(bundle)
    _validate_pending_bundle(bundle)
    path = run_root / f'pending-{bundle["draft"]["draft_hash"]}.json'
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(bundle))
            handle.write("\n")
    except FileExistsError as exc:
        raise AssertionError(f"pending bundle already exists: {path}") from exc
    return bundle, path.resolve()


def _load_pending_bundle(bundle_path, run_dir):
    raw_path = Path(bundle_path)
    assert raw_path.is_absolute(), "PROMPT_FORGE_PENDING_BUNDLE must be an absolute path"
    assert raw_path.exists(), "PROMPT_FORGE_PENDING_BUNDLE does not exist"
    raw_root = Path(run_dir)
    assert raw_root.is_absolute(), "caller run-dir consumption root must be absolute"
    run_root = raw_root.resolve(strict=True)
    assert str(raw_root) == str(run_root), (
        "caller run-dir consumption root must be canonical and must not use an alias"
    )
    resolved = raw_path.resolve(strict=True)
    assert str(raw_path) == str(resolved), "pending bundle path must not use an alias"
    bundle = json.loads(resolved.read_text(encoding="utf-8"))
    assert bundle.get("consumption_root") == str(run_root), (
        "pending bundle consumption root must exactly match caller run-dir"
    )
    assert resolved.parent == run_root, "pending bundle must be directly inside consumption root"
    return _validate_pending_bundle(bundle)


def _select_b_bundle(run_dir, first_run_builder):
    pending_path = os.environ.get("PROMPT_FORGE_PENDING_BUNDLE")
    if pending_path:
        bundle, draft = _load_pending_bundle(Path(pending_path), run_dir)
        return bundle, draft, True
    bundle, _ = first_run_builder()
    return bundle, bundle["draft"], False


def _require_safe_current_report(report, now):
    assert isinstance(report, dict) and report_is_fresh(report, now), (
        "current CapabilityReport must be fresh"
    )
    assert report.get("comfyui", {}).get("reachable") is True, (
        "current ComfyUI runtime must be reachable"
    )
    assert report.get("adapter", {}).get("runtime_classification") == "local", (
        "current runtime must remain local"
    )
    assert report.get("queue") == {"running": 0, "pending": 0}, (
        "current ComfyUI queue is not empty"
    )


def _load_external_approval(draft, run_dir):
    pending_path = _write_json_evidence(
        run_dir / f'{draft["draft_hash"]}.pending-draft.json', draft
    )
    approval_file = os.environ.get("PROMPT_FORGE_APPROVAL_FILE")
    assert approval_file, (
        "set PROMPT_FORGE_APPROVAL_FILE to a fresh external approval event bound to "
        f"draft_hash={draft['draft_hash']}; pending draft: {pending_path}"
    )
    event_path = Path(approval_file).resolve(strict=True)
    event = json.loads(event_path.read_text(encoding="utf-8"))
    plan = approve_execution_draft(
        draft,
        event,
        consumption_root=run_dir,
    )
    retained_event = _write_json_evidence(
        run_dir / f'{plan["approval_id"]}.approval.json', event
    )
    retained_plan = _write_json_evidence(
        run_dir / f'{plan["plan_hash"]}.approved-plan.json', plan
    )
    return plan, pending_path, retained_event, retained_plan


def _control_record(
    run_dir,
    source_prompt_id,
    prompt_id,
    source_seed,
    seed,
    source_graph,
    executable_graph,
    history,
    hashes,
    paths,
):
    record = {
        "schema_version": "1.0",
        "record_type": "seed_only_replay_control",
        "production_execution_plan": False,
        "prior_prompt_id": source_prompt_id,
        "prompt_id": prompt_id,
        "terminal_status": "succeeded",
        "source_seed": source_seed,
        "seed": seed,
        "source_graph_hash": content_hash(source_graph),
        "executable_graph_hash": content_hash(executable_graph),
        "raw_history_hash": content_hash(history),
        "artifact_paths": paths,
        "artifact_hashes": hashes,
    }
    record["record_hash"] = content_hash(record)
    path = _write_run_record(run_dir, record)
    raw_history_path = _write_json_evidence(run_dir / f"{prompt_id}-raw-history.json", history)
    return record, path, raw_history_path


def _production_record(
    run_dir, task_context, build, source_graph, plan, prompt_id, history, hashes
):
    record = build_run_record(
        task_context,
        build,
        source_graph,
        plan,
        prompt_id,
        "succeeded",
        {},
        hashes,
        history=history,
    )
    path = _write_run_record(run_dir, record)
    raw_history_path = _write_json_evidence(run_dir / f"{prompt_id}-raw-history.json", history)
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == record
    return record, path, raw_history_path


def _historical_characterization_record(
    run_dir, prompt_id, source_graph, executable_graph, history, hashes, paths
):
    record = {
        "schema_version": "1.0",
        "record_type": "historical_render_graph_characterization",
        "production_execution_plan": False,
        "approval_lineage_verified": False,
        "prompt_id": prompt_id,
        "terminal_status": "succeeded",
        "source_graph_hash": content_hash(source_graph),
        "executable_graph_hash": content_hash(executable_graph),
        "raw_history_hash": content_hash(history),
        "artifact_paths": paths,
        "artifact_hashes": hashes,
    }
    record["record_hash"] = content_hash(record)
    path = _write_run_record(run_dir, record)
    raw_history_path = _write_json_evidence(run_dir / f"{prompt_id}-raw-history.json", history)
    return record, path, raw_history_path


def _resume_live_b(run_dir, output_dir):
    def _forbid_first_run():
        raise AssertionError("B recovery must not execute the Experiment A first-run path")

    bundle, draft, resumed = _select_b_bundle(run_dir, _forbid_first_run)
    assert resumed, "PROMPT_FORGE_PENDING_BUNDLE is required for B recovery"

    # This report is a current safety gate only. It must never replace the
    # frozen CapabilityReport that deterministically rebuilt `draft` above.
    current_report = _capability_report()
    _require_safe_current_report(current_report, datetime.now(timezone.utc))
    verified_resources = _verify_graph_resources(
        bundle["source_api_graph"], _request_json("/object_info")
    )

    consumption_root = Path(bundle["consumption_root"])
    plan, displayed_path, event_path, approved_plan_path = _load_external_approval(
        draft, consumption_root
    )
    plan = approve_execution_draft(
        draft,
        plan["approval_event"],
        consumption_root=consumption_root,
    )
    executable = patch_character_base(
        bundle["source_api_graph"],
        bundle["prompt_build"],
        {"positive_prompt": 24, "negative_prompt": 25},
    )
    assert content_hash(executable) == draft["executable_api_graph_hash"]

    enqueue_request_id = os.environ.get("PROMPT_FORGE_ENQUEUE_REQUEST_ID")
    if not enqueue_request_id:
        enqueue_request_id = f"prompt-forge-{uuid.uuid4()}"
    consumption = build_approval_consumption(plan, enqueue_request_id)
    consumption_path = _write_approval_consumption(consumption_root, consumption)

    # Consumption is intentionally not rolled back if POST raises or times out:
    # the server may already have accepted the request. Recovery must inspect
    # history using enqueue_request_id, never blindly enqueue again.
    prompt_id = _enqueue_or_recover(
        executable,
        bundle["history_ui_workflow"],
        "B-positive-prompt-only",
        enqueue_request_id,
    )
    history, entry = _wait_terminal(prompt_id)
    experiment_a = bundle["experiment_a"]
    hashes, paths = _verify_outputs(
        entry,
        output_dir,
        set(experiment_a["artifact_hashes"]),
    )
    record, record_path, raw_history_path = _production_record(
        consumption_root,
        bundle["task_context"],
        bundle["prompt_build"],
        bundle["source_api_graph"],
        plan,
        prompt_id,
        history,
        hashes,
    )
    print(
        canonical_json(
            {
                "workflow": WORKFLOW_NAME,
                "selected_history_ui_fingerprint": structure_fingerprint(
                    bundle["history_ui_workflow"]
                ),
                "verified_resources": verified_resources,
                "seed": bundle["seed"],
                "experiment_a": copy.deepcopy(experiment_a),
                "experiment_b": {
                    "evidence_class": "production-approved-consumed-once",
                    "approval_lineage_verified": True,
                    "displayed_draft": str(displayed_path),
                    "approval_event": str(event_path),
                    "approved_plan": str(approved_plan_path),
                    "approval_consumption": str(consumption_path),
                    "enqueue_request_id": enqueue_request_id,
                    "prompt_id": prompt_id,
                    "output_paths": paths,
                    "output_hashes": hashes,
                    "run_record": str(record_path),
                    "raw_history": str(raw_history_path),
                    "record_hash": record["record_hash"],
                },
            }
        )
    )


def test_latest_history_selection_uses_workflow_id_and_profile_not_current_saved_fingerprint():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    history_ui = json.loads(
        (Path(__file__).parent / "fixtures/camera-ui-minimal.json").read_text(encoding="utf-8")
    )
    history_ui["id"] = "stable-workflow-id"
    saved_ui = copy.deepcopy(history_ui)
    saved_ui["nodes"].append({"id": 999, "type": "UnrelatedNode", "title": "CURRENT"})
    graph = json.loads(
        (Path(__file__).parent / "fixtures/camera-api-minimal.json").read_text(encoding="utf-8")
    )
    entry = {
        "prompt": [7, "history-prompt", graph, {"extra_pnginfo": {"workflow": history_ui}}],
        "status": {"status_str": "success", "completed": True},
    }

    selected = _latest_matching_history(
        {"history-prompt": entry}, saved_ui, profile
    )

    assert selected[1] == "history-prompt"
    assert structure_fingerprint(saved_ui) != structure_fingerprint(selected[3])


def test_missing_external_approval_preserves_pending_draft(tmp_path, monkeypatch):
    monkeypatch.delenv("PROMPT_FORGE_APPROVAL_FILE", raising=False)
    draft = {"draft_hash": "a" * 64, "plan_state": "draft"}

    with pytest.raises(AssertionError, match="PROMPT_FORGE_APPROVAL_FILE"):
        _load_external_approval(draft, tmp_path)

    pending = tmp_path / f'{draft["draft_hash"]}.pending-draft.json'
    assert json.loads(pending.read_text(encoding="utf-8")) == draft


def _pending_bundle_fixture(now):
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    ui_workflow = json.loads(
        (Path(__file__).parent / "fixtures/camera-ui-minimal.json").read_text(encoding="utf-8")
    )
    profile["workflow_fingerprint"] = structure_fingerprint(ui_workflow)
    graph = json.loads(
        (Path(__file__).parent / "fixtures/camera-api-minimal.json").read_text(encoding="utf-8")
    )
    build = {
        "schema_version": "1.0",
        "target": "image",
        "generation_mode": "text-to-image",
        "model_id": "anima",
        "dialect": "tags",
        "prompt": "score_9, 1girl, solo, from_front, full_body",
        "negative_prompt": "worst quality, low quality, watermark",
        "validated_tags": ["1girl", "solo", "from_front", "full_body"],
        "rejected_tags": [],
        "recipe_control_tokens": ["score_9"],
        "locked_facts": ["1girl"],
        "ready_to_execute": True,
        "execution": {"requested": True, "performed": False},
    }
    report = {
        "schema_version": "1.0",
        "comfyui": {"url": BASE_URL, "reachable": True},
        "adapter": {"runtime_classification": "local", "tools": ["enqueue"]},
        "queue": {"running": 0, "pending": 0},
        "workflow_candidates": [
            {
                "profile_id": "camera-anima-v1",
                "production": True,
                "status": "needs-normalization",
                "production_ready": False,
            }
        ],
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "valid_until": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
    }
    draft = _draft(build, profile, ui_workflow, graph, report)
    prompt_id = "historical-a"
    history = {
        prompt_id: {
            "prompt": [7, prompt_id, copy.deepcopy(graph)],
            "status": {"status_str": "success", "completed": True},
            "outputs": {},
        }
    }
    return {
        "draft": draft,
        "task_context": _task_context("B"),
        "prompt_build": build,
        "profile": profile,
        "history_ui_workflow": ui_workflow,
        "source_api_graph": graph,
        "seed_node": "24",
        "seed": 101,
        "patches": draft["patches"],
        "capability_report": report,
        "experiment_a": {
            "prompt_id": prompt_id,
            "history": history,
            "artifact_hashes": {"a.png": "a" * 64},
            "artifact_paths": {"a.png": "E:/Comfy/output/a.png"},
            "record_hash": "b" * 64,
        },
    }


def test_pending_bundle_resume_rebuilds_exact_frozen_draft_without_first_run(tmp_path, monkeypatch):
    now = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(execution_module, "_utc_now", lambda: now)
    frozen = _pending_bundle_fixture(now)
    bundle, bundle_path = _write_pending_bundle(tmp_path, frozen)
    changed_report = copy.deepcopy(frozen["capability_report"])
    changed_report["generated_at"] = (now + timedelta(seconds=1)).isoformat().replace(
        "+00:00", "Z"
    )
    first_run_calls = []
    monkeypatch.setenv("PROMPT_FORGE_PENDING_BUNDLE", str(bundle_path))

    first = _select_b_bundle(
        tmp_path,
        lambda: first_run_calls.append(changed_report),
    )
    second = _select_b_bundle(
        tmp_path,
        lambda: first_run_calls.append(changed_report),
    )

    assert first_run_calls == []
    assert first[2] is True and second[2] is True
    assert first[0] == second[0] == bundle
    assert first[1] == second[1] == frozen["draft"]
    assert content_hash(changed_report) != frozen["draft"]["capability_report_hash"]


def test_pending_bundle_resume_rejects_missing_expired_or_modified_bundle(tmp_path, monkeypatch):
    now = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(execution_module, "_utc_now", lambda: now)
    frozen = _pending_bundle_fixture(now)
    _, bundle_path = _write_pending_bundle(tmp_path, frozen)

    with pytest.raises(AssertionError, match="absolute|exists"):
        _load_pending_bundle(tmp_path / "missing.json", tmp_path)

    monkeypatch.setattr(execution_module, "_utc_now", lambda: now + timedelta(seconds=601))
    with pytest.raises(AssertionError, match="600"):
        _load_pending_bundle(bundle_path, tmp_path)

    monkeypatch.setattr(execution_module, "_utc_now", lambda: now)
    modified = json.loads(bundle_path.read_text(encoding="utf-8"))
    modified["prompt_build"]["prompt"] = "tampered"
    bundle_path.write_text(json.dumps(modified), encoding="utf-8")
    with pytest.raises(AssertionError, match="bundle_hash"):
        _load_pending_bundle(bundle_path, tmp_path)


def test_parent_run_dir_cannot_load_bundle_bound_to_child(tmp_path, monkeypatch):
    now = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(execution_module, "_utc_now", lambda: now)
    parent = tmp_path / "runs"
    child = parent / "child"
    _, bundle_path = _write_pending_bundle(child, _pending_bundle_fixture(now))

    with pytest.raises(AssertionError, match="consumption root"):
        _load_pending_bundle(bundle_path, parent)


def test_child_run_dir_cannot_load_bundle_bound_to_parent(tmp_path, monkeypatch):
    now = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(execution_module, "_utc_now", lambda: now)
    parent = tmp_path / "runs"
    child = parent / "child"
    _, bundle_path = _write_pending_bundle(parent, _pending_bundle_fixture(now))
    child.mkdir()

    with pytest.raises(AssertionError, match="consumption root"):
        _load_pending_bundle(bundle_path, child)


def test_symlink_run_dir_alias_cannot_load_pending_bundle(tmp_path, monkeypatch):
    now = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(execution_module, "_utc_now", lambda: now)
    root = tmp_path / "runs"
    _, bundle_path = _write_pending_bundle(root, _pending_bundle_fixture(now))
    alias = tmp_path / "runs-alias"
    try:
        alias.symlink_to(root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")

    with pytest.raises(AssertionError, match="canonical|alias|consumption root"):
        _load_pending_bundle(bundle_path, alias)


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda report: report["queue"].update(pending=1), "queue"),
        (lambda report: report["comfyui"].update(reachable=False), "reachable"),
        (lambda report: report["adapter"].update(runtime_classification="unknown"), "local"),
    ],
)
def test_resume_current_capability_gate_fails_closed(mutate, match, monkeypatch):
    now = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(execution_module, "_utc_now", lambda: now)
    report = _pending_bundle_fixture(now)["capability_report"]
    mutate(report)
    with pytest.raises(AssertionError, match=match):
        _require_safe_current_report(report, now)


def _experiment_story(lighting="cool window light"):
    values = [
        "ink wash",
        "digital watercolor",
        "quiet negative space",
        "indigo",
        "cedar",
        "linen",
        "bronze",
        lighting,
        "sealed threshold",
        "modern electronics absent",
        "reuse fixed anchors",
        "ink wash digital watercolor",
    ]
    return {
        "schema_version": "1.0",
        "visual_system": {
            "primary_style": values[0],
            "medium": values[1],
            "visual_grammar": values[2],
            "palette": values[3:5],
            "materials": values[5:7],
            "lighting": lighting,
            "motifs": [values[8]],
            "world_taboos": [values[9]],
            "continuity_strategy": values[10],
            "style_prompt": values[11],
        },
        "characters": [{"asset_id": "character-lee"}],
        "scenes": [{"asset_id": "environment-workshop"}],
        "story_logic": ["the key opens the archive"],
        "uncertainty": ["archive contents are uncertain"],
        "source_hash": "d" * 64,
        "provenance": {
            "explicit_evidence": values + [
                "the key opens the archive",
                "archive contents are uncertain",
            ],
            "reasonable_inference": ["the archive uses the locked palette"],
            "prohibited_expansion": ["neon signage"],
        },
    }


def _experiment_character_card():
    fingerprint = [
        {"feature": "silhouette", "value": "slender silhouette"},
        {"feature": "proportions", "value": "balanced proportions"},
        {"feature": "palette", "value": "indigo and cedar"},
        {"feature": "materials", "value": "linen and bronze"},
        {"feature": "surface", "value": "matte linen"},
        {"feature": "lighting", "value": "cool window light"},
    ]
    facts = [
        "young archivist",
        "short black bob",
        "indigo coat",
        "brown almond eyes",
        *(part["value"] for part in fingerprint),
    ]
    return {
        "schema_version": "1.0",
        "asset_type": "character",
        "asset_id": "character-lee",
        "source_story_hash": "a" * 64,
        "visual_fingerprint": fingerprint,
        "identity_lock": facts[:3],
        "face_lock": [{"feature": "eyes", "value": facts[3]}],
        "provenance": {
            "explicit_evidence": facts,
            "reasonable_inference": ["the coat uses the art-bible palette"],
            "prohibited_expansion": ["metallic armor"],
        },
    }


def _experiment_environment_card():
    fingerprint = [
        {"feature": "silhouette", "value": "arched workshop silhouette"},
        {"feature": "proportions", "value": "narrow east-wall counter"},
        {"feature": "palette", "value": "indigo and cedar"},
        {"feature": "materials", "value": "weathered stone and cedar"},
        {"feature": "wear_trace", "value": "faded seal damage"},
        {"feature": "lighting", "value": "cool window light"},
    ]
    anchors = [
        {"feature": "entrance", "value": "weathered stone arch"},
        {"feature": "emblem", "value": "red lacquer seal"},
        {"feature": "counter", "value": "narrow cedar counter"},
    ]
    facts = [*(item["value"] for item in fingerprint), *(item["value"] for item in anchors)]
    return {
        "schema_version": "1.0",
        "asset_type": "environment",
        "asset_id": "environment-workshop",
        "source_story_hash": "b" * 64,
        "visual_fingerprint": fingerprint,
        "environment_anchors": anchors,
        "spatial_layout": "arch faces the east-wall counter",
        "provenance": {
            "explicit_evidence": facts + ["arch faces the east-wall counter"],
            "reasonable_inference": ["the archive uses the workshop palette"],
            "prohibited_expansion": ["modern neon signage"],
        },
    }


def _changed_keys(left, right):
    return {
        key
        for key in set(left) | set(right)
        if canonical_json(left.get(key)) != canonical_json(right.get(key))
    }


def test_experiment_a_one_art_bible_lighting_change_preserves_identity_and_taboos():
    base_bible = build_art_bible(_experiment_story())
    changed_bible = build_art_bible(_experiment_story("warm window light"))
    card = _experiment_character_card()
    base_board = build_character_board_plan(base_bible, card)
    changed_board = build_character_board_plan(changed_bible, card)

    assert base_board["identity_lock"] == changed_board["identity_lock"]
    assert base_board["face_lock"] == changed_board["face_lock"]
    assert base_board["world_taboos"] == changed_board["world_taboos"]
    assert base_board["asset_card_hash"] == changed_board["asset_card_hash"]
    assert base_board["style_prompt"] == changed_board["style_prompt"]
    assert base_board["lighting"] != changed_board["lighting"]
    assert base_board["art_bible_hash"] != changed_board["art_bible_hash"]
    assert content_hash(base_board) != content_hash(changed_board)
    assert _changed_keys(base_board, changed_board) <= {
        "art_bible_hash",
        "lighting",
        "explicit_evidence",
    }


def test_experiment_b_environment_master_reuse_locks_layout_and_materials():
    environment = _experiment_environment_card()
    first = build_scene_variant_plan(
        environment,
        {"shot_deltas": {"framing": "wide", "camera_height": "eye-level"}},
    )
    second = build_scene_variant_plan(
        environment,
        {"shot_deltas": {"framing": "medium", "camera_height": "low"}},
    )

    for field in (
        "environment_anchors",
        "spatial_layout",
        "materials",
        "lighting",
        "visual_fingerprint",
        "asset_card_hash",
    ):
        assert first[field] == second[field], field
    assert first["shot_deltas"] != second["shot_deltas"]
    assert _changed_keys(first, second) == {"shot_deltas"}
    assert content_hash(first) != content_hash(second)


@LIVE_MARK
def test_live_character_base_experiments_a_then_b():
    assert BASE_URL == "http://127.0.0.1:8188"
    assert _queue_is_empty(), "ComfyUI queue must be empty before live preflight"
    output_dir_raw = os.environ.get("PROMPT_FORGE_COMFY_OUTPUT_DIR")
    assert output_dir_raw, "set PROMPT_FORGE_COMFY_OUTPUT_DIR to the absolute ComfyUI output directory"
    output_dir = Path(output_dir_raw).resolve(strict=True)
    assert output_dir.is_absolute() and output_dir.is_dir()
    run_dir = Path(os.environ.get("PROMPT_FORGE_RUN_DIR", DEFAULT_RUN_DIR)).resolve()
    if os.environ.get("PROMPT_FORGE_PENDING_BUNDLE"):
        _resume_live_b(run_dir, output_dir)
        return

    names, saved_ui_workflow = _saved_workflow()
    history_before = _request_json("/history")
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    requested_source_id = os.environ.get("PROMPT_FORGE_SOURCE_PROMPT_ID")
    source_history = (
        {requested_source_id: history_before[requested_source_id]}
        if requested_source_id
        else history_before
    )
    source_sequence, source_prompt_id, source_entry, ui_workflow, baseline_graph = (
        _latest_matching_history(source_history, saved_ui_workflow, profile)
    )
    assert source_entry["status"] == {"status_str": "success", "completed": True} or _successful(source_entry)
    _verify_graph_resources(baseline_graph, _request_json("/object_info"))
    prompts = _prompt_inputs(baseline_graph)
    seed_node, baseline_seed = _seed_location(baseline_graph)
    history_at_source = {
        prompt_id: entry
        for prompt_id, entry in history_before.items()
        if isinstance(entry, dict)
        and isinstance(entry.get("prompt"), list)
        and entry["prompt"]
        and isinstance(entry["prompt"][0], (int, float))
        and entry["prompt"][0] <= source_sequence
    }
    before_filenames = _history_filenames(history_at_source)

    # Historical Experiment A: characterize the retained seed-only replay. This
    # repaired test never creates a new A job.
    graph_a = copy.deepcopy(baseline_graph)
    seed_a = 0 if baseline_seed >= 2**63 - 1 else baseline_seed + 1
    graph_a[seed_node]["inputs"]["seed"] = seed_a
    assert _diff_paths(baseline_graph, graph_a) == [f"{seed_node}.inputs.seed"]
    prompt_id_a = os.environ.get("PROMPT_FORGE_EXPERIMENT_A_PROMPT_ID")
    assert prompt_id_a, (
        "set PROMPT_FORGE_EXPERIMENT_A_PROMPT_ID to retained historical A; "
        "the repaired test will not enqueue a new control run"
    )
    history_a = _request_json(f"/history/{urllib.parse.quote(prompt_id_a, safe='')}")
    entry_a = history_a[prompt_id_a]
    assert _successful(entry_a), "reused Experiment A is not terminal success"
    assert canonical_json(entry_a["prompt"][2]) == canonical_json(graph_a)
    hashes_a, paths_a = _verify_outputs(entry_a, output_dir, before_filenames)
    record_a, record_path_a, raw_history_path_a = _control_record(
        run_dir,
        source_prompt_id,
        prompt_id_a,
        baseline_seed,
        seed_a,
        baseline_graph,
        graph_a,
        history_a,
        hashes_a,
        paths_a,
    )

    # Experiment B: hold Experiment A graph and seed fixed; change only positive PromptBuild.
    intent_b = json.loads(ANIMA_INTENT.read_text(encoding="utf-8"))
    intent_b["mode"] = "execute"
    intent_b["locked_facts"] = []
    for items in intent_b["dimensions"].values():
        for item in items:
            if item.get("origin") == "explicit" and item.get("tag_candidates"):
                item["value"] = item["tag_candidates"][0]
                item["source_text"] = item["value"]
    build_b = compile_prompt(intent_b, {"negative_prompt": prompts["negative"]})
    assert build_b["ready_to_execute"] is True, build_b["errors"]
    assert build_b["prompt"] != prompts["positive"]
    assert build_b["negative_prompt"] == prompts["negative"]
    report_b = _capability_report()
    draft_b = _draft(build_b, profile, ui_workflow, graph_a, report_b)
    bundle, bundle_path = _write_pending_bundle(
        run_dir,
        {
            "draft": draft_b,
            "task_context": _task_context("B"),
            "prompt_build": build_b,
            "profile": profile,
            "history_ui_workflow": ui_workflow,
            "source_api_graph": graph_a,
            "seed_node": seed_node,
            "seed": seed_a,
            "patches": draft_b["patches"],
            "capability_report": report_b,
            "experiment_a": {
            "prompt_id": prompt_id_a,
            "history": history_a,
            "artifact_paths": paths_a,
            "artifact_hashes": hashes_a,
            "record_hash": record_a["record_hash"],
            },
        },
    )
    assert bundle["draft"]["draft_hash"] == draft_b["draft_hash"]
    pytest.fail(
        "B draft is pending external approval; display the frozen bundle and rerun with "
        f"PROMPT_FORGE_PENDING_BUNDLE={bundle_path} and an approval event bound to "
        f"draft_hash={draft_b['draft_hash']}"
    )
