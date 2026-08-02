# Prompt Forge v7 Slice 2 Multi-Angle Character References Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Feed the accepted Stage 1 image into both Flux2-Klein base-image buses and emit normalized, traceable multi-angle character references.

**Architecture:** Reuse Slice 1 contracts, profile validation, execution planning and RunRecord. Add a Flux-specific profile/adapter that changes exactly two synchronized `LoadImage` inputs and leaves pose references, per-view prompts, model and LoRAs immutable. Normalize outputs into contact-sheet and angle-view artifacts without judging aesthetics in the graph patcher.

**Tech Stack:** Python 3.11+ standard library, pytest, ComfyUI REST, comfyui-mcp workflow strip/validate/enqueue.

## Global Constraints

- Slice 1 completion gate and interfaces are required.
- Input is one accepted `CharacterBaseImage` with content hash.
- Patch nodes 111 and 667 together for the verified fingerprint.
- FLUX negative prompts are never injected.
- Pose-reference images and per-view CR Text nodes remain immutable.
- Never mutate the saved workflow.
- Runtime must be local-only and explicitly approved.
- Default tests never enqueue; live Experiment C requires `PROMPT_FORGE_LIVE=1`.

---

## File Structure

- Create `skills/prompt-forge/runtime/profiles/flux2-klein-multiview.json`.
- Create `skills/prompt-forge/runtime/adapters/flux_multiview.py`.
- Create `skills/prompt-forge/runtime/artifacts.py`.
- Create `skills/prompt-forge/runtime/tests/fixtures/flux-api-minimal.json`.
- Create `skills/prompt-forge/runtime/tests/test_flux_multiview.py`.
- Create `skills/prompt-forge/runtime/tests/test_artifacts.py`.
- Create `skills/prompt-forge/runtime/tests/test_live_multiview.py`.
- Modify `skills/prompt-forge/runtime/runtime_cli.py`.
- Modify `skills/prompt-forge/SKILL.md`.
- Modify `README.md`.

### Task 1: Verified Flux profile and synchronized dual-input adapter

**Files:**
- Create: `skills/prompt-forge/runtime/profiles/flux2-klein-multiview.json`
- Create: `skills/prompt-forge/runtime/adapters/flux_multiview.py`
- Create: `skills/prompt-forge/runtime/tests/fixtures/flux-api-minimal.json`
- Create: `skills/prompt-forge/runtime/tests/test_flux_multiview.py`

**Interfaces:**
- Consumes: API graph, accepted image filename/hash, resolved `base_image_primary` and `base_image_secondary` slots.
- Produces: `patch_base_images(graph, image_name, slots) -> dict`, `assert_dual_input_sync(graph, slots) -> None`.

- [ ] **Step 1: Write failing tests**

~~~python
import json
from pathlib import Path
import pytest
from runtime.adapters.flux_multiview import (
    FluxAdapterError, assert_dual_input_sync, patch_base_images
)

FIXTURE = Path(__file__).parent / "fixtures" / "flux-api-minimal.json"


def test_both_flux_inputs_receive_the_same_image():
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    patched = patch_base_images(
        graph, "runs/abc/base-deadbeef.png",
        {"base_image_primary": 111, "base_image_secondary": 667},
    )
    assert patched["111"]["inputs"]["image"] == "runs/abc/base-deadbeef.png"
    assert patched["667"]["inputs"]["image"] == "runs/abc/base-deadbeef.png"
    assert_dual_input_sync(
        patched, {"base_image_primary": 111, "base_image_secondary": 667}
    )


def test_one_sided_patch_is_rejected():
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    graph["111"]["inputs"]["image"] = "a.png"
    graph["667"]["inputs"]["image"] = "b.png"
    with pytest.raises(FluxAdapterError, match="same image"):
        assert_dual_input_sync(
            graph, {"base_image_primary": 111, "base_image_secondary": 667}
        )


def test_pose_images_are_not_changed():
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    patched = patch_base_images(
        graph, "base.png", {"base_image_primary": 111, "base_image_secondary": 667}
    )
    assert patched["368"] == graph["368"]
~~~

- [ ] **Step 2: Run RED**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_flux_multiview.py -q
~~~

Expected: import failure.

- [ ] **Step 3: Implement the adapter**

