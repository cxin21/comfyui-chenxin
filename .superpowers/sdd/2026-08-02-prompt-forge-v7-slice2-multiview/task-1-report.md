# Task 1 report: Flux2-Klein dual base-image adapter

## RED

Added `test_flux_multiview.py` before production code. The initial focused run
failed during collection with the expected `ModuleNotFoundError` for
`runtime.adapters.flux_multiview`.

## Verified workflow evidence

Read-only inspection of local ComfyUI at `127.0.0.1:8188` listed
`Flux2-Klein人物一键多视图工作流.json`. Its saved workflow was read without
modification or enqueueing:

- nodes 111 and 667 are `LoadImage`; their stored widgets contain the same
  current base image;
- pose-image `LoadImage` nodes are 368, 151, 152, 154, 360, 364, 148, 149,
  147, 373, 150 and 367;
- `object_info` confirms `LoadImage` is available;
- structural fingerprint is
  `fff6236efa6727ac6584d61f640a63f9602b2d07a545d216b96a870a681e6faf`.

## GREEN

Implemented `patch_base_images` and `assert_dual_input_sync` with deep-copy,
strict dual-slot validation, image-reference path validation, exact dual-image
synchronization and canonical comparison that permits only the two declared
`inputs.image` values. The profile is local-only and records the verified
fingerprint, base slots, allowed mutations and immutable pose role.

Focused regression: `13 passed`.

## Self-review and risk

The actual UI workflow nodes 111 and 667 do not contain a persisted `title`
field. The profile therefore uses only the verified `id` and `type` selectors;
inventing `title: "Load Image"` would make profile resolution fail against the
real workflow. Existing `resolve_slots` still checks every declared selector,
and the profile's structural fingerprint protects against drift. A later
profile-schema change may explicitly model the verified absence of a title if
title-presence validation becomes mandatory.

No image hash is written into the API graph; it remains upstream lineage
evidence as required. No workflow was saved and no execution was enqueued.

## Verification

- `python -m pytest skills/prompt-forge/runtime/tests/test_flux_multiview.py skills/prompt-forge/runtime/tests/test_workflow_profile.py -q` — `23 passed`
- `python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q` — `215 passed, 3 skipped`
- `python -m compileall -q skills/prompt-forge/runtime` — success
- `git diff --check` — success
