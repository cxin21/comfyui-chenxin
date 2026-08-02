# Prompt Forge v7 Slice 3 Shot Image-to-Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select the best available character angle, compile a shot-specific Anima PromptBuild, activate the complete G1 image path and produce a concrete shot image.

**Architecture:** Add a deterministic reference selector and extend the camera adapter with one atomic G1 activation operation. The stage reuses the camera profile but creates a new PromptIntent/PromptBuild; it never reuses the Stage 1 prompt. Converted-graph preflight must prove that the selected image reaches the intended latent/sampler path.

**Tech Stack:** Python 3.11+ standard library, pytest, Prompt Forge compiler, ComfyUI REST, comfyui-mcp conversion/validation.

## Global Constraints

- Slice 1 and Slice 2 completion gates are required.
- Prefer an individual `CharacterAngleView`; use `CharacterBaseImage` only as a recorded fallback.
- Create a new PromptIntent and PromptBuild for the shot.
- Preserve identity/costume facts as locked facts.
- Activate all G1 nodes together: 21, 58, 57 and 59 for the verified fingerprint.
- Never inject an unverified img2img strength.
- Do not enable unrelated groups or mutate saved workflows.
- Default tests never enqueue; Experiment D requires `PROMPT_FORGE_LIVE=1`.

---

## File Structure

- Create `skills/prompt-forge/runtime/reference_select.py`.
- Create `skills/prompt-forge/runtime/tests/test_reference_select.py`.
- Modify `skills/prompt-forge/runtime/profiles/camera-anima.json`.
- Modify `skills/prompt-forge/runtime/adapters/camera.py`.
- Create `skills/prompt-forge/runtime/tests/fixtures/camera-img2img-ui-minimal.json`.
- Create `skills/prompt-forge/runtime/tests/fixtures/camera-img2img-api-minimal.json`.
- Create `skills/prompt-forge/runtime/tests/test_camera_img2img.py`.
- Create `skills/prompt-forge/runtime/stages.py`.
- Create `skills/prompt-forge/runtime/tests/test_stage3_plan.py`.
- Create `skills/prompt-forge/runtime/tests/test_live_shot_img2img.py`.
- Modify `skills/prompt-forge/runtime/runtime_cli.py`.
- Modify `skills/prompt-forge/SKILL.md`.
- Modify `README.md`.

### Task 1: Deterministic reference-angle selection

**Files:**
- Create: `skills/prompt-forge/runtime/reference_select.py`
- Create: `skills/prompt-forge/runtime/tests/test_reference_select.py`

**Interfaces:**
- Consumes: desired camera direction and accepted artifact list.
- Produces: `select_reference(desired_view: str, artifacts: list[dict]) -> dict`.

- [ ] **Step 1: Write failing tests**

~~~python
from runtime.reference_select import select_reference


def artifacts():
    return [
        {
            "artifact_type": "CharacterBaseImage",
            "view_label": "front",
            "accepted": True,
            "content_hash": "base",
        },
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "left_45",
            "accepted": True,
            "content_hash": "left45",
        },
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "right",
            "accepted": True,
            "content_hash": "right",
        },
    ]


def test_exact_angle_view_wins():
    result = select_reference("left_45", artifacts())
    assert result["artifact"]["content_hash"] == "left45"
    assert result["selection_reason"] == "exact-angle"


def test_nearest_angle_beats_base_fallback():
    result = select_reference("left", artifacts())
    assert result["artifact"]["content_hash"] == "left45"
    assert result["selection_reason"] == "nearest-angle"


def test_base_image_is_recorded_fallback():
    result = select_reference("rear", [artifacts()[0]])
    assert result["artifact"]["content_hash"] == "base"
    assert result["selection_reason"] == "base-fallback"
~~~

- [ ] **Step 2: Run RED**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_reference_select.py -q
~~~

Expected: import failure.

- [ ] **Step 3: Implement explicit view distance**

~~~python
VIEW_DEGREES = {
    "front": 0,
    "right_45": 45,
    "right": 90,
    "rear_45": 135,
    "rear": 180,
    "left_45": 315,
    "left": 270,
}

VIEW_ALIASES = {
    "front_closeup": "front",
    "front_upper": "front",
}


