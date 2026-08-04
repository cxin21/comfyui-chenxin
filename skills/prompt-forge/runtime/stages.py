"""Pure stage-specific execution-plan builders."""

from __future__ import annotations

import copy
import math
import re
from datetime import datetime, timezone

from .asset_plans import (
    AssetPlanError,
    build_character_board_plan,
    build_environment_board_plan,
    build_prop_board_plan,
)
from .artifacts import has_shot_derivative_metadata, is_ltx_input_eligible
from .contracts import ContractError, content_hash, validate_json_compatible
from .prompt_quality import validate_anima_prompt_build, validate_ltx_prompt_build
from .reference_select import (
    VIEW_ALIASES,
    VIEW_DEGREES,
    ReferenceSelectionError,
    select_reference_for_shot,
)
from .story_assets import (
    art_bible_hash,
    asset_card_hash,
    story_breakdown_hash,
    validate_art_bible,
    validate_asset_card,
    validate_story_breakdown,
)


class StageError(ValueError):
    """Raised when a stage cannot be built from complete accepted evidence."""


_G1_NODE_IDS = [21, 58, 57, 59]
_ASSET_BOARD_BUILDERS = {
    "environment": build_environment_board_plan,
    "character": build_character_board_plan,
    "prop": build_prop_board_plan,
}
_BOARD_ARTIFACT_TYPES = {
    "environment": "EnvironmentBoard", "character": "CharacterBoard", "prop": "PropBoard",
}
_NEUTRAL_CAMERA_EXTRA = {
    "extreme_type": "none", "extreme_weight": 0.0,
    "lens_enabled": False, "lens_value": "",
    "dof_enabled": False, "dof_value": "", "dof_weight": 0.0,
    "movement_enabled": False, "movement_value": "",
    "composition_enabled": False, "composition_value": "",
    "style_enabled": False, "style_value": "",
}
_CAMERA_EXECUTION_PROFILE_ID = "camera-anima-v1"
_CHARACTER_DERIVATIVE_FIELDS = frozenset(
    (
        "is_variant",
        "parent_artifact_hash",
        "parent_artifact_type",
        "source_artifact_hash",
        "source_artifact_type",
        "derived_from",
        "derivative_type",
    )
)
_CHARACTER_SCENE_PROP_FIELDS = frozenset(
    (
        "scene",
        "scene_id",
        "scene_lock",
        "environment",
        "environment_id",
        "prop",
        "props",
        "prop_ids",
        "prop_lock",
    )
)
_CHARACTER_SCENE_PROP_FACT = re.compile(
    r"(?<![A-Za-z_])(scene|room|background|environment|prop|weapon|sword)(?![A-Za-z_])",
    re.IGNORECASE,
)

# The profiled LTX Director graph requests a 1280x720 target box, but its
# maintain-aspect-ratio image adapter snaps the 1216x832 Stage 3 camera frame
# to the model's 32-pixel lattice.  The resulting production baseline is
# therefore 1024x704.  Keep this explicit so a changed upstream canvas cannot
# silently alter the video contract.
LTX_BASELINE_OUTPUT_WIDTH = 1024
LTX_BASELINE_OUTPUT_HEIGHT = 704

# Duration is selected explicitly at the Stage 4 boundary.  These are the
# only production budgets accepted by the compiler; the profile JSON files
# carry the same values for adapter/execution validation.
LTX_DURATION_PROFILES = {
    "ltx-yusu-director-v1": {
        "duration_seconds": 1.0,
        "frames": 24,
        "fps": 24,
        "output_frames": 25,
    },
    "ltx-yusu-short-v1": {
        "duration_seconds": 1.0,
        "frames": 24,
        "fps": 24,
        "output_frames": 25,
    },
    "ltx-yusu-long-v1": {
        "duration_seconds": 4.0,
        "frames": 96,
        "fps": 24,
        "output_frames": 97,
    },
}


def _duration_profile(profile_id: object) -> tuple[str, dict] | None:
    if profile_id is None:
        return None
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise StageError("duration profile id is required")
    normalized = profile_id.strip()
    aliases = {"ltx-yusu-short": "ltx-yusu-short-v1", "ltx-yusu-long": "ltx-yusu-long-v1"}
    normalized = aliases.get(normalized, normalized)
    profile = LTX_DURATION_PROFILES.get(normalized)
    if profile is None:
        raise StageError("unsupported duration profile")
    return normalized, copy.deepcopy(profile)


