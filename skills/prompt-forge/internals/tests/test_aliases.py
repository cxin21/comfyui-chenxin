# skills/prompt-forge/internals/tests/test_aliases.py
from internals._aliases import ALIASES, resolve_alias, all_aliases


def test_resolve_alias_known():
    assert resolve_alias("anima_baseV10") == "anima"
    assert resolve_alias("AnimaStandardV7") == "anima"


def test_resolve_alias_unknown():
    assert resolve_alias("nonexistent_xyz") is None


def test_resolve_alias_case_insensitive():
    assert resolve_alias("ANIMASTANDARDV7") == "anima"


def test_all_aliases_count():
    assert len(all_aliases()) >= 50


def test_aliases_format():
    for alias, canonicals in ALIASES.items():
        assert isinstance(canonicals, list)
        assert len(canonicals) >= 1


def test_resolve_sdxl_aliases():
    assert resolve_alias("sdxl_base") == "sdxl"
    assert resolve_alias("stable_diffusion_xl") == "sdxl"


def test_resolve_flux_aliases():
    assert resolve_alias("flux_1_dev") == "flux_1"
    assert resolve_alias("flux_1_schnell") == "flux_1"
