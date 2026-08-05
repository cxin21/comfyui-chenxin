import pytest

from runtime.asset_plans import (
    AssetPlanError,
    build_art_bible,
    build_character_board_plan,
    build_environment_board_plan,
    build_prop_board_plan,
    build_scene_variant_plan,
)


def _provenance(*facts):
    return {
        "explicit_evidence": list(facts),
        "reasonable_inference": ["the archive uses the workshop palette"],
        "prohibited_expansion": ["modern electronics"],
    }


def _visual_fingerprint():
    return [
        {"feature": "silhouette", "value": "heart-shaped silhouette"},
        {"feature": "proportions", "value": "slender proportions"},
        {"feature": "palette", "value": "indigo and brass palette"},
        {"feature": "materials", "value": "linen and brass materials"},
        {"feature": "surface", "value": "matte fabric surface"},
        {"feature": "lighting", "value": "cool window lighting"},
    ]


def _story():
    visual_evidence = [
        "restrained ink wash",
        "digital watercolor",
        "negative space foregrounds the key",
        "indigo",
        "cedar red",
        "linen",
        "cedar",
        "bronze",
        "cool window light with warm sidelight",
        "sealed thresholds",
        "no modern electronics",
        "reuse fixed anchors and palette",
        "restrained ink wash, digital watercolor",
    ]
    return {
        "schema_version": "1.0",
        "visual_system": {
            "primary_style": "restrained ink wash",
            "medium": "digital watercolor",
            "visual_grammar": "negative space foregrounds the key",
            "palette": ["indigo", "cedar red"],
            "materials": ["linen", "cedar", "bronze"],
            "lighting": "cool window light with warm sidelight",
            "motifs": ["sealed thresholds"],
            "world_taboos": ["no modern electronics"],
            "continuity_strategy": "reuse fixed anchors and palette",
            "style_prompt": "restrained ink wash, digital watercolor",
        },
        "characters": [{"asset_id": "character-lee"}],
        "scenes": [{"asset_id": "environment-workshop"}],
        "story_logic": ["the key opens the archive"],
        "uncertainty": ["archive contents are uncertain"],
        "source_hash": "d" * 64,
        "provenance": _provenance(*visual_evidence),
    }


def _art_bible():
    return build_art_bible(_story())


def _environment_card():
    fingerprint = _visual_fingerprint()
    facts = [
        "weathered stone arch at the entrance",
        "red lacquer seal above the doorway",
        "narrow cedar counter along the east wall",
        *(part["value"] for part in fingerprint),
    ]
    return {
        "schema_version": "1.0",
        "asset_type": "environment",
        "asset_id": "environment-workshop",
        "source_story_hash": "b" * 64,
        "visual_fingerprint": fingerprint,
        "environment_anchors": [
            {"feature": "entrance", "value": facts[0]},
            {"feature": "emblem", "value": facts[1]},
            {"feature": "counter", "value": facts[2]},
        ],
        "spatial_layout": "arch faces the narrow east-wall counter",
        "provenance": _provenance(*facts),
    }


def _character_card():
    fingerprint = _visual_fingerprint()
    facts = [
        "young woman with a heart-shaped face",
        "deep brown almond eyes",
        "short black bob with blunt fringe",
        "indigo linen coat with brass buttons",
        *(part["value"] for part in fingerprint),
    ]
    return {
        "schema_version": "1.0",
        "asset_type": "character",
        "asset_id": "character-lee",
        "source_story_hash": "a" * 64,
        "visual_fingerprint": fingerprint,
        "identity_lock": [facts[0], facts[2], facts[3]],
        "face_lock": [{"feature": "eyes", "value": facts[1]}],
        "provenance": _provenance(*facts),
    }


