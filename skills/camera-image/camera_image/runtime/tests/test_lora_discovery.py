"""P1 tests for runtime.lora_discovery (config-surface-lora-unit design)."""

from __future__ import annotations

import pytest

from runtime.lora_discovery import (
    LoraDiscoveryError,
    LoraSelection,
    compatibility_tier,
    hash_inventory,
    hard_filter,
    recommend,
    render_lora_stack,
    validate_unit_invariants,
    verify_lora_presence,
)

ANIMA_MODEL = "miaomiaoHarem_anima15.safetensors"

INVENTORY = {
    "loras": [
        "Anima\\anima-base-1-masterpiece-v51.safetensors",
        "Anima\\缁嗚妭璋冩暣.safetensors",
        "Anima\\gpt-image-2_anima-base1_v1-1.safetensors",
        "Anima\\Anima_in_real_epoch_10.safetensors",
        "FLux\\bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors",
        "LTX\\ltx-2.3-22b-ic-lora-refocus.safetensors",
        "WAN\\animedenser_v01rc.safetensors",
        "ip-adapter-faceid-plusv2_sd15_lora.safetensors",
    ]
}

METADATA = {
    "Anima\\anima-base-1-masterpiece-v51.safetensors": {
        "base_model": "anima",
        "tags": ["masterpiece", "aesthetic"],
    },
    "Anima\\缁嗚妭璋冩暣.safetensors": {"base_model": "anima", "tags": ["detail"]},
    "Anima\\gpt-image-2_anima-base1_v1-1.safetensors": {
        "base_model": "anima",
        "tags": ["@gpt-image-2"],
    },
    "Anima\\Anima_in_real_epoch_10.safetensors": {
        "base_model": "anima",
        "tags": ["realistic"],
    },
}


def _inventory_hash() -> str:
    return hash_inventory(INVENTORY)


def _selection(name: str, **overrides) -> LoraSelection:
    base = {
        "name": name,
        "strength_model": 1.0,
        "strength_clip": 1.0,
        "active": True,
        "trigger_words": [],
    }
    base.update(overrides)
    return LoraSelection(**base)


def test_hash_inventory_is_stable_and_order_insensitive():
    shuffled = {"loras": list(reversed(INVENTORY["loras"]))}
    assert hash_inventory(INVENTORY) == hash_inventory(shuffled)
    assert hash_inventory({"loras": []}) != _inventory_hash()


def test_hash_inventory_rejects_non_canonical_shapes():
    with pytest.raises(LoraDiscoveryError):
        hash_inventory({"loras": "not-a-list"})
    with pytest.raises(LoraDiscoveryError):
        hash_inventory({})


def test_compatibility_tier_prefers_metadata_over_folder():
    assert compatibility_tier("Anima\\缁嗚妭璋冩暣.safetensors", ANIMA_MODEL, METADATA) == "metadata"
    assert compatibility_tier("Anima\\Anima_in_real_epoch_10.safetensors", ANIMA_MODEL, {}) == "folder"
    assert compatibility_tier("Anima\\Anima_in_real_epoch_10.safetensors", ANIMA_MODEL, METADATA) == "metadata"


def test_hard_filter_rejects_other_families():
    keep, rejected = hard_filter(INVENTORY, ANIMA_MODEL, METADATA)
    names = {item["name"] for item in keep}
    assert names == {
        "Anima\\anima-base-1-masterpiece-v51.safetensors",
        "Anima\\缁嗚妭璋冩暣.safetensors",
        "Anima\\gpt-image-2_anima-base1_v1-1.safetensors",
        "Anima\\Anima_in_real_epoch_10.safetensors",
    }
    assert all(item["reason"] for item in rejected)


def test_recommend_marks_single_top_pick_with_reasons():
    rec = recommend(INVENTORY, ANIMA_MODEL, METADATA, style_tags=["masterpiece", "detail"])
    assert rec["inventory_hash"] == _inventory_hash()
    flagged = [c for c in rec["candidates"] if c["recommended"]]
    assert len(flagged) == 1
    assert all(candidate["reason"] for candidate in rec["candidates"])
    assert rec["recommendation_hash"]


def test_recommend_rejects_unknown_base_model():
    with pytest.raises(LoraDiscoveryError):
        recommend(INVENTORY, "no-such-model.safetensors", METADATA, style_tags=[])


def test_render_lora_stack_round_trip():
    selections = [
        _selection("Anima\\anima-base-1-masterpiece-v51.safetensors", strength_model=1.0),
        _selection("Anima\\缁嗚妭璋冩暣.safetensors", strength_model=0.8, strength_clip=0.9, active=False),
    ]
    text = render_lora_stack(selections)
    assert text == (
        "<lora:Anima\\anima-base-1-masterpiece-v51:1.00>"
        "<lora:Anima\\缁嗚妭璋冩暣:0.80:0.90>"
    )
    assert render_lora_stack([]) == ""


def test_unit_invariants_accept_consistent_unit():
    selections = [
        _selection("Anima\\anima-base-1-masterpiece-v51.safetensors", trigger_words=["masterpiece"]),
        _selection("Anima\\缁嗚妭璋冩暣.safetensors", trigger_words=["detail"]),
        _selection("Anima\\Anima_in_real_epoch_10.safetensors", active=False, trigger_words=["realistic"]),
    ]
    validate_unit_invariants(selections, active_words=["masterpiece", "detail"])


def test_unit_invariants_reject_word_from_inactive_lora():
    selections = [
        _selection("Anima\\Anima_in_real_epoch_10.safetensors", active=False, trigger_words=["realistic"]),
    ]
    with pytest.raises(LoraDiscoveryError, match="inactive"):
        validate_unit_invariants(selections, active_words=["realistic"])


def test_unit_invariants_reject_missing_word_for_active_lora():
    selections = [
        _selection("Anima\\anima-base-1-masterpiece-v51.safetensors", trigger_words=["masterpiece"]),
    ]
    with pytest.raises(LoraDiscoveryError):
        validate_unit_invariants(selections, active_words=[])
def test_lora_inventory_filenames_are_normalized_for_comfy_references():
    selection = _selection("Anima\\anima-base-1-masterpiece-v51.safetensors")

    assert verify_lora_presence(INVENTORY, [selection]) == [
        "Anima\\anima-base-1-masterpiece-v51.safetensors"
    ]
    assert render_lora_stack([selection]) == (
        "<lora:Anima\\anima-base-1-masterpiece-v51:1.00>"
    )


def test_mcp_lora_listing_is_parsed_and_recommendation_becomes_a_plan():
    from runtime.lora_discovery import build_lora_plan, parse_local_model_listing

    raw = "## loras (2)\n- Anima\\base.safetensors\n- FLux\\other.safetensors\n"
    inventory = parse_local_model_listing(raw)
    recommendation = recommend(inventory, "anima15")
    plan = build_lora_plan(recommendation)

    assert plan["selections"][0]["name"] == "Anima\\base.safetensors"
    assert plan["stack_text"] == "<lora:Anima\\base:1.00>"
    assert plan["inventory_hash"] == recommendation["inventory_hash"]
    assert plan["recommendation_hash"] == recommendation["recommendation_hash"]
