# Camera image flow

Both `t2i-camera` and `i2i-camera` consume a complete production-ready Anima `prompt_artifact`. The envelope contains exactly that object; positive and negative strings are not independent request fields.

## Sequence

```text
validate artifact hash/task/model/token status
-> upload reference/control images when declared
-> load fixed camera-anima UI asset
-> apply camera-owned config and group modes
-> revalidate artifact and write nodes 24/25
-> strip UI to API once
-> validate graph and local runtime
-> enqueue once and wait for terminal history
-> download image and record bytes/SHA-256
```

`i2i-camera` requires `reference_image` and activates the released reference latent path before strip. ControlNet requires its declared group and uploaded image. Camera, image size, sampling, seed, ControlNet, groups, and camera runtime LoRA selections remain execution settings and are absent from Prompt Forge.

The fixed source asset is `skills/camera-image/camera_image/runtime/workflow_assets/camera-anima.json`; group membership comes from `workflow/{stage}/groups.json`. Do not discover another workflow, modify the post-strip topology, or use raw prompt text.

Acceptance requires a valid artifact, valid submitted API graph, successful terminal history, nonempty real image, output hash, submitted graph record, and run record.
