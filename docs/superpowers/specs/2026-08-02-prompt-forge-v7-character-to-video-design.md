# Prompt Forge v7 — Character-to-Video Production Loop

**Date:** 2026-08-02
**Status:** approved design
**Target environment:** ComfyUI `0.29.0` at `http://127.0.0.1:8188`, RTX 4060 Laptop GPU, 8 GB VRAM, `comfyui-mcp 0.49.0`

## 1. First-principles decision

The product is not a collection of prompts or a fixed ComfyUI graph. It is a
controlled production loop that preserves character identity while moving from
an abstract character brief to a rendered video shot:

```text
character intent
  -> front-facing base image
  -> multi-angle character sheet
  -> concrete camera shot
  -> directed LTX video clip
```

Prompt Forge owns semantics, model-specific prompt compilation, authority and
auditability. `comfyui-mcp` owns ComfyUI discovery, workflow conversion,
validation, execution, history and asset provenance. The project must not
reimplement capabilities already supplied by `comfyui-mcp`.

Every stage consumes an immutable artifact from the preceding stage and emits a
new versioned artifact. No stage silently edits a previous artifact or the
user's saved workflow.

## 2. Four knowledge quadrants

Every production run starts with a `TaskContext`:

```json
{
  "schema_version": "1.0",
  "shared_known": {
    "goal": "",
    "background": [],
    "acceptance": [],
    "boundaries": []
  },
  "user_known_agent_unknown": {
    "references": [],
    "aesthetic_preferences": [],
    "real_world_constraints": []
  },
  "agent_known_user_unknown": {
    "capabilities": [],
    "risks": [],
    "alternatives": []
  },
  "shared_unknown": {
    "hypotheses": [],
    "experiments": []
  }
}
```

Rules:

1. Do not ask again for values already present in `shared_known`.
2. Ask at most three questions only when an unknown would materially change an
   artifact, workflow choice or safety boundary.
3. State non-material assumptions and continue with an exploratory version.
4. Expose capability limits and safer alternatives instead of hiding them.
5. Convert shared unknowns into falsifiable experiments with one changed
   variable and explicit success/failure signals.

## 3. Scope

### v7 production scope

1. Compile an excellent Anima positive and negative prompt.
2. Generate a front-facing character base image with
   `文生图相机视角.json`.
3. Generate a multi-angle character sheet with
   `Flux2-Klein人物一键多视图工作流.json`.
4. Compile a shot-specific Anima positive and negative prompt.
5. Enable the `加载图片（G1）` image-to-image path in
   `文生图相机视角.json` and generate a concrete shot image.
6. Insert the shot image and a video prompt into `YusuLTXDirector` in
   `LTX全新导演台工作流.json` and generate an LTX video.
7. Preserve complete lineage from source intent to final clip.

### Non-goals

- Automatic model or custom-node installation.
- Editing the user's saved workflows in place.
- Paid API nodes without a separate explicit approval.
- General-purpose ComfyUI workflow authoring.
- Manga orchestration, subtitles, final editing or publishing.
- Claiming aesthetic superiority without rendered comparisons.

## 4. Runtime architecture

```text
TaskContext
  -> PromptIntent
  -> PromptBuild
  -> CapabilityReport
  -> WorkflowCandidate[]
  -> ExecutionPlan
  -> comfyui-mcp adapter
  -> ComfyUI
  -> ArtifactVerifier
  -> RunRecord
```

### 4.1 Pure compiler boundary

Prompt Forge remains side-effect-free. It may return
`execution.requested=true`, but always returns `execution.performed=false`.
Execution starts only after a separate `ExecutionPlan` passes preflight and the
current user request explicitly authorizes generation.

### 4.2 Adapter boundary

The adapter negotiates actual tool availability at runtime. It must not assume
that a tool exists merely because a tool name is documented. The desired
`comfyui-mcp` capabilities are:

- workflow library listing and loading;
- UI-to-API conversion, strip and slice;
- workflow runtime classification and validation;
- image upload;
- workflow enqueue and job monitoring;
- output asset and metadata retrieval;
- history and generation-setting inspection.

