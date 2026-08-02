# Prompt Forge v7 Slice 4 Yusu LTX Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile a motion-aware video prompt, atomically patch the Yusu LTX timeline with the accepted shot image and produce a verified one-second video with complete lineage.

**Architecture:** Add video PromptBuild quality gates, a dedicated Yusu timeline adapter and technical video verification. The adapter parses and reserializes timeline JSON and synchronizes every derived field; string replacement is forbidden. Stage 4 reuses Slice 1 execution/record contracts and never changes workflow models, LoRAs or fixed negative conditioning.

**Tech Stack:** Python 3.11+ standard library, pytest, Prompt Forge video compiler, ComfyUI REST, comfyui-mcp, LTX 2.3/Yusu nodes already installed locally.

## Global Constraints

- Slices 1–3 completion gates are required.
- Input is one accepted `ShotImage`.
- Video PromptBuild must contain subject, action, motion and camera.
- Preserve workflow-owned negative node 195 unchanged.
- Patch `YusuLTXDirector` node 174 through structured JSON only.
- Baseline is one image segment, 24 frames, 24 fps.
- Keep current model, LoRAs, sampler, scheduler and resolution unchanged.
- One ComfyUI job at a time; never clear VRAM while a job runs.
- Default tests never enqueue; Experiment E requires `PROMPT_FORGE_LIVE=1`.

---

## File Structure

- Modify `skills/prompt-forge/runtime/prompt_quality.py`.
- Modify `skills/prompt-forge/runtime/tests/test_prompt_quality.py`.
- Create `skills/prompt-forge/runtime/profiles/ltx-yusu-director.json`.
- Create `skills/prompt-forge/runtime/adapters/yusu_timeline.py`.
- Create `skills/prompt-forge/runtime/tests/fixtures/yusu-api-minimal.json`.
- Create `skills/prompt-forge/runtime/tests/test_yusu_timeline.py`.
- Modify `skills/prompt-forge/runtime/artifacts.py`.
- Create `skills/prompt-forge/runtime/tests/test_video_artifact.py`.
- Modify `skills/prompt-forge/runtime/stages.py`.
- Create `skills/prompt-forge/runtime/pipeline_state.py`.
- Create `skills/prompt-forge/runtime/tests/test_pipeline_state.py`.
- Create `skills/prompt-forge/runtime/tests/test_stage4_plan.py`.
- Create `skills/prompt-forge/runtime/tests/test_live_ltx_video.py`.
- Modify `skills/prompt-forge/runtime/runtime_cli.py`.
- Modify `skills/prompt-forge/SKILL.md`.
- Modify `README.md` and `CHANGELOG.md`.

### Task 1: Video PromptBuild quality gate

**Files:**
- Modify: `skills/prompt-forge/runtime/prompt_quality.py`
- Modify: `skills/prompt-forge/runtime/tests/test_prompt_quality.py`

**Interfaces:**
- Consumes: PromptBuild plus its normalized PromptIntent.
- Produces: `validate_ltx_prompt_build(build, intent) -> list[str]`.

- [ ] **Step 1: Write failing tests**

~~~python
from runtime.prompt_quality import validate_ltx_prompt_build


def valid_intent():
    dimensions = {name: [] for name in (
        "subject", "action", "scene", "lighting", "composition", "camera",
        "motion", "timeline", "audio", "color", "style", "mood", "medium", "quality"
    )}
    dimensions["subject"] = [{"value": "the swordswoman", "origin": "explicit"}]
    dimensions["action"] = [{"value": "raises her sword", "origin": "explicit"}]
    dimensions["motion"] = [{"value": "cloth and hair trail continuously", "origin": "explicit"}]
    dimensions["camera"] = [{"value": "slow dolly in", "origin": "explicit"}]
    return {"target": "video", "dimensions": dimensions, "locked_facts": ["the swordswoman"]}


def test_complete_ltx_build_passes():
    build = {
        "target": "video",
        "dialect": "video-timeline",
        "prompt": "The swordswoman raises her sword as cloth and hair trail continuously. The camera slowly dollies in.",
        "negative_prompt": "",
        "ready_to_execute": True,
    }
    assert validate_ltx_prompt_build(build, valid_intent()) == []


def test_static_quality_only_prompt_fails():
    build = {
        "target": "video",
        "dialect": "video-timeline",
        "prompt": "masterpiece, best quality, cinematic",
        "negative_prompt": "",
        "ready_to_execute": True,
    }
    errors = validate_ltx_prompt_build(build, valid_intent())
    assert "motion" in " ".join(errors)


