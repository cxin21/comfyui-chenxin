---
name: character-video-pipeline
description: Approval-gated four-stage ComfyUI production consumer for PromptPackage outputs
status: active
side_effects: approval-gated-local-comfyui
owner: character-video-pipeline
---

# Character Video Pipeline

This is the only skill allowed to cross the local ComfyUI and MCP boundary. It consumes a validated PromptPackage from Prompt Forge and turns approved prompt packages and user-approved assets into production artifacts.

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
## Ownership

This skill owns workflow discovery and profile pinning, model and node capability checks, ComfyUI/MCP transport, approval, one-time consumption, queue submission, raw history, artifact verification, lineage, and RunRecords. It must fail closed when workflow, profile, fingerprint, history, artifact, or receipt evidence is missing.

## Runtime boundary

Implementation lives under `skills/character-video-pipeline/runtime/`. The host injects a trusted `host_call_tool(tool_name, arguments)` callable for MCP operations. The runtime does not import a host SDK, invent a conversion receipt, or bypass the approval and consumption gates.

## Prompt boundary

Prompt Forge is offline and side-effect free. It owns CreativeEvidence, model prompt dialects, visual-language styles, exact tag validation, PromptPackage authoring, and deterministic lint. This skill owns only the external production lifecycle. Model availability never changes what makes a prompt excellent; it only affects whether a separate production request can run.

