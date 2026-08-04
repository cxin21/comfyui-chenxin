# Controlled Character-to-Video Pipeline Design

## Status

Approved design, pending implementation planning.

## Goal

Turn a character-to-video request into a reproducible local ComfyUI pipeline:

1. establish identity and shot intent;
2. generate and approve a clean identity master;
3. generate only the character views needed by the shot plan;
4. render an approved shot image with explicit camera controls;
5. generate a temporally consistent LTX video from that approved shot.

The system must preserve identity facts across stages, make optional workflow branches explicit, and reject graph or artifact drift before execution.

## Current MCP evidence

The live ComfyUI MCP workflow library was re-read on 2026-08-04.

| Workflow | Live shape | MCP/API result | Decision |
|---|---:|---|---|
| `文生图相机视角.json` | 141 nodes / 44 groups | 42-node conversion with 7 warnings; raw conversion omits known literal/output links | Keep as the camera source, require `normalize-camera` before planning |
| `Flux2-Klein人物一键多视图工作流.json` | 393 nodes / 34 groups | 261-node conversion with 70 warnings and broken virtual-bus references | Reference UI only; do not execute directly |
| `PromptForge-Flux2-Klein-multiview-flat-v2.json` | 261-node flat graph | MCP validation passed with no issues | Production multiview graph |
| `LTX全新导演台工作流.json` | 26 nodes / 4 groups | MCP validation passed with no issues | Production video graph, with explicit duration profile |

The camera UI contains 97 nodes in `mode=4`. The disabled capabilities are real branches, not merely visual annotations: G1 img2img, Face/Hand/Eye/SAM detailers, background removal, upscale, color match, G2 effects, regional prompting, ControlNet LLLite, CFGZeroStar, and CLIP NegPip.

The flat Flux workflow has no `mode=4` nodes. Its optional behavior is controlled by 17 `Switch any` nodes, three text index switches, and three image index switches. Its validated production profile currently allows only the two base image slots (nodes 111 and 667); pose references, view switches, view prompts, sampler settings, and output topology remain immutable until a separate view-selection profile is introduced.

The live LTX file defaults to 15 seconds / 360 logical frames / 24 fps. The current production profile intentionally uses a short baseline of 24 logical frames, 24 fps, and an `8n+1` output-frame rule. This difference must be explicit and never implicit.

## First-principles invariants

### Identity is monotonic

The identity facts established in the first Prompt Forge build are locked. Later stages may add shot deltas and motion deltas, but may not replace face, hair, body proportions, costume, accessories, or color identity without creating a new lineage.

### Every stage has one responsibility

- Prompt Forge compiles intent into structured positive/negative prompt builds.
- Camera T2I creates the clean identity master.
- Flux creates reusable character-view evidence.
- Camera G1 creates one concrete shot.
- LTX adds time and motion to an approved shot.

### Optional branches are profiles, not ad-hoc toggles

Detailers, ControlNet, regional prompts, background removal, upscaling, signatures, and G2 effects alter graph topology or artifact semantics. Each enabled combination needs its own profile, fingerprint, dependency contract, and acceptance rule.

### Unapproved artifacts never become inputs

Each handoff must carry artifact hash, lineage ID, source stage, workflow profile ID, and prompt-build hash. The next stage accepts only an approved artifact whose contract matches the selected profile.

### Clean identity precedes style

Strong post-processing effects, signatures, background removal, and aggressive upscaling must not be fed into Flux as identity references. They are derived outputs after the clean still is accepted.

## Pipeline architecture

```text
TaskContext
  -> identity PromptBuild
  -> camera base profile
  -> identity_master (approved)
  -> Flux view_plan / flat-v2
  -> character views (approved)
  -> shot PromptBuild (identity lock + shot delta)
  -> camera shot profile + G1
  -> shot_master (approved)
  -> optional refinement/style derivatives
  -> LTX short/long profile + motion delta
  -> video (approved)
```

## Stage 0: TaskContext

Create one canonical context object before any generation. It contains:

- character identity facts;
- visual direction and palette;
- shot goal, action, environment, and camera intent;
- delivery constraints such as aspect ratio and duration class;
- must-keep and must-avoid boundaries.

The canonical context receives a SHA-256 hash. All prompt builds, stage plans, and artifacts reference this hash.

## Stage 1: Identity master

### Prompt Forge contract

Produce `identity_positive` and `identity_negative` from the TaskContext. The build must optimize for identity observability, not cinematic complexity:

- front-facing;
- eye-level;
- medium or full-body framing;
- simple background;
- complete face, costume, and accessories;
- no strong motion blur, heavy grain, VHS, glitch, or signature.

### Camera contract

Use the camera workflow with:

- positive/negative prompt slots 24/25;
- CameraAngle node 583 set to `front`, `eye-level`, and `medium` or `full_body`;
- CameraExtra node 585 neutral;
- G1 and all optional detailer/control/style branches disabled.

Generate candidates, then approve exactly one `identity_master` artifact. Rejected candidates do not enter Flux.

### Acceptance

- identity facts are visibly present;
- face, hands, costume, and accessories are usable;
- no obvious identity contamination from style or reference artifacts;
- image dimensions and file reference are valid for the next profile.

## Stage 2: Character views

### Workflow

Execute only `PromptForge-Flux2-Klein-multiview-flat-v2.json`. The original grouped Flux workflow is not a valid production API graph because MCP cannot resolve its virtual buses reliably.

### View plan

The caller provides a `view_plan`, for example:

