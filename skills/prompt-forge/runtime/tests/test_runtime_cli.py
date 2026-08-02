import copy
import json
import subprocess
import sys
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.adapters.camera import patch_character_base
from runtime.contracts import content_hash
from runtime.execution import build_execution_plan
from runtime.workflow_profile import structure_fingerprint
import runtime.runtime_cli as runtime_cli


WORKSPACE = Path(__file__).resolve().parents[4]
SCRIPT = WORKSPACE / "skills/prompt-forge/runtime/runtime_cli.py"
FIXTURES = Path(__file__).parent / "fixtures"


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


def _plan_envelope(execution_approved=True):
    build = _ready_build()
    workflow = _ui_workflow()
    return {
        "stage": "character-base",
        "prompt_build": build,
        "workflow_profile_id": "camera-anima-v1",
        "workflow_fingerprint": structure_fingerprint(workflow),
        "patches": _exact_patches(build),
        "execution_approved": execution_approved,
        "capability_report": _capability_report(),
        "profile": _profile(),
        "actual_ui_workflow": workflow,
        "api_graph": _api_graph(),
    }


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


def test_plan_rejection_is_json_exit_one_without_runtime_diagnostic(tmp_path):
    payload = tmp_path / "plan.json"
    payload.write_text(json.dumps(_plan_envelope(execution_approved=False)), encoding="utf-8")

    result = _run("plan", "--input", payload)

    assert result.returncode == 1
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "accepted": False,
        "error": "current explicit execution approval is required",
    }


def test_malformed_json_is_exit_two_with_one_prefixed_stderr_line():
    result = _run("fingerprint", "--from-stdin", input_text="{")

    assert result.returncode == 2
    assert result.stdout == ""
    lines = result.stderr.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("[prompt-forge-runtime] ")


def test_record_uses_exclusive_create_and_identical_content_is_idempotent(tmp_path):
    plan_input = _plan_envelope()
    plan = build_execution_plan(**plan_input)
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
