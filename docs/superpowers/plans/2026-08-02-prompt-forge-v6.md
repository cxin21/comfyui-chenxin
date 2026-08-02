# Prompt Forge v6.1 Production Implementation Plan

**Goal:** Deliver an auditable image/video prompt compiler that preserves user
intent, speaks model-specific dialects and never exceeds execution authority.

## Completed implementation

- [x] Restore non-mutating, active-worktree-relative baseline tests.
- [x] Replace flat translation with a structured Chinese concept map and canonical
  tag integrity checks.
- [x] Add PromptIntent normalization with provenance and intact unknown CJK.
- [x] Expand PromptIntent to target/mode/generation mode, negative/output
  constraints, references, locked facts, and fourteen image/video dimensions.
- [x] Add longest-phrase and safe single-character match policy.
- [x] Add batch exact tag validation and public recipe lookup API.
- [x] Correct video recipe modality metadata.
- [x] Replace diluted scene scoring with specificity-weighted phrase evidence.
- [x] Return explicit preset choices on scene miss instead of selecting a default.
- [x] Add side-effect-free `prompt_compile.py` and PromptBuild 1.0.
- [x] Separate tag, natural-language and video-timeline compilation/auditing.
- [x] Enforce locked-fact, negative-policy, tag and video-contract hard stops.
- [x] Make compile the default and execution an explicit later action.
- [x] Rewrite SKILL.md with narrow triggers, absolute-path semantics and
  progressive-disclosure references.
- [x] Add image, video, contract and concept-map reference docs.
- [x] Add 24 trigger-boundary and 12 PromptBuild evaluation cases.
- [x] Add Anima, Flux and Wan frozen fixtures plus integration tests.

## Final verification

- [x] Deterministic corpus pass rate >= 0.90.
- [x] Full unit suite passes.
- [x] Recipe schema/check and Python compile checks pass.
- [x] Official Skill quick validator passes.
- [x] Skill-eval-lab offline trigger smoke is recorded with its known tokenizer
  limitations.
- [x] CodeGraph refreshed and diff hygiene checks pass.
- [x] Obsidian design note synchronized.

## Acceptance boundary

“Production-grade” here means deterministic contracts, policy correctness,
regression evidence and safe execution boundaries. Visual excellence remains a
model-specific rendered A/B gate and is not claimed from text-only tests.
