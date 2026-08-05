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

## Ownership

This skill owns workflow discovery and profile pinning, model and node capability checks, ComfyUI/MCP transport, approval, one-time consumption, queue submission, raw history, artifact verification, lineage, and RunRecords. It must fail closed when workflow, profile, fingerprint, history, artifact, or receipt evidence is missing.

## Runtime boundary

Implementation lives under `skills/character-video-pipeline/runtime/`. The host injects a trusted `host_call_tool(tool_name, arguments)` callable for MCP operations. The runtime does not import a host SDK, invent a conversion receipt, or bypass the approval and consumption gates.

## Prompt boundary

Prompt Forge is offline and side-effect free. It owns CreativeEvidence, model prompt dialects, visual-language styles, exact tag validation, PromptPackage authoring, and deterministic lint. This skill owns only the external production lifecycle. Model availability never changes what makes a prompt excellent; it only affects whether a separate production request can run.