```json
{
  "views": ["front", "front_45", "right_side", "rear"],
  "face_closeup": false,
  "upper_body": false,
  "face_enhancement": false
}
```

Defaults:

- primary and secondary base image both reference `identity_master`;
- pose reference images remain immutable;
- view switches are changed only through the future view-selection profile;
- view prompts remain deterministic templates unless explicitly overridden.

The output is a set of labeled artifacts such as `front`, `front_45`, `right_side`, and `rear`.

### Acceptance

Each view must preserve identity, costume, accessories, and intended orientation. The view set is approved as evidence; it is not automatically used for Stage 3.

## Stage 3: Shot image

### Source selection

Select the character view closest to the target shot. A right-side shot should normally use `right_side`, not the front master. This reduces geometric rewriting and identity drift.

### Prompt Forge contract

Produce a shot build with:

- `identity_lock` copied from the approved TaskContext/build;
- `shot_positive` and `shot_negative` describing only shot deltas;
- camera direction, elevation, distance, action, environment, lighting, and composition.

The shot build must not rewrite identity facts.

### Camera G1 contract

The runtime must atomically:

1. activate the complete G3 group `[21, 58, 57, 59]`;
2. load the selected character view into node 21;
3. patch prompt nodes 24/25;
4. patch CameraAngle node 583;
5. patch CameraExtra node 585;
6. execute the profiled G1 path `[27, 75, 59]`.

CameraExtra fields are explicit and allowlisted:

- lens enabled/value;
- depth-of-field enabled/value/weight;
- movement enabled/value;
- composition enabled/value;
- style enabled/value;
- extreme type/weight.

The current implementation declares `camera_extra` but does not yet patch node 585; implementation must close this contract gap.

### Optional branches

The default shot profile keeps all optional branches off. A separate refinement profile may enable a complete dependency closure:

- face issue: Face Detailer + detector + SAM/Detailer dependencies;
- hand issue: Hand Detailer + detector + dependencies;
- eye issue: Eye Detailer + detector + dependencies;
- complex mask issue: Mask Detailer or SAM3.1.

Regional prompts, ControlNet LLLite, CFGZeroStar, and CLIP NegPip are control profiles, not default quality switches.

### Derived outputs

Keep separate artifacts:

- `shot_master`: clean accepted shot;
- `shot_refined`: detailer output, if used;
- `shot_style_variant`: optional G2/post-process output;
- `shot_cutout`: optional background-removed output.

The default LTX input is `shot_master` or an approved `shot_refined`, never an unapproved derivative.

## Stage 4: Video

### LTX contract

Inject the approved shot image into Yusu Director node 174 as the timeline image reference. The video prompt is composed from:

```text
identity_lock + shot_description + motion_delta
```

The workflow-owned negative node 195 remains immutable.

### Duration profiles

At least two explicit profiles are required:

- `ltx-yusu-short`: 24 logical frames, 24 fps, `8n+1` output rule, quick validation;
- `ltx-yusu-long`: a separately budgeted frame count such as 96 or 120 logical frames.

Director timeline fields, local prompts, segment lengths, frame range, duration, and frame rate are mutable only within the selected profile. Models, LoRAs, sampler, scheduler, resolution policy, and guide topology remain immutable by default.

### Acceptance

- frame count matches the profile rule;
- fps and effective resolution are correct;
- first, middle, and final frames preserve identity;
- camera motion is continuous;
- no obvious flicker, clothing jumps, or facial drift.

## Configuration profiles

The implementation should split the current broad workflow into these contracts:

1. `camera-anima-base`: clean identity master;
2. `flux2-klein-view-selection`: flat-v2 with explicit view switches and view-plan outputs;
3. `camera-anima-shot`: G1 plus CameraAngle and CameraExtra;
4. `camera-anima-detailer`: opt-in quality dependency closures;
5. `camera-anima-control`: regional prompt/ControlNet/CFG variants;
6. `camera-anima-style`: post-process derivatives only;
7. `ltx-yusu-short` and `ltx-yusu-long`: explicit temporal budgets.

Every profile must declare:

- workflow fingerprint and API graph hash;
- mutable paths;
- immutable nodes and roles;
- required input artifact types;
- output artifact types;
- dependency closure;
- acceptance rule.

## Error handling and fail-closed behavior

- Reject a stage plan when its source artifact is not approved or its lineage/hash does not match.
- Reject a graph when it is not normalized, its fingerprint drifted, or a required output path is missing.
- Reject an optional profile when its dependency closure is incomplete.
- Reject a video run when the requested duration is not allowed by the selected LTX profile.
- Preserve rejected artifacts for audit, but never promote them to the next stage.

## Minimal validation experiments

1. **CameraExtra experiment**: change only node 585 lens/DOF fields; verify the patched graph changes only the declared fields and the generated prompt/output reflects the change.
2. **Face-detailer experiment**: enable only the complete Face Detailer dependency closure; compare identity similarity and artifact rate against the base shot.
3. **View-selection experiment**: toggle exactly one Flux view switch; verify only the expected labeled output changes and pose-reference nodes remain immutable.
4. **LTX duration experiment**: run the short profile with 24 logical frames, then validate output frame count, fps, and temporal identity.

## Definition of done for the redesign

- the four stages exchange typed, hashed, approved artifacts;
- only flat-v2 Flux is executable in production;
- camera G1 and CameraExtra are covered by a complete profile;
- optional branches are dependency-checked profiles;
- LTX duration is explicit and tested;
- regression tests cover graph identity, allowlists, lineage, output contracts, and profile-specific temporal rules;
- at least one local ComfyUI run passes the full pipeline from identity master to video.

