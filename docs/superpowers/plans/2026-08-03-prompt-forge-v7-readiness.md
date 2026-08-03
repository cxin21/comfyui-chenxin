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
| 1. Base | Prompt Forge image PromptBuild; camera text-to-image; front-facing acceptance; PNG + RunRecord | Camera UI fingerprint `7fa7a85e...e20a`; pinned normalization bridge repairs the observed MCP loss in memory; local ComfyUI is reachable | No fresh production artifact was generated in this audit; approval/receipt/history/artifact chain still required |
| 2. Multiview | Reuse one accepted Stage 1 PNG in Flux nodes `111` and `667`; no injected Flux negative; normalize outputs | Promoted flat workflow `PromptForge-Flux2-Klein-multiview-flat-v2.json`, fingerprint `9dc2b01e...c29e4da`; live API conversion validates with zero errors/health warnings and local runtime | No current production upload/enqueue/RunRecord; legacy `Flux2-Klein人物一键多视图工作流.json` is audit-only because conversion has unresolved buses/dangling refs |
| 3. Shot | New shot PromptBuild preserving identity facts; accepted individual angle; camera G1 path `27 -> 75 -> 59`; PNG + ShotImage | Deterministic reference selector, camera patcher, path proof, stage approval/consumption/submission contracts and tests | No fresh live ShotImage or Experiment D receipt/history/artifact |
| 4. Video | Accepted ShotImage; video PromptBuild with subject/action/motion/camera; atomic Yusu timeline patch; preserve node `195`; 24 frames/24 fps | LTX UI fingerprint `cc9f26b0...c0c5a`; API conversion validates locally with zero errors/health warnings; timeline adapter and video artifact validators are deterministic; profile filename is pinned to exact UTF-8 `LTX全新导演台工作流.json` | No fresh live VideoClip or Experiment E receipt/history/ffprobe artifact |

## Optimizations that follow from the contract

The Stage 4 profile now also rejects drift in the Director base model, all
three LTX LoRAs, Euler sampler, `linear_quadratic` scheduler, and active
`1280x720` resolution selector before any timeline mutation. Its complete
profile digest is pinned in the execution boundary, so a caller cannot weaken
the contract by supplying a self-authored profile.

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
   mistaken for the effective output size.

## Completion rule

The product is production-ready only after Experiments D and E produce new,
traceable artifacts under explicit approval. A clean deterministic suite or a
zero-warning workflow conversion alone proves implementation readiness, not a
successful end-to-end render.