def _prop_card():
    fingerprint = _visual_fingerprint()
    facts = [
        "hand-sized bronze key",
        "opens the workshop archive",
        *(part["value"] for part in fingerprint),
    ]
    return {
        "schema_version": "1.0",
        "asset_type": "prop",
        "asset_id": "prop-archive-key",
        "source_story_hash": "c" * 64,
        "visual_fingerprint": fingerprint,
        "scale": facts[0],
        "function": facts[1],
        "provenance": _provenance(*facts),
    }


def test_build_art_bible_keeps_explicit_story_style_when_override_conflicts():
    bible = build_art_bible(
        _story(),
        style_override={"style": "photorealistic cyberpunk", "palette": ["neon"]},
    )

    assert bible["style"] == "restrained ink wash"
    assert bible["palette"] == ["indigo", "cedar red"]
    assert bible["prohibited_expansion"] == ["modern electronics"]


def test_build_art_bible_treats_style_as_explicit_story_evidence_too():
    story = _story()
    story["visual_system"]["style"] = story["visual_system"].pop("primary_style")

    bible = build_art_bible(story, style_override={"style": "photorealistic cyberpunk"})

    assert bible["style"] == "restrained ink wash"


def test_environment_board_requires_four_consistent_regions():
    plan = build_environment_board_plan(_art_bible(), _environment_card())

    assert plan["layout"] == [
        "panorama",
        "top_down",
        "material_detail",
        "cross_section",
    ]
    assert plan["no_people"] is True
    assert plan["style_prompt"] == "restrained ink wash, digital watercolor"
    assert plan["environment_anchors"][1]["value"] == "red lacquer seal above the doorway"
    assert plan["reasonable_inference"] == ["the archive uses the workshop palette"]


def test_character_board_isolated_to_a_single_subject_without_scene_or_props():
    plan = build_character_board_plan(_art_bible(), _character_card())

    assert plan["layout"] == ["head_close_up", "front", "side_90", "rear"]
    assert plan["single_subject"] is True
    assert plan["no_scene_or_props"] is True
    assert plan["face_lock"] == [{"feature": "eyes", "value": "deep brown almond eyes"}]


def test_prop_board_isolated_from_people_and_hands():
    plan = build_prop_board_plan(_art_bible(), _prop_card())

    assert plan["layout"] == ["master", "exploded_structure", "material_slice", "function_state"]
    assert plan["no_people"] is True
    assert plan["no_hands"] is True
    assert plan["function"] == "opens the workshop archive"


def test_scene_variant_preserves_fixed_environment_and_only_copies_declared_shot_deltas():
    plan = build_scene_variant_plan(
        _environment_card(),
        {"shot_deltas": {"framing": "wide", "camera_height": "eye level"}},
    )

    assert plan["environment_anchors"][0]["value"] == "weathered stone arch at the entrance"
    assert plan["spatial_layout"] == "arch faces the narrow east-wall counter"
    assert plan["materials"] == ["linen and brass materials"]
    assert plan["lighting"] == ["cool window lighting"]
    assert plan["shot_deltas"] == {"framing": "wide", "camera_height": "eye level"}


def test_scene_variant_cannot_replace_environment_anchor():
    with pytest.raises(AssetPlanError, match="fixed visual anchor"):
        build_scene_variant_plan(
            _environment_card(),
            {"environment_anchor_changes": ["remove stone arch"]},
        )


def test_scene_variant_cannot_hide_fixed_environment_changes_in_shot_deltas():
    with pytest.raises(AssetPlanError, match="fixed visual anchor"):
        build_scene_variant_plan(
            _environment_card(),
            {
                "shot_deltas": {
                    "composition": {
                        "environment_anchor_changes": ["remove stone arch"]
                    }
                }
            },
        )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("layout_changes", "fixed environment layout"),
        ("material_changes", "fixed environment materials"),
        ("lighting_changes", "fixed environment light logic"),
    ],
)
def test_scene_variant_cannot_replace_other_fixed_environment_properties(field, message):
    with pytest.raises(AssetPlanError, match=message):
        build_scene_variant_plan(_environment_card(), {field: ["replace it"]})


