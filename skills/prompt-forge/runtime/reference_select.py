"""Deterministic selection of an accepted character reference for a shot."""

from __future__ import annotations

import copy


class ReferenceSelectionError(ValueError):
    """Raised when a shot reference cannot be selected safely."""


VIEW_DEGREES = {
    "front": 0,
    "right_45": 45,
    "right": 90,
    "rear_45": 135,
    "rear": 180,
    "left": 270,
    "left_45": 315,
}

VIEW_ALIASES = {
    "front_closeup": "front",
    "front_upper": "front",
}

_EXPLICIT_ORIENTATION_SOURCES = frozenset(
    ("camera-calibration", "embedded-metadata", "manual-review", "user-confirmation")
)


def _canonical_view(label: object) -> str | None:
    if not isinstance(label, str):
        return None
    normalized = label.strip().lower()
    return VIEW_ALIASES.get(normalized, normalized) if normalized else None


def circular_distance(left: str, right: str) -> int:
    """Return the shortest angular distance between two known views."""
    try:
        delta = abs(VIEW_DEGREES[left] - VIEW_DEGREES[right])
    except KeyError as exc:
        raise ReferenceSelectionError("unknown view label") from exc
    return min(delta, 360 - delta)


def prove_view_orientation(artifact: dict, expected_view: str, *, evidence: dict) -> dict:
    """Return an artifact carrying a verified, non-invented orientation proof."""
    if not isinstance(artifact, dict):
        raise ReferenceSelectionError("orientation proof requires an artifact object")
    expected = _canonical_view(expected_view)
    if expected not in VIEW_DEGREES:
        raise ReferenceSelectionError(f"unknown expected orientation: {expected_view!r}")
    if not isinstance(evidence, dict):
        raise ReferenceSelectionError("orientation evidence must be an object")
    observed = _canonical_view(evidence.get("observed_view"))
    source = evidence.get("source")
    if evidence.get("verified") is not True or observed != expected or not isinstance(source, str) or not source.strip():
        raise ReferenceSelectionError("orientation evidence does not prove the expected view")
    artifact_view = _canonical_view(artifact.get("view_label"))
    if artifact_view == "side_unknown":
        if source not in _EXPLICIT_ORIENTATION_SOURCES:
            raise ReferenceSelectionError("side_unknown requires explicit directional orientation evidence")
    elif artifact_view not in VIEW_DEGREES or artifact_view != expected:
        raise ReferenceSelectionError("artifact orientation conflicts with orientation evidence")
    proven = copy.deepcopy(artifact)
    proven["orientation_proof"] = {
        "schema_version": "1.0", "expected_view": expected, "observed_view": observed,
        "source": source, "verified": True,
    }
    return proven


def _valid_artifacts(artifacts: object) -> list[dict]:
    if not isinstance(artifacts, list):
        raise ReferenceSelectionError("accepted references must be a list")
    accepted: list[dict] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("accepted") is not True:
            continue
        if artifact.get("artifact_type") not in {"CharacterAngleView", "CharacterBaseImage"}:
            continue
        content_hash = artifact.get("content_hash")
        if not isinstance(content_hash, str) or not content_hash.strip():
            continue
        accepted.append(copy.deepcopy(artifact))
    if not accepted:
        raise ReferenceSelectionError("no accepted reference is available")
    return accepted


def _tie_key(artifact: dict) -> tuple[str, str]:
    return (str(artifact.get("content_hash")), str(artifact.get("view_label", "")))