~~~python
import copy


class FluxAdapterError(ValueError):
    pass


def _node(graph, node_id):
    key = str(node_id)
    node = graph.get(key)
    if not isinstance(node, dict) or node.get("class_type") != "LoadImage":
        raise FluxAdapterError(f"Flux slot {node_id} must resolve to LoadImage")
    return node


def assert_dual_input_sync(graph, slots):
    first = _node(graph, slots["base_image_primary"])["inputs"].get("image")
    second = _node(graph, slots["base_image_secondary"])["inputs"].get("image")
    if not first or first != second:
        raise FluxAdapterError("Flux base-image slots must contain the same image")


def patch_base_images(graph, image_name, slots):
    if not isinstance(image_name, str) or not image_name.strip():
        raise FluxAdapterError("image_name must be non-empty")
    patched = copy.deepcopy(graph)
    _node(patched, slots["base_image_primary"])["inputs"]["image"] = image_name
    _node(patched, slots["base_image_secondary"])["inputs"]["image"] = image_name
    assert_dual_input_sync(patched, slots)
    return patched
~~~

After patching, compare every node except 111/667 `inputs.image` with the source
graph and raise on any other mutation.

- [ ] **Step 4: Add the profile**

~~~json
{
  "schema_version": "1.0",
  "profile_id": "flux2-klein-multiview-v1",
  "workflow_name": "Flux2-Klein人物一键多视图工作流.json",
  "generation_modes": ["image-to-image"],
  "runtime_classification": "local",
  "slots": {
    "base_image_primary": {"id": 111, "type": "LoadImage"},
    "base_image_secondary": {"id": 667, "type": "LoadImage"}
  },
  "allowed_mutations": [
    "base_image_primary.image",
    "base_image_secondary.image"
  ],
  "immutable_node_ids": [368, 151, 152, 154, 360, 364, 148, 149, 147, 373, 150, 367],
  "output_nodes": {
    "524": {"artifact_type": "CharacterAngleView", "view_label": "front_closeup"},
    "663": {"artifact_type": "CharacterAngleView", "view_label": "front"},
    "761": {"artifact_type": "CharacterAngleView", "view_label": "right_45"},
    "565": {"artifact_type": "CharacterAngleView", "view_label": "side_unknown"},
    "609": {"artifact_type": "CharacterAngleView", "view_label": "side_unknown"},
    "224": {"artifact_type": "CharacterSheet", "view_label": "sheet"},
    "338": {"artifact_type": "CharacterSheet", "view_label": "sheet"},
    "201": {"artifact_type": "CharacterSheet", "view_label": "sheet"}
  },
  "expected_outputs": ["image/png"]
}
~~~

Profile loading must still verify node type/title and the current structural
fingerprint; IDs alone are insufficient.

- [ ] **Step 5: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_flux_multiview.py skills/prompt-forge/runtime/tests/test_workflow_profile.py -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): patch flux multiview inputs safely"
~~~

### Task 2: Normalize character-sheet and angle artifacts

**Files:**
- Create: `skills/prompt-forge/runtime/artifacts.py`
- Create: `skills/prompt-forge/runtime/tests/test_artifacts.py`

**Interfaces:**
- Consumes: ComfyUI history output entries, profile output-node map and Stage 1 lineage.
- Produces: `normalize_image_outputs(outputs, output_nodes, lineage_id, source_hash) -> list[dict]`.

- [ ] **Step 1: Write failing tests**

~~~python
from runtime.artifacts import normalize_image_outputs


def test_outputs_are_normalized_and_deduplicated():
    outputs = {
        "524": {"images": [
            {"filename": "face_00005_.png", "subfolder": "", "type": "output"}
        ]},
        "224": {"images": [
            {"filename": "sheet_00005_.png", "subfolder": "", "type": "output"},
            {"filename": "face_00005_.png", "subfolder": "", "type": "output"},
        ]},
    }
    output_nodes = {
        "524": {"artifact_type": "CharacterAngleView", "view_label": "front_closeup"},
        "224": {"artifact_type": "CharacterSheet", "view_label": "sheet"},
    }
    result = normalize_image_outputs(outputs, output_nodes, "lineage-1", "basehash")
    assert [item["filename"] for item in result] == [
        "face_00005_.png", "sheet_00005_.png"
    ]
    assert result[0]["view_label"] == "front_closeup"
    assert result[1]["view_label"] == "sheet"
    assert all(item["lineage_id"] == "lineage-1" for item in result)
    assert all(item["source_artifact_hash"] == "basehash" for item in result)
