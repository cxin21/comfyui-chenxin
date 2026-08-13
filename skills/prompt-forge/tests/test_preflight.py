"""Unit tests for scripts/preflight.py."""
import pytest
from scripts.preflight import preflight_check


def _seg(text: str, field: str = "general") -> dict:
    return {"field": field, "text": text, "fact_ids": ["f"]}


def test_pov_plus_full_body_caught():
    """pov + full body is a view conflict."""
    segments = [_seg("pov"), _seg("full body", field="composition_and_camera")]
    result = preflight_check(segments, {"subjects": 1})
    assert not result["ok"]
    assert any("pov" in e for e in result["errors"])


def test_solo_plus_hetero_caught():
    """solo + hetero is an identity conflict."""
    segments = [_seg("solo"), _seg("hetero")]
    result = preflight_check(segments, {"subjects": 1})
    assert not result["ok"]


def test_hanfu_plus_cyberpunk_caught():
    """hanfu + cyberpunk city is a style inconsistency."""
    segments = [_seg("hanfu"), _seg("cyberpunk city", field="environment_and_props")]
    result = preflight_check(segments, {"subjects": 1})
    assert not result["ok"]
    assert any("style" in e for e in result["errors"])


def test_clean_prompt_passes():
    """A clean single-subject prompt passes all gates."""
    segments = [_seg("2boys"), _seg("fighting"), _seg("ruined city", field="environment_and_props")]
    result = preflight_check(segments, {"subjects": 2})
    assert result["ok"]


def test_count_over_cap_warns():
    """Exceeding tag-count hard cap returns a warning."""
    segments = [_seg(f"tag_{i}") for i in range(60)]
    result = preflight_check(segments, {"subjects": 1})  # simple tier, cap 40
    assert any("hard cap" in w for w in result["warnings"])