def _validate_video_timeline_segments(segments: object, duration: float) -> list[dict]:
    """Validate one contiguous, full-coverage timeline before execution."""
    if not isinstance(segments, list) or not segments:
        raise StageError("video timeline_segments must be a non-empty list")
    normalized: list[dict] = []
    previous_end = 0.0
    for index, raw in enumerate(segments, 1):
        if not isinstance(raw, dict):
            raise StageError("video timeline segment must be an object")
        start = raw.get("start_second")
        end = raw.get("end_second")
        prompt = raw.get("prompt")
        if (
            isinstance(start, bool)
            or not isinstance(start, (int, float))
            or not math.isfinite(float(start))
            or isinstance(end, bool)
            or not isinstance(end, (int, float))
            or not math.isfinite(float(end))
            or not isinstance(prompt, str)
            or not prompt.strip()
        ):
            raise StageError("video timeline segment seconds or prompt are invalid")
        start = float(start)
        end = float(end)
        if start < 0 or end <= start or end > duration + 1e-9:
            raise StageError("video timeline segment is outside the profile duration")
        if index == 1 and not math.isclose(start, 0.0, abs_tol=1e-9):
            raise StageError("video timeline must start at zero")
        if index > 1 and not math.isclose(start, previous_end, abs_tol=1e-9):
            raise StageError("video timeline segments must be contiguous")
        normalized.append(
            {**copy.deepcopy(raw), "start_second": start, "end_second": end, "prompt": prompt.strip()}
        )
        previous_end = end
    if not math.isclose(previous_end, duration, abs_tol=1e-9):
        raise StageError("video timeline must cover profile duration")
    return normalized


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


def _record_id(record: object, *fields: str) -> str | None:
    if not isinstance(record, dict):
        return None
    for field in fields:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _find_record(records: object, expected_id: str, *fields: str) -> dict | None:
    if not isinstance(records, list):
        return None
    matches = [
        record
        for record in records
        if _record_id(record, *fields) == expected_id
    ]
    if len(matches) > 1:
        raise StageError(f"story contains duplicate asset id {expected_id!r}")
    return copy.deepcopy(matches[0]) if matches else None


def _evidence_tiers(*contracts: dict) -> dict[str, list]:
    result = {
        "explicit_evidence": [],
        "reasonable_inference": [],
        "prohibited_expansion": [],
    }
    for contract in contracts:
        source = contract.get("provenance", contract)
        if not isinstance(source, dict):
            continue
        for key in result:
            values = source.get(key, [])
            if not isinstance(values, list):
                raise StageError(f"{key} must be a list")
            for value in values:
                if value not in result[key]:
                    result[key].append(copy.deepcopy(value))
    return result


def _timeline_node(story: dict, scene: dict, timeline_node_id: str) -> dict | None:
    sources = (
        scene.get("timeline_nodes"),
        story.get("timeline_nodes"),
        story.get("timeline"),
    )
    matches: list[dict] = []
    for source in sources:
        if not isinstance(source, list):
            continue
        for node in source:
            if _record_id(node, "timeline_node_id", "node_id", "id") == timeline_node_id:
                matches.append(node)
    if len(matches) > 1 and any(match != matches[0] for match in matches[1:]):
        raise StageError(f"timeline node {timeline_node_id!r} is ambiguous")
    return copy.deepcopy(matches[0]) if matches else None


def _required_id_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise StageError(f"{label} must be a list of non-empty identifiers")
    normalized = [item.strip() for item in value]
    if len(set(normalized)) != len(normalized):
        raise StageError(f"{label} must not contain duplicates")
    return normalized


