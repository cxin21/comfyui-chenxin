# Task 4 report: profiled camera asset boards and character base

## Delivered

- Added typed `build_asset_board_plan` output for environment, character, and prop boards. Plans bind the asset ID, source story, art bible, visual fingerprint, workflow fingerprint, profile, expected artifact type, and optional variant parent hashes.
- Added `build_character_base_plan` for a validated `CharacterAsset`, with front/eye-level medium-or-full-body framing, neutral CameraExtra, and all groups/optional branches disabled.
- Added `patch_asset_board_prompt`, which deep-copies the graph, patches only nodes 24/25, rejects cross-role prompt contamination, and appends the profile-owned negative constraints.
- Added `patch_camera_controls`, which patches only the declared node 583 and node 585 input allowlists and rejects incomplete field sets, invalid selectors, invalid values, and graph drift outside those paths.
- Added role-specific environment/character/prop board profiles and the clean `camera-anima-base-v1` profile from the pinned camera fingerprint and normalization bridge.

## TDD evidence

1. The initial focused RED run produced `5 failed, 46 passed`: the two public adapter functions and two stage builders were absent.
2. The profile RED run produced four expected missing-file failures for the three board profiles and the character-base profile.
3. The first GREEN run exposed that the test art bible lacked the complete evidence tiers required by the existing asset-plan boundary; the fixture was corrected without weakening production validation.

## Verification

```text
pytest -q skills/prompt-forge/runtime/tests/test_camera_adapter.py skills/prompt-forge/runtime/tests/test_camera_img2img.py skills/prompt-forge/runtime/tests/test_stage2_plan.py skills/prompt-forge/runtime/tests/test_execution.py
# 132 passed, 1 skipped

python -m compileall -q skills/prompt-forge/runtime/adapters/camera.py skills/prompt-forge/runtime/stages.py skills/prompt-forge/runtime/execution.py skills/prompt-forge/runtime/tests/test_camera_adapter.py skills/prompt-forge/runtime/tests/test_stage2_plan.py skills/prompt-forge/runtime/tests/test_execution.py

ruff check skills/prompt-forge/runtime/adapters/camera.py skills/prompt-forge/runtime/stages.py skills/prompt-forge/runtime/tests/test_camera_adapter.py skills/prompt-forge/runtime/tests/test_stage2_plan.py
# All checks passed

git diff --check
# exit 0; only repository line-ending warnings
```

All four new JSON profiles were parsed successfully. The existing skipped camera test remains unchanged.

## Scope

No submission path or live ComfyUI generation was added. User-owned `stage_execution.py` and `test_stage_execution.py` changes, the design document, and the untracked plan documents were not modified or staged by Task 4.

## Fix round 1: profile binding, lineage, and fail-closed isolation

The review failures traced to five disconnected trust boundaries: camera normalization recognized only the legacy profile ID; stage plans trusted caller-shaped hashes; asset-card validation intentionally admitted unknown derivative metadata; role matching used `\w` boundaries that let `1girl` bypass `girl`; and CameraExtra patching trusted arbitrary profile slot selectors.

Repairs:

- Base and board profiles now declare their legacy execution alias and pinned output topology. The normalization adapter accepts only those named aliases with the exact inherited bridge. Character-base execution accepts the clean base alias and explicitly rejects board profiles.
- Both Task 4 stage builders require the loaded profile object, recompute its canonical content hash, compare the supplied fingerprint/hash, and derive the emitted profile fields from that object.
- Every Task 4 plan now has a deterministic hash-bound `lineage_id`. Parent lineage is copied only for an explicit complete variant whose source and parent hashes agree.
- Character-base planning rejects explicit non-acceptance, derivative/source metadata, top-level scene/prop fields, and scene/prop facts embedded inside identity or face locks.
- Role vocabularies and ASCII-letter token boundaries close numeric-prefix and semantic bypasses while leaving character identity tokens such as `1girl` valid in character boards.
- Camera controls require fixed nodes 583/585, the pinned workflow fingerprint, declared output topology, complete CameraExtra inputs, and unchanged data outside the allowlist.

RED evidence:

```text
pytest -q test_camera_adapter.py test_stage2_plan.py test_execution.py
# 18 failed, 107 passed, 1 skipped

pytest -q test_execution.py -k non_clean_base_profile_alias
# 1 failed: alias enabled_groups=[3] was not rejected
```

GREEN and final verification:

```text
pytest -q skills/prompt-forge/runtime/tests/test_camera_adapter.py skills/prompt-forge/runtime/tests/test_camera_img2img.py skills/prompt-forge/runtime/tests/test_stage2_plan.py skills/prompt-forge/runtime/tests/test_execution.py
# 150 passed, 1 skipped

python -m compileall -q <Task 4 Python sources and focused tests>
ruff check <Task 4 Python sources and focused tests>
# All checks passed

git diff --check
# exit 0; repository line-ending warnings only
```
