# Prompt Forge v7 Slice 1 Runtime and Character Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the auditable runtime foundation and generate a front-facing Anima character base image through the verified camera workflow.

**Architecture:** Keep `internals/prompt_compile.py` pure. Add a sibling `runtime` package that validates task context, probes ComfyUI, fingerprints workflow structure, builds an allowlisted execution plan and records immutable provenance. The Skill calls `comfyui-mcp` for UI-to-API conversion and validation; Python does not implement a workflow converter.

**Tech Stack:** Python 3.11+ standard library, pytest, ComfyUI REST API 0.29.0, comfyui-mcp 0.49.0, JSON workflow profiles.

## Global Constraints

- Default ComfyUI URL: `http://127.0.0.1:8188`; it must remain configurable.
- Runtime code is stdlib-only.
- Prompt compilation never performs generation and keeps `execution.performed=false`.
- Only a current explicit generate/run request may set `execution_approved=true`.
- Never mutate the saved workflow or install models/custom nodes.
- Reject paid, mixed and unknown runtime classifications.
- Capability reports expire after 600 seconds.
- Use one ComfyUI job at a time on the 8 GB device.
- Default tests never enqueue; live tests require `PROMPT_FORGE_LIVE=1`.

---

## File Structure

- Create `skills/prompt-forge/runtime/__init__.py` — stable exports.
- Create `skills/prompt-forge/runtime/contracts.py` — TaskContext, canonical JSON and hashes.
- Create `skills/prompt-forge/runtime/errors.py` — five-category structured runtime faults.
- Create `skills/prompt-forge/runtime/comfy_api.py` — narrow REST client.
- Create `skills/prompt-forge/runtime/capabilities.py` — CapabilityReport.
- Create `skills/prompt-forge/runtime/workflow_profile.py` — structure fingerprint and slot resolution.
- Create `skills/prompt-forge/runtime/execution.py` — ExecutionPlan and RunRecord.
- Create `skills/prompt-forge/runtime/adapters/camera.py` — Stage 1 graph patcher.
- Create `skills/prompt-forge/runtime/prompt_quality.py` — Anima PromptBuild quality gate.
- Create `skills/prompt-forge/runtime/profiles/camera-anima.json` — camera profile.
- Create `skills/prompt-forge/runtime/runtime_cli.py` — JSON CLI.
- Create `skills/prompt-forge/runtime/tests/**` — deterministic and opt-in live tests.
- Modify `skills/prompt-forge/SKILL.md` — valid UTF-8 v7 procedure.
- Modify `README.md` — truthful Slice 1 surface.

### Task 1: TaskContext and canonical identity

**Files:**
- Create: `skills/prompt-forge/runtime/__init__.py`
- Create: `skills/prompt-forge/runtime/contracts.py`
- Create: `skills/prompt-forge/runtime/tests/__init__.py`
- Create: `skills/prompt-forge/runtime/tests/test_contracts.py`

**Interfaces:**
- Consumes: JSON-compatible dictionaries.
- Produces: `validate_task_context(value: dict) -> dict`, `canonical_json(value: object) -> str`, `content_hash(value: object) -> str`.

- [ ] **Step 1: Write failing tests**

~~~python
import pytest
from runtime.contracts import ContractError, content_hash, validate_task_context


def valid_context():
    return {
        "schema_version": "1.0",
        "shared_known": {
            "goal": "create one character video shot",
            "background": [],
            "acceptance": ["front-facing base image"],
            "boundaries": ["local only"],
        },
        "user_known_agent_unknown": {
            "references": [],
            "aesthetic_preferences": [],
            "real_world_constraints": [],
        },
        "agent_known_user_unknown": {
            "capabilities": [],
            "risks": [],
            "alternatives": [],
        },
        "shared_unknown": {"hypotheses": [], "experiments": []},
    }


def test_context_is_copied_and_validated():
    source = valid_context()
    result = validate_task_context(source)
    assert result == source
    assert result is not source