def build_shot_intent(
    story: dict,
    art_bible: dict,
    *,
    scene_id: str,
    timeline_node_id: str,
    character_ids: list[str],
    environment_id: str | None,
    prop_ids: list[str],
    desired_view: str,
    camera: dict,
) -> dict:
    """Compile one evidence-bound shot intent without inventing missing facts."""
    try:
        story_copy = validate_story_breakdown(story)
        bible_copy = validate_art_bible(art_bible)
        validate_json_compatible(camera, "shot camera")
    except ContractError as exc:
        raise StageError(f"invalid shot intent source: {exc}") from exc
    scene_key = _required_text(scene_id, "scene_id")
    node_key = _required_text(timeline_node_id, "timeline_node_id")
    cast = _required_id_list(character_ids, "character_ids")
    props = _required_id_list(prop_ids, "prop_ids")
    if environment_id is not None:
        environment_id = _required_text(environment_id, "environment_id")
    if not isinstance(camera, dict) or not camera:
        raise StageError("camera must be a non-empty object")
    view = _canonical_view(desired_view)

    scene = _find_record(story_copy.get("scenes"), scene_key, "scene_id", "asset_id", "id")
    if scene is None:
        raise StageError(f"scene_id {scene_key!r} is not present in StoryBreakdown")
    node = _timeline_node(story_copy, scene, node_key)
    uncertainty = copy.deepcopy(story_copy.get("uncertainty", []))
    if not isinstance(uncertainty, list):
        raise StageError("story uncertainty must be a list")
    if node is None:
        uncertainty.append(f"timeline node {node_key!r} is not present in StoryBreakdown")

    known_characters = {
        value
        for record in story_copy.get("characters", [])
        if (value := _record_id(record, "character_id", "asset_id", "id")) is not None
    }
    for character_id in cast:
        if character_id not in known_characters:
            uncertainty.append(f"character asset {character_id!r} is not present in StoryBreakdown")
    if environment_id is not None:
        scene_environment = _record_id(scene, "environment_id", "asset_id")
        if scene_environment not in {None, environment_id}:
            raise StageError("environment_id conflicts with the selected story scene")
        if scene_environment is None:
            uncertainty.append(
                f"environment asset {environment_id!r} is not explicit in the selected scene"
            )
    known_props = {
        value
        for record in story_copy.get("props", [])
        if (value := _record_id(record, "prop_id", "asset_id", "id")) is not None
    }
    for prop_id in props:
        if prop_id not in known_props:
            uncertainty.append(f"prop asset {prop_id!r} is not present in StoryBreakdown")

    node = node or {}
    declared_deltas = copy.deepcopy(node.get("shot_deltas", {}))
    if not isinstance(declared_deltas, dict):
        raise StageError("timeline node shot_deltas must be an object")
    evidence = _evidence_tiers(story_copy, bible_copy)
    story_digest = story_breakdown_hash(story_copy)
    bible_digest = art_bible_hash(bible_copy)
    intent = {
        "schema_version": "1.0",
        "artifact_type": "ShotIntent",
        "source_story_hash": story_digest,
        "art_bible_hash": bible_digest,
        "scene_id": scene_key,
        "timeline_node_id": node_key,
        "character_ids": cast,
        "environment_id": environment_id,
        "prop_ids": props,
        "desired_view": view,
        "camera": copy.deepcopy(camera),
        "action": copy.deepcopy(node.get("action")),
        "dialogue": copy.deepcopy(node.get("dialogue")),
        "emotion": copy.deepcopy(node.get("emotion")),
        "continuity_locks": {
            "style": {
                key: copy.deepcopy(bible_copy[key])
                for key in (
                    "style", "medium", "visual_grammar", "palette", "materials",
                    "lighting", "motifs", "world_taboos", "continuity_strategy",
                )
            },
            "scene": copy.deepcopy(scene),
            "character_ids": list(cast),
            "environment_id": environment_id,
            "prop_ids": list(props),
        },
        "shot_deltas": declared_deltas,
        "uncertainty": uncertainty,
        **evidence,
    }
    task_context_hash = story_copy.get("task_context_hash")
    if task_context_hash is not None:
        intent["task_context_hash"] = _required_text(
            task_context_hash, "task_context_hash"
        )
    intent["shot_intent_hash"] = content_hash(intent)
    return intent


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StageError(f"{label} is required")
    return value.strip()


def _required_sha256(value: object, label: str) -> str:
    value = _required_text(value, label)
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise StageError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _validated_asset(asset_card: object, asset_type: str) -> dict:
    try:
        return validate_asset_card(asset_card, asset_type)
    except ContractError as exc:
        raise StageError(f"invalid {asset_type} asset: {exc}") from exc


def _validated_render_profile(
    profile: object,
    expected_profile_id: str,
    workflow_fingerprint: str,
    profile_hash: str,
) -> dict:
    if not isinstance(profile, dict) or profile.get("schema_version") != "1.0":
        raise StageError("a loaded versioned camera profile is required")
    if profile.get("profile_id") != expected_profile_id:
        raise StageError(f"render profile must be {expected_profile_id}")
    selected_fingerprint = _required_sha256(
        profile.get("workflow_fingerprint"), "profile workflow_fingerprint"
    )
    if _required_sha256(workflow_fingerprint, "workflow_fingerprint") != selected_fingerprint:
        raise StageError("workflow_fingerprint does not match the loaded profile")
    try:
        selected_hash = content_hash(profile)
    except (TypeError, ValueError) as exc:
        raise StageError(f"camera profile is not canonical JSON: {exc}") from exc
    if _required_sha256(profile_hash, "profile_hash") != selected_hash:
        raise StageError("profile_hash does not match the loaded profile")
    if (
        profile.get("source_profile_id") != _CAMERA_EXECUTION_PROFILE_ID
        or profile.get("execution_profile_id") != _CAMERA_EXECUTION_PROFILE_ID
        or profile.get("enabled_groups") != []
        or profile.get("enabled_optional_branches") != []
        or profile.get("expected_outputs") != ["image/png"]
    ):
        raise StageError("camera profile is not a clean pinned render contract")
    return copy.deepcopy(profile)