def test_second_negative_system_fails():
    build = {
        "target": "video",
        "dialect": "video-timeline",
        "prompt": "The swordswoman moves while the camera dollies in.",
        "negative_prompt": "watermark",
        "ready_to_execute": True,
    }
    assert any("workflow-owned negative" in item for item in validate_ltx_prompt_build(build, valid_intent()))
~~~

- [ ] **Step 2: Run RED**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_prompt_quality.py -q
~~~

Expected: import failure.

- [ ] **Step 3: Implement the gate**

Require ready video build, `video-timeline` dialect, non-empty subject/action/motion/
camera dimensions, every locked fact represented in normalized prompt text and an
empty PromptBuild negative prompt for the Yusu profile. Return deterministic
human-readable errors; do not mutate the build.

- [ ] **Step 4: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_prompt_quality.py skills/prompt-forge/internals/tests/test_prompt_compile.py -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): validate ltx video prompt builds"
~~~

### Task 2: Atomic Yusu timeline adapter

**Files:**
- Create: `skills/prompt-forge/runtime/profiles/ltx-yusu-director.json`
- Create: `skills/prompt-forge/runtime/adapters/yusu_timeline.py`
- Create: `skills/prompt-forge/runtime/tests/fixtures/yusu-api-minimal.json`
- Create: `skills/prompt-forge/runtime/tests/test_yusu_timeline.py`

**Interfaces:**
- Consumes: node 174 API inputs, uploaded shot image path, video prompt, 24 frames/fps.
- Produces: `patch_yusu_timeline(graph, image_ref, prompt, frames, fps, profile) -> dict`, `validate_yusu_sync(graph, profile) -> None`.

- [ ] **Step 1: Write failing round-trip tests**

~~~python
import json
from pathlib import Path
import pytest
from runtime.adapters.yusu_timeline import (
    YusuTimelineError, patch_yusu_timeline, validate_yusu_sync
)

FIXTURE = Path(__file__).parent / "fixtures" / "yusu-api-minimal.json"
PROFILE = {"director_node_id": 174, "negative_node_id": 195}


def test_one_segment_is_patched_and_derived_fields_match():
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    patched = patch_yusu_timeline(
        graph,
        {"imageFile": "runs/lineage/shot.png", "imageB64": "/api/view?filename=shot.png&type=input&subfolder=runs/lineage"},
        "The swordswoman lunges as the camera slowly dollies in.",
        24,
        24,
        PROFILE,
    )
    node = patched["174"]["inputs"]
    timeline = json.loads(node["timeline_data"])
    assert timeline["segments"][0]["imageFile"] == "runs/lineage/shot.png"
    assert timeline["segments"][0]["prompt"].startswith("The swordswoman")
    assert node["local_prompts"] == timeline["segments"][0]["prompt"]
    assert node["segment_lengths"] == "24"
    assert node["duration_frames"] == 24
    assert node["frame_rate"] == 24
    validate_yusu_sync(patched, PROFILE)


def test_malformed_timeline_is_rejected():
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    graph["174"]["inputs"]["timeline_data"] = "{broken"
    with pytest.raises(YusuTimelineError, match="timeline_data"):
        patch_yusu_timeline(graph, {"imageFile": "a.png", "imageB64": "/api/view?a"}, "move", 24, 24, PROFILE)


def test_fixed_negative_node_is_unchanged():
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    patched = patch_yusu_timeline(
        graph, {"imageFile": "a.png", "imageB64": "/api/view?a"},
        "The subject moves while the camera pans.", 24, 24, PROFILE
    )
    assert patched["195"] == graph["195"]
~~~

- [ ] **Step 2: Run RED**

Run `test_yusu_timeline.py`. Expected: import failure.

- [ ] **Step 3: Add the exact profile**

~~~json
{
  "schema_version": "1.0",
  "profile_id": "ltx-yusu-director-v1",
  "workflow_name": "LTX全新导演台工作流.json",
  "generation_modes": ["image-to-video"],
  "runtime_classification": "local",
  "director_node_id": 174,
  "negative_node_id": 195,
  "slots": {
    "director": {"id": 174, "type": "YusuLTXDirector"},
    "negative": {"id": 195, "type": "CLIPTextEncode"}
  },
  "allowed_mutations": [
    "director.timeline_data",
    "director.local_prompts",
    "director.segment_lengths",
    "director.guide_strength",
    "director.transition_smoothness",
    "director.start_second",
    "director.end_second",
    "director.duration_seconds",
    "director.start_frame",
    "director.end_frame",
    "director.duration_frames",
    "director.frame_rate"
  ],
  "expected_outputs": ["video"]
}
~~~

