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

## Evidence matrix (2026-08-03)

| Stage | Contract | Current evidence | Remaining gate |
|---|---|---|---|
| 1. Base | Prompt Forge image PromptBuild; camera text-to-image; front-facing acceptance; PNG + RunRecord | Camera UI fingerprint `7fa7a85e...e20a`; accepted front base generated in the local ComfyUI run and reused by hash; `submit-character-base` now has the same consumed intent/receipt boundary as later stages | A new approved live run still must be recorded with the receipt-bound `record` path and front-facing acceptance |
| 2. Multiview | Reuse one accepted Stage 1 PNG in Flux nodes `111` and `667`; no injected Flux negative; normalize outputs | Promoted flat workflow `PromptForge-Flux2-Klein-multiview-flat-v2.json`, fingerprint `9dc2b01e...c29e4da`; prompt `3d8627ab-ec60-46b2-b648-77d8662412ed` completed with character-sheet and angle outputs | Individual-angle acceptance remains a human gate; legacy `Flux2-Klein人物一键多视图工作流.json` is audit-only because conversion has unresolved buses/dangling refs |
| 3. Shot | New shot PromptBuild preserving identity facts; accepted individual angle; camera G1 path `27 -> 75 -> 59`; PNG + ShotImage | Prompt `fe64ee38-a437-44de-9c15-1de7d9bc1f75` succeeded through the pinned normalized graph; output `2026-08-03-231455_anima-aesthetic-v1.1_2026080304.png` is a valid 1216x832 PNG; `submit-stage` and mandatory raw-history record validation are implemented | The local exploratory run proves the queue and bytes; a new approved live run still must persist a receipt-bound RunRecord |
| 4. Video | Accepted ShotImage; video PromptBuild with subject/action/motion/camera; atomic Yusu timeline patch; preserve node `195`; 24 logical frames/24 fps | Prompt `dd6f2956-1041-461c-a000-a766fb0c125f` succeeded; `屿僳_00004_.mp4` is H.264, 1024x704, 24 fps, 25 decoded frames; profile filename is pinned to exact UTF-8 `LTX全新导演台工作流.json` | Formal RunRecord persistence remains the production handoff; dimension and `8n+1` checks are now hard gates |

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

## Completion rule

The product is production-ready only after Experiments D and E produce new,
traceable artifacts under explicit approval. A clean deterministic suite or a
zero-warning workflow conversion alone proves implementation readiness, not a
successful end-to-end render.
