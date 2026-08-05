# Controlled Character-to-Video Pipeline Design

## Status

Approved design, revised on 2026-08-04 to include the narrative-decomposition, visual-asset, and LTX prompt contracts supplied in the downloaded reference documents. The revised implementation plan supersedes the earlier plan while preserving its graph/profile safety decisions.

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

## Revision 2026-08-04: upstream narrative and asset layer

The three supplied documents add a required upstream layer that the original
four-stage image/video sequence did not model. The system is not only a graph
executor; it is a controlled compiler from story evidence to visual assets,
then to prompts, then to images and video. The following contracts are now
part of the design.

### Source contract: story decomposition

`StoryBreakdown` is the evidence-bearing input to all later stages. It keeps
the template's separation between visual judgment, character setting, scene
timeline, story logic, dialogue attribution, and uncertainty. It must contain:

- a visual-system assessment before the genre label, distinguishing art style,
  medium/rendering, palette/light, material language, and mixed-style changes;
- character records with identity, appearance, hair, costume, accessories,
  goals, motives, actions, emotion arc, relationships, dialogue ownership,
  narrative function, end state, and unknowns;
- scene records with spatial structure, atmosphere, staging, key objects,
  narrative focus, and continuous non-overlapping timeline nodes;
- per-node local style change, cast, action/reaction, dialogue attribution,
  conflict, emotion, narrative function, and transition to the next node;
- story logic for start, goal, obstacle, conflict, information gap, twist,
  climax, ending, and audience emotion;
- explicit uncertainty categories for characters, scenes, plot, time, props,
  and style. Missing source information is never promoted to a fact.

The decomposition stage must not emit model parameters or image/video prompt
syntax. It produces evidence and constraints for the next compiler stage.

### Source contract: visual asset bible and asset cards

`ArtBible` and typed `AssetCard` records are compiled from the story evidence.
The supplied asset document requires a single global visual bible before
individual assets, with style variant, image grammar, palette, materials,
lighting, visual motifs, world taboos, and a continuity strategy. Every asset
must separate `explicit_evidence`, `reasonable_inference`, and
`prohibited_expansion` and must carry a six-part visual fingerprint:
silhouette, material, color, wear/trace, lighting, and memory point.

The asset union has three concrete members:

- `EnvironmentAsset`: space personality, spatial/structural/material/light
  design, five fixed visual anchors, a setting-board prompt, and scene variants
  that inherit the environment master rather than recreating the space;
- `CharacterAsset`: narrative role, specific face geometry, hair system,
  layered costume, body state, immutable identity lock, allowed variations,
  forbidden changes, and a board prompt requiring head close-up plus front,
  90-degree side, and rear views;
- `PropAsset`: narrative function, measurable scale, silhouette, construction,
  materials, wear, symbols, functional states, and an engineering-board prompt
  requiring master view, exploded structure, material slice, and function
  state. Prop boards contain no people or hands.

Environment boards contain no people, character boards contain no scene or
props, and prop boards contain no people or hands. These are acceptance rules,
not prompt suggestions.

### Prompt Forge contracts

Prompt Forge now has two distinct dialects and must not mix analysis with
generation:

1. Image builds consume `ArtBible`, one or more asset cards, a shot intent,
   explicit evidence, and prohibited expansions. They produce positive and
   negative prompts plus identity/style/scene/prop locks and reference roles.
2. LTX builds consume an accepted `ShotImage` and shot intent. They produce a
   concise Chinese positive prompt, an English positive prompt that preserves
   Chinese dialogue verbatim, one selected global director prompt, and an
   optional split recommendation. The prompt has exactly one action layer:
   reference roles and one-sentence premise followed by a dynamic, non-uniform
   timeline with `s` units. It names the speaker and exact dialogue, uses
   stable medium/medium-close shots by default, and avoids an unnecessary
   second narrative retelling.

The LTX build must represent identity lock, shot action, motion delta, camera
intent, scene continuity, prop continuity, dialogue attribution, and temporal
segments. The workflow-owned negative node remains immutable and
`negative_prompt` remains empty in the build contract.

