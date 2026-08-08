from __future__ import annotations

import pytest

from runtime.reference_select import (
    ReferenceSelectionError,
    prove_view_orientation,
    select_reference,
    select_reference_for_shot,
)


def _artifacts():
    return [
        {
            "artifact_type": "CharacterBaseImage",
            "view_label": "front",
            "accepted": True,
            "content_hash": "base",
        },
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "left_45",
            "accepted": True,
            "content_hash": "left45",
        },
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "right",
            "accepted": True,
            "content_hash": "right",
        },
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "side_unknown",
            "accepted": True,
            "content_hash": "ambiguous",
        },
    ]


def test_exact_angle_view_wins():
    result = select_reference("left_45", _artifacts())
    assert result["artifact"]["content_hash"] == "left45"
    assert result["selection_reason"] == "exact-angle"


def test_nearest_angle_beats_base_fallback():
    result = select_reference("left", _artifacts())
    assert result["artifact"]["content_hash"] == "left45"
    assert result["selection_reason"] == "nearest-angle"


def test_base_image_is_recorded_fallback():
    result = select_reference("rear", [_artifacts()[0]])
    assert result["artifact"]["content_hash"] == "base"
    assert result["selection_reason"] == "base-fallback"


def test_ambiguous_angle_is_never_auto_selected():
    result = select_reference("rear", [_artifacts()[3], _artifacts()[0]])
    assert result["artifact"]["content_hash"] == "base"
    assert result["selection_reason"] == "base-fallback"


def test_duplicate_known_angle_is_treated_as_ambiguous():
    artifacts = [
        _artifacts()[0],
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "left_45",
            "accepted": True,
            "content_hash": "left-a",
        },
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "left_45",
            "accepted": True,
            "content_hash": "left-b",
        },
    ]
    result = select_reference("left_45", artifacts)
    assert result["artifact"]["content_hash"] == "base"
    assert result["selection_reason"] == "base-fallback"


def test_selection_is_deterministic_for_equal_distance():
    artifacts = [
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "left_45",
            "accepted": True,
            "content_hash": "b" * 64,
        },
        {
            "artifact_type": "CharacterAngleView",
            "view_label": "right_45",
            "accepted": True,
            "content_hash": "a" * 64,
        },
    ]
    result = select_reference("front", artifacts)
    assert result["artifact"]["content_hash"] == "a" * 64
    assert result["selection_reason"] == "nearest-angle"


def test_rejects_unknown_desired_view():
    with pytest.raises(ReferenceSelectionError, match="unknown desired view"):
        select_reference("three_quarter", _artifacts())


def test_rejects_when_no_accepted_reference_exists():
    with pytest.raises(ReferenceSelectionError, match="accepted reference"):
        select_reference("front", [{"artifact_type": "CharacterBaseImage", "accepted": False}])


def _angle(view_label: str, content_hash: str) -> dict:
    return {"artifact_type": "CharacterAngleView", "view_label": view_label, "accepted": True, "content_hash": content_hash}


def _proof(artifact: dict, view: str, *, source: str = "profile-output-map") -> dict:
    return prove_view_orientation(artifact, view, evidence={"source": source, "observed_view": view, "verified": True})


def test_side_unknown_cannot_feed_directional_shot_without_explicit_orientation_proof():
    with pytest.raises(ReferenceSelectionError, match="orientation"):
        select_reference_for_shot("right", {"views": ["side_unknown"]}, [_angle("side_unknown", "ambiguous")])


def test_exact_and_nearest_selection_require_matching_orientation_proof():
    exact = _proof(_angle("right", "right"), "right")
    nearest = _proof(_angle("right_45", "right45"), "right_45")
    exact_result = select_reference_for_shot("right", {"views": ["right", "right_45"]}, [nearest, exact])
    nearest_result = select_reference_for_shot("right", {"views": ["right_45"]}, [nearest])
    assert exact_result["artifact"]["content_hash"] == "right"
    assert exact_result["selection_reason"] == "exact-angle"
    assert exact_result["distance_degrees"] == 0
    assert nearest_result["artifact"]["content_hash"] == "right45"
    assert nearest_result["selection_reason"] == "nearest-angle"
    assert nearest_result["distance_degrees"] == 45


def test_side_unknown_needs_manual_directional_evidence_before_selection():
    proven = _proof(_angle("side_unknown", "manual-right"), "right", source="manual-review")
    result = select_reference_for_shot("right", {"views": ["side_unknown"]}, [proven])
    assert result["selected_view"] == "right"
    assert result["artifact"]["view_label"] == "side_unknown"
    assert result["orientation_proof"]["source"] == "manual-review"


def test_orientation_proof_rejects_mismatched_observation_and_preserves_source_artifact():
    artifact = _angle("left", "left")
    original = dict(artifact)
    with pytest.raises(ReferenceSelectionError, match="orientation"):
        prove_view_orientation(artifact, "right", evidence={"source": "manual-review", "observed_view": "left", "verified": True})
    assert artifact == original
