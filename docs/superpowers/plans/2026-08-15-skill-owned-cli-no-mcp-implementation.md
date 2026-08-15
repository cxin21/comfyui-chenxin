# Skill-Owned CLI and MCP-Free Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Skill independently callable through its own CLI and remove MCP as a runtime dependency, while preserving the existing authoring, validation, fixed-workflow, provenance, and artifact guarantees.

**Architecture:** Prompt skills own their author/audit/catalog CLIs. Camera skills own their describe/validate/run CLIs and use a neutral direct ComfyUI HTTP transport. No central registry or MCP bridge is required for production execution; optional integrations, if ever added, must wrap these CLIs without changing their contracts.

**Tech Stack:** Python 3.10+, setuptools console scripts, stdlib JSON/HTTP/SQLite, existing `tokenizers` dependency for H3, pytest, fixed ComfyUI API workflows and SHA-256 manifests.

**Spec:** `docs/superpowers/specs/2026-08-15-skill-owned-cli-no-mcp-design.md`

## Global Constraints

- CLI stdout is machine-readable JSON when `--json` is provided; diagnostics go to stderr.
- Exit codes are `0` success, `2` request/argument error, `3` validation failure, `4` asset/catalog integrity failure, `5` ComfyUI runtime failure, `70` unexpected failure.
- No Skill package may depend on `comfyui-chenxin-mcp`.
- Prompt scripts never replace semantic authoring by the Skill LLM.
- Camera workflows remain fixed and fail closed.
- User facts, locked content, provenance, unknowns, inferred values, and diagnostics remain separate.
- Do not edit the managed plugin cache directly; reinstall from the source tree after implementation.

---

### Task 1: Freeze the standalone CLI protocol

**Files:**
- Create: `docs/cli-protocol.md`
- Create: `tests/cli_protocol/README.md`
- Create: `skills/anima-prompt-v1/anima_prompt_v1/cli_protocol.py`
- Create: `skills/minimax-h3-prompt/h3_prompt/cli_protocol.py`
- Create: `skills/camera-image/camera_image/cli_protocol.py`
- Create: `skills/camera-video/camera_video/cli_protocol.py`
- Create: `skills/camera-multiview/camera_multiview/cli_protocol.py`
- Modify: `docs/superpowers/specs/2026-08-15-skill-owned-cli-no-mcp-design.md`
- Test: `tests/cli_protocol/test_protocol_examples.py`

**Interfaces:**
- Produces the shared JSON envelope, exit-code table, request-file/stdin rules, and stderr rules used by every Skill CLI. The contract is shared, but each Skill owns an internal stdlib implementation so no central protocol package is required.

- [x] **Step 1: Write failing protocol tests**

Test that a successful JSON response contains `ok`, `command`, `stage`, `result`, `errors`, and `advisories`, and that error exit codes are distinct from JSON content errors.

- [x] **Step 2: Run the protocol tests**

Run: `python -m pytest tests/cli_protocol -q`

Expected: FAIL because the standalone CLI fixtures do not exist.

- [x] **Step 3: Add the Skill-owned protocol modules**

Create the same small stdlib-only module inside each Skill package with `emit_success()`, `emit_failure()`, `load_json_request()`, `exit_code_for_error()`, and `write_json()`; do not import another Skill or any MCP module.

- [x] **Step 4: Run the protocol tests again**

Run: `python -m pytest tests/cli_protocol -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/cli-protocol.md tests/cli_protocol
git commit -m "feat(cli): freeze standalone JSON and exit-code protocol"
```

### Task 2: Extract the Anima CLI from the existing package

**Files:**
- Create: `skills/anima-prompt-v1/anima_prompt_v1/cli.py`
- Modify: `skills/anima-prompt-v1/pyproject.toml`
- Modify: `skills/anima-prompt-v1/anima_prompt_v1/catalog/cli.py`
- Modify: `skills/anima-prompt-v1/scripts/search_catalog.py`
- Modify: `skills/anima-prompt-v1/scripts/submit_relations.py`
- Test: `skills/anima-prompt-v1/tests/test_cli.py`
- Test: `skills/anima-prompt-v1/tests/test_catalog_cli.py`

**Interfaces:**
- `anima-prompt-v1 author --request FILE --json` consumes a serialized `PromptBrief` request and produces `PromptOutput` plus phase metadata.
- `anima-prompt-v1 inspect --draft FILE --brief FILE --json` produces read-only inspection issues.
- `anima-prompt-v1 catalog search|related|browse|stats|build|export|verify` wraps the existing Catalog APIs.
- `anima-prompt-v1 relation submit|list|accept|reject` wraps relation validation and overlay status changes.
- Existing `anima-catalog` remains an alias to the new Catalog command surface.