def test_goal_is_required():
    source = valid_context()
    source["shared_known"]["goal"] = ""
    with pytest.raises(ContractError, match="goal"):
        validate_task_context(source)


def test_hash_ignores_dictionary_key_order():
    assert content_hash({"b": 2, "a": 1}) == content_hash({"a": 1, "b": 2})
~~~

- [ ] **Step 2: Run RED**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_contracts.py -q
~~~

Expected: collection fails because `runtime.contracts` is missing.

- [ ] **Step 3: Implement contracts**

~~~python
import copy
import hashlib
import json

QUADRANTS = {
    "shared_known": ("goal", "background", "acceptance", "boundaries"),
    "user_known_agent_unknown": (
        "references", "aesthetic_preferences", "real_world_constraints"
    ),
    "agent_known_user_unknown": ("capabilities", "risks", "alternatives"),
    "shared_unknown": ("hypotheses", "experiments"),
}


class ContractError(ValueError):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_task_context(value: dict) -> dict:
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        raise ContractError("TaskContext schema_version must be '1.0'")
    for quadrant, fields in QUADRANTS.items():
        section = value.get(quadrant)
        if not isinstance(section, dict):
            raise ContractError(f"TaskContext requires object '{quadrant}'")
        for field in fields:
            if field not in section:
                raise ContractError(f"TaskContext {quadrant} requires '{field}'")
            if field != "goal" and not isinstance(section[field], list):
                raise ContractError(f"TaskContext {quadrant}.{field} must be a list")
    if not str(value["shared_known"]["goal"]).strip():
        raise ContractError("TaskContext shared_known.goal must be non-empty")
    return copy.deepcopy(value)
~~~

Export these names from `runtime/__init__.py`.

- [ ] **Step 4: Run GREEN**

Run Step 2 again. Expected: `3 passed`.

- [ ] **Step 5: Commit**

~~~powershell
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): add v7 runtime contracts"
~~~

### Task 2: Read-only ComfyUI capability discovery

**Files:**
- Create: `skills/prompt-forge/runtime/comfy_api.py`
- Create: `skills/prompt-forge/runtime/capabilities.py`
- Create: `skills/prompt-forge/runtime/tests/test_capabilities.py`

**Interfaces:**
- Consumes: `ComfyApi`, injected UTC clock, adapter metadata.
- Produces: `build_capability_report(api, adapter, now) -> dict`, `report_is_fresh(report, now) -> bool`, `require_adapter_tools(report, required) -> None`.

- [ ] **Step 1: Write failing tests**

~~~python
from datetime import datetime, timezone
import pytest
from runtime.capabilities import (
    build_capability_report, report_is_fresh, require_adapter_tools
)
from runtime.comfy_api import CapabilityError


class FakeApi:
    def system_stats(self):
        return {
            "system": {"comfyui_version": "0.29.0"},
            "devices": [{"name": "RTX 4060", "vram_total": 8585216000, "vram_free": 1000}],
        }

    def queue(self):
        return {"queue_running": [], "queue_pending": []}

    def object_info(self):
        return {"ImpactWildcardProcessor": {}, "CameraAngleNode": {}}

    def saved_workflows(self):
        return ["文生图相机视角.json"]


def test_report_contains_live_counts_and_expiry():
    now = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
    report = build_capability_report(
        FakeApi(), {"name": "comfyui-mcp", "version": "0.49.0", "tools": []}, now
    )
    assert report["hardware"]["vram_total_bytes"] == 8585216000
    assert report["node_type_count"] == 2
    assert report["saved_workflows"] == ["文生图相机视角.json"]
    assert report_is_fresh(report, now)


def test_report_expires_after_600_seconds():
    now = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
    report = build_capability_report(FakeApi(), {"name": "x", "version": "1", "tools": []}, now)
    later = datetime(2026, 8, 2, 15, 10, 1, tzinfo=timezone.utc)
    assert not report_is_fresh(report, later)


