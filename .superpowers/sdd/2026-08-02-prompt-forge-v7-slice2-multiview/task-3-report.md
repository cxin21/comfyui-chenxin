# Slice 2 Task 3 Report

## Deterministic RED → GREEN

The first focused run failed during collection with the expected missing
`build_multiview_draft` import. A later adversarial RED proved that a
self-hashed Stage 2 draft could initially replace the content-derived upload
name and still reach generic approval; the new Stage 2 draft-contract validator
now rejects that mutation before approval.

Implemented:

- accepted Stage 1 RunRecord + `CharacterBaseImage` validation, including
  self-consistent record hash, terminal/history proof, exact output SHA-256,
  canonical path/root containment, real file-byte SHA-256, safe lineage, source
  record binding, and front-facing/identity-visible acceptance;
- Stage 2 unapproved draft bound to Stage 1 record/artifact, current fresh local
  capability report, verified Flux profile/fingerprint, source/executable graph
  hashes, exact synchronized nodes 111/667 image patches, and immutable pose
  inputs;
- existing generic `approve-plan` → exact external event → canonical root →
  atomic `consume-approval` support for both stages, with no Boolean shortcut;
- `plan-multiview` and `patch-flux` JSON CLI commands;
- Stage 2 RunRecord with raw history, canonical executable-graph equality,
  normalized artifacts, output hashes, Stage 1 source hash and lineage;
- Stage 3 eligibility fix: `semantic_conflict=true` is never reference eligible;
- opt-in Experiment C preflight tests that accept only an MCP-validated local
  executable graph and otherwise fail closed before pending-draft creation.

## Skill pressure test

The fresh baseline operator stopped because the old Skill had no compliant
upload contract and would have used generic `plan` without Stage 1 hash/lineage
or Flux-specific patch rules. After the edit it selected real MCP capability
discovery, verified-graph conversion, content-derived MCP upload,
`plan-multiview`/`patch-flux`, exact approval/consume-once, raw history and
artifact eligibility. A second pressure pass found an upload-before-validation
ordering contradiction; the final text now requires MCP validation first,
then upload, and names `executable_api_graph_hash` explicitly.

## Live Experiment C preflight (not passed)

Read-only discovery on 2026-08-03 established:

- ComfyUI queue: running `0`, pending `0`;
- saved `Flux2-Klein人物一键多视图工作流.json` exists;
- saved UI fingerprint equals the profile fingerprint
  `fff6236efa6727ac6584d61f640a63f9602b2d07a545d216b96a870a681e6faf`;
- `comfyui-mcp` exposes real `get_workflow`, `strip_workflow`,
  `validate_workflow`, `check_workflow_runtime`, queue, upload, enqueue and
  history tools; runtime classification of the converted graph was `local`
  with no API nodes;
- no successful `/history` entry matched the Flux profile slots;
- `get_workflow(format=api)` and `strip_workflow(format=api)` each emitted 70
  conversion warnings. `validate_workflow` rejected the resulting 261-node
  graph with 86 missing-required-input errors. The attempt to obtain a separate
  frontend serialization path produced no usable evidence before the bounded
  exploration was stopped.

Therefore no validated executable API graph existed. Per the task boundary,
the Stage 1 PNG was **not uploaded**, no pending C bundle/draft hash was
created, no approval was fabricated, and nothing was enqueued. Experiment C is
environment-blocked at validated graph conversion and is not claimed as
pending or passed. The opt-in harness can create `pending-c-<draft_hash>.json`
only after `PROMPT_FORGE_MCP_PREFLIGHT_FILE` proves a real zero-error local MCP
conversion.

## Verification

- focused Stage 2/artifact/live-default gate: `22 passed, 1 skipped` before the
  final two adversarial tests; both later RED→GREEN tests also pass;
- full deterministic runtime + internals gate: `239 passed, 4 skipped`;
- evaluator: `12/12`, pass rate `1.0`;
- `python -m compileall -q skills/prompt-forge/runtime`: passed;
- `git diff --check`: passed (Git emitted only configured LF→CRLF notices).

## Residual risk

The saved Flux UI may still be executable inside the ComfyUI frontend; the
evidence only proves that the currently callable MCP conversion produced an
invalid API prompt. It must not be generalized into “the workflow itself is
broken.” A future continuation needs a real frontend-serialized API prompt that
passes the same MCP validator; accepting or repairing the current invalid graph
by hand is prohibited.
