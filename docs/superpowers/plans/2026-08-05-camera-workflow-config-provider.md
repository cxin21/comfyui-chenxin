# Camera Workflow Config Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace complete-workflow-per-request camera generation with a versioned UI/API workflow pack, bounded configuration projection, atomic LoRA configuration, and a provider boundary ready for a future local service.

**Architecture:** A maintenance-only synchronizer imports the current ComfyUI workflow into a versioned `camera-anima-v1` pack containing UI and API graphs plus manifest/config metadata. Normal execution uses an in-process `CameraWorkflowProvider`; the provider exposes only workflow metadata, config projections, validated patches, LoRA recommendations, execution receipts, and submission results. The same provider protocol will later be implemented by a local service without changing agent-facing schemas.

**Tech Stack:** Python 3, pytest, JSON workflow packs, existing ComfyUI REST transport, negotiated MCP calls for local-model inventory, SHA-256 content hashes, existing approval/consumption/history/RunRecord contracts.

## Global Constraints

- Normal camera generation must not call ComfyUI `get_workflow` or expose a complete UI/API graph.
- Full workflow reads are allowed only in explicit `sync-workflow-pack`, `refresh-workflow-pack`, and `verify-workflow-pack` maintenance operations.
- This is a new boundary; do not preserve legacy complete-graph caller APIs or legacy fallback behavior.
- UI and API workflow files must both be bundled; UI is for semantic projection/evidence and API is for execution.
- Only fields declared by `config-surface.json` may be read or patched.
- LoRA Loader and TriggerWord Toggle are one atomic configuration unit.
- Recommendation is not selection, selection is not approval, and approval is required before execution.
- Revision mismatch, hash drift, invalid inventory, partial atomic patch, group topology violation, uncertain enqueue, history mismatch, and artifact mismatch fail closed.
- Existing user changes in the worktree belong to the user; do not revert or overwrite unrelated edits.
- Do not create a Git commit or push without explicit user authorization.

---

## File map and ownership

Create the following focused runtime modules:

- `skills/character-video-pipeline/runtime/workflow_pack.py`: pack schema, safe loading, manifest/hash validation, and workflow-id resolution.
- `skills/character-video-pipeline/runtime/config_projection.py`: bounded config reads and optimistic-concurrency patch validation.
- `skills/character-video-pipeline/runtime/providers.py`: `CameraWorkflowProvider` protocol and in-process provider implementation.
- `skills/character-video-pipeline/runtime/workflow_pack_sync.py`: explicit full-graph synchronization and verification commands.
- `skills/character-video-pipeline/runtime/tests/test_workflow_pack.py`.
- `skills/character-video-pipeline/runtime/tests/test_config_projection.py`.
- `skills/character-video-pipeline/runtime/tests/test_provider_contract.py`.
- `skills/character-video-pipeline/runtime/tests/test_workflow_pack_sync.py`.

Modify the following existing modules only where their public boundary changes:

- `skills/character-video-pipeline/runtime/runtime_cli.py`: add pack/config/provider commands and remove legacy complete-graph normal-path inputs.
- `skills/character-video-pipeline/runtime/stage_execution.py`: accept provider-generated execution evidence instead of caller-supplied graphs.
- `skills/character-video-pipeline/runtime/execution.py`: bind approval, consumption, submission, history, and RunRecord lineage to pack/config/executable hashes.
- `skills/character-video-pipeline/runtime/config_surface.py`: move canonical surface validation/projection primitives into the new boundary or make it a focused dependency of `config_projection.py`; do not keep duplicate schemas.
- `skills/character-video-pipeline/runtime/lora_discovery.py`: expose provider-facing inventory/recommendation results with current inventory hashes.
- `skills/character-video-pipeline/runtime/adapters/camera.py`: expose pack-bound patch adapters and reject graph ownership outside the manifest.
- `skills/character-video-pipeline/runtime/adapters/lora_unit.py`: enforce atomic loader/toggle patching through the provider.
- `skills/character-video-pipeline/runtime/tests/test_stage_execution.py`, `test_execution.py`, `test_runtime_cli.py`, `test_config_surface.py`, `test_lora_unit.py`: update tests to the new boundary, not compatibility shims.
- `docs/USAGE.md`: document the new high-level workflow operations.
- `skills/character-video-pipeline/SKILL.md`: state that normal execution consumes a bundled workflow pack and that full sync is maintenance-only.

