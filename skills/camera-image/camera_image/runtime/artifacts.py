"""Normalize ComfyUI image history into traceable multiview artifacts."""

from __future__ import annotations

import copy
import re
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath


class ArtifactNormalizationError(ValueError):
    """Raised when ComfyUI output data cannot meet the artifact contract."""


class ArtifactError(ArtifactNormalizationError):
    """Raised when a generated artifact fails technical verification."""


_PROFILE_KEYS = frozenset(("artifact_type", "view_label"))
_IMAGE_KEYS = frozenset(("filename", "subfolder", "type"))
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ALLOWED_IMAGE_TYPES = frozenset(("output", "temp"))
_SHOT_DERIVATIVE_TYPES = {
    "ShotRefined": "detailer",
    "ShotStyleVariant": "style",
    "ShotCutout": "cutout",
}
_SHOT_DERIVATIVE_METADATA_KEYS = frozenset(
    {
        "derivative_type",
        "source_artifact_hash",
        "source_artifact_type",
        "parent_artifact_hash",
        "parent_artifact_type",
        "derived_from",
        "is_variant",
        "derivative_profile_id",
    }
)


def has_shot_derivative_metadata(artifact: object) -> bool:
    return isinstance(artifact, dict) and not _SHOT_DERIVATIVE_METADATA_KEYS.isdisjoint(
        artifact
    )


def _require_identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not _SAFE_IDENTIFIER_RE.fullmatch(value):
        raise ArtifactNormalizationError(f"{field_name} must be a safe non-empty identifier")
    return value


def _require_safe_filename(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ArtifactNormalizationError("image filename must be a non-empty string")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or len(posix.parts) != 1
        or len(windows.parts) != 1
        or value in {".", ".."}
    ):
        raise ArtifactNormalizationError("image filename must be a safe relative filename")
    return value


def _require_safe_subfolder(value: object) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ArtifactNormalizationError("image subfolder must be a string")
    if not value:
        return value
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or "\\" in value
        or value != "/".join(posix.parts)
    ):
        raise ArtifactNormalizationError("image subfolder must be a canonical safe relative path")
    if any(part in {"", ".", ".."} for part in (*posix.parts, *windows.parts)):
        raise ArtifactNormalizationError("image subfolder must not contain path traversal")
    return value


def _validated_profile(output_nodes: object) -> dict[str, dict[str, str]]:
    if not isinstance(output_nodes, dict) or not output_nodes:
        raise ArtifactNormalizationError("output_nodes must be a non-empty profile output-node map")
    normalized: dict[str, dict[str, str]] = {}
    for raw_node_id, raw_descriptor in output_nodes.items():
        node_id = _require_identifier(raw_node_id, "output node id")
        if node_id in normalized:
            raise ArtifactNormalizationError("output_nodes contains duplicate node ids")
        if not isinstance(raw_descriptor, dict) or set(raw_descriptor) != _PROFILE_KEYS:
            raise ArtifactNormalizationError("output node descriptor schema is invalid")
        artifact_type = _require_identifier(raw_descriptor["artifact_type"], "artifact_type")
        view_label = _require_identifier(raw_descriptor["view_label"], "view_label")
        normalized[node_id] = {"artifact_type": artifact_type, "view_label": view_label}
    return normalized


def _validated_image(image: object) -> tuple[str, str, str]:
    if not isinstance(image, dict) or set(image) != _IMAGE_KEYS:
        raise ArtifactNormalizationError("image descriptor schema is invalid")
    filename = _require_safe_filename(image["filename"])
    subfolder = _require_safe_subfolder(image["subfolder"])
    image_type = image["type"]
    if not isinstance(image_type, str) or image_type not in _ALLOWED_IMAGE_TYPES:
        raise ArtifactNormalizationError("image type must be output or temp")
    return image_type, subfolder, filename


def is_stage3_reference_eligible(artifact: object) -> bool:
    """Return whether an accepted, verified multiview artifact may be reused."""
    return (
        isinstance(artifact, dict)
        and artifact.get("accepted") is True
        and artifact.get("artifact_type") == "CharacterAngleView"
        and isinstance(artifact.get("view_label"), str)
        and bool(artifact["view_label"])
        and artifact.get("reference_eligible") is True
        and artifact.get("semantic_conflict") is False
        and artifact.get("hash_verified") is True
    )