def test_scene_variant_normalizes_chinese_material_and_lighting_features():
    environment = _environment_card()
    environment["visual_fingerprint"][3] = {"feature": "材质", "value": "雪松与黄铜"}
    environment["visual_fingerprint"][5] = {"feature": "光照", "value": "冷窗光"}
    provenance = environment["provenance"]["explicit_evidence"]
    provenance.remove("linen and brass materials")
    provenance.remove("cool window lighting")
    provenance.extend(["雪松与黄铜", "冷窗光"])

    plan = build_scene_variant_plan(environment, {"shot_deltas": {"framing": "wide"}})

    assert plan["materials"] == ["雪松与黄铜"]
    assert plan["lighting"] == ["冷窗光"]
    assert plan["visual_fingerprint"] == environment["visual_fingerprint"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda story: story.pop("provenance"), "requires all evidence tiers"),
        (
            lambda story: story["provenance"].__setitem__("explicit_evidence", "style"),
            "evidence tiers must be lists",
        ),
        (
            lambda story: story["provenance"].__setitem__(
                "prohibited_expansion", ["restrained ink wash"]
            ),
            "cannot also be explicit evidence",
        ),
    ],
)
def test_build_art_bible_rejects_missing_invalid_or_conflicting_provenance(mutate, message):
    story = _story()
    mutate(story)

    with pytest.raises(AssetPlanError, match=message):
        build_art_bible(story)


def test_public_entry_points_convert_non_json_inputs_to_asset_plan_errors():
    with pytest.raises(AssetPlanError, match="invalid style_override"):
        build_art_bible(_story(), style_override={"palette": object()})

    invalid_bible = _art_bible()
    invalid_bible["palette"].append(object())
    with pytest.raises(AssetPlanError, match="invalid art bible"):
        build_environment_board_plan(invalid_bible, _environment_card())

    invalid_character = _character_card()
    invalid_character["identity_lock"].append(object())
    with pytest.raises(AssetPlanError, match="invalid asset card"):
        build_character_board_plan(_art_bible(), invalid_character)

    invalid_prop = _prop_card()
    invalid_prop["function"] = object()
    with pytest.raises(AssetPlanError, match="invalid asset card"):
        build_prop_board_plan(_art_bible(), invalid_prop)

    with pytest.raises(AssetPlanError, match="invalid shot_intent"):
        build_scene_variant_plan(_environment_card(), {"shot_deltas": {"camera": object()}})


def test_board_plan_is_deep_copied_from_its_source_contracts():
    bible = _art_bible()
    environment = _environment_card()

    plan = build_environment_board_plan(bible, environment)
    plan["palette"].append("bronze")
    plan["environment_anchors"][0]["value"] = "new arch"
    plan["explicit_evidence"].append("new fact")

    assert bible["palette"] == ["indigo", "cedar red"]
    assert environment["environment_anchors"][0]["value"] == "weathered stone arch at the entrance"
    assert "new fact" not in bible["explicit_evidence"]
    assert "new fact" not in environment["provenance"]["explicit_evidence"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("primary_style", "restrained ink wash"),
        ("palette", "indigo"),
        ("materials", "bronze"),
    ],
)
def test_build_art_bible_rejects_visual_facts_declared_prohibited(field, value):
    story = _story()
    story["provenance"]["explicit_evidence"].remove(value)
    story["provenance"]["prohibited_expansion"] = [value]

    with pytest.raises(AssetPlanError, match="prohibited expansion cannot become an art bible fact"):
        build_art_bible(story)