### Revised stage ordering

The original four render stages remain, but two controlled compiler stages
precede them and one prompt compilation gate is added before video:

```text
StoryBreakdown
  -> ArtBible + Character/Environment/Prop AssetCards
  -> Prompt Forge image build
  -> Camera base identity master
  -> Flux flat-v2 character board / requested views
  -> ShotIntent + Prompt Forge shot build
  -> Camera G1 shot_master
  -> Prompt Forge LTX bilingual timeline build
  -> LTX short/long Director video
```

An environment or prop asset is generated only when the story evidence says
it has narrative or continuity value. If it is needed, its accepted board is
referenced by `AssetCard` ID and its fixed anchors are inherited by every shot
variant. If a shot contains multiple major events, more than three core
characters, a scene/time jump, more than four complex storyboard beats, or a
mixture of complex action and long dialogue, the prompt compiler emits a
split recommendation and Stage 4 refuses to compress the request into one
video.

### New invariants and experiments

- `explicit_evidence`, `reasonable_inference`, and `prohibited_expansion` are
  hash-bound fields; a later prompt cannot turn an inference into an identity
  fact without a new approved lineage.
- A scene variant must reference one accepted environment master and preserve
  its layout, anchors, palette, materials, light logic, damage, and world
  symbols; only the declared shot delta may change.
- A character board is not interchangeable with a scene board or a prop board;
  artifact types and accepted reference roles enforce the separation.
- The Flux `side_unknown` output is not direction-safe. A requested
  `right_side` or `left_side` shot may use it only after an orientation proof is
  recorded; otherwise the view plan fails closed.
- Dynamic LTX timeline segments must be monotonic, non-overlapping, contain
  explicit seconds, and sum within the selected duration profile. The default
  short run still uses 24 logical frames/24 fps and decodes to 25 frames.

Minimal new experiments are: evidence-to-asset fidelity (change only one
visual-bible field), environment-master reuse (change only a shot delta),
character-board orientation proof (change one Flux switch), and LTX timeline
split (compare one simple event with a deliberately over-complex request).

## Verification record: 2026-08-04

The local ComfyUI REST preflight at `127.0.0.1:8188` responded with version
`0.29.0`; the queue had zero running and zero pending jobs. Read-only workflow
retrieval confirmed 141/44 nodes/groups for the camera workflow, 393/34 for the
grouped Flux workflow, 261/0 for the flat-v2 workflow, and 26/4 for the LTX
Director workflow. The pinned flat-v2 profile remains bound to UI fingerprint
`9dc2b01e2aea0b051113b187b134d007f452df6c83cfcbbd8d325eaa4c29e4da` and API
graph hash `450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36`;
the pinned LTX profile remains bound to UI fingerprint
`8f777f6315bab2c14fb4d99d83a44d73cf8dfd7362011fc3a931fffa9a081074` and API
graph hash `c7d0c07e2e6656af9737a7d92bea62bc4b4c7c11291bfb910e13eaa8a3f1fb74`.

The four single-variable checks are executable without generation: changing
only ArtBible lighting leaves identity and taboo locks unchanged; reusing one
environment master leaves anchors, layout, palette/materials, damage, and light
logic unchanged; changing only flat-v2 switch `731.boolean` leaves all twelve
pose references unchanged and requires proof for `side_unknown`; and the short
LTX profile compiles 24 logical frames at 24 fps to 25 output frames on
1024x704 while preserving negative node `195`, with complex scene/time changes
blocked by the split gate.

The LTX adapter also rejects any profile whose declared duration is not exactly
the baseline logical-frame budget divided by fps, and rejects timeline segments
whose rounded frame lengths do not form one contiguous baseline frame range.
The same invariant is enforced by `validate_yusu_sync` and the JSON CLI
`patch-yusu` boundary.

No `/prompt` enqueue, upload, approval consumption, or generated artifact was
performed for this record. The MCP conversion receipt is not exposed by the
read-only REST endpoints, so the record does not claim a fresh end-to-end
generation pass. A production acceptance still requires an approved run record
and hashes for the retained PNG/video artifacts.
