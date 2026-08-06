# Camera Workflow Config Provider Design

## Status

Design approved in conversation on 2026-08-05. This document redesigns the
`character-video-pipeline` camera workflow boundary so normal generation does
not read or expose the complete ComfyUI workflow.

## Problem and first-principles diagnosis

The current runtime treats the complete UI/API workflow graph as the common
input for discovery, configuration, patching, planning, and submission. That
creates three failures:

1. Workflow asset management, business configuration, and execution are
   coupled.
2. Every request pays the cost of reading large UI/API graphs, even when the
   user only wants to inspect or change a few fields.
3. The agent is forced to reason about node topology, links, and conversion
   details that should remain runtime-owned.

The observed session repeatedly listed workflows, fetched UI/API graphs,
stripped and normalized the graph, and then retried tool calls until the host
returned HTTP 429. This is an architectural retry amplifier, not merely a
transient transport problem.

## Goals

- Bundle a fixed camera-view text-to-image workflow synchronized from the
  current ComfyUI installation.
- Preserve both the UI workflow and executable API workflow in the bundle.
- Make normal runtime calls use the bundled workflow instead of rereading the
  current ComfyUI workflow.
- Expose only business-level configurable properties to the agent.
- Treat the LoRA Loader and TriggerWord Toggle as one atomic configuration
  unit.
- Query local LoRAs through MCP, filter and recommend compatible choices, and
  require approval before selection affects execution.
- Keep approval, one-time consumption, hashes, history verification, artifact
  verification, and RunRecords.
- Define a provider boundary that can later be implemented by a local service
  without changing the agent-facing protocol.

## Non-goals

- Supporting arbitrary user-supplied workflow graphs during normal execution.
- Allowing the agent to patch arbitrary node IDs or links.
- Automatically changing the saved ComfyUI workflow.
- Introducing a separate local service in the first implementation phase.
- Redesigning Flux or LTX workflow configuration in this phase.

## Architecture

### Versioned workflow pack

The skill owns a versioned workflow pack:

```text
skills/character-video-pipeline/runtime/workflow_packs/
└── camera-anima-v1/
    ├── pack.json
    ├── ui-workflow.json
    ├── api-workflow.json
    ├── manifest.json
    └── config-surface.json
```

`ui-workflow.json` is retained for semantic configuration, group membership,
LoRA Manager structure, PNG metadata, diagnostics, and rollback evidence.
`api-workflow.json` is the immutable execution base and is patched only by
runtime-owned allowlisted adapters.

`pack.json` identifies the pack, stage, source workflow, version, and asset
files. `manifest.json` contains the UI fingerprint, API graph hash, immutable
topology hash, config-surface hash, profile hash, and node bindings. It does
not contain a second copy of the complete graph.

### Provider boundary

The first implementation uses an in-process provider:

```python
class CameraWorkflowProvider(Protocol):
    def get_workflow_info(self, workflow_id: str) -> dict: ...
    def get_config(self, workflow_id: str, fields: list[str] | None = None) -> dict: ...
    def patch_config(self, workflow_id: str, request: dict) -> dict: ...
    def list_loras(self, workflow_id: str) -> dict: ...
    def recommend_loras(self, workflow_id: str, intent: dict) -> dict: ...
    def build_execution(self, workflow_id: str, config: dict) -> dict: ...
    def submit(self, execution: dict) -> dict: ...
```

The provider loads the fixed pack, projects configuration, applies patches,
builds the executable graph, and submits through the existing local transport.
The agent receives metadata, configuration projections, patch summaries, and
execution receipts, not the complete graph.

The future service implementation exposes the same operations over a local
HTTP, named-pipe, or Unix-socket boundary. The provider is the only component
that changes.

## Workflow synchronization

Full workflow reads are restricted to explicit maintenance operations:

```text
sync-workflow-pack
refresh-workflow-pack
verify-workflow-pack
```

Synchronization reads the current ComfyUI UI workflow, derives or validates
the API workflow, records conversion evidence, derives the manifest and config
surface, and writes a new versioned pack. Normal generation never invokes
`get_workflow` for the current ComfyUI library.

The runtime may check ordinary ComfyUI reachability, model availability, queue
state, and LoRA inventory. These checks do not require rereading the complete
workflow.

## Configuration surface

`config-surface.json` describes business fields and their validation rules. It
does not expose arbitrary node inputs.

### Prompts

- `prompts.positive`: required text, mapped to the positive prompt slot.
- `prompts.negative`: required text, mapped to the negative prompt slot.

Prompt prose is never silently rewritten by the production consumer.

### Reference image

`reference_image` is empty for character-base and required for shot-image. It
must refer to an accepted artifact, not an arbitrary local path. Its content
hash participates in lineage.

### Anima camera controls

The camera slot exposes only allowlisted fields:

- direction: front, back, left, right;
- elevation: high-angle, eye-level, low-angle;
- distance: full_body, medium;
- roll: bounded numeric value.

Stage 1 uses a neutral pinned default. Stage 3 can use shot-directed values.

### Anima camera extra

The extra slot is represented by structured sections for extreme, lens, depth
of field, movement, composition, and style. Each section has an enabled flag
and validated values. Disabled sections cannot contribute stale values.

### Fast Groups

The two `Fast Groups Bypasser` structures are exposed as high-level group
states, not raw node modes:

