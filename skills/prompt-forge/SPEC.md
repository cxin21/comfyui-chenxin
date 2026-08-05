# Prompt Forge specification

## Objective

Prompt Forge is a pure prompt authoring and quality-audit skill. Claude or Codex is the authoring caller. Python performs deterministic validation after the caller supplies the final draft. No additional model provider is part of this contract.

## Inputs

The caller supplies:

- a CreativeEvidence ledger with four-quadrant provenance;
- an exact image or video dialect ID;
- an optional explicit visual-language style;
- a final caller-authored draft.

The evidence ledger preserves shared_known, user_known_agent_unknown, assistant_known_user_unknown, joint_unknown, locked_facts, continuity_locks, style_evidence, asset_refs, and uncertainty. Every supplied dimension keeps origin and source_text when available.

## Authoring sequence

1. Confirm the goal, background, delivery standard, and boundary.
2. Separate known facts, reasonable inferences, user-unknown information, and testable joint unknowns.
3. Resolve the exact dialect and keep style advice advisory.
4. Have Claude or Codex write the final prompt fields.
5. Run adversarial review for facts, style, action, camera, timeline, dialogue, and dialect.
6. Run deterministic lint and emit PromptPackage.

If the draft is missing, production validation fails. The compiler never synthesizes prose as a fallback.

## PromptPackage

The package may contain authored image fields (`positive`, `negative`) or authored video fields (`positive_zh`, `positive_en`, `global_prompt`, `timeline_segments`, `dialogue_attribution`, `continuity_locks`). Unused modality fields are omitted. Quality flags include facts_preserved, no_unsupported_invention, style_coherent, dialect_valid, temporal_logic_valid, and ready_for_review.

Forbidden fields include ready_to_execute, execution, workflow, workflow_hash, profile_hash, node, node_id, slot_id, gpu, transport, and runtime state. The boundary rejects these keys recursively, including camelCase variants.

## Image rules

The dialect registry defines ordering, negative policy, reference language, required dimensions, and forbidden patterns. Exact tags and approved aliases are validated separately from recipe control tokens. Unknown tags are rejected and never guessed into canonical tags.

## Video rules

Video drafts include a global prompt, bilingual positive fields, contiguous non-negative time ranges beginning at zero, explicit Chinese and English timeline text, attributed dialogue ranges, and continuity locks. The validator checks these structures without deciding whether any model or workflow is installed.

## Model and style separation

Model dialects describe prompt language only. Styles describe visual language only. Style rendering cannot add identity, plot, prop, dialogue, or continuity facts. Two style variants built from the same evidence must preserve protected facts byte-for-byte in the evidence ledger.

## Boundary

Prompt Forge does not inspect ComfyUI, MCP, workflows, nodes, models, hardware, hashes, or execution state. The external character-video-pipeline consumes the package and owns production submission, approvals, artifacts, and run records.

## Offline acceptance

Acceptance is based on deterministic tests for exact lookup, evidence provenance, tag validation, PromptPackage structure, style invariance, and boundary imports. Runtime generation tests belong to the external production pipeline.