If an expected MCP capability is unavailable, the adapter may use a minimal
read-only REST fallback for health, `/object_info`, queue and history. It must
not implement its own general UI-workflow converter.

### 4.3 Prompt quality gates

"Excellent prompt" is an acceptance contract, not a subjective label.

An Anima PromptBuild passes only when:

- all explicit character and shot facts are represented and locked;
- semantic tags resolve by exact or approved alias lookup;
- recipe control tokens are separated from semantic tags and ordered first;
- positive tags are deduplicated and contain no internal placeholders;
- the negative prompt follows the selected Anima recipe, is deduplicated and
  does not contradict a locked positive fact;
- camera facts injected by the workflow do not conflict with PromptIntent;
- `ready_to_execute=true` and there are no rejected tags.

An LTX PromptBuild passes only when:

- subject, action, primary motion and camera are present;
- ordered events have an explicit timeline;
- persistent identity, costume and environment facts are locked;
- instructions describe visible motion instead of static image quality alone;
- the prompt does not inject a second negative-prompt system over the
  workflow-owned negative conditioning.

## 5. Core contracts

### 5.1 CapabilityReport

```json
{
  "schema_version": "1.0",
  "comfyui": {
    "url": "http://127.0.0.1:8188",
    "reachable": true,
    "version": "0.29.0"
  },
  "hardware": {
    "device": "NVIDIA GeForce RTX 4060 Laptop GPU",
    "vram_total_bytes": 8585216000,
    "vram_free_bytes": 0
  },
  "adapter": {
    "name": "comfyui-mcp",
    "version": "0.49.0",
    "tools": []
  },
  "workflow_candidates": [],
  "generated_at": "",
  "valid_until": ""
}
```

Capability reports expire after ten minutes or immediately after ComfyUI,
custom nodes, models or saved workflows change.

### 5.2 WorkflowProfile

A profile binds semantic slots to one verified workflow fingerprint:

```json
{
  "profile_id": "camera-anima-v1",
  "workflow_name": "文生图相机视角.json",
  "workflow_fingerprint": "",
  "generation_modes": ["text-to-image", "image-to-image"],
  "slots": {},
  "required_nodes": [],
  "required_models": [],
  "allowed_mutations": [],
  "expected_outputs": []
}
```

Node IDs are evidence for the currently verified fingerprint, not global
constants. When the fingerprint changes, the profile must be rediscovered or
reapproved before execution.

### 5.3 ExecutionPlan

```json
{
  "schema_version": "1.0",
  "stage": "character-base",
  "prompt_build_id": "",
  "workflow_profile_id": "camera-anima-v1",
  "workflow_fingerprint": "",
  "patches": [],
  "immutable_inputs": [],
  "local_only": true,
  "preflight": {
    "nodes": "pass",
    "models": "pass",
    "resources": "pass",
    "policy": "pass"
  },
  "expected_outputs": [],
  "execution_approved": false
}
```

Only allowlisted slots may be changed. Model, LoRA, sampler, scheduler and graph
structure remain immutable unless a later profile version explicitly exposes
them.

### 5.4 RunRecord

The append-only record contains:

- TaskContext and PromptIntent hashes;
- full PromptBuild;
- workflow name, UI/API fingerprints and profile version;
- exact patches and immutable graph hash;
- model and LoRA names plus available content hashes;
- seed, dimensions, sampler, steps and guidance;
- ComfyUI prompt ID, timestamps and terminal status;
- input and output artifact hashes;
- validation result and structured failure, if any.

## 6. Four-stage production flow

### Stage 1 — Front-facing character base

**Goal:** create one clear canonical identity image before attempting alternate
views or narrative shots.

**Prompt compilation:**

- target: `image`;
- generation mode: `text-to-image`;
- model family: Anima;
- dialect: validated Danbooru-style tags;
- output: model-specific positive and negative prompts;
- locked facts: face, hairstyle, body proportions, costume, colors,
  accessories and species/age-category facts supplied by the user.

**Workflow:** `文生图相机视角.json`.

Verified slots for the current fingerprint:

- positive prompt: `ImpactWildcardProcessor`, title `POSITIVE`, node `24`;
- negative prompt: `ImpactWildcardProcessor`, title `NEGATIVE`, node `25`;
- camera direction: `CameraAngleNode`, node `583`;
- lens/depth controls: `CameraExtraConfigNode`, node `585`;
- image-to-image group `加载图片（G1）`, group `3`, remains bypassed;
- output: enabled image saver and preview nodes.

Default framing is front-facing, eye-level and identity-readable. The character
must not be hidden by extreme pose, strong foreshortening, heavy occlusion or a
complex background. A user-specified composition overrides these defaults.

**Output artifact:** `CharacterBaseImage`.

Acceptance checks:

- PNG exists and decodes;
- front-facing identity is visible;
- locked visual facts are represented;
- image metadata links to the Stage 1 RunRecord;
- no img2img input was active.

### Stage 2 — Flux2-Klein multi-angle character sheet

**Goal:** expand the canonical identity into consistent reference views without
redesigning the character.

**Workflow:** `Flux2-Klein人物一键多视图工作流.json`.

The Stage 1 image is uploaded once and patched into both active base-image
inputs in the `Input image` group. For the currently verified fingerprint these
are `LoadImage` nodes `111` and `667`, feeding the `input image0` and
`input image1` buses. Both must point to the same uploaded artifact hash.

The workflow's pose-reference group and per-view transformation instructions
remain immutable. Prompt Forge may supply an identity-preservation clause when
the profile exposes a custom-prompt slot, but it must not replace the workflow's
view-specific instructions. FLUX negative prompts are not injected.

Expected views include front, 45-degree, side, rear and face/upper-body details,
subject to the currently active workflow branches.

**Output artifacts:**

- `CharacterSheet` contact sheet;
- zero or more individual `CharacterAngleView` images with normalized view
  labels.

Acceptance checks:

- every output is derived from the Stage 1 artifact;
- identity, costume and colors remain consistent;
- no new primary character is introduced;
- at least one front/45-degree/side reference is recoverable for Stage 3;
- all outputs retain the same lineage ID.

### Stage 3 — Concrete shot image with img2img

**Goal:** render the exact narrative composition that will become the first
video guide frame.

**Reference selection:** select the `CharacterAngleView` closest to the desired
shot direction. Do not feed a contact sheet when an individual angle image is
available. If no suitable angle exists, use `CharacterBaseImage` and record the
fallback.

**Prompt compilation:** create a new PromptIntent and PromptBuild. Do not reuse
the Stage 1 prompt. Preserve character identity as locked facts, then add the
shot-specific action, scene, lighting, composition, camera, color, style and
mood. Compile a new Anima positive and negative prompt.

**Workflow:** `文生图相机视角.json`, image-to-image mode.

For the current fingerprint:

- patch node `24` with the Stage 3 positive prompt;
- patch node `25` with the Stage 3 negative prompt;
- patch camera nodes `583` and `585` from the requested shot;
- upload the selected reference and patch `LoadImage` node `21`;
- enable every node in group `加载图片（G1）` / group `3` together:
  `LoadImage 21`, `PrimitiveInt 58`, `ImageResizeKJv2 57`, and `VAEEncode 59`;
- preserve all other workflow branches and settings unless the profile exposes
  a documented control.

Img2img strength is a profile-owned parameter. It must be read from the
converted runtime graph and recorded in the ExecutionPlan; the LLM must not
invent an unverified node or value.

**Output artifact:** `ShotImage`.

Acceptance checks:

- selected character reference is present in lineage;
- requested camera direction and composition are visible;
- character identity and costume remain consistent with Stage 1 and Stage 2;
- output is suitable as an LTX guide image;
- no unexpected workflow group was enabled.

### Stage 4 — LTX directed video

**Goal:** animate the approved Stage 3 shot with explicit temporal direction.

**Prompt compilation:** create a video-target PromptIntent and PromptBuild with
subject, action, motion and camera dimensions. Add timeline ordering when the
shot contains multiple events. Preserve character, costume, environment and
camera-continuity facts. The workflow's fixed negative conditioning remains
profile-owned.