def _variant_parent(asset: dict) -> str | None:
    variant_fields = {"parent_artifact_hash", "source_artifact_hash"}
    present = variant_fields.intersection(asset)
    marker = asset.get("is_variant")
    if not present and marker is not True:
        if marker not in (None, False):
            raise StageError("asset variant marker must be boolean")
        return None
    if marker is not True or present != variant_fields:
        raise StageError("asset parent hash requires an explicit complete variant contract")
    parent = _required_sha256(asset["parent_artifact_hash"], "parent_artifact_hash")
    source = _required_sha256(asset["source_artifact_hash"], "source_artifact_hash")
    if source != parent:
        raise StageError("variant source_artifact_hash must match parent_artifact_hash")
    return parent


def _validate_character_base_source(character: dict) -> None:
    if character.get("accepted") is False:
        raise StageError("character base rejects an asset with accepted=False")
    if _CHARACTER_DERIVATIVE_FIELDS.intersection(character):
        raise StageError("character base rejects derivative source metadata")
    if _CHARACTER_SCENE_PROP_FIELDS.intersection(character):
        raise StageError("character base rejects scene or prop contamination")
    facts = list(character.get("identity_lock", []))
    for face_fact in character.get("face_lock", []):
        if isinstance(face_fact, dict):
            facts.append(face_fact.get("value"))
    if any(
        isinstance(fact, str) and _CHARACTER_SCENE_PROP_FACT.search(fact)
        for fact in facts
    ):
        raise StageError("character base identity contains scene or prop facts")


def build_asset_board_plan(
    asset_type: str,
    art_bible: dict,
    asset_card: dict,
    *,
    workflow_fingerprint: str,
    profile_hash: str,
    profile: dict,
) -> dict:
    """Bind a validated asset-board intent to one role-specific camera profile."""
    if asset_type not in _ASSET_BOARD_BUILDERS:
        raise StageError("asset_type must be environment, character, or prop")
    asset = _validated_asset(asset_card, asset_type)
    selected_profile = _validated_render_profile(
        profile,
        f"camera-anima-asset-board-{asset_type}-v1",
        workflow_fingerprint,
        profile_hash,
    )
    if (
        selected_profile.get("board_role") != asset_type
        or selected_profile.get("expected_artifact_type")
        != _BOARD_ARTIFACT_TYPES[asset_type]
    ):
        raise StageError(f"{asset_type} board profile role contract is invalid")
    try:
        board_intent = _ASSET_BOARD_BUILDERS[asset_type](art_bible, asset)
        bible_digest = art_bible_hash(art_bible)
    except (AssetPlanError, ContractError) as exc:
        raise StageError(f"invalid {asset_type} board contract: {exc}") from exc
    parent = _variant_parent(asset)
    asset_digest = asset_card_hash(asset)
    selected_profile_hash = content_hash(selected_profile)
    plan = {
        "schema_version": "1.0", "stage": "asset-board", "plan_state": "draft",
        "local_only": True, "asset_type": asset_type, "asset_id": asset["asset_id"],
        "source_story_hash": asset["source_story_hash"], "art_bible_hash": bible_digest,
        "asset_card_hash": asset_digest,
        "visual_fingerprint_hash": content_hash(asset["visual_fingerprint"]),
        "workflow_profile_id": f"camera-anima-asset-board-{asset_type}-v1",
        "workflow_fingerprint": selected_profile["workflow_fingerprint"],
        "profile_hash": selected_profile_hash,
        "board_intent": board_intent, "enabled_groups": [],
        "enabled_optional_branches": [],
        "expected_artifact_type": _BOARD_ARTIFACT_TYPES[asset_type],
        "expected_outputs": ["image/png"], "execution_approved": False,
    }
    lineage_contract = {
        "asset_card_hash": asset_digest,
        "art_bible_hash": bible_digest,
        "profile_hash": selected_profile_hash,
        "parent_artifact_hash": parent,
    }
    plan["lineage_id"] = content_hash(lineage_contract)
    if parent is not None:
        plan["parent_artifact_hash"] = parent
    plan["plan_hash"] = content_hash(plan)
    return plan