def test_missing_adapter_tool_is_a_hard_stop():
    now = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
    report = build_capability_report(
        FakeApi(),
        {"name": "comfyui-mcp", "version": "0.49.0", "tools": ["list_workflows"]},
        now,
    )
    with pytest.raises(CapabilityError, match="validate_workflow"):
        require_adapter_tools(report, ["list_workflows", "validate_workflow"])
~~~

- [ ] **Step 2: Run RED**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_capabilities.py -q
~~~

Expected: import failure.

- [ ] **Step 3: Implement the narrow REST client**

~~~python
class ComfyApi:
    def __init__(self, base_url="http://127.0.0.1:8188", timeout=30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_json(self, path):
        request = urllib.request.Request(
            self.base_url + path, headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def system_stats(self):
        return self.get_json("/system_stats")

    def queue(self):
        return self.get_json("/queue")

    def object_info(self):
        return self.get_json("/object_info")

    def saved_workflows(self):
        result = self.get_json("/userdata?dir=workflows&recurse=true")
        if not isinstance(result, list) or not all(isinstance(item, str) for item in result):
            raise CapabilityError("saved workflow response must be a string list")
        return result
~~~

Wrap URL, timeout and JSON failures as `CapabilityError`; never log headers.

- [ ] **Step 4: Implement the report**

Use ISO-8601 UTC timestamps, `valid_until=now+600 seconds`, first device stats,
node count, workflow list and queue counts. `report_is_fresh` parses
`valid_until` and compares it to the injected UTC time.

`require_adapter_tools` compares required names with `report["adapter"]["tools"]`
and reports every missing tool in sorted order. The Skill calls it before
workflow load, conversion, validation or enqueue operations.

- [ ] **Step 5: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_capabilities.py skills/prompt-forge/internals/tests -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): discover live comfyui capabilities"
~~~

### Task 3: Structural fingerprint and camera profile

**Files:**
- Create: `skills/prompt-forge/runtime/workflow_profile.py`
- Create: `skills/prompt-forge/runtime/profiles/camera-anima.json`
- Create: `skills/prompt-forge/runtime/tests/fixtures/camera-ui-minimal.json`
- Create: `skills/prompt-forge/runtime/tests/test_workflow_profile.py`

**Interfaces:**
- Consumes: UI-format workflow and profile JSON.
- Produces: `structure_fingerprint(workflow) -> str`, `resolve_slots(workflow, profile) -> dict[str, int]`.

- [ ] **Step 1: Write failing tests**

~~~python
import copy
import json
from pathlib import Path
import pytest
from runtime.workflow_profile import ProfileError, resolve_slots, structure_fingerprint

FIXTURE = Path(__file__).parent / "fixtures" / "camera-ui-minimal.json"


def test_prompt_change_does_not_change_structure():
    workflow = json.loads(FIXTURE.read_text(encoding="utf-8"))
    changed = copy.deepcopy(workflow)
    changed["nodes"][0]["widgets_values"][0] = "different prompt"
    assert structure_fingerprint(workflow) == structure_fingerprint(changed)


def test_node_type_change_changes_structure():
    workflow = json.loads(FIXTURE.read_text(encoding="utf-8"))
    changed = copy.deepcopy(workflow)
    changed["nodes"][0]["type"] = "DifferentNode"
    assert structure_fingerprint(workflow) != structure_fingerprint(changed)


def test_slots_resolve_by_type_and_title():
    workflow = json.loads(FIXTURE.read_text(encoding="utf-8"))
    profile = {"slots": {
        "positive_prompt": {"type": "ImpactWildcardProcessor", "title": "POSITIVE"},
        "negative_prompt": {"type": "ImpactWildcardProcessor", "title": "NEGATIVE"},
    }}
    assert resolve_slots(workflow, profile) == {
        "positive_prompt": 24, "negative_prompt": 25
    }


def test_ambiguous_slot_stops():
    workflow = json.loads(FIXTURE.read_text(encoding="utf-8"))
    workflow["nodes"].append(copy.deepcopy(workflow["nodes"][0]))
    with pytest.raises(ProfileError, match="exactly one"):
        resolve_slots(workflow, {"slots": {
            "positive": {"type": "ImpactWildcardProcessor", "title": "POSITIVE"}
        }})
~~~

- [ ] **Step 2: Run RED**

Run the new test file. Expected: import failure.

- [ ] **Step 3: Implement stable structural hashing**

~~~python
def structure_fingerprint(workflow):
    nodes = [{
        "id": node["id"],
        "type": node.get("type", ""),
        "title": node.get("title", ""),
        "inputs": [
            {"name": item.get("name"), "link": item.get("link")}
            for item in node.get("inputs", [])
        ],
        "outputs": [
            {"name": item.get("name"), "links": item.get("links") or []}
            for item in node.get("outputs", [])
        ],
    } for node in workflow.get("nodes", [])]
    groups = [
        {"id": group.get("id"), "title": group.get("title", "")}
        for group in workflow.get("groups", [])
    ]
    payload = {
        "nodes": sorted(nodes, key=lambda item: str(item["id"])),
        "groups": sorted(groups, key=lambda item: str(item["id"])),
        "links": sorted(workflow.get("links", []), key=canonical_json),
    }
    return content_hash(payload)
~~~

Do not hash positions, widgets, prompt, seed, image filename or node mode.

- [ ] **Step 4: Add the verified profile**

~~~json
{
  "schema_version": "1.0",
  "profile_id": "camera-anima-v1",
  "workflow_name": "文生图相机视角.json",
  "generation_modes": ["text-to-image", "image-to-image"],
  "runtime_classification": "local",
  "slots": {
    "positive_prompt": {"type": "ImpactWildcardProcessor", "title": "POSITIVE"},
    "negative_prompt": {"type": "ImpactWildcardProcessor", "title": "NEGATIVE"},
    "camera_angle": {"type": "CameraAngleNode"},
    "camera_extra": {"type": "CameraExtraConfigNode"}
  },
  "allowed_mutations": [
    "positive_prompt.wildcard_text",
    "positive_prompt.populated_text",
    "negative_prompt.wildcard_text",
    "negative_prompt.populated_text",
    "camera_angle",
    "camera_extra"
  ],
  "expected_outputs": ["image/png"]
}
~~~

- [ ] **Step 5: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_workflow_profile.py skills/prompt-forge/internals/tests -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): profile the anima camera workflow"
~~~

