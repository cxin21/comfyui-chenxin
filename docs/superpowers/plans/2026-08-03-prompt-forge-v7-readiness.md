# Prompt Forge v7 production-readiness matrix

## First-principles contract

The pipeline is valid only when each stage consumes one accepted artifact and
produces the next artifact without losing identity, provenance, or operator
intent:

```text
PromptBuild(image/base) -> CharacterBaseImage
CharacterBaseImage -> CharacterAngleView[]
CharacterAngleView + PromptBuild(shot) -> ShotImage
ShotImage + PromptBuild(video) -> VideoClip
```

The prompt is not the artifact. A stage is complete only after the graph is
validated, the requested change is bounded, the job is approved and consumed
once, ComfyUI returns a terminal result, and the output bytes are retained and
hash-verified. A later stage must never regenerate identity from an unbound
prompt; it inherits the accepted upstream hash and carries a new stage-specific
PromptBuild only where the visual intent changes.

## Evidence matrix (2026-08-04)

| Stage | Contract | Current evidence | Remaining gate |
|---|---|---|---|
| 1. Base | Prompt Forge image PromptBuild; camera text-to-image; front-facing acceptance; PNG + RunRecord | Formal RunRecord: prompt `225eb85b-64c7-493c-b990-99dcfe960b77`, record `6dbec47bd60c5b5584788f356455b1c949bfc5cf0178f595a5bfd580c9ccfb82`, PNG hash `f2ce2f1a3f8bf9c26bc205b7af48f239ffd163bf5702c5cda7f895abd171a738` | Human front-facing acceptance remains required for every new lineage |
| 2. Multiview | Reuse one accepted Stage 1 PNG in the promoted flat Flux graph; normalize outputs and preserve per-view hashes | Formal RunRecord: record `fe02700c7452c4f9d5428b427ec55a889f05e2d76efbc80cdcadb7f19ebedd31`, 28 normalized artifacts; accepted `front_closeup` hash `66a484a543796ddca0cd8494f20d0244186fa3845d7b6f29f8e2c3038dd56968`; flat profile fingerprint `9dc2b01e...c29e4da` | Individual-angle acceptance remains a human gate; the legacy saved workflow remains audit-only |
| 3. Shot | New shot PromptBuild; accepted individual angle; camera G1 path `27 -> 75 -> 59`; camera direction/distance patch; PNG + ShotImage | Formal RunRecord: prompt `c9a8b32a-087a-42b2-bb03-d276e5388048`, record `e005420a0c1a1159b614b7a3f5f4c01b6b71277dd0dc478e093b9bd667bd734e`, output hash `4dde2c460cc08a451a0dcadfb7eaa99696d0c26acca4a149521bb7ad08bc15a9`; G1 reference hash `66a484a...d56968` | Camera mappings are allowlisted; new directions still require visual acceptance |
| 4. Video | Accepted ShotImage; video PromptBuild; atomic Yusu timeline patch; preserve node `195`; 24 logical frames/24 fps | Formal RunRecord: prompt `003890a3-6307-4cd9-8665-90c1d522eab0`, record `1f3911e835174738170762cba0827d3aa40a8ba890b40540de1870e29eb034c1`, output `屿僳_00006_.mp4`, hash `c158dcaad050ff9fdc8089e8af21037d126d20a38d365764950b4e55a895125b`; ffprobe: H.264, 1024x704, 24 fps, 25 frames; current LTX UI fingerprint `8f777f...081074` | Motion/identity remains an explicit visual-quality gate in addition to structural verification |

## Implementation status after the first-principles review

The runtime now has explicit workflow-candidate discovery (including the
legacy Flux candidate and its promoted flat-v2 replacement), a loopback-only
ComfyUI transport, Stage 1 and Stage 3/4 consumed submission bridges, a
read-only `wait-stage` monitor, mandatory raw-history checks for Stage 3/4,
receipt-bound Stage 1 RunRecords, and optional canonical output-root binding.
The live exploratory prompts below remain characterization evidence; they are
not silently upgraded to production records.