def is_ltx_input_eligible(artifact: object) -> bool:
    """Return whether a clean or separately accepted shot may feed LTX."""
    if not isinstance(artifact, dict) or artifact.get("accepted") is not True:
        return False
    content = artifact.get("content_hash")
    if not isinstance(content, str) or not re.fullmatch(r"[0-9a-f]{64}", content):
        return False
    artifact_type = artifact.get("artifact_type")
    if artifact_type == "ShotImage":
        return not has_shot_derivative_metadata(artifact)
    derivative_type = _SHOT_DERIVATIVE_TYPES.get(artifact_type)
    parent = artifact.get("parent_artifact_hash")
    source = artifact.get("source_artifact_hash")
    return (
        derivative_type is not None
        and artifact.get("derivative_type") == derivative_type
        and isinstance(parent, str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", parent))
        and parent != content
        and source == parent
    )


def accept_stage3_reference(artifact: object, actor: str, accepted_at: str) -> dict:
    """Record an explicit human acceptance for one verified angle artifact.

    Normalization deliberately leaves ``accepted`` false.  This function is the
    only transition that may make a multiview output eligible for Stage 3; it
    binds the actor, timestamp, and exact artifact hash into a self-hashed
    acceptance object.
    """
    if not (
        isinstance(artifact, dict)
        and artifact.get("artifact_type") == "CharacterAngleView"
        and isinstance(artifact.get("view_label"), str)
        and bool(artifact["view_label"])
        and artifact.get("reference_eligible") is True
        and artifact.get("semantic_conflict") is False
        and artifact.get("hash_verified") is True
    ):
        raise ArtifactNormalizationError("reference is not eligible for Stage 3 acceptance")
    if artifact.get("accepted") is True:
        raise ArtifactNormalizationError("reference is already accepted")
    if not isinstance(actor, str) or not actor.strip():
        raise ArtifactNormalizationError("reference acceptance actor is required")
    if not isinstance(accepted_at, str) or not accepted_at.strip():
        raise ArtifactNormalizationError("reference acceptance timestamp is required")
    try:
        parsed = datetime.fromisoformat(accepted_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactNormalizationError("reference acceptance timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ArtifactNormalizationError("reference acceptance timestamp must be UTC")
    content = artifact.get("content_hash")
    if not isinstance(content, str) or not re.fullmatch(r"[0-9a-f]{64}", content):
        raise ArtifactNormalizationError("reference content_hash must be a lowercase SHA-256 digest")
    acceptance = {
        "schema_version": "1.0",
        "artifact_hash": content,
        "actor": actor.strip(),
        "accepted_at": accepted_at,
    }
    acceptance["acceptance_id"] = hashlib.sha256(
        json.dumps(acceptance, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result = copy.deepcopy(artifact)
    result["accepted"] = True
    result["acceptance"] = acceptance
    result["acceptance_id"] = acceptance["acceptance_id"]
    return result


def _candidate(semantic: dict[str, str | None], node_id: str) -> dict[str, str | None]:
    return {
        "artifact_type": semantic["artifact_type"],
        "view_label": semantic["view_label"],
        "source_node_id": node_id,
    }


def _append_image(
    collected: dict[tuple[str, str, str], dict],
    image: object,
    semantic: dict[str, str | None],
    node_id: str,
    lineage_id: str,
    source_hash: str,
) -> None:
    image_type, subfolder, filename = _validated_image(image)
    key = (image_type, subfolder, filename)
    candidate = _candidate(semantic, node_id)
    descriptor = collected.setdefault(key, {
        "filename": filename,
        "subfolder": subfolder,
        "type": image_type,
        "artifact_type": semantic["artifact_type"],
        "view_label": semantic["view_label"],
        "lineage_id": lineage_id,
        "source_artifact_hash": source_hash,
        "source_node_ids": [],
        "semantic_candidates": [],
    })
    if node_id not in descriptor["source_node_ids"]:
        descriptor["source_node_ids"].append(node_id)
    if candidate not in descriptor["semantic_candidates"]:
        descriptor["semantic_candidates"].append(candidate)


def _node_images(node_output: object) -> list:
    if not isinstance(node_output, dict):
        raise ArtifactNormalizationError("output node entry must be an object")
    images = node_output.get("images", [])
    if not isinstance(images, list):
        raise ArtifactNormalizationError("output node images must be a list")
    return images


def normalize_image_outputs(outputs, output_nodes, lineage_id, source_hash) -> list[dict]:
    """Return sorted, schema-validated descriptors for ComfyUI history outputs.

    View semantics are copied only from the verified profile map.  The physical
    ComfyUI location is never interpreted as a view direction.
    """
    profile = _validated_profile(output_nodes)
    safe_lineage_id = _require_identifier(lineage_id, "lineage_id")
    safe_source_hash = _require_identifier(source_hash, "source_hash")
    if not isinstance(outputs, dict):
        raise ArtifactNormalizationError("outputs must be a mapping of output node ids")

    collected: dict[tuple[str, str, str], dict] = {}

    # The verified profile's insertion order is the explicit semantic priority;
    # it is never derived from an arbitrary generated filename.
    for node_id, semantic in profile.items():
        if node_id not in outputs:
            continue
        for image in _node_images(outputs[node_id]):
            _append_image(collected, image, semantic, node_id, safe_lineage_id, safe_source_hash)

    diagnostic = {"artifact_type": "DiagnosticImage", "view_label": None}
    unknown_node_ids = sorted(
        (_require_identifier(node_id, "output node id") for node_id in outputs if node_id not in profile),
    )
    for node_id in unknown_node_ids:
        for image in _node_images(outputs[node_id]):
            _append_image(collected, image, diagnostic, node_id, safe_lineage_id, safe_source_hash)

    normalized: list[dict] = []
    for key in sorted(collected, key=lambda item: (item[2], item[1], item[0])):
        descriptor = collected[key]
        descriptor["source_node_ids"].sort()
        declared_conflicts = [
            candidate for candidate in descriptor["semantic_candidates"]
            if candidate["artifact_type"] != "DiagnosticImage"
            and (candidate["artifact_type"], candidate["view_label"])
            != (descriptor["artifact_type"], descriptor["view_label"])
        ]
        descriptor["semantic_conflict"] = bool(declared_conflicts)
        descriptor["reference_eligible"] = (
            descriptor["artifact_type"] == "CharacterAngleView"
            and descriptor["semantic_conflict"] is False
        )
        normalized.append(descriptor)
    return normalized


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ArtifactError("video artifact bytes cannot be read") from exc
    return digest.hexdigest()


def _parse_frame_rate(value: object) -> int | float:
    if not isinstance(value, str) or not value or value in {"0/0", "N/A"}:
        raise ArtifactError("video stream frame rate is invalid")
    try:
        rate = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ArtifactError("video stream frame rate is invalid") from exc
    if rate <= 0:
        raise ArtifactError("video stream frame rate is invalid")
    return int(rate) if rate.denominator == 1 else float(rate)


def probe_video(path: Path) -> dict:
    """Read technical video metadata using the installed ffprobe binary."""
    if not isinstance(path, Path):
        raise ArtifactError("video path must be a pathlib.Path")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ArtifactError("video path does not exist") from exc
    if not resolved.is_file():
        raise ArtifactError("video path is not a file")
    command = [
        "ffprobe",
        "-v",
        "error",
        "-count_frames",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(resolved),
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise ArtifactError("ffprobe could not inspect the video") from exc
    if result.returncode != 0:
        raise ArtifactError("ffprobe returned a non-zero status")
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ArtifactError("ffprobe returned invalid JSON") from exc
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list):
        raise ArtifactError("ffprobe returned no streams")
    video_stream = next(
        (stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"),
        None,
    )
    if video_stream is None:
        raise ArtifactError("video stream is missing")
    frame_value = video_stream.get("nb_read_frames") or video_stream.get("nb_frames")
    try:
        frame_count = int(frame_value)
    except (TypeError, ValueError) as exc:
        raise ArtifactError("video frame count is invalid") from exc
    if frame_count <= 0:
        raise ArtifactError("video frame count is empty")
    try:
        size_bytes = resolved.stat().st_size
    except OSError as exc:
        raise ArtifactError("video file metadata cannot be read") from exc
    if size_bytes <= 0:
        raise ArtifactError("video artifact is empty")
    return {
        "filename": resolved.name,
        "path": str(resolved),
        "size_bytes": size_bytes,
        "fps": _parse_frame_rate(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
        "frame_count": frame_count,
        "codec_name": video_stream.get("codec_name"),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
    }


def verify_video_artifact(
    metadata: dict,
    expected_fps: int,
    expected_frames: int,
    *,
    expected_width: int | None = None,
    expected_height: int | None = None,
    lineage_id: str | None = None,
    source_shot_hash: str | None = None,
    artifact_path: Path | None = None,
) -> dict:
    """Validate a video against the planned technical contract."""
    if not isinstance(metadata, dict):
        raise ArtifactError("video metadata must be an object")
    if not isinstance(expected_fps, int) or isinstance(expected_fps, bool) or expected_fps <= 0:
        raise ArtifactError("expected fps must be a positive integer")
    if not isinstance(expected_frames, int) or isinstance(expected_frames, bool) or expected_frames <= 0:
        raise ArtifactError("expected frame count must be a positive integer")
    if (expected_width is None) != (expected_height is None):
        raise ArtifactError("expected video width and height must be provided together")
    for value, label in ((expected_width, "expected video width"), (expected_height, "expected video height")):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
            raise ArtifactError(f"{label} must be a positive integer")

    resolved: Path | None = None
    probed: dict | None = None
    if artifact_path is not None:
        if not isinstance(artifact_path, Path):
            raise ArtifactError("video artifact_path must be a pathlib.Path")
        try:
            resolved = artifact_path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ArtifactError("video artifact_path does not exist") from exc
        if not resolved.is_file():
            raise ArtifactError("video artifact_path is not a file")
        # A caller-supplied metadata object is only a claim.  Once bytes are
        # available, ffprobe is the authority for technical acceptance.
        probed = probe_video(resolved)

    filename = metadata.get("filename")
    if not isinstance(filename, str) or not filename.strip() or filename != filename.strip():
        raise ArtifactError("video filename is invalid")
    size_bytes = metadata.get("size_bytes")
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
        raise ArtifactError("video artifact is empty")
    if probed is not None:
        for key in ("filename", "size_bytes", "fps", "frame_count", "width", "height"):
            declared = metadata.get(key)
            actual = probed.get(key)
            if declared is not None and declared != actual:
                raise ArtifactError(f"declared video {key} does not match the artifact bytes")
        # Use the probed values below, even when the declaration omitted an
        # optional field such as width or height.
        filename = probed["filename"]
        size_bytes = probed["size_bytes"]
        metadata = probed
    if metadata.get("fps") != expected_fps:
        raise ArtifactError("video fps does not match the expected plan")
    if metadata.get("frame_count") != expected_frames:
        raise ArtifactError("video frame count does not match the expected plan")
    width = metadata.get("width")
    height = metadata.get("height")
    if expected_width is not None:
        if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
            raise ArtifactError("video width is missing or invalid")
        if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
            raise ArtifactError("video height is missing or invalid")
        if width != expected_width or height != expected_height:
            raise ArtifactError("video dimensions do not match the expected plan")

    result = {
        "schema_version": "1.0",
        "artifact_type": "VideoClip",
        "accepted": True,
        "filename": filename,
        "size_bytes": size_bytes,
        "fps": expected_fps,
        "frame_count": expected_frames,
    }
    if isinstance(width, int) and not isinstance(width, bool) and width > 0:
        result["width"] = width
    if isinstance(height, int) and not isinstance(height, bool) and height > 0:
        result["height"] = height
    if lineage_id is not None:
        if not isinstance(lineage_id, str) or not _SAFE_IDENTIFIER_RE.fullmatch(lineage_id):
            raise ArtifactError("video lineage_id is invalid")
        result["lineage_id"] = lineage_id
    if source_shot_hash is not None:
        if not isinstance(source_shot_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_shot_hash):
            raise ArtifactError("video source_shot_hash is invalid")
        result["source_shot_hash"] = source_shot_hash
    if resolved is not None:
        if resolved.name != filename:
            raise ArtifactError("video artifact_path does not match metadata")
        result["artifact_path"] = str(resolved)
        result["content_hash"] = _sha256_file(resolved)
    return result