def build_character_base_plan(
    character_asset: dict,
    *,
    workflow_fingerprint: str,
    profile_hash: str,
    profile: dict,
    distance: str = "full_body",
) -> dict:
    """Build a clean identity-master plan from one validated CharacterAsset."""
    character = _validated_asset(character_asset, "character")
    _validate_character_base_source(character)
    selected_profile = _validated_render_profile(
        profile,
        "camera-anima-base-v1",
        workflow_fingerprint,
        profile_hash,
    )
    if selected_profile.get("expected_artifact_type") != "CharacterBaseImage":
        raise StageError("character base profile artifact contract is invalid")
    if distance not in {"medium", "full_body"}:
        raise StageError("character base distance must be medium or full_body")
    asset_digest = asset_card_hash(character)
    selected_profile_hash = content_hash(selected_profile)
    plan = {
        "schema_version": "1.0", "stage": "character-base", "plan_state": "draft",
        "local_only": True, "asset_id": character["asset_id"],
        "source_story_hash": character["source_story_hash"],
        "asset_card_hash": asset_digest,
        "visual_fingerprint_hash": content_hash(character["visual_fingerprint"]),
        "identity_lock": copy.deepcopy(character["identity_lock"]),
        "face_lock": copy.deepcopy(character["face_lock"]),
        "workflow_profile_id": selected_profile["execution_profile_id"],
        "render_profile_id": selected_profile["profile_id"],
        "workflow_fingerprint": selected_profile["workflow_fingerprint"],
        "profile_hash": selected_profile_hash,
        "camera": {"direction": "front", "elevation": "eye-level", "distance": distance, "roll": 0.0},
        "camera_extra": copy.deepcopy(_NEUTRAL_CAMERA_EXTRA),
        "enabled_groups": [], "enabled_optional_branches": [],
        "expected_artifact_type": "CharacterBaseImage", "expected_outputs": ["image/png"],
        "execution_approved": False,
    }
    plan["lineage_id"] = content_hash(
        {"asset_card_hash": asset_digest, "profile_hash": selected_profile_hash}
    )
    plan["plan_hash"] = content_hash(plan)
    return plan


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