def test_build_art_bible_accepts_structured_evidence_for_nested_visual_values():
    story = _story()
    story["visual_system"]["palette"] = [["indigo"], ["cedar red"]]
    story["provenance"]["explicit_evidence"] = [
        {"field": "style", "value": "restrained ink wash"},
        {"field": "medium", "value": "digital watercolor"},
        {"field": "visual_grammar", "value": "negative space foregrounds the key"},
        {"field": "palette", "value": "indigo"},
        {"field": "palette", "value": "cedar red"},
        {"field": "materials", "value": "linen"},
        {"field": "materials", "value": "cedar"},
        {"field": "materials", "value": "bronze"},
        {"field": "lighting", "value": "cool window light with warm sidelight"},
        {"field": "motifs", "value": "sealed thresholds"},
        {"field": "world_taboos", "value": "no modern electronics"},
        {"field": "continuity_strategy", "value": "reuse fixed anchors and palette"},
        {"field": "style_prompt", "value": "restrained ink wash, digital watercolor"},
    ]

    bible = build_art_bible(story)

    assert bible["palette"] == [["indigo"], ["cedar red"]]


@pytest.mark.parametrize(
    ("builder", "asset_factory"),
    [
        (build_environment_board_plan, _environment_card),
        (build_character_board_plan, _character_card),
        (build_prop_board_plan, _prop_card),
    ],
)
def test_board_builders_cannot_bypass_prohibited_art_bible_visual_facts(
    builder, asset_factory
):
    bible = _art_bible()
    bible["style"] = "forbidden style"
    bible["explicit_evidence"].remove("restrained ink wash")
    bible["prohibited_expansion"] = ["forbidden style"]

    with pytest.raises(AssetPlanError, match="prohibited expansion cannot become an art bible fact"):
        builder(bible, asset_factory())


def test_art_bible_rejects_conflicting_top_level_and_nested_provenance_sources():
    bible = _art_bible()
    bible["style"] = "forbidden style"
    bible["explicit_evidence"].append("forbidden style")
    bible["prohibited_expansion"] = ["forbidden style"]
    bible["provenance"] = {
        "explicit_evidence": list(bible["explicit_evidence"]),
        "reasonable_inference": list(bible["reasonable_inference"]),
        "prohibited_expansion": [],
    }

    with pytest.raises(AssetPlanError, match="multiple provenance sources"):
        build_environment_board_plan(bible, _environment_card())


@pytest.mark.parametrize(
    "visual_system_change",
    [
        lambda visual_system: visual_system.__setitem__("palette", [[]]),
        lambda visual_system: visual_system.__setitem__("materials", {"surface": []}),
    ],
)
def test_build_art_bible_rejects_empty_nested_visual_collections(visual_system_change):
    story = _story()
    visual_system_change(story["visual_system"])

    with pytest.raises(AssetPlanError, match="must contain a visual fact"):
        build_art_bible(story)


def test_structured_evidence_scopes_same_value_to_its_field():
    story = _story()
    story["visual_system"]["primary_style"] = "shared"
    story["visual_system"]["style"] = "shared"
    story["provenance"]["explicit_evidence"].append(
        {"field": "style", "value": "shared"}
    )
    story["provenance"]["prohibited_expansion"] = [
        {"field": "palette", "value": "shared"}
    ]

    assert build_art_bible(story)["style"] == "shared"


def test_structured_evidence_scopes_different_values_to_the_same_field():
    story = _story()
    story["visual_system"]["primary_style"] = "style-a"
    story["visual_system"]["style"] = "style-a"
    story["provenance"]["explicit_evidence"].remove("restrained ink wash")
    story["provenance"]["explicit_evidence"].append(
        {"field": "style", "value": "style-a"}
    )
    story["provenance"]["prohibited_expansion"] = [
        {"field": "style", "value": "style-b"}
    ]

    assert build_art_bible(story)["style"] == "style-a"


def test_plain_evidence_conflicts_with_scoped_structured_prohibition():
    story = _story()
    story["provenance"]["prohibited_expansion"] = [
        {"field": "style", "value": "restrained ink wash"}
    ]

    with pytest.raises(AssetPlanError, match="prohibited expansion cannot also be explicit evidence"):
        build_art_bible(story)