def select_reference(desired_view: str, artifacts: list[dict]) -> dict:
    """Select the closest accepted individual angle, with a base fallback.

    Unknown/ambiguous angle labels are intentionally excluded from automatic
    selection.  Ties are ordered by content hash so repeated runs make the
    same decision without relying on input ordering.
    """
    desired = _canonical_view(desired_view)
    if desired not in VIEW_DEGREES:
        raise ReferenceSelectionError(f"unknown desired view: {desired_view!r}")
    accepted = _valid_artifacts(artifacts)

    by_view: dict[str, list[dict]] = {}
    for artifact in accepted:
        if artifact.get("artifact_type") != "CharacterAngleView":
            continue
        view = _canonical_view(artifact.get("view_label"))
        if view not in VIEW_DEGREES:
            continue
        by_view.setdefault(view, []).append(artifact)

    angle_candidates: list[tuple[int, int, tuple[str, str], dict]] = []
    for view, view_artifacts in by_view.items():
        # Two accepted artifacts for one semantic angle are not safe to choose
        # automatically: content-hash ordering cannot prove which identity is
        # the intended reference.  Keep the deterministic tie-break only for
        # distinct angles at the same distance.
        if len(view_artifacts) != 1:
            continue
        artifact = view_artifacts[0]
        angle_candidates.append(
            (
                0 if view == desired else 1,
                circular_distance(view, desired),
                _tie_key(artifact),
                artifact,
            )
        )
    if angle_candidates:
        exact_or_nearest = min(angle_candidates, key=lambda item: item[:3])
        return {
            "artifact": exact_or_nearest[3],
            "desired_view": desired,
            "selected_view": _canonical_view(exact_or_nearest[3].get("view_label")),
            "selection_reason": "exact-angle"
            if exact_or_nearest[0] == 0
            else "nearest-angle",
            "distance_degrees": exact_or_nearest[1],
        }

    base_candidates = [
        artifact
        for artifact in accepted
        if artifact.get("artifact_type") == "CharacterBaseImage"
    ]
    if not base_candidates:
        raise ReferenceSelectionError("no accepted angle or base reference is available")
    base = min(base_candidates, key=_tie_key)
    return {
        "artifact": base,
        "desired_view": desired,
        "selected_view": _canonical_view(base.get("view_label")),
        "selection_reason": "base-fallback",
        "distance_degrees": None,
    }


def select_reference_for_shot(desired_view: str, view_plan: dict, artifacts: list[dict]) -> dict:
    """Select an exact/nearest planned angle only from orientation-proven artifacts."""
    desired = _canonical_view(desired_view)
    if desired not in VIEW_DEGREES:
        raise ReferenceSelectionError(f"unknown desired view: {desired_view!r}")
    if not isinstance(view_plan, dict) or not isinstance(view_plan.get("views"), list):
        raise ReferenceSelectionError("view plan requires a views list")
    planned_labels: list[str] = []
    planned_views: set[str] = set()
    for label in view_plan["views"]:
        normalized = _canonical_view(label)
        if normalized not in VIEW_DEGREES and normalized != "side_unknown":
            raise ReferenceSelectionError(f"view plan contains unknown view: {label!r}")
        if not isinstance(label, str) or not label.strip():
            raise ReferenceSelectionError("view plan contains an invalid view label")
        planned_labels.append(label.strip().lower())
        planned_views.add(normalized)
    if not planned_labels:
        raise ReferenceSelectionError("view plan requires at least one requested view")
    accepted = _valid_artifacts(artifacts)
    candidates_by_view: dict[str, list[dict]] = {}
    for artifact in accepted:
        if artifact.get("artifact_type") != "CharacterAngleView":
            continue
        artifact_label = artifact.get("view_label")
        if not isinstance(artifact_label, str):
            continue
        normalized_artifact_label = _canonical_view(artifact_label)
        if artifact_label.strip().lower() not in planned_labels and normalized_artifact_label not in planned_views:
            continue
        proof = artifact.get("orientation_proof")
        if not isinstance(proof, dict):
            continue
        proven_view = _canonical_view(proof.get("observed_view"))
        source = proof.get("source")
        if (
            proof.get("schema_version") != "1.0"
            or proof.get("verified") is not True
            or _canonical_view(proof.get("expected_view")) != proven_view
            or proven_view not in VIEW_DEGREES
            or not isinstance(source, str)
            or not source.strip()
        ):
            continue
        if normalized_artifact_label == "side_unknown":
            if source not in _EXPLICIT_ORIENTATION_SOURCES:
                continue
        elif normalized_artifact_label != proven_view:
            continue
        candidates_by_view.setdefault(proven_view, []).append(artifact)
    candidates: list[tuple[int, int, tuple[str, str], dict, dict]] = []
    for proven_view, proven_artifacts in candidates_by_view.items():
        if len(proven_artifacts) != 1:
            continue
        artifact = proven_artifacts[0]
        candidates.append((0 if proven_view == desired else 1, circular_distance(proven_view, desired), _tie_key(artifact), artifact, artifact["orientation_proof"]))
    if not candidates:
        raise ReferenceSelectionError("no accepted reference has orientation evidence for the requested view plan")
    selected = min(candidates, key=lambda item: item[:3])
    return {
        "artifact": selected[3], "desired_view": desired, "selected_view": selected[4]["observed_view"],
        "selection_reason": "exact-angle" if selected[0] == 0 else "nearest-angle",
        "distance_degrees": selected[1], "orientation_proof": copy.deepcopy(selected[4]),
    }
