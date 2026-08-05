---
name: prompt-forge
description: LLM-first authoring and deterministic quality review for image and video prompts
status: active
side_effects: none
owner: prompt-compiler
---

# Prompt Forge

Prompt Forge is an LLM-first prompt authoring skill. Claude or Codex writes the final prompt; deterministic code audits structure, facts, style, dialect, tags, and temporal logic.

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