**Workflow:** `LTX全新导演台工作流.json`.

The current workflow contains:

- `YusuLTXDirector`, node `174`;
- `YusuLTXDirectorGuide`, node `175`;
- fixed negative `CLIPTextEncode`, node `195`;
- 24 fps and a current one-second / 24-frame logical timeline; Yusu decodes
  this on its `8n+1` lattice as 25 output frames;
- an active `1280x720` target selector whose fixed 1216x832 guide input,
  `maintain aspect ratio`, and 32-pixel snap yield an effective `1024x704`
  output canvas;
- local LTX 2.3 GGUF, text encoders, VAEs and three referenced LTX LoRAs.

The guide image and local prompt are not independent scalar inputs. They are
embedded in the `timeline_data` JSON stored by `YusuLTXDirector`. A dedicated
`YusuTimelineAdapter` must atomically update:

- `timeline_data.segments`;
- each segment's `imageFile`, `imageB64`, `prompt`, `start`, `length`, `type`
  and `isEndFrame` fields;
- derived `local_prompts`;
- derived `segment_lengths`;
- guide strengths and transition fields when present;
- total start/end/duration frames and seconds.

The adapter must parse and reserialize JSON; string replacement is forbidden.
The default minimal experiment uses one image segment, one prompt, 24 logical
frames at 24 fps, the existing workflow models/settings, and therefore expects
25 decoded frames at 1024x704.

**Output artifact:** `VideoClip`.

Acceptance checks:

- video decodes with 25 output frames at 24 fps and the planned 1024x704 canvas;
- first-frame identity matches the ShotImage;
- instructed primary motion occurs;
- no unrequested new subject or shot cut appears;
- prompt ID, workflow hash, guide image hash and video file hash are recorded.

## 7. State machine and resumability

```text
DISCOVERED
  -> BASE_PREFLIGHTED -> BASE_READY
  -> SHEET_PREFLIGHTED -> SHEET_READY
  -> SHOT_PREFLIGHTED -> SHOT_READY
  -> VIDEO_PREFLIGHTED -> VIDEO_READY
```

Every transition is idempotent. A completed stage is reused only when its input
hashes, PromptBuild hash, workflow fingerprint and profile version are
unchanged. A failed stage does not invalidate previous accepted artifacts.

## 8. Workflow discovery and selection

Hard gates run before scoring:

1. generation mode matches;
2. workflow is local-only;
3. UI graph can be converted to executable API format;
4. required nodes and output nodes exist;
5. selected models and LoRAs appear in the exact node input schema;
6. expected VRAM fits the current device or a verified 8 GB history exists;
7. profile fingerprint matches;
8. all planned mutations are allowlisted.

Ranking signals:

- recent success with the same workflow fingerprint: `+40`;
- exact model/generation-mode match: `+20`;
- confirmed local-only runtime: `+15`;
- verified 8 GB execution: `+10`;
- lower runtime-graph complexity: `+5`;
- better reference/aesthetic match: `+10`.

Stage-specific profiles take priority over generic ranking. If a specified
workflow fails a hard gate, execution stops with reasons; the system does not
silently substitute another model or workflow.

## 9. Resource and safety policy

- Query queue and VRAM immediately before execution.
- Never clear VRAM while another job is running.
- Clearing unloaded model caches is an explicit execution precondition and is
  recorded in the RunRecord.
- Upload inputs under a run-specific subfolder and content-derived filename.
- Never mutate or overwrite the saved user workflow.
- Never modify model or LoRA selections during a baseline experiment.
- Never queue a graph that contains paid API nodes without separate approval.
- Validate all local file references and reject path traversal.
- Use one active ComfyUI job at a time on the 8 GB device.

## 10. Error model

Errors use one of five categories:

- `CAPABILITY_ERROR`: ComfyUI or adapter is unavailable;
- `WORKFLOW_ERROR`: profile drift, conversion, node or connection failure;
- `RESOURCE_ERROR`: model, input, disk or VRAM shortage;
- `POLICY_ERROR`: unauthorized execution, mutation or paid node;
- `EXECUTION_ERROR`: runtime node failure, interruption or missing output.