Add the first fixed asset pack under:

- `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/pack.json`
- `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/ui-workflow.json`
- `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/api-workflow.json`
- `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/manifest.json`
- `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/config-surface.json`

The pack source and synchronization evidence must be retained in the run or
maintenance evidence directory, not embedded in agent-facing responses.

---

### Task 1: Establish the fixed workflow-pack contract

**Files:**
- Create: `skills/character-video-pipeline/runtime/workflow_pack.py`
- Create: `skills/character-video-pipeline/runtime/tests/test_workflow_pack.py`
- Create: `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/pack.json`
- Create: `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/ui-workflow.json`
- Create: `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/api-workflow.json`
- Create: `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/manifest.json`
- Create: `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/config-surface.json`

**Interfaces:**
- Produces `WorkflowPack`, `WorkflowManifest`, `load_workflow_pack(workflow_id: str) -> WorkflowPack`, and `workflow_pack_info(workflow_id: str) -> dict`.
- `WorkflowPack` exposes validated `ui_workflow`, `api_workflow`, `manifest`, and `config_surface` only to runtime code; provider responses must use bounded metadata.

- [ ] **Step 1: Write failing tests for pack resolution and bounded metadata.**

```python
def test_load_pack_validates_all_hashes():
    pack = load_workflow_pack("camera-anima-v1")
    assert pack.manifest["workflow_id"] == "camera-anima-v1"
    assert pack.manifest["api_graph_hash"] == content_hash(pack.api_workflow)

def test_workflow_info_does_not_include_graphs():
    info = workflow_pack_info("camera-anima-v1")
    assert "ui_workflow" not in info
    assert "api_workflow" not in info
    assert info["workflow_id"] == "camera-anima-v1"

def test_pack_hash_drift_fails_closed(tmp_path):
    with pytest.raises(WorkflowPackError, match="hash"):
        load_workflow_pack_from_root(tmp_path)
```

- [ ] **Step 2: Run the focused tests and verify they fail because the pack loader is absent.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_workflow_pack.py -q`

Expected: FAIL with import or missing-contract errors.

- [ ] **Step 3: Implement safe pack loading.**

Validate exact pack keys, safe relative asset paths, JSON object types, SHA-256 lowercase hashes, workflow ID consistency, config-surface hash, API graph hash, and immutable topology hash. Never accept a path supplied by the caller as a workflow asset path.

- [ ] **Step 4: Run the focused tests and verify they pass.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_workflow_pack.py -q`

Expected: PASS.

---

### Task 2: Add explicit workflow-pack synchronization

**Files:**
- Create: `skills/character-video-pipeline/runtime/workflow_pack_sync.py`
- Create: `skills/character-video-pipeline/runtime/tests/test_workflow_pack_sync.py`
- Modify: `skills/character-video-pipeline/runtime/workflow_discovery.py`
- Modify: `skills/character-video-pipeline/runtime/runtime_cli.py`

**Interfaces:**
- Produces `sync_workflow_pack(workflow_tools: dict, workflow_name: str, destination: Path, profile: dict) -> dict`.
- Adds CLI commands `sync-workflow-pack`, `refresh-workflow-pack`, and `verify-workflow-pack`.
- `workflow_discovery` full reads remain callable only by these maintenance commands.

- [ ] **Step 1: Write failing tests proving full reads occur only through maintenance commands.**

```python
def test_sync_reads_ui_api_and_strip_once_and_writes_pack(recording_tools, tmp_path):
    result = sync_workflow_pack(recording_tools, "camera.json", tmp_path, PROFILE)
    assert result["workflow_id"] == "camera-anima-v1"
    assert recording_tools.calls.count(("get_workflow", "ui")) == 1
    assert recording_tools.calls.count(("get_workflow", "api")) == 1

def test_verify_rejects_changed_source_graph(recording_tools, tmp_path):
    sync_workflow_pack(recording_tools, "camera.json", tmp_path, PROFILE)
    recording_tools.api_graph["999"] = {"class_type": "Unexpected", "inputs": {}}
    with pytest.raises(WorkflowPackSyncError, match="immutable topology"):
        verify_workflow_pack(recording_tools, tmp_path / "camera-anima-v1")
```

