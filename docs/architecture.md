# Architecture and first principles

## Two bounded skills

Prompt Forge is pure authoring and audit. `character-video-pipeline` is the production consumer and execution owner.

## Data flow

`brief + evidence -> Claude/Codex draft -> deterministic PromptPackage -> external pipeline`

The external pipeline adds profiles, approval, ComfyUI/MCP submission, artifacts, and history.

## Ownership table

- Prompt Forge: evidence normalization, dialect and style language, tag checks, package validation.
- Character video pipeline: model/workflow discovery, MCP, approvals, submission, artifacts, and RunRecords.

## Boundary invariants

- Prompt Forge never imports runtime code, reads workflow profiles, checks model installation, or emits execution state.
- The pipeline never asks Prompt Forge to execute or silently rewrite a prompt.

## Four-stage handoff

1. Prompt Forge writes the base-image prompt.
2. The pipeline consumes it for the base image.
3. Prompt Forge writes multiview, shot, and video prompts while preserving locked evidence.
4. The pipeline consumes external assets; Prompt Forge remains side-effect free.

## Verification

Prompt Forge is verified offline with deterministic tests. Runtime integration and live workflow checks belong to the production consumer.
