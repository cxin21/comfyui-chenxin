---
name: character-video-pipeline
description: Approval-gated four-stage ComfyUI production consumer for PromptPackage outputs
status: active
side_effects: approval-gated-local-comfyui
owner: character-video-pipeline
---

# Character Video Pipeline

This is the only skill allowed to cross the local ComfyUI and MCP boundary. It consumes a validated PromptPackage from Prompt Forge and turns approved prompt packages and user-approved assets into production artifacts.

## Quick start (mandatory first action)

Before any prompt authoring, file write, or capability probe, run the zero-dependency environment checker:

    powershell -ExecutionPolicy Bypass -File skills/character-video-pipeline/preflight-env.ps1

This checks cache integrity, Python availability, ComfyUI reachability, and delegates to the runtime preflight. A blocker means STOP -- do not attempt workarounds, do not rewrite tools in another language, do not bypass the gate.

If `preflight-env.ps1` itself is missing, the plugin cache is severely stale. Re-run `scripts/install.ps1` to sync.

## Environment prerequisites

- **Python 3.10+** -- must be on PATH or at a common location (ComfyUI embedded Python is auto-detected by `preflight-env.ps1`)
- **ComfyUI** -- running at http://127.0.0.1:8188 (override with `-ComfyUrl`)
- **MCP tools** -- `check_workflow_runtime`, `get_workflow`, `strip_workflow`, `validate_workflow`, `list_local_models` must be loaded in the host session
- **Plugin cache** -- must be in sync with the project source (verified by `preflight-env.ps1`)

## Degradation paths

- **Python not found** -- Stop. Install Python 3.10+ or ensure ComfyUI's embedded Python is accessible. Do not rewrite runtime tools in Node.js or any other language.
- **ComfyUI not reachable** -- Stop. Start ComfyUI first. Prompt Forge can run offline, but production stages cannot.
- **MCP tools missing** -- Stop. Surface the missing tool names to the user. Do not proceed with partial MCP capability.
- **Cache stale (files missing)** -- Stop. Re-run `scripts/install.ps1` to sync the plugin cache. Do not improvise with on-disk workflow files or direct ComfyUI API calls.
- **preflight-env.ps1 missing** -- Cache is severely stale. Re-run install.ps1 immediately.

## Reading rules (agent)

1. **Only read what the current step requires.** Do not bulk-read the entire runtime directory before starting.
2. **Step 0 must pass before Step 1.** Do not skip ahead or read ahead.
3. **A blocker means stop.** Do not search for workarounds, do not rewrite tools, do not continue exploring.
4. **Code is implementation detail, not an operating manual.** Read function signatures when needed, not entire files.
5. **Run from the skill root.** Do not operate on arbitrary filesystem paths or search for workflows on disk.

## Four-stage production flow

1. Consume an image PromptPackage for the camera-view text-to-image base image.
2. Consume the accepted base image for the Flux2-Klein multiview character sheet.
3. Consume the accepted reference plus a new shot PromptPackage for camera-view G1 image-to-image.
4. Consume the accepted shot image plus a bilingual video PromptPackage for the LTX Yusu Director stage.

Prompt Forge writes each prompt package. This skill never silently rewrites prompt prose; it may only map approved fields to a pinned workflow slot after approval.

## Fixed workflow and helper contract

The Anima camera workflow is a release asset, not a runtime discovery result. During development or installation, compare the complete live ComfyUI UI workflow with `runtime/workflow_assets/camera-anima.json`, record the node and API mappings, and verify the asset hashes. At runtime, load only the fixed asset through `runtime.camera_config_helper`; do not request or serialize a complete live workflow as configuration.

The helper boundary is:

1. `load_fixed_camera_bundle(stage)` loads the fixed UI/API pair and pinned profile.
2. `read_fixed_camera_config(bundle)` returns only prompts, reference image, all Anima camera angle fields, all 13 camera-extra fields, the two group-controller selections, and the atomic LoRA/TriggerWord unit.
3. `build_fixed_camera_config(...)` validates the semantic config.
4. `compile_fixed_camera_config(bundle, stage_config)` patches the UI surface and synchronizes the declared values into the API graph. The returned API graph is the only executable payload.

For a fixed workflow asset, capability discovery is asset-scoped: do not require
the workflow to appear in ComfyUI's saved library and do not require legacy
`get_workflow`/`strip_workflow` tools. Validate the bundled API graph with
`validate_workflow`, classify it with `check_workflow_runtime`, and report
missing live node types or non-local runtime as explicit fail-closed evidence.
Live workflow read/conversion tools remain required only for non-fixed stages.