### Task 4: Anima PromptBuild quality and structured faults

**Files:**
- Create: `skills/prompt-forge/runtime/errors.py`
- Create: `skills/prompt-forge/runtime/prompt_quality.py`
- Create: `skills/prompt-forge/runtime/tests/test_errors.py`
- Create: `skills/prompt-forge/runtime/tests/test_prompt_quality.py`

**Interfaces:**
- Consumes: Anima PromptBuild and PromptIntent.
- Produces: `validate_anima_prompt_build(build, intent) -> list[str]`, `make_fault(category, stage, message, retry_safe, next_action, evidence) -> dict`.

- [ ] **Step 1: Write failing quality and fault tests**

~~~python
import pytest
from runtime.errors import FaultError, make_fault
from runtime.prompt_quality import validate_anima_prompt_build


def test_anima_rejects_unverified_tags_and_positive_negative_conflict():
    build = {
        "target": "image",
        "dialect": "tags",
        "prompt": "score_9, 1girl, red_hair",
        "negative_prompt": "red hair, watermark",
        "validated_tags": ["1girl"],
        "rejected_tags": ["red_hair"],
        "recipe_control_tokens": ["score_9"],
        "locked_facts": ["red hair"],
        "ready_to_execute": True,
    }
    errors = validate_anima_prompt_build(build, {"locked_facts": ["red hair"]})
    assert any("unverified" in item for item in errors)
    assert any("contradicts" in item for item in errors)


