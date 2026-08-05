# Live/read-only evidence fixtures

This directory records sanitized preflight evidence for the controlled
character-to-video pipeline. The evidence was collected on 2026-08-04 from the
local ComfyUI instance at `http://127.0.0.1:8188/`. It contains no credentials,
request headers, prompt history, or generated media.

## Live preflight

- ComfyUI `0.29.0` responded to read-only `/system_stats`, `/object_info`,
  `/queue`, and `/userdata` requests.
- `/queue` reported zero running and zero pending jobs.
- No generation, upload, approval consumption, or `/prompt` request was made
  for this evidence run.

The hashes labelled **UI retrieval hash** are SHA-256 values of the compact
workflow JSON returned by the local `/userdata` endpoint after compact
`ConvertTo-Json -Depth 100` UTF-8 serialization. They are retrieval snapshots and are not a
replacement for the profile fingerprints. Profile and API graph hashes are the
pinned values consumed by the runtime profiles.

| Workflow | UI nodes / groups | UI retrieval hash | Profile / API evidence | Decision |
|---|---:|---|---|---|
| `文生图相机视角.json` | 141 / 44 | `bb4c97ffe954a179bbc2bda62fcdd5066c022390f0b356a3334c228771aafb83` | `camera-anima-v1` UI fingerprint `7fa7a85e005182c6be42a3f3193add3fb41531ef0fae28e1cbd54a791e72e20a`; prior MCP normalization: 42 API nodes, 7 warnings | Source only; normalize before execution |
| `Flux2-Klein人物一键多视图工作流.json` | 393 / 34 | `2936eda567e896ae5a0ebf92f3fd8b1187490c26f6492321cdcc294e8bd44a43` | Prior MCP conversion: 261 API nodes, 70 warnings and unresolved virtual-bus references | UI reference only; reject direct execution |
| `PromptForge-Flux2-Klein-multiview-flat-v2.json` | 261 / 0 | `5dda061dd9474cc688defa2e28a6fd0b9c0ae3106cd09682934fe72634b56920` | profile fingerprint `9dc2b01e2aea0b051113b187b134d007f452df6c83cfcbbd8d325eaa4c29e4da`; API graph hash `450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36`; 12 immutable pose references | Production graph, read-only verified |
| `LTX全新导演台工作流.json` | 26 / 4 | `d44e9924a68835f7da03e077c8f30c2160af8aa46b66e8e931a22603bcd309df` | profile fingerprint `8f777f6315bab2c14fb4d99d83a44d73cf8dfd7362011fc3a931fffa9a081074`; API graph hash `c7d0c07e2e6656af9737a7d92bea62bc4b4c7c11291bfb910e13eaa8a3f1fb74`; short profile `24` logical frames / `24` fps / `25` output frames / `1024x704` | Production graph, read-only verified |

The API conversion counts above are MCP evidence captured during workflow
normalization. The REST preflight does not expose the MCP conversion receipt;
therefore this README does not claim a fresh end-to-end API conversion or
generation run.

## Deterministic single-variable experiments

The tests below operate on pure plans or sanitized graph fixtures. Plan hashes
and synthetic graph diffs are computed in memory and are intentionally not
persisted as fake artifact hashes.

1. **Evidence-to-asset fidelity (A)** — only ArtBible lighting changes. The
   character identity lock, face lock, world taboos, asset-card hash, and style
   prompt remain unchanged; the allowed differences are the ArtBible hash,
   lighting field, and its evidence-list entry.
2. **Environment-master reuse (B)** — two shot deltas reuse one environment
   card. Anchors, layout, materials, light logic, wear/damage trace,
   fingerprint, and card hash are byte-identical; only `shot_deltas` changes.
3. **Flat-v2 orientation (C)** — only switch node `731.boolean` changes. All
   twelve pose-reference nodes remain byte-identical. `side_unknown` is rejected
   for directional use until an explicit manual-review orientation proof is
   attached.
4. **LTX timeline and split gate (D)** — the short profile compiles 24 logical
   frames at 24 fps to 25 output frames on a 1024x704 canvas, while node `195`
   remains unchanged. Duration must equal the profile's frame budget and
   rounded segment lengths must cover it contiguously. An intent with a
   scene/time change produces a required split recommendation and Stage 4
   rejects compression into one clip.

Focused results: `test_live_character_base.py` A/B: 2 passed;
`test_live_multiview.py` C: 2 passed (the opt-in external MCP preflight test is
skipped without a receipt); `test_yusu_timeline.py` D: 2 passed.

## Limitation and rerun boundary

The opt-in tests named `test_live_*` remain guarded by
`PROMPT_FORGE_LIVE=1` and an externally approved consumption bundle. With no
such approval, a live generation is correctly not attempted. Passing these
deterministic experiments proves the contracts and graph allowlists, not that a
new PNG or video was generated. A future live run must retain the workflow,
profile, source graph, approval, run record, and output artifact hashes before
it can be called an end-to-end pipeline pass.