Model and LoRA selections remain immutable and are checked against exact
`object_info` input options during preflight.

- [ ] **Step 4: Implement structured timeline patching**

Parse existing `timeline_data` with `json.loads`. Replace `segments` with one
object containing deterministic ID `segment-0001`, start 0, length 24, supplied
prompt/image fields, type `image`, `isEndFrame=false`. Preserve global prompt
and unrelated editor settings. Update all derived scalar fields, serialize using
canonical JSON, then call `validate_yusu_sync`.

Validation reparses JSON and checks segment count, prompt list, length list, frame
range, seconds, guide-strength cardinality and transition cardinality. Compare the
entire patched graph to source after removing allowlisted director fields; node
195 and every model/LoRA input must be identical.

- [ ] **Step 5: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_yusu_timeline.py -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): patch yusu ltx timelines atomically"
~~~

### Task 3: Video artifact verification and pipeline state

**Files:**
- Modify: `skills/prompt-forge/runtime/artifacts.py`
- Create: `skills/prompt-forge/runtime/pipeline_state.py`
- Create: `skills/prompt-forge/runtime/tests/test_video_artifact.py`
- Create: `skills/prompt-forge/runtime/tests/test_pipeline_state.py`

**Interfaces:**
- Consumes: output path, ffprobe metadata, stage hashes.
- Produces: `probe_video(path: Path) -> dict`, `verify_video_artifact(...) -> dict`, `advance_state(state, transition) -> dict`, `stage_is_reusable(...) -> bool`.

- [ ] **Step 1: Write failing tests**

~~~python
from pathlib import Path
import subprocess
import pytest
from runtime.artifacts import ArtifactError, probe_video, verify_video_artifact
from runtime.pipeline_state import PipelineStateError, advance_state, stage_is_reusable


def test_video_requires_expected_fps_and_frames():
    result = verify_video_artifact(
        {"filename": "clip.mp4", "size_bytes": 1000, "fps": 24, "frame_count": 24},
        expected_fps=24, expected_frames=24,
    )
    assert result["artifact_type"] == "VideoClip"


def test_empty_video_fails():
    with pytest.raises(ArtifactError, match="empty"):
        verify_video_artifact(
            {"filename": "clip.mp4", "size_bytes": 0, "fps": 24, "frame_count": 24},
            24, 24
        )


def test_ffprobe_reads_real_one_second_fixture(tmp_path):
    target = tmp_path / "clip.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=64x64:r=24",
        "-t", "1", "-pix_fmt", "yuv420p", str(target)
    ], check=True)
    metadata = probe_video(Path(target))
    assert metadata["fps"] == 24
    assert metadata["frame_count"] == 24


def test_stage_order_is_enforced():
    with pytest.raises(PipelineStateError, match="SHOT_READY"):
        advance_state({"status": "BASE_READY", "stages": {}}, "VIDEO_READY")


def test_reuse_requires_all_hashes():
    saved = {"input_hash": "a", "prompt_build_hash": "b", "workflow_hash": "c", "profile_version": "1"}
    assert stage_is_reusable(saved, "a", "b", "c", "1")
    assert not stage_is_reusable(saved, "a", "changed", "c", "1")
~~~

- [ ] **Step 2: Run RED**

Run both new files. Expected: missing symbols.

- [ ] **Step 3: Implement technical verification**

`probe_video` runs `ffprobe -v error -count_frames -show_streams -show_format
-of json`, parses the first video stream and converts rational frame rate plus
`nb_read_frames` into integers. Missing ffprobe, nonzero exit, invalid JSON or no
video stream raises `ArtifactError`. Accept only a safe output path, positive
size, fps equal to plan and frame count equal to plan. Compute content hash from
file bytes; do not infer semantic quality from metadata. Return a `VideoClip`
artifact with lineage and source ShotImage hashes.

- [ ] **Step 4: Implement state and reuse rules**

Allowed order:

~~~python
ORDER = [
    "DISCOVERED",
    "BASE_PREFLIGHTED", "BASE_READY",
    "SHEET_PREFLIGHTED", "SHEET_READY",
    "SHOT_PREFLIGHTED", "SHOT_READY",
    "VIDEO_PREFLIGHTED", "VIDEO_READY",
]
~~~

