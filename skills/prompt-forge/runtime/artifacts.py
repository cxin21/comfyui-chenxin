"""Normalize ComfyUI image history into traceable multiview artifacts."""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath


class ArtifactNormalizationError(ValueError):
    """Raised when ComfyUI output data cannot meet the artifact contract."""


_PROFILE_KEYS = frozenset(("artifact_type", "view_label"))
_IMAGE_KEYS = frozenset(("filename", "subfolder", "type"))
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ALLOWED_IMAGE_TYPES = frozenset(("output", "temp"))


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
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ArtifactNormalizationError("image subfolder must be a safe relative path")
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
