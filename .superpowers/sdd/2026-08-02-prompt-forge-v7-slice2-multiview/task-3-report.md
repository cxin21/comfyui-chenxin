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

## Fix round 1: adversarial-review closure

The review findings are now enforced at the runtime boundary rather than in
live-test helpers. `multiview_evidence.py` is the single Stage 2 evidence
module for the pinned Flux profile digest/semantic map, strict PNG validation,
MCP conversion receipt, local/no-API/no-remote/no-unknown runtime result, and
content-derived upload receipt. `execution.py` retains only typed error
translation plus generic approval, consumption, pending and record primitives.

- `plan-multiview` requires the complete conversion/upload receipts and the
  full Stage 1 RunRecord/history/source-graph/consumption chain. It cannot
  accept a minimal self-hashed record, a non-PNG artifact, a mixed UI/API pair,
  a remote/API graph, a non-zero validation result, or a profile semantic-map
  mutation.
- `patch-flux` consumes only an approved Stage 2 plan, its exact source graph,
  the content-derived upload receipt and the retained atomic consumption
  sentinel. It forces 111/667, compares all pose inputs, recomputes the exact
  executable hash and returns the stable enqueue request identity with the
  submitted graph.
- Stage 2 `record` now consumes that submission and sentinel, requires the
  history `enqueue_request_id`, reads every history output from a canonical
  output root, verifies PNG bytes and computes SHA-256 itself. Normalized
  artifacts have `hash_verified=true` but `accepted=false` until explicit
  selection; Stage 3 eligibility additionally requires accepted,
  CharacterAngleView, reference eligibility and no semantic conflict.
- `write_pending_bundle` / `load_pending_bundle` are shared for both stages.
  They exclusive-create canonical-root bundles, validate exact draft hash and
  stage-specific frozen inputs, enforce `<stage>:<draft_hash>` namespace and a
  maximum 600-second UTC window. Stage 2 uses `pending-c-<draft_hash>.json`.
- Live preflight uses runtime `ExecutionError`, never bare `assert`; a
  `python -O` regression confirms invalid evidence is still rejected. The
  trusted boundary is the local orchestrator and its actual MCP calls. Receipts
  are auditable observations, not invented cryptographic MCP signatures.

The focused RED runs were:

- Stage 2 record before the new consumption/submission/output-root interface:
  `2 failed` (unexpected missing keyword arguments).
- Pending bundle before implementation: collection failed because
  `load_pending_bundle` / `write_pending_bundle` did not exist.
- Canonical artifact path checks: `3 failed` for `./`, duplicate slash and
  backslash subfolder references.
- Stage 3 eligibility predicate before implementation: collection failed
  because `is_stage3_reference_eligible` did not exist.

All GREEN verification after the fixes:

```powershell
$env:PYTHONPATH='skills/prompt-forge'
Remove-Item Env:PROMPT_FORGE_LIVE -ErrorAction SilentlyContinue
python -m pytest skills/prompt-forge/runtime/tests/test_artifacts.py skills/prompt-forge/runtime/tests/test_stage2_plan.py skills/prompt-forge/runtime/tests/test_live_multiview.py -q
# 35 passed, 1 skipped
python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q
# 250 passed, 4 skipped
python skills/prompt-forge/internals/evaluate.py
# 12/12, pass_rate 1.0
python -m compileall -q skills/prompt-forge/runtime
git diff --check
```

## Fix round 4: strict recovery and controlled conversion boundary

Recovery now uses the same strict `_validate_enqueue_receipt` path for both a
freshly retained success and a later exactly-once recovery. Before returning a
recovered success it re-reads the canonical receipt and validates complete
schema/type/version, self-hash, intent, consumption/request/submission/graph
identities, exact `enqueue_workflow` arguments, response digest/prompt ID/node
errors, trusted-local-orchestrator provenance, canonical path and on-disk
equality. A truncated receipt, a self-rehashed response mismatch, and a
self-rehashed graph mismatch all fail closed without another MCP call.

Failed recovery has a separate strict validator and canonical failed-receipt
path. In-progress (intent only), failed, succeeded, unknown intent status, and
ambiguous success+failed evidence are handled separately; no unknown state is
treated as success.

Production Stage 2 planning now uses
`build_multiview_draft_with_mcp`. The authorized local orchestrator injects
the four actual comfyui-mcp callables; the builder itself executes and binds:

- `get_workflow({workflow_id, format: "ui"})`;
- `get_workflow({workflow_id, format: "api"})`;
- `strip_workflow({workflow_id})`;
- `validate_workflow({workflow: api_graph})`;
- `check_workflow_runtime({workflow: api_graph})`.

It rejects a conversion/strip mismatch, validates the real response objects,
constructs the receipt internally with tool version, exact arguments, response
digests and fixed local-orchestrator provenance, retains that receipt inside
the hash-bound draft, then calls the pure Stage 2 validator/builder. The old
caller-authored-receipt entry point now raises a typed audit-only error. JSON
`plan-multiview` therefore returns exit 1 with `accepted=false` and cannot
produce an approvable production draft. Offline
`validate_multiview_mcp_preflight` remains available only for audit fixtures.
JSON `patch-flux` remains a non-submit fail-closed boundary.

RED evidence:

```text
recovery forged receipts: 3 failed (DID NOT RAISE; enqueue recovery calls=0)
controlled conversion boundary: 2 failed (missing callable builder; JSON plan returned 0)
```

Fresh GREEN verification:

```powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_stage2_plan.py -q
# 27 passed
python -m pytest skills/prompt-forge/runtime/tests/test_stage2_plan.py skills/prompt-forge/runtime/tests/test_artifacts.py skills/prompt-forge/runtime/tests/test_live_multiview.py -q
# 45 passed, 1 skipped
python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q
# 260 passed, 4 skipped
python skills/prompt-forge/internals/evaluate.py
# 12/12, pass rate 1.0
python -m compileall -q skills/prompt-forge/runtime
git diff --check
# both exit 0; diff-check emitted only configured LF-to-CRLF notices
```

Experiment C remains blocked and is not passed. The current real
comfyui-mcp 0.49.0 conversion evidence remains 70 warnings and 86 validation
errors. No production draft, upload, pending approval, consumption or enqueue
was created from that invalid conversion.

## Fix round 3: exactly-once enqueue gate

Before invoking the trusted local `enqueue_workflow` callable, `submit_multiview`
now exclusive-creates a canonical consumption-id submission-intent sentinel.
It binds the consumption id, request id, submission hash, executable graph hash
and exact request. A concurrent caller sees the retained in-progress sentinel
and cannot call MCP; a later identical caller returns the retained successful
receipt without calling MCP again. A different graph/hash/request under the
same consumption is rejected.

If the callable raises, the intent remains and an exclusive typed
`*.enqueue-failed.json` evidence record is retained. Subsequent calls fail
closed and direct the caller to query server state rather than deleting or
blindly retrying. A successful final receipt binds the intent hash, response
prompt id, exact tool arguments, response digest and trusted-local-orchestrator
provenance.

The conversion receipt now also carries strict invocation entries for real
`get_workflow` calls with `{workflow_id, format: "ui"}` and `{workflow_id,
format: "api"}`, plus strip/validate/runtime arguments and response digests;
the validator rejects a mismatch and retains the explicit local trust model.

Final verification:

```powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_stage2_plan.py skills/prompt-forge/runtime/tests/test_artifacts.py skills/prompt-forge/runtime/tests/test_live_multiview.py -q
# 41 passed, 1 skipped
python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q
# 256 passed, 4 skipped
python skills/prompt-forge/internals/evaluate.py
# 12/12, pass rate 1.0
python -m compileall -q skills/prompt-forge/runtime
git diff --check
```

The full run initially exposed a pre-existing CLI error-path regression:
`runtime_cli.py` caught `FluxAdapterError` without importing it, turning eight
expected exit-2 cases into `NameError` exit-1 cases. The minimal import fix was
validated by `python -m pytest skills/prompt-forge/runtime/tests/test_runtime_cli.py -q`
(`11 passed`) before the final full run.

Experiment C remains blocked and is not passed: current real comfyui-mcp
0.49.0 conversion remains at 70 warnings and 86 validation errors. No upload,
pending draft, approval, consumption or enqueue was created from that invalid
conversion.

## Fix round 2: controlled enqueue and raw-history binding

- Stage 1 now persists one accepted raw-history image descriptor and Stage 2
  requires it to be exactly one `type=output` descriptor from the verified raw
  history whose canonical `subfolder/filename` path is the accepted PNG. The
  descriptor is carried in the Stage 2 draft and approved-plan lineage.