- [x] **Step 1: Write CLI contract tests for author, catalog, inspect, and relations**

Use the existing fixture Catalog and relation payloads. Assert exact prompt output fields, provenance outside prompt text, fuzzy-hit labeling, candidate-only relation persistence, and stable error exit codes.

- [x] **Step 2: Run the new Anima CLI tests**

Run: `python -m pytest skills/anima-prompt-v1/tests/test_cli.py skills/anima-prompt-v1/tests/test_catalog_cli.py -q`

Expected: FAIL because no unified CLI exists.

- [x] **Step 3: Implement the CLI dispatcher**

Route each subcommand to existing public APIs. Keep semantic Brief construction outside the CLI; reject raw text as an authoritative author request.

- [x] **Step 4: Add console scripts**

Declare `anima-prompt-v1` and retain `anima-catalog` as an alias in `pyproject.toml`.

- [x] **Step 5: Run the CLI and package tests**

Run: `python -m pytest skills/anima-prompt-v1/tests -q`

Expected: PASS, with the pre-existing test suite unchanged.

- [ ] **Step 6: Commit**

```bash
git add skills/anima-prompt-v1
git commit -m "feat(anima): expose standalone authoring and catalog CLI"
```

### Task 3: Complete and expose the H3 CLI

**Files:**
- Create: `skills/minimax-h3-prompt/h3_prompt/cli.py`
- Create: `skills/minimax-h3-prompt/h3_prompt/audit.py`
- Modify: `skills/minimax-h3-prompt/h3_prompt/t2va.py`
- Modify: `skills/minimax-h3-prompt/h3_prompt/ref2va.py`
- Modify: `skills/minimax-h3-prompt/h3_prompt/common.py`
- Modify: `skills/minimax-h3-prompt/h3_prompt/token_counting.py`
- Modify: `skills/minimax-h3-prompt/pyproject.toml`
- Test: `skills/minimax-h3-prompt/tests/test_cli.py`
- Test: `skills/minimax-h3-prompt/tests/test_budget_cli.py`

**Interfaces:**
- `minimax-h3-prompt author --stage t2va|ref2va --request FILE --json` returns text, findings, advisories, and verified budget metadata.
- `minimax-h3-prompt audit --stage ... --request FILE --json` runs temporal, dialogue, audio, and reference audits without authoring.
- `minimax-h3-prompt tokenizer verify` verifies the bundled snapshot.
- `minimax-h3-prompt count` counts exact H3 context tokens.
- `minimax-h3-prompt context-plan` returns visual/chat/safety/effective limits.

- [ ] **Step 1: Write failing tests for all H3 commands**

Cover t2va, ref2va, malformed shots, invalid Picture ownership, exact dialogue, tokenizer hash failure, and context overflow.

- [ ] **Step 2: Run the H3 CLI tests**

Run: `python -m pytest skills/minimax-h3-prompt/tests -q`

Expected: FAIL because the CLI and budget wiring are missing.

- [ ] **Step 3: Implement the CLI and audit facade**

Reuse the existing `FactLedger`, `parse_shots`, `audit_*`, `TokenCounter`, and `plan_h3_context` functions. Do not duplicate validation rules in argument parsing.

- [ ] **Step 4: Wire exact context planning into author output**

For ref2va, load the verified tokenizer and reference dimensions before returning `verified=true`. For t2va, preserve the current no-reference path and report that visual budget is not applicable.

- [ ] **Step 5: Add the console script and run tests**

Run: `python -m pytest skills/minimax-h3-prompt/tests -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/minimax-h3-prompt
git commit -m "feat(h3): expose authoring audit and exact budget CLI"
```

### Task 4: Implement neutral direct ComfyUI HTTP transport

**Files:**
- Create: `runtime/comfyui_http/pyproject.toml`
- Create: `runtime/comfyui_http/comfyui_http/client.py`
- Create: `runtime/comfyui_http/comfyui_http/errors.py`
- Create: `runtime/comfyui_http/comfyui_http/protocol.py`
- Test: `runtime/comfyui_http/tests/test_client.py`
- Test: `runtime/comfyui_http/tests/test_protocol.py`