- [ ] **Step 2: Run the tests and verify they fail.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_workflow_pack_sync.py -q`

Expected: FAIL because synchronization and maintenance commands do not exist.

- [ ] **Step 3: Implement synchronization using the existing discovery/normalization evidence.**

Write UI and API files, derive `manifest.json` and `config-surface.json`, record source fingerprints and conversion hashes, and refuse to overwrite an existing pack version with different content. A refresh creates a new explicit pack version or fails; it never mutates the active pack silently.

- [ ] **Step 4: Add CLI dispatch and assert normal commands cannot invoke sync.**

Normal `get-config`, `patch-config`, `plan-camera`, and `submit-camera` commands must resolve only the bundled pack. Do not add an automatic “if pack missing, sync now” fallback.

- [ ] **Step 5: Run the focused tests.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_workflow_pack_sync.py skills/character-video-pipeline/runtime/tests/test_workflow_pack.py -q`

Expected: PASS.

---

### Task 3: Implement bounded configuration projection and patching

**Files:**
- Create: `skills/character-video-pipeline/runtime/config_projection.py`
- Create: `skills/character-video-pipeline/runtime/tests/test_config_projection.py`
- Modify: `skills/character-video-pipeline/runtime/config_surface.py`
- Modify: `skills/character-video-pipeline/runtime/adapters/camera.py`

**Interfaces:**
- Produces `read_config(pack: WorkflowPack, fields: list[str] | None = None) -> dict`.
- Produces `apply_config_patch(pack: WorkflowPack, request: dict, inventory: dict | None) -> ConfigPatchResult`.
- `ConfigPatchResult` contains `config`, `config_hash`, `revision`, `changed_fields`, and `patch_evidence`, never a complete graph in its public serialization.

- [ ] **Step 1: Write failing tests for field allowlists and revision control.**

```python
def test_read_config_returns_only_declared_projection(pack):
    result = read_config(pack, ["prompts", "camera"])
    assert set(result["config"]) == {"prompts", "camera"}
    assert "nodes" not in result

def test_unknown_patch_field_is_rejected(pack):
    with pytest.raises(ConfigProjectionError, match="config surface"):
        apply_config_patch(pack, {"expected_revision": pack.revision,
                                  "patch": {"nodes.24.inputs": {}}}, None)

def test_revision_mismatch_never_overwrites(pack):
    with pytest.raises(ConfigProjectionError, match="revision"):
        apply_config_patch(pack, {"expected_revision": "stale",
                                  "patch": {"camera.direction": "front"}}, None)
```

- [ ] **Step 2: Run the focused tests and verify they fail.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_config_projection.py -q`

Expected: FAIL because projection and patch contracts are absent.

- [ ] **Step 3: Implement projection from manifest bindings and config-surface declarations.**

Support prompts, reference image, camera, camera extra, G1/G2 high-level group state, and structured LoRA state. Do not expose arbitrary widget values or links.

- [ ] **Step 4: Implement patch validation and immutable result construction.**

Validate types, enum/range values, stage conditions, field ownership, revision, and cross-field rules. Apply patches to private UI/API copies only through adapters, calculate `config_hash`, and return a bounded result.

- [ ] **Step 5: Run the focused tests.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_config_projection.py skills/character-video-pipeline/runtime/tests/test_config_surface.py skills/character-video-pipeline/runtime/tests/test_camera_adapter.py -q`

Expected: PASS.

---

### Task 4: Enforce atomic LoRA discovery, recommendation, and patching

**Files:**
- Modify: `skills/character-video-pipeline/runtime/lora_discovery.py`
- Modify: `skills/character-video-pipeline/runtime/adapters/lora_unit.py`
- Modify: `skills/character-video-pipeline/runtime/config_projection.py`
- Create or modify: `skills/character-video-pipeline/runtime/tests/test_lora_provider.py`
- Modify: `skills/character-video-pipeline/runtime/tests/test_lora_discovery.py`
- Modify: `skills/character-video-pipeline/runtime/tests/test_lora_unit.py`