~~~

- [ ] **Step 2: Run RED**

Run `test_artifacts.py`. Expected: import failure.

- [ ] **Step 3: Implement normalization**

Flatten only `images` lists from profile-declared output node IDs. Require
filename/subfolder/type strings, reject absolute paths and `..`, deduplicate by
`(type, subfolder, filename)`, and copy `artifact_type` plus `view_label` from
the verified profile. Undeclared preview/output nodes are retained only as
`DiagnosticImage` and are never eligible for Stage 3 reference selection. Store
the source base-image hash and lineage ID on every artifact. Do not infer view
direction from an arbitrary filename.

- [ ] **Step 4: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_artifacts.py -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): normalize multiview artifacts"
~~~

### Task 3: Stage 2 planning, CLI and live Experiment C

**Files:**
- Modify: `skills/prompt-forge/runtime/execution.py`
- Modify: `skills/prompt-forge/runtime/runtime_cli.py`
- Create: `skills/prompt-forge/runtime/tests/test_stage2_plan.py`
- Create: `skills/prompt-forge/runtime/tests/test_live_multiview.py`
- Modify: `skills/prompt-forge/SKILL.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: accepted Stage 1 RunRecord and artifact, Flux profile/API graph.
- Produces: Stage 2 ExecutionPlan, Flux graph, Stage 2 RunRecord and artifacts.

- [ ] **Step 1: Write a failing lineage test**

~~~python
import pytest
from runtime.execution import ExecutionError, build_multiview_plan


def test_multiview_plan_requires_accepted_base_artifact():
    artifact = {
        "artifact_type": "CharacterBaseImage",
        "content_hash": "abc",
        "accepted": False,
        "lineage_id": "lineage-1",
    }
    with pytest.raises(ExecutionError, match="accepted"):
        build_multiview_plan(artifact, "flux2-klein-multiview-v1", "wfhash", True)
~~~

- [ ] **Step 2: Implement the plan builder**

Require `artifact_type=CharacterBaseImage`, `accepted=true`, non-empty content
hash and lineage ID, current capability report, local preflight, matching
fingerprint and explicit approval. Emit exactly two image patches with the same
uploaded filename and source hash.

- [ ] **Step 3: Add CLI and Skill steps**

Add `plan-multiview` and `patch-flux` subcommands. The Skill must:

1. upload the Stage 1 PNG under a lineage-specific content-derived name;
2. load/strip/validate the named Flux workflow through comfyui-mcp;
3. verify profile/fingerprint;
4. patch both image slots;
5. show the ExecutionPlan;
6. enqueue only after approval;
7. normalize artifacts and record the run.

- [ ] **Step 4: Add opt-in Experiment C**

Use the proven Flux workflow graph. Change one logical variable: both base-image
slots now reference the Stage 1 artifact. Assert:

- both API inputs match;
- pose-image nodes retain their original values;
- terminal history status is success;
- at least one normalized image artifact exists;
- every artifact carries the Stage 1 hash and lineage ID.

- [ ] **Step 5: Run deterministic verification**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
Remove-Item Env:PROMPT_FORGE_LIVE -ErrorAction SilentlyContinue
python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q
python skills/prompt-forge/internals/evaluate.py
git diff --check
~~~

- [ ] **Step 6: Run Experiment C after explicit approval**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
$env:PROMPT_FORGE_LIVE='1'
python -m pytest skills/prompt-forge/runtime/tests/test_live_multiview.py -v
~~~

- [ ] **Step 7: Commit Slice 2**

~~~powershell
git add skills/prompt-forge README.md
git commit -m "feat(prompt-forge): complete flux multiview stage"
~~~

## Slice 2 Completion Gate

- Both Flux base-image inputs use the accepted Stage 1 artifact.
- Pose references and view prompts are unchanged.
- Experiment C produces traceable image outputs.
- No negative prompt is injected into FLUX.
- Slice 3 starts only after review of this commit.