**Interfaces:**
- `ComfyUIClient.health() -> dict`
- `ComfyUIClient.upload_image(path: Path) -> UploadedFile`
- `ComfyUIClient.enqueue(workflow: dict) -> str`
- `ComfyUIClient.history(prompt_id: str) -> dict`
- `ComfyUIClient.get_artifact(filename: str, subfolder: str, artifact_type: str) -> bytes`
- `ComfyUIClient.wait_for_success(prompt_id: str, timeout: float, poll_interval: float) -> dict`

- [ ] **Step 1: Write HTTP contract tests with a fake HTTP server**

Test JSON decoding, upload filename parsing, 404 history polling, artifact bytes, timeout, and typed error mapping.

- [ ] **Step 2: Run the transport tests**

Run: `python -m pytest runtime/comfyui_http/tests -q`

Expected: FAIL because the transport package does not exist.

- [ ] **Step 3: Implement the stdlib HTTP client**

Use `urllib.request` and deterministic JSON/bytes handling. Never invoke `npx`, `node`, MCP JSON-RPC, or shell commands.

- [ ] **Step 4: Run the transport tests**

Run: `python -m pytest runtime/comfyui_http/tests -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runtime/comfyui_http
git commit -m "feat(runtime): add direct ComfyUI HTTP transport"
```

### Task 5: Decouple camera-image from MCP

**Files:**
- Create: `skills/camera-image/camera_image/cli.py`
- Create: `skills/camera-image/camera_image/runtime/runner.py`
- Create: `skills/camera-image/camera_image/runtime/ui_to_api.py`
- Modify: `skills/camera-image/camera_image/runtime/source_workflow.py`
- Modify: `skills/camera-image/camera_image/runtime/lora_resolver.py`
- Modify: `skills/camera-image/pyproject.toml`
- Modify: `skills/camera-image/SKILL.md`
- Test: `skills/camera-image/tests/test_cli.py`
- Test: `skills/camera-image/tests/test_ui_to_api.py`
- Test: `skills/camera-image/tests/test_lora_inventory.py`

**Interfaces:**
- `camera-image describe --stage t2i-camera|i2i-camera --json`
- `camera-image validate --stage ... --envelope FILE --config FILE --json`
- `camera-image run --stage ... --envelope FILE --config FILE --output-dir DIR --json`
- `camera-image assets verify --stage ... --json`

- [ ] **Step 1: Write failing tests for describe/validate/run**

Use fake ComfyUI transport and the fixed workflow asset. Assert prompt patching, camera mapping, i2i reference requirements, controlnet dependencies, artifact hashes, and no MCP import.

- [ ] **Step 2: Implement local UI-to-API conversion**

Replace the upstream `strip_workflow` call with a local converter whose output is validated by `validate_api_graph`. The converter must preserve the current fixed asset and node values exactly.

- [ ] **Step 3: Implement local LoRA inventory resolution**

Use an explicit local LoRA root or verified inventory file. Default stack remains available without inventory; custom names fail with a typed input error when inventory is unavailable or ambiguous.

- [ ] **Step 4: Implement the camera-image runner and CLI**

Compose upload, graph preparation, local validation, direct enqueue, history polling, and artifact download. Preserve existing run-record fields and add transport/runtime status.

- [ ] **Step 5: Remove the MCP dependency and run tests**

Run: `python -m pytest skills/camera-image/tests -q`

Expected: PASS with no import of `comfyui_chenxin_mcp`.

- [ ] **Step 6: Commit**

```bash
git add skills/camera-image
git commit -m "refactor(camera-image): run independently through direct HTTP"
```

### Task 6: Decouple camera-video and camera-multiview from MCP

**Files:**
- Create: `skills/camera-video/camera_video/cli.py`
- Create: `skills/camera-video/camera_video/runtime/runner.py`
- Create: `skills/camera-multiview/camera_multiview/cli.py`
- Create: `skills/camera-multiview/camera_multiview/runtime/runner.py`
- Modify: `skills/camera-video/camera_video/runtime/source_workflow.py`
- Modify: `skills/camera-multiview/camera_multiview/runtime/source_workflow.py`
- Modify: both camera `pyproject.toml` files
- Modify: both camera `SKILL.md` files
- Test: `skills/camera-video/tests/test_cli.py`
- Test: `skills/camera-multiview/tests/test_cli.py`

**Interfaces:**
- `camera-video describe|validate|run --stage t2v-video|i2v-video|multi-i2v-video`
- `camera-multiview describe|validate|run|assets verify --stage multiview`

- [ ] **Step 1: Write fake-transport tests**

Assert fixed video node patching, duration/reference stage requirements, fixed multiview node `111`/`667` patching, 13 pose hydration, all-artifact download, and manifest failure behavior.

