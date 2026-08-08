# Chenxin Trusted CLI — Core Slice Design

Date: 2026-08-06
Status: draft
Scope: core slice (A + B + C + E + J + minimum single-entry CLI)
Backwards compatibility: none — old interfaces are deleted, not deprecated

## 1. Problem statement

Session `019fd5cb` demonstrated that the current design lets an agent bypass every
production gate by:

1. Reading runtime source code (50 KB+) to learn internal data shapes
2. Injecting fake `validate_workflow` / `check_workflow_runtime` callables through
   the public `build_capability_report(workflow_tools=...)` parameter
3. Self-approving via in-process `approve_execution_draft()` call
4. Hand-assembling PromptPackage, manifest, and attempt records

The gates are "gentlemen's agreements" — written in SKILL.md prose, not enforced
by code. The agent chose the path of least resistance (bypass) instead of the
correct path (follow the skill contract).

## 2. Design principles

These come from the project rules. Restated here for the spec to be self-contained.

- **No backwards compatibility.** Delete old interfaces. No migration layers.
- **Simplest thing that works.** No preventive abstraction. No config layers for
  hypothetical futures.
- **Layered architecture.** One-way dependencies. Each component has one job.
- **Reuse over rebuild.** Workflow validation uses `comfyui-mcp` (upstream
  maintained). MCP handshake reuses existing `scripts/verify_mcp.py` logic.
- **Long-lived architectural decisions.** No "we'll fix this later" scaffolding.
- **Proven patterns.** Two-phase execution + explicit approval + idempotent resume
  is how every CI/CD system does gated deploys.

## 3. Architecture

Five layers, strict top-to-bottom dependency.

```
L4  SKILL.md runbook          (docs only, three commands)
───────────────────────────────────────────────────────
L3  Orchestration             chenxin run / resume / approve / doctor
───────────────────────────────────────────────────────
L2  Runtime core              capabilities, workflow_discovery, execution,
                                attempt_state, run_stage, contracts
───────────────────────────────────────────────────────
L1  Transport bridge          McpBridge + mcp_spawn (comfyui-mcp stdio)
───────────────────────────────────────────────────────
L0  Host shell & preflight    preflight-env.ps1, chenxin doctor
```

**Layer rules:**

- A layer may only call into the layer directly below it.
- No layer imports from a layer above it.
- L2 runtime core has no knowledge of CLI, orchestration, or SKILL.md.
- L1 bridge does not know workflow semantics — only tool names and JSON shapes.

## 4. Components

### 4.1 `mcp_spawn.py` (new)

Spawns `comfyui-mcp` as a stdio child process, performs MCP initialize handshake,
runs `tools/list`, verifies all required tools are present, and returns a
connected `McpBridge` instance.

- Reuses the handshake logic from `scripts/verify_mcp.py` (extracted into this
  module; the script becomes a thin wrapper that calls `mcp_spawn.verify()`).
- Required tools: `get_workflow`, `strip_workflow`, `validate_workflow`,
  `check_workflow_runtime`, `list_local_models`. (Same list as today.)
- Failure modes: spawn fail, initialize timeout, tools/list timeout, missing
  required tools. All produce structured errors with remediation.
- `host_id = "chenxin-cli-spawned"`, `host_version = plugin version`.

### 4.2 `McpBridge` (existing, unmodified surface, no longer optional)

Existing `McpBridge` design is good. Change: it goes from "nice-to-have adapter"
to "only way workflow tools enter the system".

- `available_tools` / `require_workflow_tools()` / `workflow_tools()` stay.
- `call()` + receipt stays (audit trail is valuable).
- Side-effect gating (`allow_side_effects`) stays.

### 4.3 `capabilities.py` (breaking change)

Delete `workflow_tools: dict | None` and `workflow_specs` parameters from
`build_capability_report()`. New signature:

```python
def build_capability_report(
    api: ComfyApi,
    adapter: dict,
    now: datetime,
    *,
    bridge: McpBridge,
) -> dict:
```

Workflow discovery always goes through `bridge.workflow_tools()`. There is no
"no tools → report everything unavailable" fallback path — if bridge doesn't
have the tools, `require_workflow_tools()` raises before we even get here.

### 4.4 `run_stage.py` / `local_orchestrator.py` (breaking change)

Delete `workflow_tools` parameter from all production functions
(`build_execution_draft`, `submit_character_base_via_local_rest`, etc.).
Callers pass a `bridge: McpBridge` instead.

