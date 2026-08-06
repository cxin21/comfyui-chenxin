import copy
import json
import subprocess
import sys
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.adapters.camera import patch_character_base
from runtime.contracts import content_hash
from runtime.execution import approve_execution_draft, build_execution_draft
from runtime.workflow_profile import structure_fingerprint
import runtime.runtime_cli as runtime_cli


WORKSPACE = Path(__file__).resolve().parents[4]
SCRIPT = WORKSPACE / "skills/character-video-pipeline/runtime/runtime_cli.py"
FIXTURES = Path(__file__).parent / "fixtures"
CONSUMPTION_ROOT = Path(__file__).parent.resolve()


def _run(*args, input_text=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=WORKSPACE,
        input=input_text,
        capture_output=True,
        text=True,
    )


def _ready_build():
    return {
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


def _profile():
    return {
        "schema_version": "1.0",
        "profile_id": "camera-anima-v1",
        "runtime_classification": "local",
        "workflow_fingerprint": "96aac5b2fc5e565eadf4b9aba8d7c59016d327589fc40153be737b6187f27011",
        "api_normalization": {
            "schema_version": "1.0",
            "literal_inputs": [
                {"node_id": 26, "input_name": "text", "ui_node_id": 26, "widget_index": 1}
            ],
            "output_fallbacks": [
                {"source_node_id": 111, "output_index": 0, "target_node_id": 35, "target_input": "images"},
                {"source_node_id": 111, "output_index": 0, "target_node_id": 490, "target_input": "images"},
            ],
            "remove_nodes": [28, 41, 52, 62, 67, 70, 77],
        },
        "allowed_mutations": ["untrusted.profile.value"],
        "slots": {
            "positive_prompt": {
                "id": 24,
                "type": "ImpactWildcardProcessor",
                "title": "POSITIVE",
            },
            "negative_prompt": {
                "id": 25,
                "type": "ImpactWildcardProcessor",
                "title": "NEGATIVE",
            },
            "camera_angle": {"id": 583},
            "camera_extra": {"id": 585, "type": "CameraExtraConfigNode"},
        },
        "img2img": {
            "group_id": 3,
            "node_ids": [21, 58, 57, 59],
            "load_image_node_id": 21,
            "vae_encode_node_id": 59,
            "latent_switch_node_id": 75,
            "sampler_node_id": 27,
            "expected_path_node_ids": [27, 75, 59],
        },
        "expected_outputs": ["image/png"],
    }


def _capability_report():
    now = datetime.now(timezone.utc)
    return {
        "schema_version": "1.0",
        "comfyui": {"url": "http://127.0.0.1:8188", "reachable": True},
        "adapter": {"runtime_classification": "local", "tools": []},
        "queue": {"running": 0, "pending": 0},
        "workflow_candidates": [
            {
                "profile_id": "camera-anima-v1",
                "production": True,
                "status": "needs-normalization",
                "production_ready": False,
            }
        ],
        "generated_at": (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        "valid_until": (now + timedelta(minutes=9)).isoformat().replace("+00:00", "Z"),
    }


def _ui_workflow():
    return json.loads((FIXTURES / "camera-ui-minimal.json").read_text(encoding="utf-8"))


def _api_graph():
    return json.loads((FIXTURES / "camera-api-minimal.json").read_text(encoding="utf-8"))


def _exact_patches(build):
    return [
        {"slot": "positive_prompt", "input": "wildcard_text", "value": build["prompt"]},
        {"slot": "positive_prompt", "input": "populated_text", "value": build["prompt"]},
        {"slot": "negative_prompt", "input": "wildcard_text", "value": build["negative_prompt"]},
        {"slot": "negative_prompt", "input": "populated_text", "value": build["negative_prompt"]},
    ]


def _plan_envelope():
    build = _ready_build()
    workflow = _ui_workflow()
    return {
        "stage": "character-base",
        "prompt_build": build,
        "workflow_profile_id": "camera-anima-v1",
        "workflow_fingerprint": structure_fingerprint(workflow),
        "patches": _exact_patches(build),
        "capability_report": _capability_report(),
        "profile": _profile(),
        "actual_ui_workflow": workflow,
        "api_graph": _api_graph(),
    }


def _approval_event(draft, consumption_root=None, **overrides):
    now = datetime.now(timezone.utc)
    event = {
        "decision": "approved",
        "draft_hash": draft["draft_hash"],
        "displayed_at": (now - timedelta(seconds=2)).isoformat().replace("+00:00", "Z"),
        "approved_at": (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "scope": "enqueue-once",
        "consumption_root": str(
            CONSUMPTION_ROOT if consumption_root is None else Path(consumption_root)
        ),
        "actor": "user:test",
        "source": "cli-test",
    }
    event.update(overrides)
    return event


def _task_context():
    return {
        "schema_version": "1.0",
        "shared_known": {
            "goal": "create a front-facing character base",
            "background": [],
            "acceptance": ["new PNG"],
            "boundaries": ["local only"],
        },
        "user_known_agent_unknown": {
            "references": [],
            "aesthetic_preferences": [],
            "real_world_constraints": [],
        },
        "agent_known_user_unknown": {"capabilities": [], "risks": [], "alternatives": []},
        "shared_unknown": {"hypotheses": [], "experiments": []},
    }


def test_fingerprint_command_emits_json(tmp_path):
    workflow = tmp_path / "workflow.json"
    workflow.write_text('{"nodes":[],"groups":[],"links":[]}', encoding="utf-8")

    result = _run("fingerprint", "--workflow", workflow)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert len(json.loads(result.stdout)["structure_fingerprint"]) == 64


def test_discover_command_builds_report_from_negotiated_adapter(monkeypatch, capsys):
    class FakeApi:
        def __init__(self, base_url, timeout):
            self.base_url = base_url

        def system_stats(self):
            return {
                "system": {"comfyui_version": "0.29.0"},
                "devices": [{"name": "GPU", "vram_total": 8, "vram_free": 4}],
            }

        def queue(self):
            return {"queue_running": [], "queue_pending": []}

        def object_info(self):
            return {"ImpactWildcardProcessor": {}}

        def saved_workflows(self):
            return ["文生图相机视角.json"]

    monkeypatch.setattr(runtime_cli, "ComfyApi", FakeApi)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "base_url": "http://127.0.0.1:8188",
                    "adapter": {
                        "name": "comfyui-mcp",
                        "version": "0.49.0",
                        "runtime_classification": "local",
                        "tools": ["workflow-load"],
                    },
                }
            )
        ),
    )

    exit_code = runtime_cli.main(["discover", "--from-stdin"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report["adapter"]["tools"] == ["workflow-load"]
    assert report["saved_workflows"] == ["文生图相机视角.json"]


def test_submit_stage_command_is_explicit_and_delegates_local_post(monkeypatch, capsys):
    observed = {}

    def fake_submit(*args, **payload):
        payload["positional"] = args
        observed.update(payload)
        return {"receipt": {"prompt_id": "prompt-cli-stage"}, "history": {}}

    monkeypatch.setattr(runtime_cli, "submit_stage_via_local_rest", fake_submit)
    payload = {
        "approved_plan": {},
        "source_api_graph": {},
        "consumption": {},
        "consumption_path": "C:/run/consumed.json",
        "profile": {},
        "capability_report": {},
    }

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    exit_code = runtime_cli.main(["submit-stage", "--from-stdin"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out)["receipt"]["prompt_id"] == "prompt-cli-stage"
    assert observed["base_url"] == "http://127.0.0.1:8188"


def test_submit_character_base_command_delegates_local_post(monkeypatch, capsys):
    observed = {}

    def fake_submit(*args, **payload):
        payload["positional"] = args
        observed.update(payload)
        return {"enqueue_receipt": {"prompt_id": "prompt-cli-base"}, "history": {}}

    monkeypatch.setattr(runtime_cli, "submit_character_base_via_local_rest", fake_submit)
    payload = {
        "approved_plan": {},
        "prompt_build": {},
        "source_api_graph": {},
        "consumption": {},
        "consumption_path": "C:/run/consumed.json",
        "profile": {},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    exit_code = runtime_cli.main(["submit-character-base", "--from-stdin"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out)["enqueue_receipt"]["prompt_id"] == "prompt-cli-base"
    assert observed["base_url"] == "http://127.0.0.1:8188"


def test_wait_stage_command_delegates_read_only_history_poll(monkeypatch, capsys):
    class FakeApi:
        def __init__(self, base_url, timeout):
            self.base_url = base_url
            self.timeout = timeout

    observed = {}

    def fake_wait(api, prompt_id, *, timeout, poll_interval):
        observed.update({"base_url": api.base_url, "prompt_id": prompt_id, "timeout": timeout, "poll_interval": poll_interval})
        return {prompt_id: {"status": {"status_str": "success", "completed": True}}}

    monkeypatch.setattr(runtime_cli, "ComfyApi", FakeApi)
    monkeypatch.setattr(runtime_cli, "wait_for_stage_history", fake_wait)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"prompt_id": "prompt-wait"})))
    exit_code = runtime_cli.main([
        "wait-stage", "--from-stdin", "--timeout", "12", "--poll-interval", "3",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert observed == {
        "base_url": "http://127.0.0.1:8188",
        "prompt_id": "prompt-wait",
        "timeout": 12.0,
        "poll_interval": 3.0,
    }


def test_record_stage_rejects_missing_raw_history_before_writing(tmp_path):
    payload = tmp_path / "record-stage.json"
    payload.write_text(
        json.dumps({
            "approved_plan": {},
            "submission": {},
            "enqueue_receipt": {},
            "artifact": {},
        }),
        encoding="utf-8",
    )
    result = _run("record-stage", "--input", payload, "--run-dir", tmp_path / "runs")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "raw history" in result.stderr


def test_patch_camera_accepts_stdin_and_emits_only_json():
    payload = {
        "api_graph": _api_graph(),
        "prompt_build": _ready_build(),
        "slots": {"positive_prompt": 24, "negative_prompt": 25},
    }

    result = _run("patch-camera", "--from-stdin", input_text=json.dumps(payload))

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    graph = json.loads(result.stdout)
    assert graph["24"]["inputs"]["wildcard_text"] == payload["prompt_build"]["prompt"]
    assert graph["25"]["inputs"]["populated_text"] == payload["prompt_build"]["negative_prompt"]


def test_plan_emits_unapproved_draft_without_accepting_approval_boolean(tmp_path):
    payload = tmp_path / "plan.json"
    envelope = _plan_envelope()
    payload.write_text(json.dumps(envelope), encoding="utf-8")

    result = _run("plan", "--input", payload)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    draft = json.loads(result.stdout)
    assert draft["plan_state"] == "draft"
    assert draft["execution_approved"] is False
    assert len(draft["draft_hash"]) == 64

    envelope["execution_approved"] = True
    payload.write_text(json.dumps(envelope), encoding="utf-8")
    rejected = _run("plan", "--input", payload)
    assert rejected.returncode == 2
    assert rejected.stdout == ""
    assert "unexpected keyword" in rejected.stderr


def test_approve_plan_binds_exact_draft_and_exclusive_writes_evidence(tmp_path):
    draft = build_execution_draft(**_plan_envelope())
    payload = tmp_path / "approval.json"
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    event = _approval_event(draft, run_dir.resolve())
    payload.write_text(
        json.dumps({"draft": draft, "approval_event": event}), encoding="utf-8"
    )
    first = _run("approve-plan", "--input", payload, "--run-dir", run_dir)
    second = _run("approve-plan", "--input", payload, "--run-dir", run_dir)

    assert first.returncode == second.returncode == 0
    result = json.loads(first.stdout)
    assert json.loads(second.stdout) == result
    assert result["plan"]["approval_id"] == content_hash(event)
    assert Path(result["approval_event_path"]).name.endswith(".approval.json")
    assert Path(result["plan_path"]).name.endswith(".approved-plan.json")
    assert json.loads(Path(result["approval_event_path"]).read_text(encoding="utf-8")) == event
    assert json.loads(Path(result["plan_path"]).read_text(encoding="utf-8")) == result["plan"]

    plan_path = Path(result["plan_path"])
    tampered = copy.deepcopy(result["plan"])
    tampered["plan_state"] = "tampered"
    plan_path.write_text(json.dumps(tampered), encoding="utf-8")
    rejected = _run("approve-plan", "--input", payload, "--run-dir", run_dir)
    assert rejected.returncode == 2
    assert rejected.stdout == ""
    assert "refusing to overwrite" in rejected.stderr
    assert json.loads(plan_path.read_text(encoding="utf-8")) == tampered


def test_approve_plan_wrong_or_stale_event_is_exit_two_without_files(tmp_path):
    draft = build_execution_draft(**_plan_envelope())
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    for event in (
        _approval_event(draft, run_dir.resolve(), draft_hash="0" * 64),
        _approval_event(
            draft,
            run_dir.resolve(),
            displayed_at="2026-08-02T00:00:00Z",
            approved_at="2026-08-02T00:00:01Z",
            expires_at="2026-08-02T00:05:00Z",
        ),
    ):
        result = _run(
            "approve-plan",
            "--from-stdin",
            "--run-dir",
            run_dir,
            input_text=json.dumps({"draft": draft, "approval_event": event}),
        )
        assert result.returncode == 2
        assert result.stdout == ""
    assert list(run_dir.iterdir()) == []


def test_approve_plan_rejects_run_dir_outside_event_consumption_root(tmp_path):
    draft = build_execution_draft(**_plan_envelope())
    bound_root = tmp_path / "bound"
    wrong_root = tmp_path / "wrong"
    bound_root.mkdir()
    wrong_root.mkdir()
    event = _approval_event(draft, consumption_root=str(bound_root.resolve()))

    result = _run(
        "approve-plan",
        "--from-stdin",
        "--run-dir",
        wrong_root,
        input_text=json.dumps({"draft": draft, "approval_event": event}),
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "consumption root" in result.stderr
    assert list(wrong_root.iterdir()) == []


def test_consume_approval_is_atomic_and_never_idempotent(tmp_path):
    draft = build_execution_draft(**_plan_envelope())
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    event = _approval_event(draft, run_dir.resolve())
    plan = approve_execution_draft(
        draft,
        event,
        consumption_root=run_dir.resolve(),
    )
    payload = {
        "approved_plan": plan,
        "enqueue_request_id": "stable-client-request-b",
    }
    first = _run(
        "consume-approval",
        "--from-stdin",
        "--run-dir",
        run_dir,
        input_text=json.dumps(payload),
    )
    second = _run(
        "consume-approval",
        "--from-stdin",
        "--run-dir",
        run_dir,
        input_text=json.dumps(payload),
    )

    assert first.returncode == 0, first.stderr
    result = json.loads(first.stdout)
    consumed_path = Path(result["consumption_path"])
    assert consumed_path.name == f'{plan["approval_id"]}.consumed.json'
    assert json.loads(consumed_path.read_text(encoding="utf-8")) == result["consumption"]
    assert second.returncode == 2
    assert second.stdout == ""
    assert "already consumed" in second.stderr


def test_same_approval_cannot_be_consumed_in_child_and_parent_run_dirs(tmp_path):
    draft = build_execution_draft(**_plan_envelope())
    parent = tmp_path / "runs"
    child = parent / "child"
    child.mkdir(parents=True)
    event = _approval_event(draft, child.resolve())
    plan = approve_execution_draft(
        draft,
        event,
        consumption_root=child.resolve(),
    )
    payload = {
        "approved_plan": plan,
        "enqueue_request_id": "stable-client-request-b",
    }
    child_result = _run(
        "consume-approval",
        "--from-stdin",
        "--run-dir",
        child,
        input_text=json.dumps(payload),
    )
    parent_result = _run(
        "consume-approval",
        "--from-stdin",
        "--run-dir",
        parent,
        input_text=json.dumps(payload),
    )

    assert child_result.returncode == 0, child_result.stderr
    assert parent_result.returncode == 2
    assert parent_result.stdout == ""
    assert "consumption root" in parent_result.stderr


def test_malformed_json_is_exit_two_with_one_prefixed_stderr_line():
    result = _run("fingerprint", "--from-stdin", input_text="{")

    assert result.returncode == 2
    assert result.stdout == ""
    lines = result.stderr.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("[character-video-pipeline-runtime] ")


def test_record_uses_exclusive_create_and_identical_content_is_idempotent(tmp_path):
    plan_input = _plan_envelope()
    draft = build_execution_draft(**plan_input)
    event = _approval_event(draft)
    plan = approve_execution_draft(
        draft,
        event,
        consumption_root=event["consumption_root"],
    )
    build = plan_input["prompt_build"]
    graph = plan_input["api_graph"]
    prompt_id = "prompt-cli-1"
    executable = patch_character_base(
        graph, build, {"positive_prompt": 24, "negative_prompt": 25}
    )
    output_hash = content_hash({"fixture": "character.png"})
    history = {
        prompt_id: {
            "prompt": [0, prompt_id, executable],
            "status": {"status_str": "success", "completed": True},
            "outputs": {
                "99": {
                    "images": [
                        {"filename": "character.png", "subfolder": "", "type": "output"}
                    ]
                }
            },
        }
    }
    record_input = {
        "task_context": _task_context(),
        "prompt_build": build,
        "api_graph": graph,
        "execution_plan": plan,
        "prompt_id": prompt_id,
        "terminal_status": "succeeded",
        "input_hashes": {},
        "output_hashes": {"character.png": output_hash},
        "history": history,
    }
    payload = tmp_path / "record-input.json"
    payload.write_text(json.dumps(record_input), encoding="utf-8")
    run_dir = tmp_path / "runs"

    first = _run("record", "--input", payload, "--run-dir", run_dir)
    second = _run("record", "--input", payload, "--run-dir", run_dir)

    assert first.returncode == second.returncode == 0
    first_result = json.loads(first.stdout)
    second_result = json.loads(second.stdout)
    assert first_result == second_result
    record_path = Path(first_result["record_path"])
    assert record_path.name == f'{first_result["record"]["record_hash"]}.json'
    assert json.loads(record_path.read_text(encoding="utf-8")) == first_result["record"]

    tampered = copy.deepcopy(first_result["record"])
    tampered["terminal_status"] = "failed"
    record_path.write_text(json.dumps(tampered), encoding="utf-8")
    rejected = _run("record", "--input", payload, "--run-dir", run_dir)
    assert rejected.returncode == 2
    assert rejected.stdout == ""
    assert "refusing to overwrite" in rejected.stderr
    assert json.loads(record_path.read_text(encoding="utf-8")) == tampered


def test_select_reference_command_is_explicit_and_deterministic():
    payload = {
        "desired_view": "left_45",
        "artifacts": [
            {"artifact_type": "CharacterBaseImage", "view_label": "front", "accepted": True, "content_hash": "base"},
            {"artifact_type": "CharacterAngleView", "view_label": "left_45", "accepted": True, "content_hash": "angle"},
        ],
    }
    result = _run("select-reference", "--from-stdin", input_text=json.dumps(payload))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["artifact"]["content_hash"] == "angle"


def test_activate_g1_and_verify_path_commands_do_not_enqueue():
    ui = json.loads((FIXTURES / "camera-img2img-ui-minimal.json").read_text(encoding="utf-8"))
    activate_payload = {"workflow": ui, "image_name": "runs/ref.png", "profile": {"img2img": {"group_id": 3, "node_ids": [21, 58, 57, 59], "load_image_node_id": 21}}}
    activated = _run("activate-g1", "--from-stdin", input_text=json.dumps(activate_payload))
    assert activated.returncode == 0, activated.stderr
    assert json.loads(activated.stdout)["nodes"][2]["mode"] == 0

    graph = json.loads((FIXTURES / "camera-img2img-api-minimal.json").read_text(encoding="utf-8"))
    verified = _run("verify-img2img-path", "--from-stdin", input_text=json.dumps({"api_graph": graph, "profile": {"img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27}}}))
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["traversed_node_ids"] == [27, 75, 59]


def test_normalize_camera_command_repairs_only_the_pinned_source_bridge():
    graph = {
        "26": {"class_type": "Lora Loader (LoraManager)", "inputs": {"model": ["22", 0]}},
        "35": {"class_type": "Image Saver Simple", "inputs": {"metadata": ["89", 0]}},
        "490": {"class_type": "PreviewImage", "inputs": {}},
        "76": {"class_type": "VAEDecode", "inputs": {"samples": ["51", 0], "vae": ["48", 0]}},
        "96": {"class_type": "AdjustContrast", "inputs": {"images": ["76", 0]}},
        "111": {"class_type": "ImageSharpen", "inputs": {"image": ["96", 0]}},
        **{
            str(node_id): {"class_type": "Optional", "inputs": {}}
            for node_id in (28, 41, 52, 62, 67, 70, 77)
        },
    }
    ui = {
        "nodes": [
            {
                "id": 26,
                "type": "Lora Loader (LoraManager)",
                "widgets_values": [{"version": 1}, "<lora:anima:1.0>"],
            }
        ]
    }
    profile = {
        "schema_version": "1.0",
        "profile_id": "camera-anima-v1",
        "api_normalization": {
            "schema_version": "1.0",
            "literal_inputs": [
                {"node_id": 26, "input_name": "text", "ui_node_id": 26, "widget_index": 1}
            ],
            "output_fallbacks": [
                {"source_node_id": 111, "output_index": 0, "target_node_id": 35, "target_input": "images"},
                {"source_node_id": 111, "output_index": 0, "target_node_id": 490, "target_input": "images"},
            ],
            "remove_nodes": [28, 41, 52, 62, 67, 70, 77],
        },
    }
    result = _run(
        "normalize-camera",
        "--from-stdin",
        input_text=json.dumps({"api_graph": graph, "ui_workflow": ui, "profile": profile}),
    )
    assert result.returncode == 0, result.stderr
    normalized = json.loads(result.stdout)
    assert normalized["26"]["inputs"]["text"] == "<lora:anima:1.0>"
    assert normalized["35"]["inputs"]["images"] == ["111", 0]
    assert "28" not in normalized


def test_plan_shot_and_plan_video_commands_are_pure():
    shot_payload = {
        "base_prompt_build_hash": "base",
        "shot_prompt_build_hash": "shot",
        "reference": {"artifact_type": "CharacterAngleView", "accepted": True, "content_hash": "ref", "view_label": "front"},
        "desired_view": "front",
        "execution_approved": True,
    }
    shot = _run("plan-shot", "--from-stdin", input_text=json.dumps(shot_payload))
    assert shot.returncode == 0, shot.stderr
    assert json.loads(shot.stdout)["stage"] == "shot-image"
    video_payload = {
        "shot": {"artifact_type": "ShotImage", "accepted": True, "content_hash": "shot"},
        "prompt_build": {"target": "video", "dialect": "video-timeline", "prompt": "The subject moves as the camera dollies in.", "negative_prompt": "", "ready_to_execute": True},
        "workflow_hash": "wf",
        "profile_hash": "profile",
        "execution_approved": True,
    }
    video = _run("plan-video", "--from-stdin", input_text=json.dumps(video_payload))
    assert video.returncode == 0, video.stderr
    assert json.loads(video.stdout)["parameters"]["frames"] == 24


def test_ingest_story_emits_canonical_hash_without_execution_side_effects(capsys):
    story = {
        "schema_version": "1.0",
        "visual_system": {
            "primary_style": "cinematic",
            "medium": "digital",
            "visual_grammar": ["clean silhouettes"],
            "palette": ["amber"],
            "materials": ["wool"],
            "lighting": ["soft key"],
            "motifs": ["rings"],
        },
        "characters": [],
        "scenes": [],
        "story_logic": [],
        "uncertainty": {},
        "source_hash": "a" * 64,
    }
    # Invoke the in-process boundary so this test cannot accidentally enqueue.
    import runtime.story_assets as story_assets
    expected = story_assets.story_breakdown_hash(story)
    import unittest.mock
    with unittest.mock.patch.object(sys, "stdin", io.StringIO(json.dumps(story))):
        assert runtime_cli.main(["ingest-story", "--from-stdin"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["story_breakdown_hash"] == expected
    assert result["planning_only"] is True


def test_plan_video_production_request_requires_trusted_duration_profile(capsys):
    payload = {
        "shot": {
            "artifact_type": "ShotImage",
            "accepted": True,
            "content_hash": "a" * 64,
            "task_context_hash": "b" * 64,
            "source_story_hash": "c" * 64,
            "art_bible_hash": "d" * 64,
            "lineage_id": "lineage-1",
        },
        "prompt_build": {
            "target": "video",
            "dialect": "video-timeline",
            "prompt": "a subject moves",
            "negative_prompt": "",
            "ready_to_execute": True,
            "split_recommendation": {"required": False},
        },
        "workflow_hash": "e" * 64,
        "profile_hash": "f" * 64,
        "execution_approved": True,
        "motion_delta": "dolly in",
        "split_decision": {"required": False, "approved": True},
        "intent": {"schema_version": "1.0"},
    }
    import unittest.mock
    with unittest.mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
        assert runtime_cli.main(["plan-video", "--from-stdin"]) == 1
    assert "duration profile" in capsys.readouterr().out.lower()


def test_plan_video_rejects_caller_forged_hashes_without_trusted_evidence(capsys):
    payload = {
        "shot": {
            "artifact_type": "ShotImage",
            "accepted": True,
            "content_hash": "a" * 64,
            "task_context_hash": "b" * 64,
            "source_story_hash": "c" * 64,
            "art_bible_hash": "d" * 64,
            "lineage_id": "lineage-1",
        },
        "prompt_build": {
            "target": "video", "dialect": "video-timeline", "prompt": "move",
            "positive_zh": "移动", "positive_en": "move", "negative_prompt": "",
            "ready_to_execute": True, "split_recommendation": {"required": False},
        },
        "workflow_hash": "0" * 64,
        "profile_hash": "0" * 64,
        "execution_approved": True,
        "duration_profile_id": "ltx-yusu-short-v1",
        "motion_delta": "dolly in",
        "split_decision": {"required": False, "approved": True},
        "intent": {"schema_version": "1.0"},
    }
    import unittest.mock
    with unittest.mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
        assert runtime_cli.main(["plan-video", "--from-stdin"]) == 1
    assert "trusted workflow" in capsys.readouterr().out.lower()