- [ ] **Step 2: Implement video runner**

Use the shared neutral HTTP transport while retaining each stage's fixed manifest and API workflow checks.

- [ ] **Step 3: Implement multiview runner**

Use the shared neutral HTTP transport while retaining pose reuse, pose hashes, fixed graph validation, and all-artifact output.

- [ ] **Step 4: Run both test suites**

Run: `python -m pytest skills/camera-video/tests skills/camera-multiview/tests -q`

Expected: PASS with no MCP imports.

- [ ] **Step 5: Commit**

```bash
git add skills/camera-video skills/camera-multiview
git commit -m "refactor(camera): expose independent video and multiview CLIs"
```

### Task 7: Remove MCP registration and installer coupling

**Files:**
- Delete: `mcp_server/` after all replacement tests pass
- Modify: `scripts/install.ps1`
- Modify: `scripts/install.sh`
- Modify: `scripts/stage_release.py`
- Modify: `scripts/verify_release.py`
- Modify: `.codex-plugin/plugin.json`
- Delete or replace: `.mcp.json`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `docs/MCP_BRIDGE.md`
- Modify: `docs/USAGE.md`
- Test: `scripts/test_release.py`

**Interfaces:**
- Installer installs five independent Skill packages and the neutral HTTP transport.
- Installer does not write `config.toml`, does not install MCP, and does not require a Codex restart.
- Release verification checks every CLI entry point and rejects any production dependency on `comfyui_chenxin_mcp`.

- [ ] **Step 1: Write release tests**

Assert no MCP config mutation, all console scripts exist, staged assets include each Skill and exclude `mcp_server`, and `rg` finds no MCP import in production packages.

- [ ] **Step 2: Update installer and staging**

Remove MCP block editing and replace package installation with explicit independent package installs plus CLI smoke checks.

- [ ] **Step 3: Update docs and plugin metadata**

Document Skill-local CLI invocation and direct ComfyUI URL configuration. Remove MCP as a required flow.

- [ ] **Step 4: Run release verification**

Run: `python scripts/verify_release.py --source-root .`

Expected: PASS with all five Skill packages and no MCP production path.

- [ ] **Step 5: Commit**

```bash
git add scripts .codex-plugin README.md README.en.md docs
git commit -m "refactor(plugin): remove MCP runtime dependency"
```

### Task 8: End-to-end installed-cache verification

**Files:**
- Modify: `scripts/verify_release.py`
- Create: `scripts/smoke_cli.py`
- Test: `tests/e2e/test_installed_cli.py`
- Test: `tests/e2e/fixtures/`

**Interfaces:**
- Smoke runner invokes each installed command from a staged release, not the source checkout.
- Prompt smoke cases use Anima and H3 structured requests.
- Camera smoke cases use fake ComfyUI HTTP server and fixed assets.

- [ ] **Step 1: Add staged-release smoke cases**

Verify command discovery, JSON output, exit codes, provenance/advisories, fixed asset checks, and absence of MCP modules.

- [ ] **Step 2: Run the complete validation suite**

Run: `python -m pytest skills/anima-prompt-v1/tests skills/minimax-h3-prompt/tests skills/camera-image/tests skills/camera-video/tests skills/camera-multiview/tests runtime/comfyui_http/tests tests/e2e -q`

Expected: PASS.

- [ ] **Step 3: Build and stage the release**

Run: `python scripts/stage_release.py --source-root . --destination-root <temp-release>`.

- [ ] **Step 4: Run staged CLI smoke tests**

Run: `python scripts/smoke_cli.py --release-root <temp-release>`.

Expected: every Skill command exits successfully for valid fixtures and fails closed for invalid assets/configs.

- [ ] **Step 5: Commit**

```bash
git add scripts tests docs
git commit -m "test: verify installed skill-owned CLI release"
```

## Final verification gate

- [ ] `rg -n "comfyui_chenxin_mcp|mcp_server|McpClient" skills runtime scripts` returns no production dependency.
- [ ] All five packages expose their own console script.
- [ ] Prompt/Catalog/H3 run without ComfyUI and without MCP.
- [ ] Camera runs use direct HTTP and do not spawn `npx` or JSON-RPC.
- [ ] Anima output keeps exact five fields and relation submission remains post-authoring.
- [ ] H3 exact tokenizer integrity and budget checks are observable from CLI.
- [ ] Camera fixed assets and artifact hashes remain verified.
- [ ] Installer does not modify Codex configuration.
- [ ] Source and staged-release tests pass.
