from __future__ import annotations

import pytest

from runtime.reference_select import ReferenceSelectionError, select_reference


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