After a successful image run, the consumer MUST return the PNG/artifact together with `result_manifest`, `effective_config`, `lora`, and `config_hash`. These fields are reconstructed from the final history prompt graph when available (otherwise the submitted executable graph): prompts, reference image, camera angle, all camera-extra inputs, group controls when available, LoRA Loader stack/raw selections, and the bound TriggerWord Toggle values. Returning only the image or only the requested configuration is incomplete.

The camera surface never exposes `seed`, `sampler`, `scheduler`, `steps`, `cfg`, or other internal execution controls. The UI and API transport must be tested together: a successful queue response is insufficient if ComfyUI history does not contain the requested prompt, camera fields, LoRA stack, and TriggerWord binding.

Before building a LoRA config, call MCP `list_local_models(model_type="loras")`. Parse the inventory, recommend only candidates compatible with the selected base model, make the selection explicit, preserve the inventory and recommendation hashes, and verify selected files are still present immediately before enqueue. Metadata is optional evidence; unavailable model-explorer metadata must not be invented.

## Step 0 - preflight gate (mandatory)

Before any prompt authoring, file write, or capability probe, the host agent
MUST run the environment checker and surface blockers with their `remediation` to
the user. The runtime does not perform code-level workarounds; a blocker means
stop and tell the user how to fix it.

The primary entry point is `preflight-env.ps1` (zero-dependency PowerShell). It
checks cache integrity, Python, and ComfyUI, then delegates to the runtime
preflight below. If `preflight-env.ps1` is missing, the cache is severely stale
-- re-run `scripts/install.ps1`.

Commands (one is enough):

    powershell -ExecutionPolicy Bypass -File skills/character-video-pipeline/preflight-env.ps1
    python -m runtime.preflight
    character-video-pipeline-runtime preflight --comfy-url http://127.0.0.1:8188

Output contract (excerpt):

    {
      "ok": false,
      "runtime_version": "0.0.0+codex.<ts>",
      "checks": [
        {"id": "version_stamp", "status": "ok", ...},
        {"id": "comfyui_reachable", "status": "fail", "remediation": "..."},
        {"id": "fixed_assets_integrity", "status": "ok", ...},
        {"id": "host_mcp_tools", "status": "informational",
         "expected_tools": ["check_workflow_runtime", "get_workflow",
                             "list_local_models", "strip_workflow",
                             "validate_workflow"]}
      ],
      "blockers": ["comfyui_reachable"]
    }

The host_mcp_tools check is informational only: the runtime cannot negotiate
MCP itself. The host agent MUST independently verify that the expected tools
are loaded in its own session before invoking any production subcommand.
If any tool is missing, surface the host_mcp_tools remediation to the user
and stop.

## Step 0b - cross-attempt state (mandatory read-first)

Before authoring, the host agent MUST read the most recent attempt record from
`%USERPROFILE%\.codex\state\comfyui-chenxin\attempts.jsonl` (or the path given
by `COMFYUI_CHENXIN_STATE_DIR`). If the previous blocker is unresolved and the
current preflight reproduces it, present the known blocker directly instead of
re-running the same 16 minutes of authoring.

Commands:

    python -m runtime.attempt_state read-last
    character-video-pipeline-runtime attempt-state read-last

After Step 0 / Step 0b / Step 1 run-stage character-base, the host agent
records the outcome so the next attempt inherits context:

    character-video-pipeline-runtime attempt-state record < attempts.json

## Ownership

This skill owns workflow discovery and profile pinning, model and node capability checks, ComfyUI/MCP transport, approval, one-time consumption, queue submission, raw history, artifact verification, lineage, and RunRecords. It must fail closed when workflow, profile, fingerprint, history, artifact, or receipt evidence is missing.

## Runtime boundary

Implementation lives under `skills/character-video-pipeline/runtime/`. The host injects a trusted `host_call_tool(tool_name, arguments)` callable for MCP operations. The runtime does not import a host SDK, invent a conversion receipt, or bypass the approval and consumption gates.

## Prompt boundary

Prompt Forge is offline and side-effect free. It owns CreativeEvidence, model prompt dialects, visual-language styles, exact tag validation, PromptPackage authoring, and deterministic lint. This skill owns only the external production lifecycle. Model availability never changes what makes a prompt excellent; it only affects whether a separate production request can run.