def test_fault_uses_one_of_five_categories():
    fault = make_fault(
        "WORKFLOW_ERROR", "preflight", "profile drift", False,
        "rediscover the workflow profile", {"profile_id": "camera-anima-v1"}
    )
    assert fault["category"] == "WORKFLOW_ERROR"
    with pytest.raises(FaultError, match="category"):
        make_fault("OTHER", "x", "x", False, "stop", {})
~~~

- [ ] **Step 2: Run RED**

Run both new test files. Expected: import failures.

- [ ] **Step 3: Implement the Anima gate**

Require tag dialect, ready build, non-empty recipe control tokens, zero rejected
tags, no placeholder, unique positive/negative tokens, representation of locked
facts, and no normalized locked fact appearing in both positive and negative
prompts. Return errors without mutating either input.

- [ ] **Step 4: Implement structured faults**

Allow exactly `CAPABILITY_ERROR`, `WORKFLOW_ERROR`, `RESOURCE_ERROR`,
`POLICY_ERROR`, and `EXECUTION_ERROR`. Require non-empty stage, message and next
action; require boolean `retry_safe` and dictionary evidence. Return a JSON-safe
dictionary with schema version `1.0`.

- [ ] **Step 5: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_errors.py skills/prompt-forge/runtime/tests/test_prompt_quality.py -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): gate anima prompts and structure faults"
~~~

### Task 5: ExecutionPlan, camera patch and RunRecord

**Files:**
- Create: `skills/prompt-forge/runtime/execution.py`
- Create: `skills/prompt-forge/runtime/adapters/__init__.py`
- Create: `skills/prompt-forge/runtime/adapters/camera.py`
- Create: `skills/prompt-forge/runtime/tests/fixtures/camera-api-minimal.json`
- Create: `skills/prompt-forge/runtime/tests/test_execution.py`
- Create: `skills/prompt-forge/runtime/tests/test_camera_adapter.py`

**Interfaces:**
- Consumes: ready PromptBuild, profile, API graph.
- Produces: `build_execution_plan(...) -> dict`, `patch_character_base(...) -> dict`, `build_run_record(...) -> dict`.

- [ ] **Step 1: Write failing tests**

~~~python
import json
from pathlib import Path
import pytest
from runtime.adapters.camera import patch_character_base
from runtime.execution import ExecutionError, build_execution_plan

FIXTURE = Path(__file__).parent / "fixtures" / "camera-api-minimal.json"


def ready_build():
    return {
        "schema_version": "1.0",
        "model_id": "anima",
        "prompt": "score_9, 1girl, solo, from_front, full_body",
        "negative_prompt": "worst quality, low quality, watermark",
        "ready_to_execute": True,
        "execution": {"requested": True, "performed": False},
    }


def test_plan_requires_current_approval():
    with pytest.raises(ExecutionError, match="approval"):
        build_execution_plan(
            "character-base", ready_build(), "camera-anima-v1", "abc", [], False
        )


def test_patch_updates_both_prompt_fields_and_copies():
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    patched = patch_character_base(
        graph, ready_build(), {"positive_prompt": 24, "negative_prompt": 25}
    )
    assert patched["24"]["inputs"]["wildcard_text"] == ready_build()["prompt"]
    assert patched["24"]["inputs"]["populated_text"] == ready_build()["prompt"]
    assert patched["25"]["inputs"]["wildcard_text"] == ready_build()["negative_prompt"]
    assert graph["24"]["inputs"]["wildcard_text"] != ready_build()["prompt"]
~~~

- [ ] **Step 2: Run RED**

Run both new test files. Expected: import failures.

- [ ] **Step 3: Implement strict patching**

Deep-copy the graph, require both nodes, update only `wildcard_text` and
`populated_text`, and compare the canonical source/patched graphs after removing
those four allowlisted values. Any other change raises `ExecutionError`.

- [ ] **Step 4: Implement plan and record builders**

`build_execution_plan` rejects a non-ready PromptBuild, absent current approval,
non-local runtime, failed preflight or a patch outside the profile allowlist.
`build_run_record` stores context/build/graph hashes, prompt ID, terminal status,
input/output hashes and computes `record_hash` over the record without that field.

