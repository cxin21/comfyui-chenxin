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
