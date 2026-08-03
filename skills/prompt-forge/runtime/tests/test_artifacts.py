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
        ("face_00005_.png", "sheet"),
        ("sheet_00005_.png", "sheet"),
    ]
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


def test_rejects_unknown_output_nodes_and_invalid_lineage_binding():
    image = {"filename": "face.png", "subfolder": "", "type": "output"}
    profile = {"524": {"artifact_type": "CharacterAngleView", "view_label": "front"}}

    with pytest.raises(ArtifactNormalizationError, match="unknown output node"):
        normalize_image_outputs({"999": {"images": [image]}}, profile, "lineage-1", "basehash")
    with pytest.raises(ArtifactNormalizationError, match="lineage_id"):
        normalize_image_outputs({"524": {"images": [image]}}, profile, "", "basehash")
    with pytest.raises(ArtifactNormalizationError, match="source_hash"):
        normalize_image_outputs({"524": {"images": [image]}}, profile, "lineage-1", "not a hash")