def _bound_board(
    board: object,
    *,
    artifact_type: str,
    asset_id: str,
    intent: dict,
) -> dict:
    label = artifact_type.removesuffix("Board").casefold()
    if not isinstance(board, dict) or board.get("accepted") is not True:
        raise StageError(f"an accepted {label} board is required")
    if board.get("artifact_type") != artifact_type:
        raise StageError(f"{label} board artifact_type is invalid")
    if board.get("asset_id") != asset_id:
        raise StageError(f"{label} board asset_id does not match ShotIntent")
    digest = board.get("content_hash")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise StageError(f"{label} board content_hash must be a lowercase SHA-256 digest")
    for field in ("source_story_hash", "art_bible_hash"):
        if board.get(field) != intent.get(field):
            raise StageError(f"{label} board {field} does not match ShotIntent")
    expected_context = intent.get("task_context_hash")
    if expected_context is not None and board.get("task_context_hash") != expected_context:
        raise StageError(f"{label} board task_context_hash does not match ShotIntent")
    return copy.deepcopy(board)


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise StageError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _validated_reference_acceptance(reference: dict, content_digest: str) -> None:
    acceptance = reference.get("acceptance")
    if not isinstance(acceptance, dict) or set(acceptance) != {
        "schema_version",
        "artifact_hash",
        "actor",
        "accepted_at",
        "acceptance_id",
    }:
        raise StageError("Stage 3 reference acceptance evidence is missing")
    if (
        acceptance.get("schema_version") != "1.0"
        or acceptance.get("artifact_hash") != content_digest
        or not isinstance(acceptance.get("actor"), str)
        or not acceptance["actor"].strip()
        or not isinstance(acceptance.get("accepted_at"), str)
        or not acceptance["accepted_at"].strip()
    ):
        raise StageError("Stage 3 reference acceptance is not self-consistent")
    try:
        accepted_at = datetime.fromisoformat(
            acceptance["accepted_at"].replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise StageError("Stage 3 reference acceptance timestamp is invalid") from exc
    if (
        accepted_at.tzinfo is None
        or accepted_at.utcoffset() != timezone.utc.utcoffset(accepted_at)
    ):
        raise StageError("Stage 3 reference acceptance timestamp must be UTC")
    unsigned = dict(acceptance)
    acceptance_id = unsigned.pop("acceptance_id")
    if (
        not isinstance(acceptance_id, str)
        or acceptance_id != content_hash(unsigned)
        or reference.get("acceptance_id") != acceptance_id
    ):
        raise StageError("Stage 3 reference acceptance hash is invalid")


def _scene_aware_shot_bindings(
    intent: object,
    reference: dict,
    desired_view: str,
    character_board: object,
    environment: object,
    props: object,
) -> dict:
    if not isinstance(intent, dict) or intent.get("artifact_type") != "ShotIntent":
        raise StageError("a typed ShotIntent is required")
    claimed_intent_hash = intent.get("shot_intent_hash")
    unsigned_intent = dict(intent)
    unsigned_intent.pop("shot_intent_hash", None)
    if (
        not isinstance(claimed_intent_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", claimed_intent_hash)
        or claimed_intent_hash != content_hash(unsigned_intent)
    ):
        raise StageError("ShotIntent hash is not self-consistent")
    for field in ("source_story_hash", "art_bible_hash"):
        value = intent.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise StageError(f"ShotIntent {field} must be a lowercase SHA-256 digest")

    character_ids = _required_id_list(intent.get("character_ids"), "ShotIntent character_ids")
    if len(character_ids) != 1:
        raise StageError("Stage 3 currently requires exactly one character board")
    character = _bound_board(
        character_board,
        artifact_type="CharacterBoard",
        asset_id=character_ids[0],
        intent=intent,
    )
    character_hash = character["content_hash"]

    content_digest = _sha256(
        reference.get("content_hash"), "Stage 3 reference content_hash"
    )
    if (
        reference.get("reference_eligible") is not True
        or reference.get("semantic_conflict") is not False
        or reference.get("hash_verified") is not True
    ):
        raise StageError("Stage 3 reference is not eligible")
    _validated_reference_acceptance(reference, content_digest)
    for field in ("source_story_hash", "art_bible_hash"):
        if reference.get(field) != intent.get(field):
            raise StageError(f"Stage 3 reference {field} does not match ShotIntent")
    if reference.get("character_board_hash") != character_hash:
        raise StageError("Stage 3 reference character_board_hash does not match")
    expected_context = _sha256(
        intent.get("task_context_hash"), "ShotIntent task_context_hash"
    )
    if reference.get("task_context_hash") != expected_context:
        raise StageError("Stage 3 reference task_context_hash does not match ShotIntent")

    try:
        selection = select_reference_for_shot(
            desired_view,
            {"views": [reference.get("view_label")]},
            [reference],
        )
    except ReferenceSelectionError as exc:
        raise StageError(f"Stage 3 reference orientation is invalid: {exc}") from exc

    environment_id = intent.get("environment_id")
    environment_board = None
    if environment_id is not None:
        environment_board = _bound_board(
            environment,
            artifact_type="EnvironmentBoard",
            asset_id=_required_text(environment_id, "ShotIntent environment_id"),
            intent=intent,
        )
    elif environment is not None:
        raise StageError("ShotIntent does not permit an environment board")

    prop_ids = _required_id_list(intent.get("prop_ids"), "ShotIntent prop_ids")
    if not isinstance(props, list):
        raise StageError("prop boards must be a list")
    prop_boards: dict[str, dict] = {}
    for board in props:
        if not isinstance(board, dict):
            raise StageError("prop board must be an object")
        prop_id = board.get("asset_id")
        if prop_id in prop_boards:
            raise StageError("prop boards contain a duplicate asset_id")
        if prop_id not in prop_ids:
            raise StageError("prop board is not referenced by ShotIntent")
        prop_boards[prop_id] = _bound_board(
            board,
            artifact_type="PropBoard",
            asset_id=prop_id,
            intent=intent,
        )
    missing_props = [prop_id for prop_id in prop_ids if prop_id not in prop_boards]
    if missing_props:
        raise StageError(f"an accepted prop board is required for {missing_props[0]}")

    lineage_id = reference.get("lineage_id")
    if not isinstance(lineage_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", lineage_id
    ):
        raise StageError("Stage 3 reference lineage_id is invalid")
    for board in [character, environment_board, *prop_boards.values()]:
        if board is not None and board.get("lineage_id") != lineage_id:
            raise StageError("asset board lineage_id does not match the selected reference")

    selection_record = {
        "selection_reason": selection["selection_reason"],
        "distance_degrees": selection["distance_degrees"],
        "desired_view": selection["desired_view"],
        "selected_view": selection["selected_view"],
        "content_hash": content_digest,
    }
    for field in ("parent_artifact_hash", "source_artifact_hash"):
        if reference.get(field) is not None:
            selection_record[field] = reference[field]
    selection_record["character_board_hash"] = character_hash

    return {
        "shot_intent_hash": claimed_intent_hash,
        "source_story_hash": intent["source_story_hash"],
        "art_bible_hash": intent["art_bible_hash"],
        "character_board_hash": character_hash,
        "environment_board_hash": (
            environment_board["content_hash"] if environment_board is not None else None
        ),
        "prop_board_hashes": {
            prop_id: prop_boards[prop_id]["content_hash"] for prop_id in prop_ids
        },
        "reference_selection": selection_record,
        "continuity_locks": copy.deepcopy(intent.get("continuity_locks")),
        "shot_deltas": copy.deepcopy(intent.get("shot_deltas")),
        "explicit_evidence": copy.deepcopy(intent.get("explicit_evidence", [])),
        "reasonable_inference": copy.deepcopy(intent.get("reasonable_inference", [])),
        "prohibited_expansion": copy.deepcopy(intent.get("prohibited_expansion", [])),
        "task_context_hash": expected_context,
    }


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
    shot_intent: dict | None = None,
    character_board: dict | None = None,
    environment: dict | None = None,
    props: list[dict] | None = None,
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
        "production_eligible": False,
        "plan_mode": "legacy-dry-run",
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
    if selected.get("lineage_id") is not None:
        lineage_id = selected.get("lineage_id")
        if not isinstance(lineage_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", lineage_id
        ):
            raise StageError("Stage 3 reference lineage_id is invalid")
        plan["lineage_id"] = lineage_id
    if shot_intent is not None:
        plan.update(
            _scene_aware_shot_bindings(
                shot_intent,
                selected,
                view,
                character_board,
                environment,
                [] if props is None else props,
            )
        )
        plan["production_eligible"] = True
        plan["plan_mode"] = "scene-aware-production"
    if shot_prompt_build is not None:
        plan["prompt_build"] = copy.deepcopy(shot_prompt_build)
    plan["plan_hash"] = content_hash(plan)
    return plan


def build_video_plan(*args, **kwargs):
    """Build a one-second Yusu Director video draft from one accepted ShotImage."""
    if len(args) < 5:
        raise StageError("video plan requires shot, PromptBuild, workflow hash, profile hash and approval")
    shot, prompt_build, workflow_hash, profile_hash, execution_approved = args[:5]
    base_eligible = is_ltx_input_eligible(shot)
    forged_clean_metadata = (
        isinstance(shot, dict)
        and shot.get("artifact_type") == "ShotImage"
        and has_shot_derivative_metadata(shot)
    )
    if forged_clean_metadata:
        raise StageError("clean ShotImage cannot carry derivative metadata")
    context_eligible = isinstance(shot, dict) and all(
        isinstance(shot.get(field), str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", shot[field]))
        for field in ("task_context_hash", "source_story_hash", "art_bible_hash")
    )
    lineage_eligible = isinstance(shot, dict) and isinstance(
        shot.get("lineage_id"), str
    ) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", shot["lineage_id"]))
    production_source = base_eligible and context_eligible and lineage_eligible
    legacy_clean_source = (
        isinstance(shot, dict)
        and shot.get("artifact_type") == "ShotImage"
        and shot.get("accepted") is True
        and isinstance(shot.get("content_hash"), str)
        and bool(shot["content_hash"].strip())
        and shot.get("parent_artifact_hash") is None
    )
    if not production_source and not legacy_clean_source:
        raise StageError("video plan requires an accepted ShotImage")
    shot_hash = (
        _sha256(shot.get("content_hash"), "ShotImage content_hash")
        if production_source
        else _required_text(shot.get("content_hash"), "ShotImage content_hash")
    )
    shot_context = (
        {
            field: _sha256(shot.get(field), f"ShotImage {field}")
            for field in ("task_context_hash", "source_story_hash", "art_bible_hash")
        }
        if production_source
        else {}
    )
    shot_lineage_id = shot.get("lineage_id") if production_source else None
    if not isinstance(prompt_build, dict):
        raise StageError("video plan requires a PromptBuild")
    _required_text(workflow_hash, "workflow hash")
    _required_text(profile_hash, "profile hash")
    if execution_approved is not True:
        raise StageError("video plan requires explicit execution approval")
    duration_profile = _duration_profile(kwargs.get("duration_profile_id"))
    strict_video_contract = duration_profile is not None or any(
        key in kwargs for key in ("motion_delta", "split_decision", "timeline_segments")
    )
    if strict_video_contract and duration_profile is None:
        raise StageError("duration profile is required for production video")
    if strict_video_contract:
        motion_delta = kwargs.get("motion_delta")
        if not isinstance(motion_delta, str) or not motion_delta.strip():
            raise StageError("video motion_delta is required")
        split_decision = kwargs.get("split_decision")
        if not isinstance(split_decision, dict) or not isinstance(
            split_decision.get("required"), bool
        ) or not isinstance(split_decision.get("approved"), bool):
            raise StageError("video split decision must explicitly declare required and approved")
        recommendation = prompt_build.get("split_recommendation")
        if not isinstance(recommendation, dict) or not isinstance(
            recommendation.get("required"), bool
        ):
            raise StageError("video PromptBuild split recommendation is required")
        if recommendation["required"] != split_decision["required"]:
            raise StageError("video split decision does not match PromptBuild recommendation")
        if recommendation["required"] or split_decision["required"]:
            raise StageError("video PromptBuild requires split; Stage 4 will not compress the shot")
        if split_decision["approved"] is not True:
            raise StageError("video split decision must explicitly clear the split gate")
        for field in ("positive_zh", "positive_en"):
            if not isinstance(prompt_build.get(field), str) or not prompt_build[field].strip():
                raise StageError(f"video PromptBuild {field} is required")
        if prompt_build.get("negative_prompt") != "":
            raise StageError("video uses the workflow-owned negative conditioning; negative_prompt must be empty")
    intent = kwargs.get("intent")
    if strict_video_contract and not isinstance(intent, dict):
        raise StageError("production video requires a PromptIntent quality contract")
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
    if duration_profile is None:
        selected_profile_id = "ltx-yusu-director-v1"
        selected_profile = {"duration_seconds": 1.0, "frames": 24, "fps": 24, "output_frames": 25}
    else:
        selected_profile_id, selected_profile = duration_profile
    frames = kwargs.get("frames", selected_profile["frames"])
    fps = kwargs.get("fps", selected_profile["fps"])
    if not isinstance(frames, int) or isinstance(frames, bool) or frames != selected_profile["frames"]:
        raise StageError(f"video duration profile requires {selected_profile['frames']} logical frames")
    if not isinstance(fps, int) or isinstance(fps, bool) or fps != selected_profile["fps"]:
        raise StageError(f"video duration profile requires {selected_profile['fps']} fps")
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
    timeline_segments = kwargs.get("timeline_segments")
    if timeline_segments is not None:
        normalized_segments = _validate_video_timeline_segments(
            timeline_segments, selected_profile["duration_seconds"]
        )
    else:
        normalized_segments = [
            {
                "start_second": 0.0,
                "end_second": selected_profile["duration_seconds"],
                "prompt": prompt_build["prompt"],
            }
        ]
    normalized_segments = _validate_video_timeline_segments(
        normalized_segments, selected_profile["duration_seconds"]
    )
    plan = {
        "schema_version": "1.0",
        "stage": "video",
        "plan_state": "draft",
        "execution_approved": True,
        "production_eligible": production_source and strict_video_contract,
        "plan_mode": (
            "lineage-bound-production"
            if production_source and strict_video_contract
            else "legacy-dry-run"
        ),
        "local_only": True,
        "workflow_profile_id": "ltx-yusu-director-v1",
        "duration_profile_id": selected_profile_id,
        "workflow_hash": workflow_hash,
        "profile_hash": profile_hash,
        "workflow_fingerprint": kwargs.get("workflow_fingerprint"),
        "capability_report_hash": kwargs.get("capability_report_hash"),
        "source_shot_hash": shot_hash,
        "source_shot_artifact_type": shot["artifact_type"],
        **shot_context,
        "prompt_build_hash": content_hash(prompt_build),
        "prompt_build": copy.deepcopy(prompt_build),
        "prompt_intent_hash": content_hash(intent) if intent is not None else None,
        "director_node_id": 174,
        "negative_node_id": 195,
        "parameters": {
            "frames": frames,
            "output_frames": selected_profile["output_frames"],
            "fps": fps,
            "duration_seconds": selected_profile["duration_seconds"],
            "output_width": output_width,
            "output_height": output_height,
            "start_frame": 0,
            "end_frame": frames - 1,
        },
        "patches": [
            {"slot": "director.timeline_data", "node_id": 174, "value": [segment.get("prompt") for segment in normalized_segments]},
            {"slot": "director.local_prompts", "node_id": 174, "value": prompt_build["prompt"]},
            {"slot": "director.segment_lengths", "node_id": 174, "value": str(frames)},
        ],
        "expected_outputs": ["video"],
    }
    plan["timeline_segments"] = normalized_segments
    if strict_video_contract:
        plan["motion_delta"] = kwargs["motion_delta"].strip()
        plan["split_decision"] = copy.deepcopy(kwargs["split_decision"])
        plan["production_eligible"] = production_source
    else:
        plan["legacy_compact"] = True
        plan["submission_blocked"] = True
    if shot_lineage_id is not None:
        plan["lineage_id"] = shot_lineage_id
    if shot.get("parent_artifact_hash") is not None:
        plan["parent_shot_hash"] = shot["parent_artifact_hash"]
        plan["source_artifact_hash"] = shot["source_artifact_hash"]
    plan["plan_hash"] = content_hash(plan)
    return plan