Only the immediate next transition is allowed. A completed stage is reusable only
when input, PromptBuild, workflow and profile hashes all match. Failure records do
not remove accepted earlier stages.

- [ ] **Step 5: Verify and commit**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
python -m pytest skills/prompt-forge/runtime/tests/test_video_artifact.py skills/prompt-forge/runtime/tests/test_pipeline_state.py -q
git add skills/prompt-forge/runtime
git commit -m "feat(prompt-forge): verify video artifacts and pipeline state"
~~~

### Task 4: Stage 4 plan, CLI and live Experiment E

**Files:**
- Modify: `skills/prompt-forge/runtime/stages.py`
- Modify: `skills/prompt-forge/runtime/runtime_cli.py`
- Create: `skills/prompt-forge/runtime/tests/test_stage4_plan.py`
- Create: `skills/prompt-forge/runtime/tests/test_live_ltx_video.py`
- Modify: `skills/prompt-forge/SKILL.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: accepted ShotImage, LTX PromptBuild, current profile/capability, approval.
- Produces: Stage 4 ExecutionPlan, patched graph, VideoClip, RunRecord, `VIDEO_READY`.

- [ ] **Step 1: Write a failing Stage 4 test**

~~~python
import pytest
from runtime.stages import StageError, build_video_plan


def test_video_plan_requires_accepted_shot():
    shot = {"artifact_type": "ShotImage", "accepted": False, "content_hash": "shot"}
    with pytest.raises(StageError, match="accepted ShotImage"):
        build_video_plan(shot, {"ready_to_execute": True}, "wfhash", "profilehash", True)


def test_video_plan_locks_one_second_baseline():
    shot = {"artifact_type": "ShotImage", "accepted": True, "content_hash": "shot"}
    build = {
        "ready_to_execute": True,
        "target": "video",
        "dialect": "video-timeline",
        "prompt": "The subject moves as the camera dollies in.",
        "negative_prompt": "",
    }
    plan = build_video_plan(shot, build, "wfhash", "profilehash", True)
    assert plan["stage"] == "video"
    assert plan["parameters"]["frames"] == 24
    assert plan["parameters"]["fps"] == 24
~~~

- [ ] **Step 2: Implement the plan and CLI**

Require accepted ShotImage, passing LTX quality gate, current capability report,
matching profile/fingerprint, exact installed model/LoRA choices, idle queue,
resource preflight and explicit approval. Add `plan-video`, `patch-yusu`,
`verify-video` and `pipeline-state` CLI commands.

- [ ] **Step 3: Add opt-in Experiment E**

The live test changes one logical variable in the validated LTX workflow: replace
the one timeline segment with the accepted ShotImage and video PromptBuild.
Preserve model, LoRAs, sampler, scheduler, resolution and fixed negative node.
Assert terminal success, 24 frames at 24 fps, non-empty video, exact guide/prompt
hashes and `VIDEO_READY`.

If preflight reports insufficient free VRAM, verify queue is empty, request the
adapter's normal cache-release operation, regenerate CapabilityReport and record
that action. Do not restart ComfyUI or install/change models.

- [ ] **Step 4: Update user-facing documentation**

SKILL.md describes the complete four-stage flow and stage resume behavior. README
lists only implemented/runtime-verified capabilities. CHANGELOG records each
slice and the exact live experiments that passed; it must not claim video success
until Experiment E completes.

- [ ] **Step 5: Run full deterministic verification**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
Remove-Item Env:PROMPT_FORGE_LIVE -ErrorAction SilentlyContinue
python -m pytest skills/prompt-forge/runtime/tests skills/prompt-forge/internals/tests -q
python skills/prompt-forge/internals/evaluate.py
git diff --check
~~~

- [ ] **Step 6: Run Experiment E after explicit approval**

~~~powershell
$env:PYTHONPATH='skills/prompt-forge'
$env:PROMPT_FORGE_LIVE='1'
python -m pytest skills/prompt-forge/runtime/tests/test_live_ltx_video.py -v
~~~

- [ ] **Step 7: Commit Slice 4**

~~~powershell
git add skills/prompt-forge README.md CHANGELOG.md
git commit -m "feat(prompt-forge): complete v7 character-to-video loop"
~~~

## Slice 4 Completion Gate

- Yusu timeline round-trips without loss or derived-field drift.
- Node 195 and all model/LoRA settings are unchanged.
- Experiment E emits a valid one-second video.
- All four stages share lineage and are independently resumable.
- All deterministic and live gates pass before v7 is called complete.