Each error records stage, original evidence, retry safety, suggested next action
and all completed artifacts that remain reusable.

## 11. Minimal experiments

### Experiment A — Stage 1 replay

- Baseline: most recent successful camera-workflow API graph.
- Change one variable: seed.
- Keep prompt, model, dimensions, sampler and guidance fixed.
- Success: a new valid PNG and successful history item with the new seed.

### Experiment B — Prompt injection

- Baseline: Experiment A graph and fixed seed.
- Change one variable: Stage 1 PromptBuild positive prompt.
- Success: submitted graph and output metadata contain the exact compiled
  prompt; the image completes without graph drift.

### Experiment C — Multi-view handoff

- Baseline: current proven Flux2-Klein multi-view graph.
- Change one variable: both base-image slots receive the Stage 1 artifact.
- Success: the workflow completes and emits a character sheet/angle images with
  the same input hash in both buses.

### Experiment D — Img2img activation

- Baseline: successful camera-workflow graph.
- Change one logical variable: switch from empty latent to the complete G1
  image-input path using the selected Stage 2 reference.
- Success: every G1 node is active, no unrelated group changes, and a valid
  ShotImage is produced.

### Experiment E — LTX one-second clip

- Baseline: current LTX director workflow.
- Change one logical variable: replace the single timeline segment with the
  Stage 3 ShotImage and its video PromptBuild.
- Duration: 24 frames at 24 fps.
- Success: valid one-second video, successful history record, matching guide
  image/prompt hashes and no OOM.

Experiments run sequentially. A later experiment cannot begin until the prior
artifact passes acceptance checks.

## 12. Testing strategy

### Deterministic tests

- TaskContext validation and question-budget behavior;
- CapabilityReport expiry;
- workflow fingerprint and profile drift;
- exact node/model preflight;
- allowlisted patch enforcement;
- synchronized dual input patch for Flux;
- complete G1 group activation;
- Yusu timeline parse/update/round-trip invariants;
- state-machine resume and invalidation;
- RunRecord lineage and hashing;
- every structured error category.

### Integration tests

- read-only discovery against the live ComfyUI instance;
- dry-run conversion and validation of all three named workflows;
- replay experiments A through E behind an explicit live-test flag;
- verify real PNG/video bytes and embedded metadata;
- retain the existing Prompt Forge 71-test and 12-case gates.

Live generation tests must never run as part of a default unit-test command.

## 13. Implementation slices

The specification is implemented as four sequential, independently reviewable
slices. A slice may be rejected or revised without invalidating accepted prior
slices.

### Slice 1 — Runtime foundation and character base

Deliver TaskContext, CapabilityReport, adapter negotiation, WorkflowProfile,
ExecutionPlan, RunRecord and the Stage 1 camera-workflow path. Its live gate is
Experiment A followed by Experiment B.

### Slice 2 — Multi-angle references

Deliver the Flux dual-input adapter, output normalization and character-lineage
checks. It consumes the accepted Stage 1 contract and passes Experiment C.

### Slice 3 — Shot img2img

Deliver reference-angle selection, a second Prompt Forge compilation and atomic
G1 activation. Its converted API graph must prove that the VAE-encoded image
latent reaches the intended sampler input before Experiment D can run.

### Slice 4 — Directed video

Deliver video PromptBuild quality gates, `YusuTimelineAdapter`, video
verification and final lineage. It passes JSON round-trip tests before the live
one-second Experiment E.

## 14. Definition of done

v7 is complete only when:

1. the system discovers and validates the three named local workflows;
2. Stage 1 produces a front-facing base image from Prompt Forge prompts;
3. Stage 2 produces traceable multi-angle character references;
4. Stage 3 activates the complete G1 img2img path and produces a concrete shot;
5. Stage 4 atomically patches Yusu timeline data and produces a valid video;
6. each stage is independently resumable and auditable;
7. all artifacts share a lineage ID and content hashes;
8. dry-run never changes queue or saved workflows;
9. execution requires explicit authorization;
10. documentation describes only verified on-disk behavior.