- [ ] **Step 5: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): plan and patch character base runs"
~~~

### Task 6: CLI, Skill contract and live Experiments A/B

**Files:**
- Create: `skills/prompt-forge/runtime/runtime_cli.py`
- Create: `skills/prompt-forge/runtime/tests/test_runtime_cli.py`
- Create: `skills/prompt-forge/runtime/tests/test_live_character_base.py`
- Modify: `skills/prompt-forge/SKILL.md`
- Modify: `skills/prompt-forge/internals/prompt_compile.py`
- Modify: `skills/prompt-forge/internals/tests/test_prompt_compile.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: file/stdin JSON for `discover`, `fingerprint`, `plan`, `patch-camera`, `record`.
- Produces: JSON stdout; diagnostics stderr; exits 0 success, 1 rejected plan, 2 malformed/runtime failure.

- [ ] **Step 1: Write a failing CLI test**

~~~python
import json
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
SCRIPT = WORKSPACE / "skills/prompt-forge/runtime/runtime_cli.py"


def test_fingerprint_command_emits_json(tmp_path):
    workflow = tmp_path / "workflow.json"
    workflow.write_text('{"nodes":[],"groups":[],"links":[]}', encoding="utf-8")
    result = subprocess.run(
        ["python", str(SCRIPT), "fingerprint", "--workflow", str(workflow)],
        cwd=WORKSPACE, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)["structure_fingerprint"]) == 64
~~~

- [ ] **Step 2: Implement argparse subcommands**

Each subcommand delegates to an already-tested function. Catch contract,
capability, profile, execution, I/O and JSON errors; print one prefixed message to
stderr and return 2.

The `record` command writes `<record_hash>.json` with exclusive-create semantics
under the caller-supplied run directory. If that path exists, compare canonical
content and succeed only when identical; never overwrite a different record.

- [ ] **Step 3: Repair and update the Skill**

Rewrite `SKILL.md` as valid UTF-8. Document this exact order: TaskContext,
PromptBuild, capability discovery, MCP load/strip/validate, fingerprint, plan,
prompt/plan display, explicit approval, enqueue, artifact verification, RunRecord.
The Skill limits material clarification questions to three and records
non-material assumptions in TaskContext.

Remove hardcoded fictional MCP tool names from `prompt_compile.py`. Set
`execution.tool=None` and add `execution.capability` equal to
`image-generation` or `video-generation`; update the existing test.

- [ ] **Step 4: Add opt-in live tests**

Start the module with:

~~~python
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("PROMPT_FORGE_LIVE") != "1",
    reason="set PROMPT_FORGE_LIVE=1 to enqueue real ComfyUI jobs",
)
~~~

Experiment A selects the latest successful matching camera API graph and changes
only its seed. Experiment B fixes that graph/seed and changes only the positive
PromptBuild. Assert terminal success, a new decodable PNG and retained RunRecord.
Never delete history or outputs.

- [ ] **Step 5: Run deterministic verification**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
Remove-Item Env:PROMPT_FORGE_LIVE -ErrorAction SilentlyContinue
python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q
python skills/prompt-forge/internals/evaluate.py
git diff --check
~~~

Expected: deterministic tests pass, live tests skip, 12/12 evaluations pass.

- [ ] **Step 6: Run Experiments A/B after explicit execution approval**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
$env:PROMPT_FORGE_LIVE='1'
python -m pytest skills/prompt-forge/runtime/tests/test_live_character_base.py -v
~~~

- [ ] **Step 7: Commit Slice 1**

~~~powershell
git add skills/prompt-forge README.md
git commit -m "feat(prompt-forge): complete v7 character base runtime"
~~~

## Slice 1 Completion Gate

- Deterministic tests pass.
- Experiments A/B pass against the current ComfyUI instance.
- The base image is front-facing and traceable to PromptBuild and RunRecord.
- No saved workflow, model or custom node changed.
- Slice 2 begins only after review of the Slice 1 commit.
