# Camera video flow

| Stage | Artifact task | Text node | Duration node | Images |
|---|---|---:|---:|---|
| `t2v-video` | `h3_t2va` | 234 | 236 | none |
| `i2v-video` | `h3_ref2va` | 312 | 323 | `reference_image_1` -> node 335 |
| `multi-i2v-video` | `h3_ref2va` | 339 | 350 | image 1/2/3 -> nodes 362/364/365 |

Every request carries the complete `prompt_artifact` under the envelope and numeric `duration` under config. Ref2VA image count must match the hashed reference context. Duration must match the final audited shot end.

## Sequence

```text
validate artifact
-> load hash-locked stage API graph
-> upload ordered local images
-> revalidate artifact in graph patcher
-> write artifact text, duration, and returned filenames
-> validate project graph, ComfyUI graph, and local runtime
-> enqueue once and wait for terminal history
-> download every saved MP4 and record bytes/SHA-256
```

Assets are fixed releases listed in `skills/camera-video/camera_video/runtime/workflow_assets/manifest.json`. The executor does not discover, strip, repair, or reconfigure them. Models, sampler, codec, audio mode, output nodes, and connections remain fixed graph content.

Acceptance requires task/model/hash/token/reference/duration gates, valid graph/runtime checks, terminal ComfyUI success, nonempty downloaded MP4 files, hashes, submitted graph, and run record. A prompt ID or successful enqueue alone is insufficient.