**Interfaces:**
- `list_lora_inventory(provider_context: dict) -> dict` returns canonical candidates and `inventory_hash`.
- `recommend_loras(inventory: dict, base_model: str, intent: dict) -> dict` returns deterministic recommendations and `recommendation_hash`.
- `patch_lora_unit(api_graph: dict, ui_workflow: dict, selection: dict, manifest: dict) -> PatchResult` patches nodes 26 and 66 together.

- [ ] **Step 1: Write failing tests for compatibility, determinism, and atomicity.**

```python
def test_recommendation_rejects_non_anima_lora(inventory):
    result = recommend_loras(inventory, "miaomiaoHarem_anima15.safetensors", {})
    assert all(item["compatible"] for item in result["recommendations"])
    assert not any(item["name"].startswith("FLux/") for item in result["recommendations"])

def test_loader_and_trigger_toggle_are_one_patch(unit_graphs, selection):
    result = patch_lora_unit(*unit_graphs, selection, MANIFEST)
    assert result.changed_nodes == {26, 66}
    assert result.trigger_words == render_active_trigger_words(selection)

def test_inactive_lora_contributes_no_trigger_word(unit_graphs, selection):
    selection["selections"][0]["active"] = False
    result = patch_lora_unit(*unit_graphs, selection, MANIFEST)
    assert result.trigger_words == []
```

- [ ] **Step 2: Run tests and verify they fail.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_lora_provider.py skills/character-video-pipeline/runtime/tests/test_lora_discovery.py skills/character-video-pipeline/runtime/tests/test_lora_unit.py -q`

Expected: FAIL on missing provider-facing inventory and atomic patch behavior.

- [ ] **Step 3: Implement canonical inventory and deterministic recommendation.**

Use MCP `list_local_models`, bind the inventory hash to the stage config, apply metadata/family/filename compatibility precedence, and return recommendation data without mutating a workflow.

- [ ] **Step 4: Implement atomic two-node patching.**

Derive loader stack text and TriggerWord Toggle table/text from structured selections. Roll back private graph copies if either node cannot be patched or any invariant fails.

- [ ] **Step 5: Run the focused tests.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_lora_provider.py skills/character-video-pipeline/runtime/tests/test_lora_discovery.py skills/character-video-pipeline/runtime/tests/test_lora_unit.py -q`

Expected: PASS.

---

### Task 5: Add the provider and contract-test the future service boundary

**Files:**
- Create: `skills/character-video-pipeline/runtime/providers.py`
- Create: `skills/character-video-pipeline/runtime/tests/test_provider_contract.py`
- Modify: `skills/character-video-pipeline/runtime/local_orchestrator.py`

**Interfaces:**
- `CameraWorkflowProvider` is the stable protocol from the spec.
- `InProcessCameraWorkflowProvider` consumes `WorkflowPack`, `config_projection`, LoRA services, and the existing local REST transport.
- Provider methods return only bounded JSON-compatible objects.

- [ ] **Step 1: Write a provider contract fixture and failing tests.**

```python
def test_provider_contract_never_returns_complete_graph(provider):
    info = provider.get_workflow_info("camera-anima-v1")
    config = provider.get_config("camera-anima-v1", ["prompts", "camera"])
    assert "api_workflow" not in info
    assert "ui_workflow" not in config

def test_provider_build_execution_returns_hashes_not_graph(provider, config):
    result = provider.build_execution("camera-anima-v1", config)
    assert result["executable_graph_hash"]
    assert "api_graph" not in result
```

- [ ] **Step 2: Run the contract tests and verify they fail.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_provider_contract.py -q`

Expected: FAIL because the provider protocol and in-process implementation are absent.

- [ ] **Step 3: Implement the in-process provider.**

Resolve only fixed pack IDs, call projection and LoRA operations, build private execution graphs, enforce allowlisted diffs, and return hashes/evidence. Keep ComfyUI enqueue behind the existing approval/consumption boundary.

- [ ] **Step 4: Run contract tests and existing transport tests.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_provider_contract.py skills/character-video-pipeline/runtime/tests/test_local_orchestrator.py skills/character-video-pipeline/runtime/tests/test_comfy_submit.py -q`