def circular_distance(left, right):
    delta = abs(VIEW_DEGREES[left] - VIEW_DEGREES[right])
    return min(delta, 360 - delta)
~~~

Filter to accepted artifacts. Normalize labels through `VIEW_ALIASES`; exclude
ambiguous labels such as `side_unknown` from automatic angle selection. Prefer
exact `CharacterAngleView`, then minimum circular distance among known angle
views, then accepted base image. Ties sort by content hash. Raise
`ReferenceSelectionError` when no accepted reference exists.

- [ ] **Step 4: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_reference_select.py -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): select shot reference angles"
~~~

### Task 2: Atomic G1 activation and graph-path proof

**Files:**
- Modify: `skills/prompt-forge/runtime/profiles/camera-anima.json`
- Modify: `skills/prompt-forge/runtime/adapters/camera.py`
- Create: `skills/prompt-forge/runtime/tests/fixtures/camera-img2img-ui-minimal.json`
- Create: `skills/prompt-forge/runtime/tests/fixtures/camera-img2img-api-minimal.json`
- Create: `skills/prompt-forge/runtime/tests/test_camera_img2img.py`

**Interfaces:**
- Consumes: UI workflow, converted API graph, selected image filename, camera profile.
- Produces: `activate_g1(ui_workflow, image_name, profile) -> dict`, `verify_img2img_path(api_graph, profile) -> dict`.

- [ ] **Step 1: Write failing tests**

~~~python
import json
from pathlib import Path
import pytest
from runtime.adapters.camera import (
    CameraAdapterError, activate_g1, verify_img2img_path
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_complete_g1_group_is_activated():
    workflow = json.loads(
        (FIXTURES / "camera-img2img-ui-minimal.json").read_text(encoding="utf-8")
    )
    profile = {
        "img2img": {
            "group_id": 3,
            "node_ids": [21, 58, 57, 59],
            "load_image_node_id": 21,
        }
    }
    patched = activate_g1(workflow, "runs/lineage/ref.png", profile)
    nodes = {node["id"]: node for node in patched["nodes"]}
    assert {nodes[node_id]["mode"] for node_id in (21, 58, 57, 59)} == {0}
    assert nodes[21]["widgets_values"][0] == "runs/lineage/ref.png"


def test_partial_g1_profile_is_rejected():
    workflow = json.loads(
        (FIXTURES / "camera-img2img-ui-minimal.json").read_text(encoding="utf-8")
    )
    with pytest.raises(CameraAdapterError, match="complete G1"):
        activate_g1(workflow, "ref.png", {
            "img2img": {"group_id": 3, "node_ids": [21, 57, 59], "load_image_node_id": 21}
        })


def test_converted_graph_must_reach_sampler_latent():
    graph = json.loads(
        (FIXTURES / "camera-img2img-api-minimal.json").read_text(encoding="utf-8")
    )
    proof = verify_img2img_path(graph, {
        "img2img": {"vae_encode_node_id": 59, "sampler_node_id": 27}
    })
    assert proof["vae_encode_node_id"] == 59
    assert proof["sampler_node_id"] == 27
~~~

- [ ] **Step 2: Run RED**

Run the new test file. Expected: missing functions.

- [ ] **Step 3: Extend the profile**

Add:

~~~json
{
  "img2img": {
    "group_id": 3,
    "node_ids": [21, 58, 57, 59],
    "load_image_node_id": 21,
    "vae_encode_node_id": 59,
    "sampler_node_id": 27
  }
}
~~~

Also add allowlisted mutations for the four node modes and node 21 image. Profile
validation confirms that all four UI nodes lie inside group 3 and initially share
the same mode.

- [ ] **Step 4: Implement atomic activation**

Deep-copy the UI graph, resolve all four IDs, reject missing/extra group members,
set each mode to 0, patch node 21 image and prove no other node/group changed.

`verify_img2img_path` walks API graph link references from the sampler's latent
input backward until node 59 is found. Return the traversed node IDs. Reject an
empty, cyclic, missing or wrong-class path.

- [ ] **Step 5: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_camera_img2img.py skills/prompt-forge/runtime/tests/test_camera_adapter.py -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): activate the complete camera g1 path"
~~~

### Task 3: Stage 3 PromptBuild and ExecutionPlan