- `submit_multiview` is the only submission boundary. It requires an injected
  trusted-local orchestrator callable, consumes the approved plan/sentinel and
  upload receipt, sends the exact graph plus stable request id, validates the
  returned `enqueue_workflow` tool arguments/response digest/provenance, and
  exclusive-writes a prompt-bound enqueue receipt. `patch-flux` at the plain
  JSON CLI boundary now returns exit 2 because JSON cannot supply that trusted
  callable; it never reports a submission.
- Stage 2 RunRecord consumes that receipt and reads the request ID only from
  `history[prompt_id]["prompt"][3]["extra_data"]` (with compatible direct
  metadata support), rejecting the former synthetic top-level history field.
  The prompt id, sentinel, submission, receipt, raw executable graph and PNG
  outputs are all cross-bound.
- Pending bundles now reject a `created_at` after the trusted clock. Stage 2
  documentation now states `draft -> external approval -> consume -> controlled
  enqueue`, and identifies UI-to-API as `get_workflow(format=api)`.

Verification after this round:

```powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_stage2_plan.py -q
# 21 passed
python -m pytest skills/prompt-forge/runtime/tests/test_stage2_plan.py skills/prompt-forge/runtime/tests/test_artifacts.py skills/prompt-forge/runtime/tests/test_live_multiview.py -q
# 39 passed, 1 skipped
python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q
# 254 passed, 4 skipped
python skills/prompt-forge/internals/evaluate.py
# 12/12, pass rate 1.0
python -m compileall -q skills/prompt-forge/runtime
git diff --check
```

## Latest status and complexity audit

Round 4 supersedes the older verification counts above: focused Stage 2 is
27 passed; scoped Stage 2/artifact/live-default is 45 passed, 1 skipped; full
deterministic is 260 passed, 4 skipped; evaluator is 12/12; compileall and
diff-check exit 0. Experiment C remains blocked at 70 warnings/86 errors.

The cumulative uncommitted Task 3 diff makes `execution.py` 2,105 lines
(`+1134/-50` versus the committed base). The largest affected boundaries are
the controlled conversion builder (148 lines), pure Stage 2 builder (114),
submit boundary (141), success receipt validator (76), and failed receipt
validator (66). Strict success receipt validation is not duplicated: the same
function has three call sites for fresh submit, recovery, and RunRecord.
Success and failure validators remain separate because their schemas and
outcome semantics differ. `_require_idle_local_capability` exists in both the
generic execution module and the isolated multiview evidence module; the
production wrapper checks it before calling MCP and the pure evidence validator
checks it again after observation. This is deliberate pre-side-effect plus
defense-in-depth validation, but the 2,105-line module is a maintainability
risk and should be split after this correctness review rather than expanded in
this fix round.

## Stage 3/4 execution addendum (2026-08-03)

The follow-on implementation adds a separate stage execution boundary instead of
reusing the Stage 1/2 executor. It validates the current graph and capability
report, patches only the profiled camera G1 or Yusu Director inputs, requires a
fresh exact approval event, persists an exclusive consumption record, and emits
a self-hashed submission/receipt/run-record chain. Reference acceptance is an
explicit state transition; a selected-but-unaccepted angle cannot reach Stage 3.

The local ComfyUI remains reachable and idle. Flux v2 promotion/live execution
evidence is retained, and the LTX Director profile is validation-clean. The
current saved camera workflow still fails conversion with 7 warnings and 3
errors, so no camera upload or enqueue is authorized. This is a live evidence
gate, not a deterministic implementation failure.

## Stage 3/4 submission hardening addendum (2026-08-03)

The stage submission request now includes `prompt_forge_enqueue_request_id` in
ComfyUI `extra_data`, matching the raw-history identity check. The submission
schema also retains the canonical consumption root. `submit_stage` requires the
consumed-namespace receipt path and exclusive-creates a self-hashed intent
sentinel before the injected enqueue callable; a retained successful receipt is
idempotently returned, while an in-progress or uncertain intent blocks retry.

Post-hardening verification: 326 deterministic tests passed, 4 skipped;
evaluator 12/12; compileall, diff-check, and focused production-module lint all
passed. Live camera execution remains blocked by the current 7-warning / 3-error
UI-to-API conversion gate.