The current local ComfyUI characterization is decisive for workflow choice:
the camera graph needs its pinned normalization bridge; the original named
Flux graph is invalid after conversion; the promoted flat-v2 Flux graph and
the LTX Director graph validate with zero errors/warnings and are classified
local/free. The requested workflow name is therefore retained as an audit
candidate, while flat-v2 is the only Stage 2 production profile.

## Optimizations that follow from the contract

The Stage 4 profile now also rejects drift in the Director base model, all
three LTX LoRAs, Euler sampler, `linear_quadratic` scheduler, and active
`1280x720` resolution selector before any timeline mutation. The selector is a
target box, not a promise of the final canvas: with the fixed Stage 3 1216x832
guide and `maintain aspect ratio`, the model emits 1024x704 after 32-pixel
snapping. That effective canvas is now part of the profile and artifact gate.
Its complete profile digest is pinned in the execution boundary, so a caller
cannot weaken the contract by supplying a self-authored profile.

1. Use the promoted flat Flux graph as the single production profile. Keep the
   original workflow only for diagnosis; never fall back after a warning.
2. Treat Stage 1 front-facing acceptance as a quality gate, not as a prompt
   compiler result. Reuse the accepted PNG by content hash, not by filename.
3. Generate a new Stage 3 PromptBuild, but derive its locked identity facts from
   the accepted Stage 1/2 lineage. Select one accepted angle, never a contact
   sheet when an individual angle exists.
4. Keep Stage 4 at a one-second/24-fps profiling render until motion continuity
   and VRAM cost are measured. Do not retry an uncertain enqueue; query history
   by the stable request ID first.
5. Separate deterministic proof from aesthetic judgment: graph/path/hash checks
   can be automated, while front-facing, angle suitability, shot composition,
   and motion quality require an explicit human acceptance record.
6. Lock Stage 4's immutable Director inputs before patching: the base model,
   all three LTX LoRAs, Euler sampler, `linear_quadratic` scheduler, and the
   active `1280x720` resolution selector. The workflow's custom `1280x736`
   widget is inactive while `use_custom_resolution=false`; it must not be
   mistaken for the effective output size. Verify the resulting `1024x704`
   canvas from the encoded video, not from node settings alone.

## Formal live closure (2026-08-04)

The four stages were executed sequentially against the local ComfyUI instance
with one shared lineage `live-lineage-20260804-fda22387d6b4`. Each stage has a
fresh PromptBuild, an approved exact draft, an exclusive consumption record, a
real ComfyUI receipt, raw history, an output-root-bound artifact, and a
content-hashed RunRecord. Stage 3 also proves the G1 image path and camera
angle mutation. Stage 4 was re-pinned to the actually saved LTX Director
workflow after fingerprint drift was detected; no stale profile was allowed to
execute. The generated video was visually spot-checked at frames 0, 12, and
24 and retained the black-haired, blue-eyed armored subject while applying a
subtle push-in/breathing motion.

The formal evidence roots are intentionally outside the repository:

- Stage 1: `C:\Users\11245\AppData\Local\Temp\prompt-forge-formal-stage1-jei_phhl`
- Stage 2: `C:\Users\11245\AppData\Local\Temp\prompt-forge-formal-stage2-pcsvf_8v`
- Stage 3: `C:\Users\11245\AppData\Local\Temp\prompt-forge-formal-stage3-wu7y_y6m`
- Stage 4: `C:\Users\11245\AppData\Local\Temp\prompt-forge-formal-stage4-gn2329n1`

## Completion rule

The product is production-ready only after the deterministic suite passes and
all four formal records above remain independently verifiable. Structural
proof is necessary but not sufficient: front-facing acceptance, angle
suitability, shot composition, and motion/identity continuity remain explicit
human quality gates.
