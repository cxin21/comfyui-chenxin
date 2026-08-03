"""Opt-in Experiments A/B against the local ComfyUI camera workflow."""

import copy
import hashlib
import io
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

LIVE_MARK = pytest.mark.skipif(
    os.environ.get("PROMPT_FORGE_LIVE") != "1",
    reason="set PROMPT_FORGE_LIVE=1 to enqueue real ComfyUI jobs",
)

from internals.prompt_compile import compile_prompt
from runtime.adapters.camera import patch_character_base
from runtime.capabilities import build_capability_report, report_is_fresh
from runtime.comfy_api import ComfyApi
from runtime.contracts import canonical_json, content_hash
from runtime.execution import (
    approve_execution_draft,
    build_execution_draft,
    build_run_record,
)
from runtime.runtime_cli import _write_run_record
from runtime.workflow_profile import resolve_slots, structure_fingerprint


BASE_URL = "http://127.0.0.1:8188"
WORKFLOW_NAME = "文生图相机视角.json"
WORKSPACE = Path(__file__).resolve().parents[4]
SKILL_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = SKILL_ROOT / "runtime/profiles/camera-anima.json"
ANIMA_INTENT = SKILL_ROOT / "internals/tests/fixtures/anima-intent.json"
DEFAULT_RUN_DIR = (
    WORKSPACE
    / ".superpowers/sdd/2026-08-02-prompt-forge-v7-slice1-runtime-base/live-runs"
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
    return build_capability_report(ComfyApi(BASE_URL), adapter, datetime.now(timezone.utc))


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


def _enqueue(graph, ui_workflow, experiment):
    assert _queue_is_empty(), "ComfyUI queue must be empty before enqueue"
    response = _request_json(
        "/prompt",
        method="POST",
        payload={
            "prompt": graph,
            "client_id": f"prompt-forge-{uuid.uuid4()}",
            "extra_data": {
                "extra_pnginfo": {"workflow": ui_workflow},
                "prompt_forge_experiment": experiment,
            },
        },
    )
    assert not response.get("node_errors"), response.get("node_errors")
    prompt_id = response.get("prompt_id")
    assert isinstance(prompt_id, str) and prompt_id
    return prompt_id


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
    plan = approve_execution_draft(draft, event)
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


@LIVE_MARK
def test_live_character_base_experiments_a_then_b():
    assert BASE_URL == "http://127.0.0.1:8188"
    assert _queue_is_empty(), "ComfyUI queue must be empty before live preflight"
    output_dir_raw = os.environ.get("PROMPT_FORGE_COMFY_OUTPUT_DIR")
    assert output_dir_raw, "set PROMPT_FORGE_COMFY_OUTPUT_DIR to the absolute ComfyUI output directory"
    output_dir = Path(output_dir_raw).resolve(strict=True)
    assert output_dir.is_absolute() and output_dir.is_dir()
    run_dir = Path(os.environ.get("PROMPT_FORGE_RUN_DIR", DEFAULT_RUN_DIR)).resolve()

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
    verified_resources = _verify_graph_resources(baseline_graph, _request_json("/object_info"))
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
    executable_b = patch_character_base(
        graph_a, build_b, {"positive_prompt": 24, "negative_prompt": 25}
    )
    assert graph_a[seed_node]["inputs"]["seed"] == executable_b[seed_node]["inputs"]["seed"]
    assert set(_diff_paths(graph_a, executable_b)) == {
        "24.inputs.populated_text",
        "24.inputs.wildcard_text",
    }
    prompt_id_b = os.environ.get("PROMPT_FORGE_EXPERIMENT_B_PROMPT_ID")
    plan_b = None
    approval_paths = None
    if prompt_id_b:
        _write_json_evidence(
            run_dir / f'{draft_b["draft_hash"]}.pending-draft.json', draft_b
        )
        history_b = _request_json(f"/history/{urllib.parse.quote(prompt_id_b, safe='')}")
        entry_b = history_b[prompt_id_b]
        assert _successful(entry_b), "reused Experiment B is not terminal success"
        assert canonical_json(entry_b["prompt"][2]) == canonical_json(executable_b)
    else:
        plan_b, pending_path, event_path, approved_plan_path = _load_external_approval(
            draft_b, run_dir
        )
        approval_paths = {
            "displayed_draft": str(pending_path),
            "approval_event": str(event_path),
            "approved_plan": str(approved_plan_path),
        }
        # Approval is checked again immediately before its one permitted enqueue.
        plan_b = approve_execution_draft(draft_b, plan_b["approval_event"])
        assert report_is_fresh(report_b, datetime.now(timezone.utc)), (
            "CapabilityReport expired after approval; rebuild and display a new draft"
        )
        assert _queue_is_empty(), "ComfyUI queue changed after approval"
        prompt_id_b = _enqueue(executable_b, ui_workflow, "B-positive-prompt-only")
        history_b, entry_b = _wait_terminal(prompt_id_b)
    hashes_b, paths_b = _verify_outputs(
        entry_b, output_dir, before_filenames.union(hashes_a)
    )
    if plan_b is None:
        record_b, record_path_b, raw_history_path_b = _historical_characterization_record(
            run_dir,
            prompt_id_b,
            graph_a,
            executable_b,
            history_b,
            hashes_b,
            paths_b,
        )
    else:
        record_b, record_path_b, raw_history_path_b = _production_record(
            run_dir,
            _task_context("B"),
            build_b,
            graph_a,
            plan_b,
            prompt_id_b,
            history_b,
            hashes_b,
        )

    summary = {
        "workflow": WORKFLOW_NAME,
        "saved_workflow_count": len(names),
        "source_prompt_id": source_prompt_id,
        "current_saved_workflow_fingerprint": structure_fingerprint(saved_ui_workflow),
        "selected_history_ui_fingerprint": structure_fingerprint(ui_workflow),
        "history_selection_basis": "workflow-id + camera-anima-v1 slots + API node classes",
        "source_graph_hash": content_hash(baseline_graph),
        "verified_resources": verified_resources,
        "seed": seed_a,
        "experiment_a": {
            "prompt_id": prompt_id_a,
            "output_paths": paths_a,
            "output_hashes": hashes_a,
            "run_record": str(record_path_a),
            "raw_history": str(raw_history_path_a),
            "record_hash": record_a["record_hash"],
        },
        "experiment_b": {
            "evidence_class": (
                "production-approved" if plan_b is not None else "historical-render-characterization"
            ),
            "approval_lineage_verified": plan_b is not None,
            "approval_paths": approval_paths,
            "prompt_id": prompt_id_b,
            "output_paths": paths_b,
            "output_hashes": hashes_b,
            "run_record": str(record_path_b),
            "raw_history": str(raw_history_path_b),
            "record_hash": record_b["record_hash"],
        },
    }
    print(canonical_json(summary))
