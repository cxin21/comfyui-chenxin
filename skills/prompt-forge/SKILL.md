---
name: prompt-forge
description: LLM-first authoring and deterministic quality review for image and video prompts
status: active
side_effects: none
owner: prompt-compiler
---

# Prompt Forge

Prompt Forge is an LLM-first prompt authoring skill. Claude or Codex writes the final prompt; deterministic code audits structure, facts, style, dialect, tags, and temporal logic.

## Quick start (mandatory first action)

Before any prompt authoring or tag validation, run the zero-dependency environment checker:

    powershell -ExecutionPolicy Bypass -File skills/prompt-forge/preflight-env.ps1

This checks Python availability and cache integrity. A blocker means STOP -- do not attempt workarounds.

If `preflight-env.ps1` itself is missing, the plugin cache is severely stale. Re-run `scripts/install.ps1` to sync.

## Environment prerequisites

- **Python 3.10+** -- must be on PATH or at a common location (ComfyUI embedded Python is auto-detected by `preflight-env.ps1`)
- **Plugin cache** -- must be in sync with the project source (verified by `preflight-env.ps1`)
- **No ComfyUI required** -- Prompt Forge is offline and side-effect free

## Degradation paths

- **Python not found** -- Stop. Install Python 3.10+ or ensure ComfyUI's embedded Python is accessible. Do not rewrite tag validation tools in Node.js or any other language.
- **Cache stale (files missing)** -- Stop. Re-run `scripts/install.ps1` to sync the plugin cache. Do not improvise with manual tag lookups.
- **preflight-env.ps1 missing** -- Cache is severely stale. Re-run install.ps1 immediately.

## Scope

The skill accepts a user brief, supplied evidence, target modality, model dialect, and optional visual-language style. It returns a PromptPackage for an external consumer. It does not discover or execute models, nodes, workflows, transports, or local services.

## Four-quadrant evidence

Keep shared facts, user-known agent-unknown information, assistant-known user-unknown inferences, and joint unknowns separate. Explicit facts and continuity locks are preserved. Missing information becomes uncertainty or a small testable hypothesis; it is never silently invented.

## LLM authoring contract

1. Build the evidence ledger.
2. Resolve an exact prompt dialect and an explicit or advisory style.
3. Claude or Codex writes the final positive, negative, image, or video fields.
4. Run deterministic lint and adversarial quality review.
5. Return PromptPackage with warnings and quality flags.

Without a caller-authored LLM draft, production validation fails. The skill never generates fallback prose.

## Model and style knowledge

Model profiles describe prompt language only: tag order, natural-language structure, negative policy, reference wording, and failure patterns. Style profiles describe visual language only: medium, palette, lighting, composition, material, texture, depth, and motion vocabulary. Neither profile contains installation, hardware, node, workflow, hash, or execution state.

## PromptPackage boundary

PromptPackage contains only authored prompt fields, evidence provenance, validated tags, warnings, errors, and quality results. It must not contain ready_to_execute, execution, workflow_hash, profile_hash, node_id, slot_id, GPU state, or transport state.

## External production boundary

Prompt Forge is offline and side-effect free. An external production consumer may handle submission, approval, artifact, and history work. Those concerns are outside this skill and are never used to decide whether a prompt is good.

## Quality principles

- Facts and continuity locks outrank plausible invention.
- Unknowns stay explicit as uncertainty or testable hypotheses.
- Dialect and style change expression, not story facts.
- Missing caller-authored fields fail closed; no fallback prose.