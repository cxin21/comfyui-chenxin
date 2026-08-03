Plan: docs/superpowers/plans/2026-08-02-prompt-forge-v7-slice2-multiview.md

## Baseline

- Worktree: D:/Projects/comfyui-chenxin/.worktrees/prompt-forge-v6
- Branch: feat/prompt-forge-v6
- Baseline commit: 7de49ed
- Baseline tests: 202 passed, 3 skipped; evaluator 12/12.
- Slice 1 live characterization: A/B succeeded; current saved camera fingerprint differs from selected history graph and is recorded explicitly.
- SDD Bash helper fallback: WSL Bash unavailable; plan-scoped artifacts are generated with equivalent PowerShell logic.

## Task Ledger

| Task | Base | Head | Implementer | Review | Status |
|---|---|---|---|---|---|
| 1 | 7de49ed | 83a6d2d | DONE, 215 passed/3 skipped | Approved, no findings | complete |
| 2 | 83a6d2d | 081b91b | DONE + fix, 156 passed/3 skipped | Approved after 1 fix round; Stage3 must reject semantic_conflict | complete |
| 3 | 081b91b | uncommitted review worktree | Fix round 4: strict final/failed recovery receipt revalidation + controlled local MCP conversion builder; focused 27 passed and scoped 45 passed/1 skipped; full 260 passed/4 skipped; evaluator 12/12; compileall/diff-check passed | round-3 blockers closed locally; MCP conversion remains 70 warnings/86 errors | deterministic complete, live blocked |

## Continuation checkpoint (2026-08-03)

- Promoted flat v2 workflow was executed on the local ComfyUI and completed
  successfully as prompt `f47e75ef-cd40-4bf5-9b77-90f538a605d9`; its saved UI,
  API, strip, validation, runtime, normalization, and promotion receipt pins
  are retained in the v2 profile/evidence module.
- A strict current Stage 1 draft was rebuilt from the retained successful
  camera history and current capability report. Its exact draft hash is
  `c33ade3ef6e7af7e33c96ae3cf70a806eb1eff533967756059045f1914d60f12`.
- Stage 1 history contains preview/temp images alongside the retained PNG;
  `build_run_record` now requires an explicit retained `artifact_descriptor`
  whenever a successful history has multiple image outputs. This closes the
  implicit-selection gap without changing failed-terminal records.
- No Stage 1 approval/consumption, upload, pending C bundle, or enqueue was
  created. The next hard gate is an approval event bound to the exact draft
  hash above; high-level approval cannot substitute for that displayed hash.

## Stage 3/4 execution-boundary continuation (2026-08-03)

- Added deterministic reference selection and an explicit `accept_stage3_reference` transition. A Flux angle is not reusable until its PNG hash, semantic checks, and human acceptance evidence are all present.
- Added Stage 3 camera img2img planning/execution and Stage 4 Yusu Director planning/execution. Both bind PromptBuild, profile, source graph, current capability report, exact graph patch, approval, exclusive consumption, submission, enqueue receipt, and terminal artifact lineage.
- Added fail-closed CLI commands: `accept-reference`, `plan-stage-execution`, `approve-stage`, `consume-stage`, `build-stage-submission`, `record-stage`, `verify-video`, and `pipeline-state`.
- Deterministic stage execution tests now cover strict schema/hash/UTC/receipt checks. No Stage 3 or Stage 4 job was enqueued in this continuation.
- Live gates remain asymmetric: Flux v2 has a successful local run and LTX Director validates with zero errors; the current saved camera conversion still has 7 warnings / 3 errors, so Stage 3 upload/enqueue remains blocked until a fresh zero-error conversion is obtained.

### Submission-boundary hardening (2026-08-03)

- Stage submission requests now carry the stable enqueue request ID in
  `extra_data`, so raw ComfyUI history can prove the exact request identity.
- `submit_stage` now requires the canonical consumed-namespace receipt path and
  exclusive-creates a self-hashed submission-intent sentinel before invoking
  the injected enqueue callable. Replays can return the retained receipt, while
  uncertain/in-progress calls fail closed without a second enqueue.
- Full deterministic verification after this hardening: 326 passed, 4 skipped;
  evaluator 12/12; compileall, diff-check, and new stage-boundary lint passed.