Expected: PASS.

---

### Task 6: Replace normal CLI and stage boundaries with provider operations

**Files:**
- Modify: `skills/character-video-pipeline/runtime/runtime_cli.py`
- Modify: `skills/character-video-pipeline/runtime/stage_execution.py`
- Modify: `skills/character-video-pipeline/runtime/execution.py`
- Modify: `skills/character-video-pipeline/runtime/tests/test_runtime_cli.py`
- Modify: `skills/character-video-pipeline/runtime/tests/test_stage_execution.py`
- Modify: `skills/character-video-pipeline/runtime/tests/test_execution.py`

**Interfaces:**
- Add `workflow-info`, `get-config`, `patch-config`, `list-loras`, `recommend-loras`, `plan-camera`, `build-camera-execution`, and `submit-camera` commands.
- Normal command payloads use `workflow_id`, config projections, provider evidence, and approval/consumption records; they do not accept `source_api_graph` or `ui_workflow`.
- Drafts bind `workflow_pack_hash`, `config_hash`, `lora_inventory_hash`, `lora_recommendation_hash`, and `executable_graph_hash`.

- [ ] **Step 1: Write failing CLI and stage tests for the new payload boundary.**

```python
def test_plan_camera_rejects_complete_graph_payload():
    with pytest.raises(CliUsageError, match="source_api_graph"):
        dispatch("plan-camera", {"workflow_id": "camera-anima-v1",
                                  "source_api_graph": {}})

def test_camera_draft_contains_pack_and_config_lineage(provider, config):
    draft = build_camera_draft(provider, "camera-anima-v1", config)
    assert draft["workflow_pack_hash"]
    assert draft["config_hash"] == config["config_hash"]
```

- [ ] **Step 2: Run focused tests and verify they fail.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_runtime_cli.py skills/character-video-pipeline/runtime/tests/test_stage_execution.py skills/character-video-pipeline/runtime/tests/test_execution.py -q`

Expected: FAIL because normal commands still require complete graph inputs.

- [ ] **Step 3: Implement the new CLI dispatch and provider-backed planning.**

Remove the legacy normal-path graph payloads rather than accepting both forms. Keep maintenance sync commands as the only full-read entry point.

- [ ] **Step 4: Bind approval and consumption to provider-generated execution evidence.**

Approval summaries show business-level changed fields and hashes. Submission reconstructs the private execution graph from the fixed pack and validates the exact executable hash before enqueue.

- [ ] **Step 5: Run focused tests.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_runtime_cli.py skills/character-video-pipeline/runtime/tests/test_stage_execution.py skills/character-video-pipeline/runtime/tests/test_execution.py -q`

Expected: PASS.

---

### Task 7: Preserve history, artifact, and retry safety under the new hashes

**Files:**
- Modify: `skills/character-video-pipeline/runtime/execution.py`
- Modify: `skills/character-video-pipeline/runtime/stage_execution.py`
- Modify: `skills/character-video-pipeline/runtime/local_orchestrator.py`
- Create or modify: `skills/character-video-pipeline/runtime/tests/test_provider_execution_lineage.py`

**Interfaces:**
- Submission evidence binds `workflow_pack_hash`, `config_hash`, `executable_graph_hash`, `request_hash`, approval ID, consumption ID, and prompt ID.
- Existing enqueue intent remains the single retry/idempotency guard.

- [ ] **Step 1: Write failing lineage and uncertain-enqueue tests.**

```python
def test_history_graph_hash_mismatch_fails_closed(submission, history):
    history["prompt"][2]["999"] = {"class_type": "Unexpected", "inputs": {}}
    with pytest.raises(ExecutionError, match="graph"):
        record_camera_execution(submission, history)

def test_uncertain_enqueue_reuses_retained_intent(submission, temp_run_dir):
    first = submit_camera(submission, failing_after_post=True, run_dir=temp_run_dir)
    second = submit_camera(submission, failing_after_post=True, run_dir=temp_run_dir)
    assert first["intent_hash"] == second["intent_hash"]
```