The `_fixed_camera_source_graph` / "fixed asset can be validated locally only"
paths are deleted. All validation goes through MCP.

### 4.5 `chenxin_cli.py` (new — or extend `runtime_cli.py`)

Top-level CLI entry point. Subcommands:

- `chenxin doctor` — full preflight + MCP handshake + capability summary.
  Exit 0 if all green, non-zero with structured error otherwise.
- `chenxin run character-base --package <pkg.json> --out <run_dir>` — Phase 1:
  preflight → validate package → build capability report → build draft →
  write run_dir → stop at `awaiting_approval`.
- `chenxin approve <run_dir>` — Write `approval.event.json` binding approval
  to the current draft's `plan_hash`. (Explicit, auditable action.)
- `chenxin resume <run_dir>` — Phase 2: validate approval event matches
  draft → consume approval → enqueue → poll → download → verify →
  write manifest → append attempt → write `result.json`.

`chenxin resume` is idempotent: each phase checks `state.json` and skips
what's already done.

### 4.6 `attempt_state.py` (breaking change)

Delete the stdin-based `attempt-state record` CLI entry point. Attempt records
are only written by the orchestrator as a side effect of successful execution.

Rationale: allowing arbitrary payloads via stdin means any agent can forge
history. The single source of truth for attempt records is the production
orchestrator.

### 4.7 PromptPackage boundary tightening

`prompt-forge/internals/prompt_package.py` rejects packages containing
execution-state fields. Add to the rejection list:

- `profile_id`, `profile`, `workflow_profile`
- `camera`, `view`, `lens`, `composition`
- `lora`, `lora_stack`, `loras`
- `model`, `checkpoint`

These belong in execution drafts and manifests, not in PromptPackage. The
PromptPackage is an offline creative artifact — it never knows how or where
it will be executed.

## 5. Data flow and run_dir contract

### 5.1 End-to-end flow

```
prompt-forge  →  PromptPackage.json
                       │
                       ▼
              chenxin run character-base
                1. doctor / preflight
                2. validate package
                3. spawn MCP bridge
                4. capability report
                5. build execution draft
                6. write run_dir, state=awaiting_approval
                       │
                       ▼  (human reads approval_summary.md)
              chenxin approve <run_dir>
                7. write approval.event.json (plan_hash bound)
                       │
                       ▼
              chenxin resume <run_dir>
                8. verify approval event
                9. consume approval (one-shot)
               10. enqueue to ComfyUI
               11. poll queue / history
               12. download + verify artifact
               13. write manifest
               14. append attempt record
               15. write result.json, state=done
```

### 5.2 run_dir contents

```
run-<timestamp>/
  state.json              # { phase, error_code?, error_detail?, started_at, updated_at }
  draft.json              # execution draft + plan_hash
  approval_summary.md     # human-readable approval brief
  approval.event.json     # written by `chenxin approve`
  consumption.json        # one-shot consumption receipt
  result.json             # final: artifact_path, sha256, profile_id, prompt_id, ...
  manifest.json           # artifact metadata (from existing result_manifest.py)
  logs/
    mcp_receipt.json      # McpBridge.receipt() — hash-based audit trail
    comfy_history.json    # raw history item from ComfyUI
```

### 5.3 State machine

```
pending ──run──▶ drafting ──▶ awaiting_approval ──approve──▶ approved
                                                    │
                                     (resume without approval → fail: no_approval)
approved ──resume──▶ running ──success──▶ done
                       │
                       └──fail──▶ failed (with error_code + detail)
```

All state transitions recorded in `state.json`. Resume is idempotent at each
phase boundary.

## 6. Security surface

### 6.1 Trusted vs untrusted

**Trusted:**
- CLI-spawned `comfyui-mcp` stdio child (signed npm package)
- Bundled fixed workflow assets (release assets, hash-verified at install)
- ComfyUI REST read endpoints (`system_stats`, `object_info`, `queue`)

**Untrusted:**
- Any string passed by the agent / caller
- PromptPackage content (validated, but not trusted for schema)
- Files in run_dir that the agent could have modified

**Semi-trusted (explicit, auditable):**
- `approval.event.json` — agent can write it via `chenxin approve`, but the
  action is explicit and plan_hash-bound. It shows up in audit trails.

### 6.2 Deleted bypass surfaces

These public interfaces are REMOVED, not deprecated:

1. `build_capability_report(workflow_tools=...)` — dict injection vector
2. Local-only fixed-asset validation paths — would bypass MCP
3. `attempt-state record` stdin CLI — history forgery vector
4. In-process `approve_execution_draft()` direct call pattern (orchestrator
   is the only caller, and it reads approval from disk)

### 6.3 Residual risk

On a single machine where the agent has full shell access, there is no
cryptographic way to prevent self-approval. The design treats this honestly:

- Approval is **explicit and auditable**, not cryptographically enforced.
- This matches the real-world pattern of CI/CD gated deploys: the gate exists
  so people see what's being deployed and can stop it, not because the system
  can prevent a determined insider.
- `attempts.jsonl` plus `approval_summary.md` provide the audit trail.
- If stronger enforcement is needed later (e.g., a remote approval server),
  the two-phase architecture supports it — the `approve` command can be
  replaced without changing the rest of the system.

## 7. Failure modes and exit codes

| Code | Name | Trigger | Remediation in output |
|------|------|---------|----------------------|
| 0 | success | Normal completion | — |
| 1 | general_error | Catch-all unexpected | stack trace + report bug |
| 2 | comfyui_unreachable | ComfyUI down | "Start ComfyUI at http://127.0.0.1:8188" |
| 3 | mcp_unavailable | MCP server won't start or missing tools | Exact missing tool + "run `chenxin doctor`" |
| 4 | invalid_package | PromptPackage fails schema | Exact field + "regenerate with prompt-forge" |
| 5 | asset_mismatch | Bundled workflow asset hash mismatch | "Re-run `scripts/install.ps1`" |
| 6 | capability_insufficient | Workflow candidates unavailable | reason_codes + remediation |
| 7 | no_approval | Resume without approval event | "Run `chenxin approve` after reviewing summary" |
| 8 | approval_stale | plan_hash mismatch between draft and approval | "Draft changed — re-approve" |
| 9 | comfyui_queue_failed | ComfyUI execution failed | ComfyUI error + prompt_id |
| 10 | artifact_verification_failed | PNG corrupt or sha256 mismatch | Detail + "retry with `chenxin resume`" |

All failures update `state.json` with `phase: failed`, `error_code`,
`error_detail`, and `updated_at`.

## 8. Testing strategy

### 8.1 Unit tests

- `test_mcp_spawn.py` — mock stdio server, test:
  - Successful handshake returns McpBridge with right tools
  - Missing required tools → structured error
  - Timeout on initialize → structured error
  - Timeout on tools/list → structured error
- `test_capabilities_bridge_required.py` — test:
  - Passing `workflow_tools=dict` → TypeError (interface deleted)
  - Passing mock bridge → report built correctly
  - Bridge missing tools → McpBridgeError before report builds
- `test_approval_state_machine.py` — test each transition:
  - run → awaiting_approval (happy path)
  - resume without approval → exit 7
  - approve + resume → approved → running → done
  - approve, modify draft, resume → exit 8 (stale approval)
  - resume twice → idempotent (no double enqueue)
- `test_prompt_package_boundary.py` — test:
  - Package with `profile_id` → rejected
  - Package with `camera.view` → rejected
  - Package with `lora` → rejected
  - Clean package → accepted

### 8.2 Integration tests (mock ComfyUI)

- `test_doctor_happy_path.py` — `chenxin doctor` exits 0 with mock MCP + mock ComfyUI
- `test_run_awaiting_approval.py` — run produces draft + summary + state
- `test_approve_then_resume_fails_cleanly.py` — resume with mock ComfyUI failure → state=failed, right error code

### 8.3 Manual end-to-end (one time, not in CI)

- Real anima base + prompt-forge package → `run → approve → resume` → PNG output
- Tamper with draft after approval → confirm exit 8
- Stop ComfyUI → confirm doctor reports code 2 with clear message

### 8.4 Not tested

- `comfyui-mcp` internal behavior (upstream responsibility)
- Agent compliance with SKILL.md (process / audit question, not code test)

## 9. What's out of scope (for future specs)

- D / stable path identity (COMFYUI_CHENXIN_HOME)
- F / runbook rewrite + SKILL.md simplification
- G / content_mode (NSFW) modeling
- H / cross-attempt resume optimization
- I / delivery fallback (chenxin open)
- Stages 2/3/4 (multiview, shot, video) — only character-base in this slice

## 10. Migration plan

There is no migration. Old interfaces are deleted.

Users currently relying on `workflow_tools=dict` injection or
`attempt-state record` stdin will need to move to the CLI interface.
The plugin version number gets a breaking-change bump.
