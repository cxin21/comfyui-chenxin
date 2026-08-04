"""Pure stage-specific execution-plan builders."""

from __future__ import annotations

import copy

from .contracts import content_hash
from .prompt_quality import validate_anima_prompt_build, validate_ltx_prompt_build
from .reference_select import VIEW_ALIASES, VIEW_DEGREES


class StageError(ValueError):
    """Raised when a stage cannot be built from complete accepted evidence."""


_G1_NODE_IDS = [21, 58, 57, 59]

# The profiled LTX Director graph requests a 1280x720 target box, but its
# maintain-aspect-ratio image adapter snaps the 1216x832 Stage 3 camera frame
# to the model's 32-pixel lattice.  The resulting production baseline is
# therefore 1024x704.  Keep this explicit so a changed upstream canvas cannot
# silently alter the video contract.
LTX_BASELINE_OUTPUT_WIDTH = 1024
LTX_BASELINE_OUTPUT_HEIGHT = 704


def ltx_output_frame_count(duration_frames: int) -> int:
    """Return LTX's decoded pixel-frame count for a timeline duration.

    Yusu's LTX Director converts a logical duration to the model's temporal
    ``8n+1`` pixel-frame lattice.  A 24-frame timeline therefore decodes to
    25 frames; treating the two numbers as identical makes a valid render
    fail artifact verification.
    """
    if not isinstance(duration_frames, int) or isinstance(duration_frames, bool) or duration_frames <= 0:
        raise StageError("LTX duration_frames must be a positive integer")
    return max(9, ((duration_frames - 1 + 7) // 8) * 8 + 1)


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StageError(f"{label} is required")
    return value.strip()


def _canonical_view(value: object) -> str:
    view = _required_text(value, "desired_view").casefold()
    view = VIEW_ALIASES.get(view, view)
    if view not in VIEW_DEGREES:
        raise StageError(f"unknown desired view: {value!r}")
    return view


def _accepted_reference(reference: object) -> dict:
    if not isinstance(reference, dict) or reference.get("accepted") is not True:
        raise StageError("an accepted reference is required")
    artifact_type = reference.get("artifact_type")
    if artifact_type != "CharacterAngleView":
        raise StageError("Stage 3 reference must be a CharacterAngleView from Stage 2")
    content = _required_text(reference.get("content_hash"), "reference content_hash")
    result = copy.deepcopy(reference)
    result["content_hash"] = content
    return result


def _validate_shot_build(
    shot_prompt_build: dict,
    identity_facts: list[str] | None,
) -> None:
    if not isinstance(identity_facts, list) or not identity_facts or not all(
        isinstance(fact, str) and fact.strip() for fact in identity_facts
    ):
        raise StageError("Stage 3 requires locked identity facts")
    errors = validate_anima_prompt_build(
        shot_prompt_build,
        {"locked_facts": list(identity_facts)},
    )
    if errors:
        raise StageError("shot PromptBuild quality gate failed: " + "; ".join(errors))
    declared = {fact.casefold().strip() for fact in shot_prompt_build.get("locked_facts", [])}
    if not {fact.casefold().strip() for fact in identity_facts}.issubset(declared):
        raise StageError("shot PromptBuild must preserve locked identity facts")


def _g1_proof(proof: object) -> dict:
    if not isinstance(proof, dict):
        raise StageError("Stage 3 requires G1 path proof")
    required = {"vae_encode_node_id", "sampler_node_id", "traversed_node_ids"}
    if not required.issubset(proof):
        raise StageError("Stage 3 requires G1 path proof")
    if not all(
        isinstance(proof[key], int) and not isinstance(proof[key], bool)
        for key in ("vae_encode_node_id", "sampler_node_id")
    ):
        raise StageError("G1 path proof node IDs are invalid")
    traversed = proof["traversed_node_ids"]
    if not isinstance(traversed, list) or not traversed:
        raise StageError("G1 path proof traversal is invalid")
    return copy.deepcopy(proof)


def build_shot_plan(
    base_prompt_build_hash: str,
    shot_prompt_build_hash: str,
    reference: dict,
    desired_view: str,
    execution_approved: bool,
    *,
    shot_prompt_build: dict | None = None,
    identity_facts: list[str] | None = None,
    g1_proof: dict | None = None,
    workflow_fingerprint: str | None = None,
    profile_hash: str | None = None,
    capability_report_hash: str | None = None,
    camera: dict | None = None,
) -> dict:
    """Build a draft for a shot-specific camera img2img run.

    The compact arguments retain a useful planning API for dry-run callers;
    supplying a PromptBuild upgrades the function to the full Stage 3 quality
    and graph-path gate.
    """
    base_hash = _required_text(base_prompt_build_hash, "base PromptBuild hash")
    shot_hash = _required_text(shot_prompt_build_hash, "shot PromptBuild hash")
    if base_hash == shot_hash:
        raise StageError("Stage 3 requires a new PromptBuild distinct from Stage 1")
    selected = _accepted_reference(reference)
    view = _canonical_view(desired_view)
    if execution_approved is not True:
        raise StageError("Stage 3 requires explicit execution approval")

    proof = None
    patches: list[dict] = [
        {"slot": "camera", "input": "direction", "value": view},
        {"slot": "reference_image", "input": "load_image", "value": selected["content_hash"]},
        {"slot": "g1_mode", "input": "node_ids", "node_ids": list(_G1_NODE_IDS), "value": 0},
    ]
    if shot_prompt_build is not None:
        _validate_shot_build(shot_prompt_build, identity_facts)
        proof = _g1_proof(g1_proof)
        patches = [
            {"slot": "positive_prompt", "input": "wildcard_text", "value": shot_prompt_build["prompt"]},
            {"slot": "positive_prompt", "input": "populated_text", "value": shot_prompt_build["prompt"]},
            {"slot": "negative_prompt", "input": "wildcard_text", "value": shot_prompt_build["negative_prompt"]},
            {"slot": "negative_prompt", "input": "populated_text", "value": shot_prompt_build["negative_prompt"]},
            {"slot": "camera", "input": "direction", "value": view},
            {"slot": "reference_image", "input": "load_image", "value": selected["content_hash"]},
            {"slot": "g1_mode", "input": "node_ids", "node_ids": list(_G1_NODE_IDS), "value": 0},
        ]

    if workflow_fingerprint is not None:
        _required_text(workflow_fingerprint, "workflow_fingerprint")
    if profile_hash is not None:
        _required_text(profile_hash, "profile_hash")
    if capability_report_hash is not None:
        _required_text(capability_report_hash, "capability_report_hash")

    plan = {
        "schema_version": "1.0",
        "stage": "shot-image",
        "plan_state": "draft",
        "execution_approved": True,
        "local_only": True,
        "workflow_profile_id": "camera-anima-v1",
        "workflow_mode": "image-to-image",
        "workflow_fingerprint": workflow_fingerprint,
        "profile_hash": profile_hash,
        "capability_report_hash": capability_report_hash,
        "base_prompt_build_hash": base_hash,
        "shot_prompt_build_hash": shot_hash,
        "reference_artifact_type": selected["artifact_type"],
        "reference_hash": selected["content_hash"],
        "reference_view": selected.get("view_label"),
        "desired_view": view,
        "identity_facts": copy.deepcopy(identity_facts or []),
        "g1_path_proof": proof,
        "camera": copy.deepcopy(camera or {"direction": view}),
        "patches": patches,
        "expected_outputs": ["image/png"],
    }
    if shot_prompt_build is not None:
        plan["prompt_build"] = copy.deepcopy(shot_prompt_build)
    plan["plan_hash"] = content_hash(plan)
    return plan


def build_video_plan(*args, **kwargs):
    """Build a one-second Yusu Director video draft from one accepted ShotImage."""
    if len(args) < 5:
        raise StageError("video plan requires shot, PromptBuild, workflow hash, profile hash and approval")
    shot, prompt_build, workflow_hash, profile_hash, execution_approved = args[:5]
    if not isinstance(shot, dict) or shot.get("artifact_type") != "ShotImage" or shot.get("accepted") is not True:
        raise StageError("video plan requires an accepted ShotImage")
    shot_hash = _required_text(shot.get("content_hash"), "ShotImage content_hash")
    if not isinstance(prompt_build, dict):
        raise StageError("video plan requires a PromptBuild")
    _required_text(workflow_hash, "workflow hash")
    _required_text(profile_hash, "profile hash")
    if execution_approved is not True:
        raise StageError("video plan requires explicit execution approval")
    intent = kwargs.get("intent")
    if intent is not None:
        quality_errors = validate_ltx_prompt_build(prompt_build, intent)
        if quality_errors:
            raise StageError("video PromptBuild quality gate failed: " + "; ".join(quality_errors))
    else:
        if prompt_build.get("target") != "video":
            raise StageError("video PromptBuild target must be video")
        if prompt_build.get("dialect") != "video-timeline":
            raise StageError("video PromptBuild requires the video-timeline dialect")
        if prompt_build.get("ready_to_execute") is not True:
            raise StageError("video PromptBuild is not ready to execute")
        if not isinstance(prompt_build.get("prompt"), str) or not prompt_build["prompt"].strip():
            raise StageError("video prompt is empty")
        if prompt_build.get("negative_prompt") != "":
            raise StageError("video uses the workflow-owned negative conditioning; negative_prompt must be empty")
    frames = kwargs.get("frames", 24)
    fps = kwargs.get("fps", 24)
    if not isinstance(frames, int) or isinstance(frames, bool) or frames != 24:
        raise StageError("video baseline must use 24 frames")
    if not isinstance(fps, int) or isinstance(fps, bool) or fps != 24:
        raise StageError("video baseline must use 24 fps")
    output_width = kwargs.get("output_width", LTX_BASELINE_OUTPUT_WIDTH)
    output_height = kwargs.get("output_height", LTX_BASELINE_OUTPUT_HEIGHT)
    if (
        not isinstance(output_width, int)
        or isinstance(output_width, bool)
        or output_width != LTX_BASELINE_OUTPUT_WIDTH
        or not isinstance(output_height, int)
        or isinstance(output_height, bool)
        or output_height != LTX_BASELINE_OUTPUT_HEIGHT
    ):
        raise StageError("video baseline output must use the profiled 1024x704 canvas")
    plan = {
        "schema_version": "1.0",
        "stage": "video",
        "plan_state": "draft",
        "execution_approved": True,
        "local_only": True,
        "workflow_profile_id": "ltx-yusu-director-v1",
        "workflow_hash": workflow_hash,
        "profile_hash": profile_hash,
        "workflow_fingerprint": kwargs.get("workflow_fingerprint"),
        "capability_report_hash": kwargs.get("capability_report_hash"),
        "source_shot_hash": shot_hash,
        "prompt_build_hash": content_hash(prompt_build),
        "prompt_build": copy.deepcopy(prompt_build),
        "prompt_intent_hash": content_hash(intent) if intent is not None else None,
        "director_node_id": 174,
        "negative_node_id": 195,
        "parameters": {
            "frames": frames,
            "output_frames": ltx_output_frame_count(frames),
            "fps": fps,
            "output_width": output_width,
            "output_height": output_height,
            "start_frame": 0,
            "end_frame": frames - 1,
        },
        "patches": [
            {"slot": "director.timeline_data", "node_id": 174, "value": "segment-0001"},
            {"slot": "director.local_prompts", "node_id": 174, "value": prompt_build["prompt"]},
            {"slot": "director.segment_lengths", "node_id": 174, "value": str(frames)},
        ],
        "expected_outputs": ["video"],
    }
    plan["plan_hash"] = content_hash(plan)
    return plan