- [ ] **Step 2: Run tests and verify they fail.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_provider_execution_lineage.py -q`

Expected: FAIL because lineage is still graph-caller oriented.

- [ ] **Step 3: Implement hash/evidence validation and bounded retry policy.**

Reject stale pack/config/inventory evidence, retain enqueue intent before POST, resolve uncertain POSTs through server state, and never blindly re-enqueue.

- [ ] **Step 4: Run focused and existing execution tests.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_provider_execution_lineage.py skills/character-video-pipeline/runtime/tests/test_errors.py skills/character-video-pipeline/runtime/tests/test_artifacts.py -q`

Expected: PASS.

---

### Task 8: Update skill documentation and acceptance tests

**Files:**
- Modify: `skills/character-video-pipeline/SKILL.md`
- Modify: `docs/USAGE.md`
- Create: `skills/character-video-pipeline/runtime/tests/test_no_legacy_camera_boundary.py`
- Modify: `application-inventory.md` if the ownership wording needs the new pack/provider boundary.

- [ ] **Step 1: Write failing boundary tests.**

```python
def test_normal_camera_path_has_no_complete_graph_input():
    source = Path("skills/character-video-pipeline/runtime/runtime_cli.py").read_text()
    assert 'source_api_graph' not in normal_camera_command_source(source)

def test_skill_documents_maintenance_only_full_sync():
    skill = Path("skills/character-video-pipeline/SKILL.md").read_text()
    assert "maintenance" in skill
    assert "workflow pack" in skill
```

- [ ] **Step 2: Run the boundary tests and verify they fail.**

Run: `pytest skills/character-video-pipeline/runtime/tests/test_no_legacy_camera_boundary.py -q`

Expected: FAIL until documentation and normal-path source boundaries are updated.

- [ ] **Step 3: Update documentation and remove obsolete legacy wording.**

Document the fixed UI/API pack, bounded config operations, LoRA recommendation approval, provider boundary, maintenance-only synchronization, and fail-closed behavior. Do not document compatibility aliases.

- [ ] **Step 4: Run the complete runtime test suite.**

Run: `pytest skills/character-video-pipeline/runtime/tests -q`

Expected: PASS with no tests asserting the old normal-path complete-graph API.

---

### Task 9: Perform live pack synchronization and verification

**Files:**
- Create or update: `skills/character-video-pipeline/runtime/workflow_packs/camera-anima-v1/*`
- Create: a maintenance evidence record under the designated local evidence directory.

- [ ] **Step 1: Confirm ComfyUI endpoint and the exact source workflow name.**

Use the maintenance command with the local ComfyUI endpoint and the explicitly selected `文生图相机视角.json`; do not enumerate and import every workflow.

- [ ] **Step 2: Run `sync-workflow-pack` once.**

Expected: UI graph, API graph, manifest, and config surface are written with hashes and conversion evidence.

- [ ] **Step 3: Run `verify-workflow-pack`.**

Expected: PASS for UI fingerprint, API hash, topology hash, config-surface hash, required bindings, camera path, group membership, and LoRA unit binding.

- [ ] **Step 4: Run a dry-run normal camera flow.**

Expected: workflow info/config/LoRA/recommendation/patch/planning calls use only the pack and MCP inventory; no current-workflow full read is observed.

---

## Final verification

Run the full test suite:

```bash
pytest skills/character-video-pipeline/runtime/tests -q
```

Then run the maintenance and dry-run acceptance checks from Task 9. Report
separately any pre-existing failures, implementation regressions, and local
environment limitations. Do not claim completion without evidence for the
normal-path no-full-read requirement and the LoRA Loader/TriggerWord Toggle
atomicity requirement.

## Handoff

After the plan is approved, execute it with either
`superpowers:subagent-driven-development` or `superpowers:executing-plans`.
Do not begin implementation from this document without selecting one of those
execution modes and without preserving the explicit no-commit-without-user-
authorization constraint.