**Files:**
- Create: `skills/prompt-forge/runtime/stages.py`
- Create: `skills/prompt-forge/runtime/tests/test_stage3_plan.py`
- Modify: `skills/prompt-forge/runtime/runtime_cli.py`

**Interfaces:**
- Consumes: Stage 1 identity facts, Stage 2 artifacts, shot request, new PromptBuild.
- Produces: `build_shot_plan(...) -> dict` and CLI `plan-shot`.

- [ ] **Step 1: Write failing tests**

~~~python
import pytest
from runtime.stages import StageError, build_shot_plan


def test_stage1_prompt_build_cannot_be_reused_for_shot():
    with pytest.raises(StageError, match="new PromptBuild"):
        build_shot_plan(
            base_prompt_build_hash="same",
            shot_prompt_build_hash="same",
            reference={"artifact_type": "CharacterAngleView", "accepted": True, "content_hash": "ref"},
            desired_view="left_45",
            execution_approved=True,
        )


def test_shot_plan_records_reference_and_camera():
    result = build_shot_plan(
        base_prompt_build_hash="base",
        shot_prompt_build_hash="shot",
        reference={"artifact_type": "CharacterAngleView", "accepted": True, "content_hash": "ref"},
        desired_view="left_45",
        execution_approved=True,
    )
    assert result["stage"] == "shot-image"
    assert result["reference_hash"] == "ref"
    assert result["desired_view"] == "left_45"
~~~

- [ ] **Step 2: Run RED**

Run `test_stage3_plan.py`. Expected: import failure.

- [ ] **Step 3: Implement shot-plan invariants**

Require distinct PromptBuild hashes; ready Stage 3 Anima build; accepted reference;
locked identity facts; camera direction; current capability/fingerprint; G1 path
proof; local runtime and approval. Emit patches for positive, negative, camera,
reference image and all four G1 modes.

- [ ] **Step 4: Add CLI subcommands**

Add `select-reference`, `activate-g1`, `verify-img2img-path` and
`plan-shot`. Commands accept explicit JSON inputs and never discover or enqueue
implicitly.

- [ ] **Step 5: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_stage3_plan.py skills/prompt-forge/internals/tests -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): plan shot-specific img2img runs"
~~~

### Task 4: Live Experiment D and Slice 3 documentation

**Files:**
- Create: `skills/prompt-forge/runtime/tests/test_live_shot_img2img.py`
- Modify: `skills/prompt-forge/SKILL.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: accepted Stage 2 angle artifact and explicit execution approval.
- Produces: accepted `ShotImage` and Stage 3 RunRecord.

- [ ] **Step 1: Add the opt-in live test**

Use the common `PROMPT_FORGE_LIVE=1` skip gate. The test:

1. compiles a new shot PromptBuild with locked identity facts;
2. selects one accepted angle artifact;
3. loads the saved camera workflow;
4. activates G1 in UI format;
5. asks comfyui-mcp to strip/convert and validate;
6. verifies the VAE-to-sampler path;
7. patches prompt/camera values;
8. enqueues after approval;
9. asserts terminal success and a new decodable PNG;
10. records the reference hash and G1 proof.

- [ ] **Step 2: Update Skill and README**

Document that Stage 3 creates a new PromptBuild, selects an individual angle, and
enables the complete G1 group. Explicitly forbid feeding a contact sheet when an
individual angle exists and forbid partial G1 activation.

- [ ] **Step 3: Run deterministic verification**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
Remove-Item Env:PROMPT_FORGE_LIVE -ErrorAction SilentlyContinue
python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q
python skills/prompt-forge/internals/evaluate.py
git diff --check
~~~

- [ ] **Step 4: Run Experiment D after explicit approval**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
$env:PROMPT_FORGE_LIVE='1'
python -m pytest skills/prompt-forge/runtime/tests/test_live_shot_img2img.py -v
~~~

- [ ] **Step 5: Commit Slice 3**

~~~powershell
git add skills/prompt-forge README.md
git commit -m "feat(prompt-forge): complete shot img2img stage"
~~~

## Slice 3 Completion Gate

- Reference selection is deterministic and explained.
- Stage 3 uses a distinct PromptBuild.
- The entire G1 group is active and no unrelated group changes.
- Converted graph proves image latent reaches the intended sampler.
- Experiment D emits a traceable ShotImage.
- Slice 4 starts only after review.
