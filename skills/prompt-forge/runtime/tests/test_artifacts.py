import pytest

from runtime.artifacts import ArtifactNormalizationError, normalize_image_outputs


def test_outputs_are_normalized_and_deduplicated():
    outputs = {
        "524": {"images": [
            {"filename": "face_00005_.png", "subfolder": "", "type": "output"}
        ]},
        "224": {"images": [
            {"filename": "sheet_00005_.png", "subfolder": "", "type": "output"},
            {"filename": "face_00005_.png", "subfolder": "", "type": "output"},
        ]},
    }
    output_nodes = {
        "524": {"artifact_type": "CharacterAngleView", "view_label": "front_closeup"},
        "224": {"artifact_type": "CharacterSheet", "view_label": "sheet"},
    }

    result = normalize_image_outputs(outputs, output_nodes, "lineage-1", "basehash")

    assert [(item["filename"], item["view_label"]) for item in result] == [
        ("face_00005_.png", "front_closeup"),
        ("sheet_00005_.png", "sheet"),
    ]
    assert result[0]["semantic_conflict"] is True
    assert result[0]["semantic_candidates"] == [
        {"artifact_type": "CharacterAngleView", "view_label": "front_closeup", "source_node_id": "524"},
        {"artifact_type": "CharacterSheet", "view_label": "sheet", "source_node_id": "224"},
    ]
    assert result[0]["reference_eligible"] is True
    assert all(item["lineage_id"] == "lineage-1" for item in result)
    assert all(item["source_artifact_hash"] == "basehash" for item in result)


def test_duplicate_physical_descriptor_is_coalesced_with_auditable_sources():
    result = normalize_image_outputs(
        {
            "524": {"images": [
                {"filename": "face.png", "subfolder": "runs/a", "type": "output"},
                {"filename": "face.png", "subfolder": "runs/a", "type": "output"},
            ]},
        },
        {"524": {"artifact_type": "CharacterAngleView", "view_label": "front"}},
        "lineage-1",
        "basehash",
    )

    assert result == [{
        "filename": "face.png",
        "subfolder": "runs/a",
        "type": "output",
        "artifact_type": "CharacterAngleView",
        "view_label": "front",
        "lineage_id": "lineage-1",
        "source_artifact_hash": "basehash",
        "source_node_ids": ["524"],
        "semantic_candidates": [{
            "artifact_type": "CharacterAngleView",
            "view_label": "front",
            "source_node_id": "524",
        }],
        "semantic_conflict": False,
        "reference_eligible": True,
    }]


@pytest.mark.parametrize("bad_image", [
    {"filename": "../escape.png", "subfolder": "", "type": "output"},
    {"filename": "C:/escape.png", "subfolder": "", "type": "output"},
    {"filename": "face.png", "subfolder": "../runs", "type": "output"},
    {"filename": "face.png", "subfolder": "/runs", "type": "output"},
    {"filename": "", "subfolder": "", "type": "output"},
    {"filename": "face.png", "subfolder": "", "type": "input"},
])
def test_rejects_unsafe_or_invalid_image_descriptors(bad_image):
    with pytest.raises(ArtifactNormalizationError):
        normalize_image_outputs(
            {"524": {"images": [bad_image]}},
            {"524": {"artifact_type": "CharacterAngleView", "view_label": "front"}},
            "lineage-1",
            "basehash",
        )


def test_unknown_history_output_is_a_non_reference_diagnostic_artifact():
    image = {"filename": "face.png", "subfolder": "", "type": "output"}
    profile = {"524": {"artifact_type": "CharacterAngleView", "view_label": "front"}}

    result = normalize_image_outputs({"999": {"images": [image]}}, profile, "lineage-1", "basehash")

    assert result[0]["artifact_type"] == "DiagnosticImage"
    assert result[0]["view_label"] is None
    assert result[0]["reference_eligible"] is False
    assert result[0]["source_node_ids"] == ["999"]


def test_declared_semantics_win_over_an_unknown_diagnostic_for_same_file():
    image = {"filename": "face.png", "subfolder": "", "type": "output"}
    result = normalize_image_outputs(
        {
            "999": {"images": [image], "gifs": []},
            "524": {"images": [image], "audio": []},
        },
        {"524": {"artifact_type": "CharacterAngleView", "view_label": "front"}},
        "lineage-1",
        "basehash",
    )

    assert len(result) == 1
    assert result[0]["artifact_type"] == "CharacterAngleView"
    assert result[0]["view_label"] == "front"
    assert result[0]["reference_eligible"] is True
    assert result[0]["source_node_ids"] == ["524", "999"]
    assert {candidate["artifact_type"] for candidate in result[0]["semantic_candidates"]} == {
        "CharacterAngleView", "DiagnosticImage"
    }


def test_ignores_non_image_history_fields_and_missing_images():
    result = normalize_image_outputs(
        {
            "524": {"images": [{"filename": "face.png", "subfolder": "", "type": "temp"}], "gifs": []},
            "224": {"audio": [], "metadata": {"ignored": True}},
        },
        {
            "524": {"artifact_type": "CharacterAngleView", "view_label": "front"},
            "224": {"artifact_type": "CharacterSheet", "view_label": "sheet"},
        },
        "lineage-1",
        "basehash",
    )

    assert [item["filename"] for item in result] == ["face.png"]


def test_rejects_invalid_lineage_binding():
    image = {"filename": "face.png", "subfolder": "", "type": "output"}
    profile = {"524": {"artifact_type": "CharacterAngleView", "view_label": "front"}}
    with pytest.raises(ArtifactNormalizationError, match="lineage_id"):
        normalize_image_outputs({"524": {"images": [image]}}, profile, "", "basehash")
    with pytest.raises(ArtifactNormalizationError, match="source_hash"):
        normalize_image_outputs({"524": {"images": [image]}}, profile, "lineage-1", "not a hash")
