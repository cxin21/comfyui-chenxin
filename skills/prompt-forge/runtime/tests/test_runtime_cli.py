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
SCRIPT = WORKSPACE / "skills/prompt-forge/runtime/runtime_cli.py"
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
    assert lines[0].startswith("[prompt-forge-runtime] ")


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