- G1: base or img2img;
- G2: saved, disabled, or selected-effects.

The manifest owns the exact member lists. A group patch is transactional,
changes all members, excludes nodes owned by other config slots, and verifies
the output path. Partial member toggles are rejected.

### LoRA unit

The LoRA Loader and TriggerWord Toggle form one atomic slot. The business
configuration contains a base model and structured selections with name,
model strength, clip strength, active state, and trigger words.

Runtime deterministically derives:

- loader stack text and structured list for the LoRA Loader;
- trigger-word table and concatenated trigger text for TriggerWord Toggle.

The following invariants are mandatory:

1. Loader and TriggerWord Toggle are patched together or neither is patched.
2. Active trigger words equal the ordered union of active LoRA selections.
3. Inactive LoRAs contribute no active trigger words.
4. Stack text and structured selections round-trip deterministically.
5. Every selected LoRA exists in the current inventory.

## LoRA discovery and recommendation

The flow is:

```text
read base model from fixed pack
  → MCP list_local_models
  → canonical inventory and inventory_hash
  → compatibility filtering
  → deterministic recommendation
  → user selection
  → approval
  → atomic LoRA patch
```

Compatibility evidence is prioritized as follows:

1. readable model metadata;
2. model-family directory;
3. filename keywords.

Recommendations include score, reasons, compatibility evidence, trigger words,
inventory hash, and recommendation hash. Recommendation is not selection, and
selection is not approval.

Inventory results may be cached for a bounded validity period. A stale or
changed inventory must be refreshed before execution.

## Configuration protocol

Configuration reads return a bounded projection:

```json
{
  "workflow_id": "camera-anima-v1",
  "revision": "...",
  "config": {},
  "config_hash": "..."
}
```

Configuration changes use optimistic concurrency:

```json
{
  "workflow_id": "camera-anima-v1",
  "expected_revision": "...",
  "patch": {
    "prompts.positive": "...",
    "camera.direction": "front",
    "groups.g1.mode": "base",
    "lora.selections": []
  }
}
```

The runtime validates field ownership, value domains, cross-field rules, stage
rules, revision, and LoRA inventory before producing a new `StageConfig` and
`config_hash`. A revision mismatch never overwrites state; it requires a fresh
bounded configuration read.

## Execution state machine

```text
IDLE
  → WORKFLOW_RESOLVED
  → CONFIG_READ
  → LORA_INVENTORIED
  → LORA_RECOMMENDED
  → CONFIG_DRAFTED
  → AWAITING_APPROVAL
  → APPROVED
  → CONSUMED
  → EXECUTION_BUILT
  → SUBMITTED
  → HISTORY_VERIFIED
  → ARTIFACT_VERIFIED
  → RECORDED
```

Only `EXECUTION_BUILT` loads and patches the bundled API graph, and that graph
remains inside the runtime boundary. The final evidence contains workflow-pack
hash, config hash, executable graph hash, request hash, prompt ID, artifact
hash, lineage, and RunRecord data.

Approval displays business changes and hashes, not a full graph. Existing
approval and one-time consumption semantics remain mandatory.

## Failure and retry policy

The runtime fails closed on missing pack files, hash drift, invalid config
surface, stale revision, stale LoRA inventory, unavailable selected LoRA,
partial LoRA-unit patch, group topology violation, capability mismatch, or
history/artifact mismatch.

Retries are bounded and operation-specific. Idempotent inventory or metadata
reads may retry within a small budget. Full workflow discovery is never an
automatic retry fallback. An uncertain enqueue is resolved through server
state and retained enqueue intent, never by blindly submitting again.

## Migration from current runtime

The current `workflow_discovery` complete-graph path becomes maintenance-only.
Normal stage planning and submission move from caller-supplied
`source_api_graph` and `ui_workflow` to `workflow_id`, bounded config evidence,
and a provider-generated execution artifact.

The existing `config_surface.py`, LoRA discovery, adapter patching, approval,
consumption, history, and RunRecord logic should be retained where compatible,
but their public boundary must stop requiring the complete graph from callers.

## Testing strategy

- Pack tests: file presence, hash consistency, immutable topology, missing-pack
  failure, and no normal-path `get_workflow` call.
- Projection tests: only declared fields are readable or patchable; unknown
  fields and stale revisions fail.
- Camera tests: allowlists, neutral Stage 1 defaults, and Stage 3 controls.
- Group tests: complete member toggles, protected node exclusions, and path
  proof.
- LoRA tests: inventory membership, compatibility filtering, recommendation
  determinism, stack/trigger round-trip, and atomic two-node patching.
- Provider contract tests: the same suite must pass for the in-process provider
  and the future local-service provider.
- Execution tests: approval, one-time consumption, executable graph hash,
  enqueue intent, history, artifact, and RunRecord lineage.

## Acceptance criteria

1. A normal camera generation performs no full current-workflow read.
2. Agent-visible payloads contain no complete UI/API graph.
3. All requested camera, prompt, image, group, and LoRA settings are exposed
   through one validated configuration surface.
4. LoRA recommendations are based on a fresh, hashed local inventory and are
   approval-gated.
5. LoRA Loader and TriggerWord Toggle cannot diverge.
6. Any final execution can be proven against the fixed workflow pack, config
   hash, executable graph hash, history, artifact, and RunRecord.
7. Replacing the in-process provider with a local service does not change the
   agent-facing request or response schemas.
